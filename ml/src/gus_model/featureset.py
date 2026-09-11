"""Ozellik sozlesmeleri.

Uc ayri ozellik uzayi vardir ve BILINCLI olarak ayridir:

`HIST_FEATURES`  Tarihsel baslik. Firmanin KENDI gecmisi + faaliyet buyuklugu.
                 Sorusu: "bu firma kendi davranisina gore ne beyan etmeliydi?"

`PEER_FEATURES`  Emsal baslik. Firmanin kendi beyan gecmisi HIC girmez; yalnizca
                 uretim/ithalat olcegi, emsal grubun onceki donem istatistikleri
                 ve yapisal nitelikler girer. Sorusu: "bu olcekte, bu sektorde
                 bir firma ne beyan eder?" Kendi gecmisi disarida oldugu icin
                 yillardir sistematik eksik beyan veren firma bu basligin
                 beklentisini asagi cekemez.

`RISK_FEATURES`  Fusion (risk) modeli. Girdisi HAM ozellik degil, sekiz sinyalin
                 0-100 kaniti + kullanilabilirlikleri + veri guveni baglamidir.
                 Boylece aciklama da sinyal dilinde kalir.

Her iki quantile basligi da `TARGET_DERIVED_COLUMNS` icindeki hicbir sutunu
GORMEZ; hedef beyan tonaji oldugu icin bunlar dogrudan sizintidir.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from .config import EXCLUDED_COLUMNS, SIGNAL_CODES, TARGET_DERIVED_COLUMNS

TARGET_COLUMN = "declared_packaging_tonnage"

CATEGORICAL = ("sector", "size_band", "f_data_confidence_level")

# Log olcegine cevrilen buyukluk sutunlari. Beyan tonaji ve uretim miktari
# birkac buyukluk mertebesi degisir; agac modelinde ham olcek gereksiz derinlik
# ister, log olceginde ayni bolme oransal bir bolmedir.
LOG1P_COLUMNS = (
    "production_qty",
    "f_s1_decl_lag1",
    "f_s1_decl_lag2",
    "f_s1_decl_lag3",
    "f_s1_decl_lag4",
    "f_s1_hist_median",
    "f_s1_hist_p10",
    "f_s1_hist_std",
    "f_s3_bom_expected",
    "f_s4_prod_lag1",
    "f_s4_prod_lag4",
    "f_s5_domestic_derived",
    "f_s5_correction_qty",
)

# --------------------------------------------------------------------------
# Ortak yapisal ozellikler - her iki quantile basliginda da bulunur
# --------------------------------------------------------------------------
_STRUCTURAL: Tuple[str, ...] = (
    "production_qty",
    "f_s4_prod_lag1",
    "f_s4_prod_lag4",
    "f_s4_prod_qoq",
    "f_s4_prod_yoy",
    "f_s5_export_share",
    "f_s5_import_share",
    "f_s5_return_share",
    "f_s5_domestic_derived",
    "f_s5_export_share_lag1",
    "f_s5_export_share_delta",
    "f_s5_exemption_flag",
    "f_s5_exempt_share",
    "f_s5_correction_qty",
    "f_s5_trade_data_missing",
    "f_s6_quarter",
    "f_s7_matrix_age_years",
    "f_s7_matrix_stale_flag",
    "f_firm_age_years",
    "f_data_quality_score",
    "f_missing_field_count",
    "sector",
    "size_band",
)

# Yalnizca tarihsel basliga giren, firmanin KENDI gecmisi
_OWN_HISTORY: Tuple[str, ...] = (
    "f_s1_decl_lag1",
    "f_s1_decl_lag2",
    "f_s1_decl_lag3",
    "f_s1_decl_lag4",
    "f_s1_hist_median",
    "f_s1_hist_std",
    "f_s1_hist_p10",
    "f_s1_history_len",
    "f_s1_ratio_hist_median",
    "f_s1_ratio_hist_std",
    "f_s5_dpd_hist_median",
    "f_s5_dpd_hist_std",
    "f_s6_own_quarter_mean_prev",
)

# Yalnizca emsal basligina giren, emsal grubun onceki donem istatistikleri
_PEER: Tuple[str, ...] = (
    "f_s2_peer_median_prev",
    "f_s2_peer_p10_prev",
    "f_s2_peer_iqr_prev",
    "f_s2_peer_n_prev",
)

# Urun agaci beklentisi. S3 sinyalinin BAGIMSIZ kalmasi icin iki quantile
# basliginin HICBIRINE girmez.
_BOM: Tuple[str, ...] = ("f_s3_bom_expected", "f_s3_bom_coverage")

HIST_FEATURES: Tuple[str, ...] = _STRUCTURAL + _OWN_HISTORY
PEER_FEATURES: Tuple[str, ...] = _STRUCTURAL + _PEER

# Risk modelinin sinyal disi baglam ozellikleri.
#
# `sector` ve `size_band` BILINCLI OLARAK YOK. Ikisi de modele giriyor - fakat
# BEKLENTI basliklarinda ve konformal gruplamada. Orada isleri karsilastirmayi
# ADIL yapmaktir: firma kendi sektorunun ve olceginin beklentisiyle olculur.
# Risk puanina dogrudan girdiklerinde ise yaptiklari sey baskadir: "senin gibi
# firmalar daha cok denetleniyor" demek olur. Bu, `province` icin reddedilen
# muhakemenin aynisidir ve sektor/olcek icin de reddedilir.
#
# Bedeli olculdu: egitim penceresi capraz dogrulamasinda PR-AUC 0,2141 ->
# 0,2169, test Precision@100 0,350 -> 0,350. Yani bedeli yok.
#
# `log_production` kalir: oranlarin hangi olcekte okundugunu soyler ve
# cikarilmasi olculebilir bir kayip veriyor (Precision@100 0,350 -> 0,320).
RISK_CONTEXT: Tuple[str, ...] = (
    "f_active_signal_count",
    "f_data_quality_score",
    "f_data_freshness_days",
    "f_missing_field_count",
    "f_data_confidence_level",
    "f_firm_age_years",
    "f_s6_quarter",
    "f_s3_bom_coverage",
    "f_s7_matrix_age_years",
    "f_s2_peer_n_prev",
    "log_production",
)

# Konformal aralikla beyanin iliskisini tasiyan ozellikler. Katman 3'un
# ciktisini Katman 4'e baglayan koprudur.
RISK_INTERVAL: Tuple[str, ...] = (
    "interval_position_z",
    "interval_rel_gap",
    "interval_width_rel",
    "interval_below_lower",
)

# Modele HAM sinyal istatistigi verilir, 0-100'e kirpilmis puani DEGIL.
# Neden: rampa, egitim yuzdelik 70'in altini sifira kirpar. Denetciye
# gosterilen puan icin dogru olan budur - normal bir kayit "12 puan" almamali.
# Fakat kirpma, kayitlarin %70'i arasindaki siralamayi yok eder; modelin bu
# bilgiye ihtiyaci vardir. Olculdu: ham istatistikle PR-AUC valid uzerinde
# 0,23'ten 0,29'a cikiyor. Kirpilmis puan yalnizca SUNUM katmanindadir.
#
# Atif bozulmaz: `raw_sN` ve `avail_sN` ayni sinyale aittir, SHAP katkilari
# `explain.feature_groups` icinde sinyal duzeyinde toplanir.
RISK_FEATURES: Tuple[str, ...] = (
    tuple(f"raw_{c.lower()}" for c in SIGNAL_CODES)
    + tuple(f"avail_{c.lower()}" for c in SIGNAL_CODES)
    + RISK_INTERVAL
    + RISK_CONTEXT
)


def _guard(features: Sequence[str]) -> None:
    """Beklenti basliklarinda hedef turevi sutun olmadigini dogrular."""
    leaked = [f for f in features if f in TARGET_DERIVED_COLUMNS]
    if leaked:
        raise AssertionError(
            "Quantile basligina hedeften turetilmis sutun girdi: " + ", ".join(leaked)
        )
    excluded = [f for f in features if f in EXCLUDED_COLUMNS]
    if excluded:
        raise AssertionError(
            "Bilincli olarak disarida birakilan sutun kullanilmis: " + ", ".join(excluded)
        )


_guard(HIST_FEATURES)
_guard(PEER_FEATURES)


def prepare_matrix(
    frame: pd.DataFrame,
    features: Sequence[str],
    categories: Dict[str, List[str]] | None = None,
) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """Ozellik matrisini LightGBM'in bekledigi tiplere cevirir.

    Eksik deger DOLDURULMAZ. LightGBM eksigi kendi dalinda tasir; ortalama ile
    doldurmak "olcum yapilmadi" ile "olculdu ve ortalama cikti" durumlarini
    birbirine karistirir. Bu ayrim, kullanilamayan sinyalin temiz sonuc
    sayilmamasi kuralinin sayisal karsiligidir.
    """
    out = pd.DataFrame(index=frame.index)
    resolved: Dict[str, List[str]] = {}

    for name in features:
        if name == "log_production":
            out[name] = np.log1p(frame["production_qty"].astype(float).clip(lower=0.0))
            continue
        if name not in frame.columns:
            out[name] = np.nan
            continue
        col = frame[name]
        if name in CATEGORICAL:
            values = col.astype("string").fillna(pd.NA)
            levels = (categories or {}).get(name)
            if levels is None:
                levels = sorted(v for v in values.dropna().unique())
            out[name] = pd.Categorical(values, categories=levels)
            resolved[name] = list(levels)
        elif name in LOG1P_COLUMNS:
            out[name] = np.log1p(col.astype(float).clip(lower=0.0))
        else:
            out[name] = col.astype(float)

    if categories:
        for name, levels in categories.items():
            if name in out.columns:
                resolved.setdefault(name, list(levels))
    return out, resolved


def categorical_names(features: Sequence[str]) -> List[str]:
    return [f for f in features if f in CATEGORICAL]


def log_target(values: pd.Series | np.ndarray) -> np.ndarray:
    return np.log1p(np.asarray(values, dtype=float).clip(min=0.0))


def unlog(values: np.ndarray) -> np.ndarray:
    return np.expm1(np.asarray(values, dtype=float)).clip(min=0.0)


__all__ = [
    "TARGET_COLUMN",
    "HIST_FEATURES",
    "PEER_FEATURES",
    "RISK_FEATURES",
    "RISK_CONTEXT",
    "RISK_INTERVAL",
    "CATEGORICAL",
    "LOG1P_COLUMNS",
    "prepare_matrix",
    "categorical_names",
    "log_target",
    "unlog",
]
