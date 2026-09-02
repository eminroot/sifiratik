"""Uctan uca dataset uretim hatti.

Determinizm: tek bir kok `seed` verilir, alt asamalar bu kokten turetilen
bagimsiz akislarla calisir. Ayni seed + ayni config = bit bazinda ayni dataset.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .config import GeneratorConfig, GEKAP_MATERIALS, SPLIT_MAP
from .reference_data import ReferenceData
from .entities import build_firms, build_product_packaging
from .observations import build_latent_panel, finalize_observations
from .anomalies import inject_anomalies, build_audit_labels
from .features import build_model_ready
from . import quality as q

# Firms sayfasinda YAYINLANMAYACAK latent sutunlar
LATENT_FIRM_COLS = ("lat_scale", "lat_compliance_type", "lat_stale_bom", "sector_true")


@dataclass
class DatasetBundle:
    config: GeneratorConfig
    reference: ReferenceData
    firms_public: pd.DataFrame
    firms_full: pd.DataFrame
    packaging: pd.DataFrame
    observations: pd.DataFrame
    model_ready: pd.DataFrame
    audit_labels: pd.DataFrame
    evaluation: pd.DataFrame
    difficulty: pd.DataFrame
    quality_checks: pd.DataFrame
    climate_scenarios: pd.DataFrame
    cop31_dashboard: pd.DataFrame
    manifest: Dict


def _sub_rng(seed: int, tag: str) -> np.random.Generator:
    """Etikete gore deterministik alt akis uretir."""
    h = int(hashlib.sha256(f"{seed}:{tag}".encode()).hexdigest()[:16], 16)
    return np.random.default_rng(h)


def build_dataset(cfg: Optional[GeneratorConfig] = None, ref_dir: str = "data/reference") -> DatasetBundle:
    cfg = cfg or GeneratorConfig()
    ref = ReferenceData(ref_dir)

    firms = build_firms(cfg, _sub_rng(cfg.seed, "firms"))
    packaging = build_product_packaging(cfg, _sub_rng(cfg.seed, "packaging"), firms, ref)

    panel = build_latent_panel(cfg, _sub_rng(cfg.seed, "latent"), firms, packaging, ref)
    panel = inject_anomalies(cfg, _sub_rng(cfg.seed, "anomalies"), panel, firms)

    observations = finalize_observations(
        cfg, _sub_rng(cfg.seed, "observed"), panel, firms, ref
    )
    labels = build_audit_labels(
        cfg, _sub_rng(cfg.seed, "labels"), panel, observations, firms
    )
    model_ready = build_model_ready(observations, firms)

    baselines = q.compute_baseline_scores(model_ready, _sub_rng(cfg.seed, "baseline"))
    evaluation = q.evaluate_baselines(baselines, labels, split="test")
    difficulty = q.difficulty_probe(model_ready, labels)

    checks = q.run_quality_checks(
        firms, observations, packaging, model_ready, labels, ref.material_share_anchor()
    )

    climate = build_climate_scenarios(observations, labels, ref)
    cop31 = build_cop31_dashboard(observations, labels, climate, ref)

    firms_public = firms.drop(columns=[c for c in LATENT_FIRM_COLS if c in firms.columns])

    manifest = {
        "dataset_version": cfg.dataset_version,
        "schema_version": cfg.schema_version,
        "seed": cfg.seed,
        "n_firms": int(len(firms)),
        "n_observations": int(len(observations)),
        "n_skus": int(len(packaging)),
        "periods": cfg.periods,
        "split_map": SPLIT_MAP,
        "prevalence_overall": float(labels["truth_anomaly_flag"].mean()),
        "config": cfg.to_dict(),
    }

    return DatasetBundle(
        config=cfg, reference=ref, firms_public=firms_public, firms_full=firms,
        packaging=packaging, observations=observations, model_ready=model_ready,
        audit_labels=labels, evaluation=evaluation, difficulty=difficulty,
        quality_checks=checks, climate_scenarios=climate, cop31_dashboard=cop31,
        manifest=manifest,
    )


# ==========================================================================
# Iklim senaryosu - YALNIZCA SENARYO, gerceklesmis azaltim DEGILDIR
# ==========================================================================
def build_climate_scenarios(
    observations: pd.DataFrame, labels: pd.DataFrame, ref: ReferenceData
) -> pd.DataFrame:
    """Dogrulanmis duzeltme tonajindan POTANSIYEL CO2e senaryosu uretir.

    Zincir acik yazilir:
      dogrulanmis_duzeltme_ton
        -> x geri_kazanim_orani (VARSAYIM)
        -> x malzeme payi (gozlenen beyan karisimindan)
        -> x WARM v16 faktoru (ABD, kisa ton -> metrik ton cevrilmis)
        = potansiyel_CO2e

    Her satir "Potential scenario - not verified impact" olarak etiketlenir.
    """
    merged = observations.merge(
        labels[["observation_id", "confirmed_correction_tonnage", "truth_anomaly_flag", "split"]],
        on="observation_id", how="left", suffixes=("", "_lbl"),
    )
    sub = merged[merged["split"] == "test"]
    total_corr = float(sub["confirmed_correction_tonnage"].fillna(0.0).sum())

    mat_cols = [f"declared_ton_{m}" for m in GEKAP_MATERIALS]
    mat_tot = sub[mat_cols].sum()
    mix = (mat_tot / mat_tot.sum()) if mat_tot.sum() > 0 else mat_tot * 0.0

    cf = ref.climate_factors.set_index("factor_id")
    scen = {
        "muhafazakar": (0.30, ref.co2e_factor_conservative, "CF-011 (yuzde 30) + muhafazakar faktor seti"),
        "orta": (0.3608, ref.co2e_factor_main, "CF-012 (yuzde 36,08 - 2024 ulke orani) + ana faktor seti"),
        "iyimser": (0.45, ref.co2e_factor_main, "CF-013 (yuzde 45 - dayanaksiz ust sinir) + ana faktor seti"),
    }

    rows = []
    for name, (rate, factors, note) in scen.items():
        recovered = total_corr * rate
        co2e = 0.0
        for m in GEKAP_MATERIALS:
            share = float(mix.get(f"declared_ton_{m}", 0.0))
            co2e += recovered * share * factors[m]
        rows.append({
            "senaryo": name,
            "kapsam": "test donemi (2026Q1-2026Q2), sentetik",
            "dogrulanmis_duzeltme_ton": round(total_corr, 3),
            "varsayilan_geri_kazanim_orani": rate,
            "potansiyel_geri_kazanim_ton": round(recovered, 3),
            "potansiyel_CO2e_ton": round(co2e, 3),
            "faktor_kaynagi": "US EPA WARM v16 Exhibit 2-2 (SRC-008)",
            "faktor_yili": 2023,
            "cografi_kapsam": "ABD (Turkiye ozgu faktor mevcut degil)",
            "sistem_siniri": "Virgin girdi yerine geri donusturulmus girdi kullaniminin sera gazi azaltimi",
            "donusum_formulu": "potansiyel_CO2e = duzeltme_ton x geri_kazanim_orani x malzeme_payi x faktor(MTCO2E/metrik ton)",
            "varsayim": note + "; malzeme payi test donemi beyan karisimindan alinmistir",
            "belirsizlik": "YUKSEK - faktorler ABD ozgu; beyan duzeltmesi ile fiziksel geri kazanim arasinda nedensellik kanitlanmamistir",
            "etiket": "Potential scenario - not verified impact",
        })
    return pd.DataFrame(rows)


def build_cop31_dashboard(
    observations: pd.DataFrame, labels: pd.DataFrame,
    climate: pd.DataFrame, ref: ReferenceData
) -> pd.DataFrame:
    """COP31 paneli: DOGRULANABILIR metrikler ile SENARYO metriklerini ayirir."""
    m = observations.merge(
        labels[["observation_id", "truth_anomaly_flag", "confirmed_correction_tonnage",
                "audit_outcome", "inspection_duration_days"]],
        on="observation_id", how="left",
    )
    test = m[m["split"] == "test"]
    rows = []

    def add(blok, gosterge, deger, birim, kaynak, etiket):
        rows.append({"blok": blok, "gosterge": gosterge, "deger": deger,
                     "birim": birim, "kaynak_hesap": kaynak, "etiket": etiket})

    V = "DOGRULANABILIR (sentetik veri uzerinde dogrudan olculur)"
    S = "SENARYO (Potential scenario - not verified impact)"

    add(V, "Analiz edilen firma sayisi", int(observations["firm_id"].nunique()), "adet",
        "Firms tablosu", V)
    add(V, "Analiz edilen beyan (firma-ceyrek) sayisi", int(len(observations)), "adet",
        "Observations tablosu", V)
    add(V, "Test doneminde onceliklendirilebilir dosya sayisi", int(len(test)), "adet",
        "split = test", V)
    add(V, "Test donemi gercek eksik beyan sayisi (ground truth)",
        int(test["truth_anomaly_flag"].fillna(0).sum()), "adet", "Audit_Labels", V)
    add(V, "Test donemi prevalans", round(float(test["truth_anomaly_flag"].fillna(0).mean()), 4),
        "oran", "Audit_Labels", V)
    add(V, "Dogrulanmis duzeltilen ambalaj tonaji (test)",
        round(float(test["confirmed_correction_tonnage"].fillna(0).sum()), 2), "ton",
        "Audit_Labels", V)
    for mat in GEKAP_MATERIALS:
        col = f"declared_ton_{mat}"
        add(V, f"Beyan edilen tonaj - {mat} (test)", round(float(test[col].sum()), 2), "ton",
            "Observations", V)
    priced = test[test["gekap_rate_status"] == "official_verified"]
    add(V, "Test donemi hesaplanan GEKAP tutari (beyan uzerinden)",
        round(float(priced["gekap_amount_try"].fillna(0).sum()), 2), "TL",
        "Observations x GEKAP_Rates (2026 tarifesi, SRC-001)", V)
    add(V, "Ortalama inceleme suresi",
        round(float(test["inspection_duration_days"].fillna(0).mean()), 1), "gun",
        "Audit_Labels", V)
    add(V, "Kapsanan sektor sayisi", int(observations["sector"].nunique()), "adet", "Firms", V)
    add(V, "Kapsanan il sayisi", int(observations["province"].nunique()), "adet", "Firms", V)
    add(V, "Dusuk veri guvenli kayit orani (test)",
        round(float((test["data_confidence_level"] == "dusuk").mean()), 4), "oran",
        "Observations", V)

    for r in climate.itertuples():
        add(S, f"Potansiyel geri kazanim tonaji - {r.senaryo} senaryo",
            r.potansiyel_geri_kazanim_ton, "ton", r.donusum_formulu, S)
        add(S, f"Potansiyel CO2e etkisi - {r.senaryo} senaryo",
            r.potansiyel_CO2e_ton, "ton CO2e", r.faktor_kaynagi, S)

    return pd.DataFrame(rows)
