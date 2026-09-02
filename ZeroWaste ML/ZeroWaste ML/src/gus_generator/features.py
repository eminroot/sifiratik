"""Model_Ready ozellik tablosu.

SIZINTI KURALLARI
-----------------
1. Bu modul `anomalies` modulunu ITHAL ETMEZ ve ground-truth alanlarina
   erisMEZ. (`validate_dataset.py` bunu otomatik dogrular.)
2. Hicbir ozellik gelecege bakmaz. Gecikmeli (lag) degerler firma icinde
   zaman sirali hesaplanir; emsal istatistikleri t-1 doneminden alinir.
3. `_` on ekli latent alanlar bu tabloya ASLA girmez.

Ozellikler, GUS-DEDEKTIV'in SEKIZ AYRI KANIT SINYALI ile eslesecek sekilde
`f_sN_` on ekiyle adlandirilmistir. Ozelliklerin kendisi sinyal DEGILDIR;
sinyaller model asamasinda bu ozelliklerden uretilir.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .config import GEKAP_MATERIALS

_EPS = 1e-9

# Bu tabloya girmesi YASAK olan sutun adi kaliplari
FORBIDDEN_PATTERNS = (
    "truth", "anomaly", "audit", "confirmed_correction", "true_expected",
    "true_gap", "true_deficit", "label_", "legitimate_cause", "_true_",
)


def _safe_div(a, b):
    b = np.asarray(b, dtype=float)
    a = np.asarray(a, dtype=float)
    out = np.full_like(a, np.nan, dtype=float)
    mask = np.abs(b) > _EPS
    out[mask] = a[mask] / b[mask]
    return out


def build_model_ready(observations: pd.DataFrame, firms: pd.DataFrame) -> pd.DataFrame:
    obs = observations.copy()
    obs = obs.sort_values(["firm_id", "period"]).reset_index(drop=True)

    fcols = ["firm_id", "operating_since", "export_orientation", "import_dependency",
             "data_maturity_score"]
    obs = obs.merge(firms[fcols], on="firm_id", how="left")

    decl = obs["declared_packaging_tonnage"].astype(float)
    prod = obs["production_qty"].astype(float)
    g = obs.groupby("firm_id", sort=False)

    # ------------------------------------------------------------------
    # S1 - Tarihsel alt sinir ihlali
    # ------------------------------------------------------------------
    for k in (1, 2, 3, 4):
        obs[f"f_s1_decl_lag{k}"] = g["declared_packaging_tonnage"].shift(k)

    obs["f_s1_decl_qoq"] = _safe_div(decl - obs["f_s1_decl_lag1"], obs["f_s1_decl_lag1"])
    obs["f_s1_decl_yoy"] = _safe_div(decl - obs["f_s1_decl_lag4"], obs["f_s1_decl_lag4"])

    # Genisleyen (expanding) gecmis istatistikleri - ileriye bakis YOK
    shifted = g["declared_packaging_tonnage"].shift(1)
    obs["_shift1"] = shifted
    gs = obs.groupby("firm_id", sort=False)["_shift1"]
    obs["f_s1_hist_median"] = gs.transform(lambda s: s.expanding(min_periods=2).median())
    obs["f_s1_hist_std"] = gs.transform(lambda s: s.expanding(min_periods=3).std())
    obs["f_s1_hist_p10"] = gs.transform(lambda s: s.expanding(min_periods=3).quantile(0.10))
    obs["f_s1_hist_n"] = gs.transform(lambda s: s.expanding(min_periods=1).count())

    obs["f_s1_z_own"] = _safe_div(decl - obs["f_s1_hist_median"], obs["f_s1_hist_std"])
    obs["f_s1_vs_hist_median_ratio"] = _safe_div(decl, obs["f_s1_hist_median"])
    obs["f_s1_below_hist_p10"] = (decl < obs["f_s1_hist_p10"]).astype(int)
    obs["f_s1_history_len"] = obs["f_s1_hist_n"].fillna(0)

    # Beyan / uretim orani (olcekten arindirilmis temel gosterge)
    obs["f_ratio_decl_per_prod"] = _safe_div(decl, prod)
    obs["_ratio_shift1"] = obs.groupby("firm_id", sort=False)["f_ratio_decl_per_prod"].shift(1)
    grs = obs.groupby("firm_id", sort=False)["_ratio_shift1"]
    obs["f_s1_ratio_hist_median"] = grs.transform(lambda s: s.expanding(min_periods=2).median())
    obs["f_s1_ratio_hist_std"] = grs.transform(lambda s: s.expanding(min_periods=3).std())
    obs["f_s1_ratio_z_own"] = _safe_div(
        obs["f_ratio_decl_per_prod"] - obs["f_s1_ratio_hist_median"], obs["f_s1_ratio_hist_std"]
    )

    # ------------------------------------------------------------------
    # S2 - Emsal alt sinir ihlali  (t-1 doneminden, ileriye bakis YOK)
    # ------------------------------------------------------------------
    obs["f_s2_peer_group"] = obs["sector"].astype(str) + "|" + obs["size_band"].astype(str)
    periods_sorted = sorted(obs["period"].unique())
    pidx = {p: i for i, p in enumerate(periods_sorted)}
    obs["_pidx"] = obs["period"].map(pidx)

    peer_stats = (
        obs.groupby(["f_s2_peer_group", "_pidx"])["f_ratio_decl_per_prod"]
        .agg(peer_median="median", peer_p10=lambda s: s.quantile(0.10),
             peer_p25=lambda s: s.quantile(0.25), peer_p75=lambda s: s.quantile(0.75),
             peer_n="count")
        .reset_index()
    )
    peer_stats["_pidx"] = peer_stats["_pidx"] + 1  # bir donem KAYDIR -> t-1 bilgisi
    obs = obs.merge(peer_stats, on=["f_s2_peer_group", "_pidx"], how="left")

    obs["f_s2_peer_median_prev"] = obs["peer_median"]
    obs["f_s2_peer_p10_prev"] = obs["peer_p10"]
    obs["f_s2_peer_iqr_prev"] = obs["peer_p75"] - obs["peer_p25"]
    obs["f_s2_peer_n_prev"] = obs["peer_n"]
    obs["f_s2_vs_peer_median"] = _safe_div(obs["f_ratio_decl_per_prod"], obs["f_s2_peer_median_prev"])
    obs["f_s2_peer_z"] = _safe_div(
        obs["f_ratio_decl_per_prod"] - obs["f_s2_peer_median_prev"],
        obs["f_s2_peer_iqr_prev"].replace(0.0, np.nan),
    )
    obs["f_s2_below_peer_p10"] = (obs["f_ratio_decl_per_prod"] < obs["f_s2_peer_p10_prev"]).astype(int)

    # ------------------------------------------------------------------
    # S3 - Beklenen ile gerceklesen ambalaj tonaji farki
    # ------------------------------------------------------------------
    bom = obs["bom_expected_tonnage_observable"].astype(float)
    obs["f_s3_bom_expected"] = bom
    obs["f_s3_bom_gap_abs"] = bom - decl
    obs["f_s3_bom_gap_rel"] = _safe_div(bom - decl, bom)
    obs["f_s3_bom_coverage"] = obs["bom_coverage_ratio"].astype(float)

    # ------------------------------------------------------------------
    # S4 - Faaliyet esnekligi uyumsuzlugu
    # ------------------------------------------------------------------
    for k in (1, 4):
        obs[f"f_s4_prod_lag{k}"] = obs.groupby("firm_id", sort=False)["production_qty"].shift(k)
    obs["f_s4_prod_qoq"] = _safe_div(prod - obs["f_s4_prod_lag1"], obs["f_s4_prod_lag1"])
    obs["f_s4_prod_yoy"] = _safe_div(prod - obs["f_s4_prod_lag4"], obs["f_s4_prod_lag4"])
    obs["f_s4_divergence_qoq"] = obs["f_s1_decl_qoq"] - obs["f_s4_prod_qoq"]
    obs["f_s4_divergence_yoy"] = obs["f_s1_decl_yoy"] - obs["f_s4_prod_yoy"]
    denom = obs["f_s4_prod_qoq"].where(obs["f_s4_prod_qoq"].abs() > 0.03)
    obs["f_s4_elasticity"] = obs["f_s1_decl_qoq"] / denom

    # ------------------------------------------------------------------
    # S5 - Dis ticaret ve duzeltme dengesi
    # ------------------------------------------------------------------
    imp = obs["import_qty"].astype(float)
    exp = obs["export_qty"].astype(float)
    ret = obs["return_qty"].astype(float)
    gross = prod + imp.fillna(0.0)
    obs["f_s5_export_share"] = _safe_div(exp, gross)
    obs["f_s5_import_share"] = _safe_div(imp, gross)
    obs["f_s5_return_share"] = _safe_div(ret, gross)
    obs["f_s5_domestic_derived"] = obs["domestic_supply_qty_derived"].astype(float)
    obs["f_s5_decl_per_domestic"] = _safe_div(decl, obs["f_s5_domestic_derived"])
    obs["f_s5_export_share_lag1"] = obs.groupby("firm_id", sort=False)["f_s5_export_share"].shift(1)
    obs["f_s5_export_share_delta"] = obs["f_s5_export_share"] - obs["f_s5_export_share_lag1"]
    obs["f_s5_exemption_flag"] = obs["exemption_flag"].astype(int)
    obs["f_s5_exempt_share"] = obs["exempt_share"].astype(float)
    obs["f_s5_correction_qty"] = obs["correction_qty"].astype(float)
    obs["f_s5_trade_data_missing"] = imp.isna().astype(int)

    # Ic piyasa arzina gore beyan oraninin KENDI GECMISINE gore normalizasyonu.
    # Bu, olcek ve dis ticaret dalgalanmasindan arindirilmis en bilgilendirici
    # gostergedir; ileriye bakis olmamasi icin bir donem kaydirilarak hesaplanir.
    obs["_dpd_shift1"] = obs.groupby("firm_id", sort=False)["f_s5_decl_per_domestic"].shift(1)
    gdp = obs.groupby("firm_id", sort=False)["_dpd_shift1"]
    obs["f_s5_dpd_hist_median"] = gdp.transform(lambda s: s.expanding(min_periods=2).median())
    obs["f_s5_dpd_hist_std"] = gdp.transform(lambda s: s.expanding(min_periods=3).std())
    obs["f_s5_dpd_vs_hist"] = _safe_div(obs["f_s5_decl_per_domestic"], obs["f_s5_dpd_hist_median"])
    obs["f_s5_dpd_z_own"] = _safe_div(
        obs["f_s5_decl_per_domestic"] - obs["f_s5_dpd_hist_median"], obs["f_s5_dpd_hist_std"]
    )
    # Emsal grubun ayni gostergedeki t-1 medyani
    peer_dpd = (
        obs.groupby(["f_s2_peer_group", "_pidx"])["f_s5_decl_per_domestic"]
        .agg(peer_dpd_median="median", peer_dpd_p10=lambda s: s.quantile(0.10))
        .reset_index()
    )
    peer_dpd["_pidx"] = peer_dpd["_pidx"] + 1
    obs = obs.merge(peer_dpd, on=["f_s2_peer_group", "_pidx"], how="left")
    obs["f_s2_dpd_vs_peer_median"] = _safe_div(obs["f_s5_decl_per_domestic"], obs["peer_dpd_median"])
    obs["f_s2_dpd_below_peer_p10"] = (obs["f_s5_decl_per_domestic"] < obs["peer_dpd_p10"]).astype(int)

    # ------------------------------------------------------------------
    # S6 - Donemsel davranis kirilmasi
    # ------------------------------------------------------------------
    obs["f_s6_quarter"] = obs["quarter"].astype(int)
    obs["_r_shift1"] = obs.groupby("firm_id", sort=False)["f_ratio_decl_per_prod"].shift(1)
    q_hist = (
        obs.groupby(["firm_id", "quarter"], sort=False)["_r_shift1"]
        .transform(lambda s: s.expanding(min_periods=1).mean())
    )
    obs["f_s6_own_quarter_mean_prev"] = q_hist
    obs["f_s6_seasonal_resid"] = _safe_div(
        obs["f_ratio_decl_per_prod"] - obs["f_s6_own_quarter_mean_prev"],
        obs["f_s6_own_quarter_mean_prev"],
    )

    # ------------------------------------------------------------------
    # S7 - Urun agaci ve ambalaj matrisi uyumsuzlugu
    # ------------------------------------------------------------------
    obs["f_s7_matrix_age_years"] = obs["year"].astype(int) - obs["weight_matrix_vintage_year"].astype(int)
    obs["f_s7_matrix_stale_flag"] = (obs["f_s7_matrix_age_years"] >= 3).astype(int)
    mat_cols = [f"declared_ton_{m}" for m in GEKAP_MATERIALS]
    mat = obs[mat_cols].astype(float).to_numpy()
    tot = mat.sum(axis=1, keepdims=True)
    mix = np.divide(mat, np.where(tot > _EPS, tot, np.nan))
    with np.errstate(divide="ignore", invalid="ignore"):
        ent = -np.nansum(np.where(mix > 0, mix * np.log(mix), 0.0), axis=1)
    obs["f_s7_material_mix_entropy"] = ent
    for j, m in enumerate(GEKAP_MATERIALS):
        obs[f"f_s7_mix_{m}"] = mix[:, j]
    prev_mix = obs.groupby("firm_id", sort=False)[[f"f_s7_mix_{m}" for m in GEKAP_MATERIALS]].shift(1)
    obs["f_s7_mix_shift_l1"] = np.abs(
        obs[[f"f_s7_mix_{m}" for m in GEKAP_MATERIALS]].to_numpy() - prev_mix.to_numpy()
    ).sum(axis=1)

    # ------------------------------------------------------------------
    # S8 - Dis dogrulama kaniti
    # ------------------------------------------------------------------
    ext = obs["external_evidence_tonnage"].astype(float)
    obs["f_s8_external_available"] = ext.notna().astype(int)
    obs["f_s8_external_gap_abs"] = ext - decl
    obs["f_s8_external_gap_rel"] = _safe_div(ext - decl, ext)

    # ------------------------------------------------------------------
    # Sinyal kullanilabilirligi ve veri guveni
    # ------------------------------------------------------------------
    obs["f_avail_s1"] = (obs["f_s1_history_len"] >= 3).astype(int)
    obs["f_avail_s2"] = (obs["f_s2_peer_n_prev"].fillna(0) >= 5).astype(int)
    obs["f_avail_s3"] = obs["f_s3_bom_expected"].notna().astype(int)
    obs["f_avail_s4"] = obs["f_s4_prod_qoq"].notna().astype(int)
    obs["f_avail_s5"] = (imp.notna() & exp.notna()).astype(int)
    obs["f_avail_s6"] = obs["f_s6_own_quarter_mean_prev"].notna().astype(int)
    obs["f_avail_s7"] = (obs["f_s3_bom_coverage"] > 0.05).astype(int)
    obs["f_avail_s8"] = obs["f_s8_external_available"]
    avail_cols = [f"f_avail_s{i}" for i in range(1, 9)]
    obs["f_active_signal_count"] = obs[avail_cols].sum(axis=1)

    obs["f_data_quality_score"] = obs["data_quality_score"].astype(float)
    obs["f_data_freshness_days"] = obs["data_freshness_days"].astype(int)
    obs["f_missing_field_count"] = obs["missing_field_count"].astype(int)
    obs["f_data_confidence_level"] = obs["data_confidence_level"]
    obs["f_firm_age_years"] = obs["year"].astype(int) - obs["operating_since"].astype(int)

    keep = (
        ["observation_id", "firm_id", "period", "year", "quarter", "split",
         "sector", "size_band", "province", "f_s2_peer_group",
         "declared_packaging_tonnage", "production_qty"]
        + [c for c in obs.columns if c.startswith("f_")]
    )
    keep = list(dict.fromkeys(keep))
    model_ready = obs[keep].copy()

    _assert_no_leakage(model_ready)
    return model_ready


def _assert_no_leakage(df: pd.DataFrame) -> None:
    bad: List[str] = []
    for c in df.columns:
        lc = c.lower()
        if lc.startswith("_"):
            bad.append(c)
            continue
        for pat in FORBIDDEN_PATTERNS:
            if pat in lc:
                bad.append(c)
                break
    if bad:
        raise AssertionError(
            "Model_Ready icinde sizinti riski tasiyan sutun(lar) bulundu: " + ", ".join(sorted(set(bad)))
        )
