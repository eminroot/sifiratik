"""Firma-ceyrek gozlem panelinin uretimi.

Iki katman vardir:

1. LATENT katman  : gercek (gozlenemeyen) uretim, dis ticaret ve gercek ambalaj
                    tonaji. Bu katman ground-truth uretiminde kullanilir.
2. GOZLENEN katman: denetciye/sisteme gorunen alanlar. Olcum gurultusu, eksik
                    veri ve eskimis ambalaj matrisi burada devreye girer.

Model yalnizca GOZLENEN katmani gorur. Latent alanlar `_` on ekiyle isaretlenir
ve `features.py` tarafindan hicbir sekilde kullanilmaz.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .config import GeneratorConfig, SECTORS, SIZE_BANDS, SPLIT_MAP, GEKAP_MATERIALS
from .reference_data import ReferenceData


def _quarter_index(period: str) -> int:
    return int(period[-1])


def _year(period: str) -> int:
    return int(period[:4])


def build_latent_panel(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    firms: pd.DataFrame,
    packaging: pd.DataFrame,
    ref: ReferenceData,
) -> pd.DataFrame:
    """Firma x ceyrek latent panelini uretir (henuz anomali enjeksiyonu YOK)."""
    periods = cfg.periods
    T = len(periods)

    # Firma bazli SKU ozetleri: malzeme payi ve birim agirlik toplami
    pack_by_firm: Dict[str, pd.DataFrame] = {
        fid: g for fid, g in packaging.groupby("firm_id", sort=False)
    }

    rows: List[Dict] = []

    for f in firms.itertuples():
        scfg = SECTORS[f.sector_true]
        bcfg = SIZE_BANDS[f.size_band]

        # AR(1) firma soku
        eps = 0.0
        rho, sigma_eps = 0.55, 0.10

        # Yapisal kirilma (makroekonomik / musteri kaybi / kapasite yatirimi)
        has_break = rng.random() < 0.09
        break_at = int(rng.integers(4, T - 1)) if has_break else -1
        break_mult = float(rng.uniform(0.55, 0.80)) if rng.random() < 0.5 else float(rng.uniform(1.25, 1.55))

        export_share_prev = float(f.export_orientation)
        pk = pack_by_firm.get(f.firm_id)

        for t, period in enumerate(periods):
            year, q = _year(period), _quarter_index(period)

            # Faaliyete baslamadan onceki donemler: firma yok
            if year < f.operating_since:
                continue

            eps = rho * eps + float(rng.normal(0.0, sigma_eps))
            trend = (1.0 + scfg["trend_yillik"]) ** (t / 4.0)
            seasonal = 1.0 + scfg["mevsim_genlik"] * np.cos(2.0 * np.pi * (q - scfg["mevsim_faz"]) / 4.0)
            level = 1.0
            if has_break and t >= break_at:
                level = break_mult

            production_units = float(f.lat_scale * trend * seasonal * level * np.exp(eps))

            # Dis ticaret
            export_share = float(np.clip(export_share_prev + rng.normal(0.0, 0.035), 0.0, 0.95))
            if rng.random() < 0.030:  # ihracat siparisi kazanimi/kaybi
                export_share = float(np.clip(export_share + rng.choice([-1, 1]) * rng.uniform(0.10, 0.30), 0.0, 0.95))
            export_share_prev = export_share

            import_units = float(production_units * f.import_dependency * np.exp(rng.normal(0.0, 0.18)))
            return_units = float((production_units + import_units) * rng.beta(1.2, 60.0))

            # Yasal muafiyet / istisna (ornegin ihrac kayitli teslim)
            exemption_flag = bool(rng.random() < 0.05)
            exempt_share = float(rng.uniform(0.08, 0.35)) if exemption_flag else 0.0

            gross_units = production_units + import_units
            export_units = gross_units * export_share
            domestic_units = max(0.0, gross_units - export_units - return_units)
            domestic_units_taxable = domestic_units * (1.0 - exempt_share)

            # --- GERCEK ambalaj tonaji (latent) ---
            # domestic_units_taxable x SKU payi x GERCEK birim agirlik
            true_by_mat = {m: 0.0 for m in GEKAP_MATERIALS}
            recorded_by_mat = {m: 0.0 for m in GEKAP_MATERIALS}
            if pk is not None:
                w_true = (pk["sku_volume_share"].to_numpy() * pk["unit_pack_weight_g_true"].to_numpy())
                w_rec = (pk["sku_volume_share"].to_numpy() * pk["unit_pack_weight_g_recorded"].to_numpy())
                mats = pk["gekap_material"].to_numpy()
                for m, wt, wr in zip(mats, w_true, w_rec):
                    true_by_mat[m] += domestic_units_taxable * wt / 1_000_000.0   # gram -> ton
                    recorded_by_mat[m] += domestic_units_taxable * wr / 1_000_000.0

            true_total = float(sum(true_by_mat.values()))

            rows.append({
                "observation_id": f"{f.firm_id}-{period}",
                "firm_id": f.firm_id,
                "period": period,
                "year": year,
                "quarter": q,
                "t_index": t,
                "split": SPLIT_MAP[period],
                # --- LATENT ---
                "lat_production_units": production_units,
                "lat_import_units": import_units,
                "lat_export_units": export_units,
                "lat_return_units": return_units,
                "lat_domestic_units": domestic_units,
                "lat_domestic_units_taxable": domestic_units_taxable,
                "lat_export_share": export_share,
                "lat_exemption_flag": exemption_flag,
                "lat_exempt_share": exempt_share,
                "lat_true_total_tonnage": true_total,
                "lat_has_break": has_break and t >= break_at,
                "lat_seasonal_low": bool(seasonal < 0.94),
                "lat_noise_sigma": bcfg["beyan_gurultu"],
                **{f"lat_true_ton_{m}": true_by_mat[m] for m in GEKAP_MATERIALS},
                **{f"lat_rec_ton_{m}": recorded_by_mat[m] for m in GEKAP_MATERIALS},
            })

    panel = pd.DataFrame(rows)
    panel = panel.sort_values(["firm_id", "t_index"]).reset_index(drop=True)
    return panel


def finalize_observations(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    panel: pd.DataFrame,
    firms: pd.DataFrame,
    ref: ReferenceData,
) -> pd.DataFrame:
    """Latent + anomali enjekte edilmis panelden GOZLENEN tabloyu uretir.

    `panel` icinde `lat_declared_total_tonnage` ve `_apparent_cause` alanlarinin
    anomalies.py tarafindan doldurulmus olmasi beklenir.
    """
    fmeta = firms.set_index("firm_id")
    out: List[Dict] = []

    for r in panel.itertuples():
        f = fmeta.loc[r.firm_id]

        # ---- Olcum gurultusu: uretim gostergesi ----
        production_reported = float(r.lat_production_units * np.exp(rng.normal(0.0, 0.03)))

        # ---- Eksik veri mekanizmasi (MAR: veri olgunluguna bagli) ----
        p_missing_trade = cfg.eksik_ithalat_ihracat_orani * (1.6 - float(f["data_maturity_score"]))
        trade_missing = rng.random() < np.clip(p_missing_trade, 0.0, 0.6)
        p_missing_prod = cfg.eksik_uretim_orani * (1.6 - float(f["data_maturity_score"]))
        prod_missing = rng.random() < np.clip(p_missing_prod, 0.0, 0.4)

        import_qty = None if trade_missing else round(float(r.lat_import_units), 2)
        export_qty = None if trade_missing else round(float(r.lat_export_units), 2)
        return_qty = round(float(r.lat_return_units), 2)

        # ---- Beyan edilen toplam tonaj ----
        declared_total = float(r.lat_declared_total_tonnage)

        # ---- Malzeme kirilimi ----
        true_mix = np.array([getattr(r, f"lat_true_ton_{m}") for m in GEKAP_MATERIALS], dtype=float)
        if true_mix.sum() > 0:
            mix = true_mix / true_mix.sum()
            mix = np.clip(mix + rng.normal(0.0, 0.012, size=mix.size), 1e-6, None)
            mix = mix / mix.sum()
        else:
            # Gercek tonaj sifir ama gec duzeltme tasimasi nedeniyle beyan > 0 olabilir.
            # Bu durumda kirilim firmanin birincil ambalaj malzemesine atanir; boylece
            # malzeme kirilimi toplami ile toplam beyan her zaman tutarli kalir.
            mix = np.zeros(len(GEKAP_MATERIALS))
            pm = str(f["primary_packaging_material"])
            if pm in GEKAP_MATERIALS:
                mix[GEKAP_MATERIALS.index(pm)] = 1.0
            elif declared_total > 0:
                mix[0] = 1.0
        declared_by_mat = {m: float(declared_total * s) for m, s in zip(GEKAP_MATERIALS, mix)}

        # ---- Gozlenebilir BOM beklentisi (yalnizca kapsanan kisim) ----
        cov = float(f["bom_coverage_ratio"])
        rec_total = float(sum(getattr(r, f"lat_rec_ton_{m}") for m in GEKAP_MATERIALS))
        bom_expected_obs = rec_total * cov if cov > 0.05 else None

        # ---- Dis dogrulama kanidi (ERP / onceki denetim) ----
        has_external = rng.random() < (cfg.dis_dogrulama_kapsami * (0.4 + 1.2 * float(f["data_maturity_score"])))
        if has_external:
            # Dis kayit gercek tonajin gurultulu bir olcumudur
            external_tonnage = float(r.lat_true_total_tonnage * np.exp(rng.normal(0.0, 0.09)))
        else:
            external_tonnage = None

        # ---- GEKAP tutari (yalnizca tarifesi dogrulanmis yillar) ----
        year = int(r.year)
        if year in ref.rate_kg:
            amount = 0.0
            for m in GEKAP_MATERIALS:
                if m == "ahsap":
                    continue  # ahsap tarifesi ADET bazlidir; tonajdan hesaplanamaz
                tl_per_ton = ref.gekap_tl_per_ton(year, m)
                if tl_per_ton:
                    amount += declared_by_mat[m] * tl_per_ton
            gekap_amount = round(amount, 2)
            rate_status = "official_verified"
        else:
            gekap_amount = None
            rate_status = "history_not_priced"

        # ---- Veri kalitesi ----
        missing_fields = []
        if trade_missing:
            missing_fields += ["import_qty", "export_qty"]
        if prod_missing:
            missing_fields.append("production_qty")
        if bom_expected_obs is None:
            missing_fields.append("bom_expected_tonnage")
        if external_tonnage is None:
            missing_fields.append("external_evidence_tonnage")

        n_missing = len(missing_fields)
        freshness_days = int(rng.integers(5, 400))
        quality = float(np.clip(
            0.92 - 0.13 * n_missing + 0.22 * (cov - 0.5) - 0.0004 * freshness_days
            + rng.normal(0.0, 0.03), 0.0, 1.0))

        if quality >= 0.72 and n_missing <= 1:
            confidence = "yuksek"
        elif quality >= 0.45 and n_missing <= 3:
            confidence = "orta"
        else:
            confidence = "dusuk"

        out.append({
            "observation_id": r.observation_id,
            "firm_id": r.firm_id,
            "period": r.period,
            "year": year,
            "quarter": int(r.quarter),
            "split": r.split,
            "sector": f["sector"],
            "size_band": f["size_band"],
            "province": f["province"],
            "nace_code": f["nace_code"],
            "main_product_group": f["main_product_group"],
            "gtip6_context_primary": f["primary_packaging_material"],
            "production_qty": None if prod_missing else round(production_reported, 2),
            "production_unit": "birim/ceyrek (sentetik urun adedi)",
            "import_qty": import_qty,
            "export_qty": export_qty,
            "return_qty": return_qty,
            "correction_qty": round(float(getattr(r, "lat_correction_qty", 0.0)), 4),
            "exemption_flag": bool(r.lat_exemption_flag),
            "exempt_share": round(float(r.lat_exempt_share), 4),
            "domestic_supply_qty_derived": (
                None if (trade_missing or prod_missing)
                else round(production_reported + float(r.lat_import_units)
                           - float(r.lat_export_units) - float(r.lat_return_units), 2)
            ),
            "declared_packaging_tonnage": round(declared_total, 4),
            **{f"declared_ton_{m}": round(declared_by_mat[m], 4) for m in GEKAP_MATERIALS},
            "bom_expected_tonnage_observable": (
                None if bom_expected_obs is None else round(bom_expected_obs, 4)
            ),
            "bom_coverage_ratio": round(cov, 4),
            "weight_matrix_vintage_year": int(f["bom_matrix_vintage_year"]),
            "external_evidence_tonnage": (
                None if external_tonnage is None else round(external_tonnage, 4)
            ),
            "external_evidence_source": "ERP / onceki denetim kaydi (sentetik)" if has_external else None,
            "gekap_rate_year": year,
            "gekap_rate_status": rate_status,
            "gekap_amount_try": gekap_amount,
            "data_quality_score": round(quality, 4),
            "data_freshness_days": freshness_days,
            "missing_field_count": n_missing,
            "missing_fields": ";".join(missing_fields) if missing_fields else "",
            "data_confidence_level": confidence,
            "data_source_type": "synthetic",
            "generation_method": "observations.build_latent_panel + anomalies.inject + observations.finalize_observations",
            "source_ids": "SYN-GEN-01;SYN-BOM-01",
        })

    return pd.DataFrame(out)
