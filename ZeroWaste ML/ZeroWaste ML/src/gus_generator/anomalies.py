"""Katman C - sentetik audit ground-truth uretimi.

DONGUSELLIK UYARISI
-------------------
Bu modul, dedektorun (modelin) sinyal mantigindan BAGIMSIZ yazilmistir ve
LATENT buyuklukler uzerinde calisir. Model ise yalnizca GOZLENEN alanlari
gorur ve latent beklentiyi CIKARSAMAK zorundadir. `features.py` bu modulden
hicbir sey ithal ETMEZ; bu kural `validate_dataset.py` icinde otomatik
kontrol edilir.

ETIKET TANIMI
-------------
truth_anomaly_flag = 1  <=>  kayitta GERCEK ve ONEMLILIK esigini asan bir
                             beyan eksigi MEKANIZMASI vardir.
Yalnizca olcum gurultusu nedeniyle dusuk gorunen kayitlar truth = 0 kalir;
bunlar bilincli olarak YANLIS-POZITIF uretmek icin vardir.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .config import GeneratorConfig, ANOMALY_TYPES, LEGITIMATE_CAUSES

# Onemlilik esigi: mutlak taban + firmanin kendi olceginin orani
MATERIALITY_ABS_TON = 0.30
MATERIALITY_REL = 0.06


def _firm_propensity(compliance_type: str) -> float:
    return {
        "uyumlu": 0.020,
        "ozensiz": 0.055,
        "gec_duzeltici": 0.045,
        "sistematik_eksik": 0.310,
    }[compliance_type]


def _pick_mechanism(rng: np.random.Generator, row, prev_row, is_test: bool) -> str:
    """Kaydin latent durumuna UYGUN bir anomali mekanizmasi secer.

    Mekanizma rastgele degil, kaydin gercek durumuyla tutarli secilir; boylece
    anomali tipi ile gozlenen ornunti arasinda gercekci bir bag kurulur.
    """
    cands: List[Tuple[str, float]] = []

    prod_growth = None
    if prev_row is not None and prev_row["lat_production_units"] > 0:
        prod_growth = row["lat_production_units"] / prev_row["lat_production_units"] - 1.0

    exp_change = None
    if prev_row is not None:
        exp_change = row["lat_export_share"] - prev_row["lat_export_share"]

    cands.append(("A01_tarihsel_dusus", 1.0))
    cands.append(("A02_emsal_alti", 1.0))
    cands.append(("A03_beklenen_fark", 1.0))
    if prod_growth is not None and prod_growth > 0.06:
        cands.append(("A04_faaliyet_uyumsuz", 2.2))
    if exp_change is not None and exp_change < -0.05:
        cands.append(("A05_dis_ticaret_uyumsuz", 2.2))
    if row["quarter"] in (1, 4):
        cands.append(("A06_mevsimsel_kirilma", 1.3))
    cands.append(("A07_urun_agaci_uyumsuz", 1.1))
    # A08 egitimde NADIR, testte DAHA SIK: kavramsal kayma (concept drift) testi
    cands.append(("A08_dis_kanit_uyumsuz", 2.4 if is_test else 0.35))

    names = [c[0] for c in cands]
    w = np.array([c[1] for c in cands], dtype=float)
    w = w / w.sum()
    return str(rng.choice(names, p=w))


def inject_anomalies(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    panel: pd.DataFrame,
    firms: pd.DataFrame,
) -> pd.DataFrame:
    """Faz 1: latent panele beyan davranisini ve gercek eksikligi enjekte eder.

    Panele su alanlari ekler:
      lat_declared_total_tonnage, lat_correction_qty, lat_intent_deficit,
      lat_mechanism, lat_truth_flag, lat_legit_cause
    """
    fmeta = firms.set_index("firm_id")
    panel = panel.copy()

    n = len(panel)
    declared = np.zeros(n)
    correction = np.zeros(n)
    intent_deficit = np.zeros(n)
    mechanism = np.array(["N00_normal"] * n, dtype=object)
    truth = np.zeros(n, dtype=int)
    legit = np.array([""] * n, dtype=object)

    # firm_id -> satir indeksleri (zaman sirali)
    groups: Dict[str, np.ndarray] = {
        fid: g.index.to_numpy() for fid, g in panel.groupby("firm_id", sort=False)
    }

    recs = panel.to_dict("records")

    for fid, idxs in groups.items():
        f = fmeta.loc[fid]
        ctype = f["lat_compliance_type"]
        base_p = _firm_propensity(ctype)
        prev_anom = False
        carry_over = 0.0  # gec duzeltme ile sonraki doneme tasinan tonaj
        decl_hist: List[float] = []

        for pos, i in enumerate(idxs):
            row = recs[i]
            prev = recs[idxs[pos - 1]] if pos > 0 else None
            true_total = float(row["lat_true_total_tonnage"])
            is_test = row["split"] == "test"

            # --- 1) Gercek eksik beyan mekanizmasi var mi? ---
            p = base_p * (2.4 if prev_anom else 1.0)
            p = min(p, 0.65)
            has_intent = (rng.random() < p) and true_total > 0

            deficit = 0.0
            mech = "N00_normal"
            if has_intent:
                lo, hi = cfg.eksik_beyan_siddeti
                a, b = cfg.eksik_beyan_beta
                deficit = float(lo + (hi - lo) * rng.beta(a, b))
                mech = _pick_mechanism(rng, row, prev, is_test)

            gap_tons = true_total * deficit
            floor = max(MATERIALITY_ABS_TON, MATERIALITY_REL * true_total * 0.5)
            material = gap_tons >= floor and deficit >= 0.05

            if has_intent and material:
                truth[i] = 1
                mechanism[i] = mech
                intent_deficit[i] = deficit
                prev_anom = True
            else:
                # Onemlilik esigini asmayan niyet: denetimde dogrulanmaz -> truth = 0
                deficit = 0.0
                prev_anom = False

            # --- 2) Beyan tonaji ---
            sigma = float(row["lat_noise_sigma"])
            if ctype == "ozensiz":
                sigma *= 1.45
            noise = float(np.exp(rng.normal(-0.5 * sigma ** 2, sigma)))
            base_declared = true_total * (1.0 - deficit) * noise

            # Gec duzeltme: onceki donemden tasinan tonaj bu doneme eklenir
            base_declared += carry_over
            corr_amt = carry_over
            carry_over = 0.0

            # --- 3) Mesru fakat riskli GORUNEN durumlar (yanlis-pozitif ureteci) ---
            # N10 yalnizca kayit GERCEKTEN riskli GORUNUYORSA atanir. Yani
            # firmanin kendi son donem seviyesinin belirgin altina dusmus olmali.
            # Boylece N10 ayirt edici bir alt kume olur; her kayda yapismaz.
            if truth[i] == 0:
                causes = _natural_legit_causes(row, f)
                if ctype == "gec_duzeltici" and rng.random() < 0.35 and true_total > 0:
                    shift = float(rng.uniform(0.22, 0.50)) * base_declared
                    base_declared -= shift
                    carry_over = shift
                    causes.append("gec_duzeltme_beyannamesi")

                ref_level = float(np.mean(decl_hist[-4:])) if len(decl_hist) >= 2 else None
                looks_risky = (
                    ref_level is not None and ref_level > 0
                    and base_declared < 0.82 * ref_level
                )
                if causes and looks_risky:
                    legit[i] = str(rng.choice(causes))
                    mechanism[i] = "N10_mesru_gorunum"

            declared[i] = max(base_declared, 0.0)
            correction[i] = corr_amt
            decl_hist.append(declared[i])

    panel["lat_declared_total_tonnage"] = declared
    panel["lat_correction_qty"] = correction
    panel["lat_intent_deficit"] = intent_deficit
    panel["lat_mechanism"] = mechanism
    panel["lat_truth_flag"] = truth
    panel["lat_legit_cause"] = legit
    return panel


def _natural_legit_causes(row: dict, f: pd.Series) -> List[str]:
    """Kaydin latent durumundan DOGAL olarak dogan mesru aciklamalar."""
    causes: List[str] = []
    if row["lat_export_share"] > 0.55:
        causes.append("ihracat_agirlikli_donem")
    if row["lat_exemption_flag"]:
        causes.append("yasal_muafiyet_istisna")
    if row["lat_has_break"]:
        causes.append("urun_gami_degisikligi")
    if int(f["operating_since"]) >= 2024:
        causes.append("yeni_firma_kisa_tarihce")
    if bool(f["sector_code_error_flag"]):
        causes.append("sektor_kodu_hatasi")
    if bool(f["lat_stale_bom"]):
        causes.append("eskimis_ambalaj_agirlik_matrisi")
    if row.get("lat_seasonal_low", False):
        causes.append("mevsimsel_uretim_duraklamasi")
    return causes


def build_audit_labels(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    panel: pd.DataFrame,
    observations: pd.DataFrame,
    firms: pd.DataFrame,
) -> pd.DataFrame:
    """Faz 2: gozlenen veriyle birlestirerek nihai audit ground-truth tablosunu uretir."""
    obs = observations.set_index("observation_id")
    fmeta = firms.set_index("firm_id")
    rows: List[Dict] = []

    cost_by_band = {"mikro": 18_000.0, "kucuk": 32_000.0, "orta": 58_000.0, "buyuk": 120_000.0}
    dur_by_band = {"mikro": 6, "kucuk": 10, "orta": 18, "buyuk": 32}

    for r in panel.itertuples():
        o = obs.loc[r.observation_id]
        f = fmeta.loc[r.firm_id]
        band = str(f["size_band"])

        truth = int(r.lat_truth_flag)
        mech = str(r.lat_mechanism)
        legit_cause = str(r.lat_legit_cause) if r.lat_legit_cause else ""

        # Veri eksikligi kuyrugu: gercek eksik beyan OLMAYAN ama kritik alanlari
        # eksik olan kayitlar. Bunlar "dusuk risk" SAYILMAZ; ayri kuyruga gider.
        if truth == 0 and str(o["data_confidence_level"]) == "dusuk" and int(o["missing_field_count"]) >= 3:
            if rng.random() < 0.62:
                mech = "N09_veri_eksikligi"
                legit_cause = ""

        true_expected = float(r.lat_true_total_tonnage)
        declared = float(o["declared_packaging_tonnage"])
        true_gap = max(true_expected - declared, 0.0)

        if truth == 1:
            # Denetci gercek acigin tamamini degil, dogrulayabildigi kismini bulur
            recovery = float(rng.beta(6.0, 2.0))
            confirmed = round(true_gap * recovery, 4)
            outcome = "dogrulandi_eksik_beyan" if recovery > 0.55 else "kismi_dogrulandi"
            label_conf = "yuksek" if recovery > 0.7 else "orta"
        else:
            confirmed = 0.0
            if mech == "N09_veri_eksikligi":
                outcome = "veri_incelemesi_gerekli"
                label_conf = "dusuk"
            elif mech == "N10_mesru_gorunum":
                outcome = "aciklandi_uygun"
                label_conf = "yuksek"
            else:
                outcome = "bulgu_yok"
                label_conf = "yuksek"

        # Etiket gurultusu: gercek denetim kayitlarinda da hata olur
        warning = ""
        if rng.random() < cfg.etiket_gurultusu:
            truth = 1 - truth if mech not in ("N09_veri_eksikligi",) else truth
            label_conf = "dusuk"
            warning = "etiket_gurultusu_uygulandi"

        rows.append({
            "observation_id": r.observation_id,
            "firm_id": r.firm_id,
            "period": r.period,
            "split": r.split,
            "truth_anomaly_flag": int(truth),
            "anomaly_type": mech,
            "anomaly_type_aciklama": ANOMALY_TYPES.get(mech, {}).get("aciklama", ""),
            "legitimate_cause": legit_cause,
            "true_expected_tonnage": round(true_expected, 4),
            "true_deficit_ratio": round(float(r.lat_intent_deficit), 4),
            "true_gap_tonnage": round(true_gap, 4),
            "confirmed_correction_tonnage": confirmed,
            "audit_outcome": outcome,
            "audit_cost_try": round(float(cost_by_band[band] * np.exp(rng.normal(0.0, 0.22))), 2),
            "inspection_duration_days": int(max(2, rng.poisson(dur_by_band[band]))),
            "label_confidence": label_conf,
            "generation_source": "anomalies.inject_anomalies + anomalies.build_audit_labels",
            "warning": warning or "SENTETIK ETIKET - gercek denetim sonucu degildir",
        })

    return pd.DataFrame(rows)
