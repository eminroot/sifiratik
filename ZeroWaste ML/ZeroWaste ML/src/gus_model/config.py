"""GUS-DEDEKTIV model katmani - konfigurasyon.

Bu modul, ARCHITECTURE.md Katman 3-5 icin TUM parametreleri tek yerde toplar.
`gus_generator.config` veri ureticinin tek dogruluk kaynagi ise, bu modul de
dedektorun tek dogruluk kaynagidir. Ikisi bilincli olarak AYRIDIR: uretici
latent buyuklukler uzerinde calisir, dedektor yalnizca gozlenen alanlari gorur.

Tekrar uretilebilirlik: ayni seed + ayni config + ayni dataset = ayni model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple

MODEL_VERSION = "gus-ml-1.0.0"
ARTIFACT_SCHEMA_VERSION = "1.0.0"

# Konformal aralik hedef kapsamasi. 0,90 => [q05, q95]
TARGET_COVERAGE = 0.90

# Model_Ready icinde HEDEFIN kendisinden turetilmis sutunlar. Bunlar beklenti
# (quantile) modeline ASLA girmez; girerse model beyani beyandan tahmin eder.
# Sinyal katmaninda ve risk modelinde kullanilmalari serbesttir - orada hedef
# denetim etiketidir, beyan tonaji degildir.
TARGET_DERIVED_COLUMNS: Tuple[str, ...] = (
    "declared_packaging_tonnage",
    "f_ratio_decl_per_prod",
    "f_s1_decl_qoq",
    "f_s1_decl_yoy",
    "f_s1_z_own",
    "f_s1_vs_hist_median_ratio",
    "f_s1_below_hist_p10",
    "f_s1_ratio_z_own",
    "f_s2_vs_peer_median",
    "f_s2_peer_z",
    "f_s2_below_peer_p10",
    "f_s2_dpd_vs_peer_median",
    "f_s2_dpd_below_peer_p10",
    "f_s3_bom_gap_abs",
    "f_s3_bom_gap_rel",
    "f_s4_divergence_qoq",
    "f_s4_divergence_yoy",
    "f_s4_elasticity",
    "f_s5_decl_per_domestic",
    "f_s5_dpd_vs_hist",
    "f_s5_dpd_z_own",
    "f_s6_seasonal_resid",
    "f_s7_material_mix_entropy",
    "f_s7_mix_plastik",
    "f_s7_mix_kagit_karton",
    "f_s7_mix_cam",
    "f_s7_mix_metal",
    "f_s7_mix_kompozit",
    "f_s7_mix_ahsap",
    "f_s7_mix_shift_l1",
    "f_s8_external_gap_abs",
    "f_s8_external_gap_rel",
)

# Modelden BILINCLI olarak cikarilan sutunlar ve gerekcesi.
EXCLUDED_COLUMNS: Dict[str, str] = {
    "province": (
        "Cografi profilleme riski. Il, denetim onceligini belirlemede girdi "
        "DEGILDIR; yalnizca alt grup adalet olcumunde kullanilir."
    ),
    "year": (
        "Agac modelleri yila gore bolerse egitim penceresi disina ekstrapole "
        "edemez. Zaman etkisi ceyrek ve gecikmeli degerlerle tasinir."
    ),
    "f_s2_peer_group": "sector x size_band ile birebir ayni bilgi.",
    "firm_id": "Firma kimligi bir kanit degildir; ezberleme riski.",
    "observation_id": "Kayit kimligi.",
    "period": "Zaman etiketi; ceyrek ayri ozellik olarak verilir.",
    "split": "Bolum etiketi.",
}

# --------------------------------------------------------------------------
# Sekiz ayri kanit sinyali - ARCHITECTURE.md 3. bolum
# --------------------------------------------------------------------------
# `yon`: ham istatistigin hangi yonu riski gosterir. Tum ham istatistikler
# "buyudukce daha riskli" olacak sekilde normalize edilir.
SIGNAL_SPECS: Tuple[Dict, ...] = (
    {
        "code": "S1",
        "key": "HISTORICAL_SHORTFALL",
        "ad": "Tarihsel alt sinir ihlali",
        "soru": "Firma kendi gecmis beyan davranisindan ne kadar sapiyor?",
        "kaynak": "quantile_hist",
        "avail": "f_avail_s1",
        "avail_reason": (
            "Firmanin en az uc onceki donemde hem beyan hem uretim kaydi yok; "
            "kendi taban cizgisi kurulamiyor."
        ),
    },
    {
        "code": "S2",
        "key": "PEER_DEVIATION",
        "ad": "Emsal alt sinir ihlali",
        "soru": "Benzer firmalarin beklenen araliginin ne kadar altinda?",
        "kaynak": "quantile_peer",
        "avail": "f_avail_s2",
        "avail_reason": (
            "Ayni sektor ve olcek bandinda onceki donemde bes emsal firma "
            "bulunmuyor; emsal karsilastirmasi yapilamiyor."
        ),
    },
    {
        "code": "S3",
        "key": "BOM_EXPECTATION_GAP",
        "ad": "Beklenen-gerceklesen tonaj farki",
        "soru": "Urun agacindan beklenen ile beyan arasindaki fark?",
        "kaynak": "feature",
        "avail": "f_avail_s3",
        "avail_reason": (
            "Urun agaci / ambalaj agirlik matrisi bu kayit icin tanimli degil."
        ),
    },
    {
        "code": "S4",
        "key": "ACTIVITY_MISMATCH",
        "ad": "Faaliyet esnekligi uyumsuzlugu",
        "soru": "Uretim artarken beyan makul olcude degisiyor mu?",
        "kaynak": "feature",
        "avail": "f_avail_s4",
        "avail_reason": "Onceki donem uretim miktari yok; hareket karsilastirilamiyor.",
    },
    {
        "code": "S5",
        "key": "TRADE_BALANCE",
        "ad": "Dis ticaret ve duzeltme dengesi",
        "soru": "Ithalat/ihracat/iade/mahsup beyanla uyumlu mu?",
        "kaynak": "feature",
        "avail": "f_avail_s5",
        "avail_reason": "Ithalat veya ihracat verisi eksik; ic piyasa arzi hesaplanamiyor.",
    },
    {
        "code": "S6",
        "key": "SEASONAL_BREAK",
        "ad": "Donemsel davranis kirilmasi",
        "soru": "Ceyreklik kalipta aciklanamayan kirilma var mi?",
        "kaynak": "feature",
        "avail": "f_avail_s6",
        "avail_reason": "Ayni ceyrek icin onceki yil kaydi yok; mevsimsel taban kurulamiyor.",
    },
    {
        "code": "S7",
        "key": "PACKAGING_MATRIX",
        "ad": "Urun agaci / ambalaj matrisi uyumsuzlugu",
        "soru": "SKU ve agirlik matrisi beyani destekliyor mu?",
        "kaynak": "feature",
        "avail": "f_avail_s7",
        "avail_reason": "Ambalaj agirlik matrisi kapsami %5'in altinda.",
    },
    {
        "code": "S8",
        "key": "EXTERNAL_EVIDENCE",
        "ad": "Dis dogrulama kaniti",
        "soru": "ERP / onceki denetim kaydiyla uyumsuzluk var mi?",
        "kaynak": "feature",
        "avail": "f_avail_s8",
        "avail_reason": "ERP veya onceki denetim kaydi bulunmuyor.",
    },
)

SIGNAL_CODES: Tuple[str, ...] = tuple(s["code"] for s in SIGNAL_SPECS)

# Sinyal ham istatistiginin 0-100 olcegine oturtuldugu capa yuzdelikleri.
# `low` altinda 0, `high` uzerinde 100. Egitim penceresinden ogrenilir ve
# `signals.json` icine yazilir - boylece butun sinyaller ayni olcekte konusur.
SIGNAL_RAMP_LOW_PCT = 70.0
SIGNAL_RAMP_HIGH_PCT = 99.0

# Bir sinyalin "atesledi" sayilmasi icin gereken esik (0-100).
SIGNAL_ACTIVE_THRESHOLD = 22.0

# --------------------------------------------------------------------------
# Oncelik puani bandlari
# --------------------------------------------------------------------------
# Ham olasilik degil, REFERANS POPULASYONDAKI yuzdelik uzerinden puan uretilir.
# Capalar: (referans yuzdeligi, puan). CRITICAL bandinin genisligi bilincli
# olarak populasyon prevalansi kadardir - kuyrugun tepesi sorunun boyu kadardir.
SCORE_ANCHORS: Tuple[Tuple[float, float], ...] = (
    (0.00, 0.0),
    (0.50, 25.0),   # LOW -> MEDIUM
    (0.80, 50.0),   # MEDIUM -> HIGH
    (0.93, 75.0),   # HIGH -> CRITICAL
    (1.00, 100.0),
)

PRIORITY_BANDS: Tuple[Tuple[str, float, float], ...] = (
    ("LOW", 0.0, 24.999),
    ("MEDIUM", 25.0, 49.999),
    ("HIGH", 50.0, 74.999),
    ("CRITICAL", 75.0, 100.0),
)

# Veri guveni esikleri.
# `f_data_quality_score` dataset'te 0-1 olceginde tutulur (backend ayni degeri
# 0-100 olceginde tasir ve adaptorde bolerek gecirir). Esikler 0-1'dedir.
CONFIDENCE_HIGH_COVERAGE = 0.75
CONFIDENCE_LOW_COVERAGE = 0.55
CONFIDENCE_HIGH_QUALITY = 0.70
CONFIDENCE_LOW_QUALITY = 0.45

# Politika agirliklari - backend `ScoringPolicy` ile ayni sirada tutulur.
# Ogrenilmis fusion devre disi birakildiginda seffaf yedek budur.
POLICY_WEIGHTS: Dict[str, float] = {
    "S1": 0.20,
    "S2": 0.18,
    "S3": 0.15,
    "S4": 0.14,
    "S5": 0.09,
    "S6": 0.07,
    "S7": 0.09,
    "S8": 0.08,
}

# Tek en guclu bulgunun puandaki payi. Bu olmadan tek bir konuda sistematik
# yanlis olan firma, birden cok konuda hafif sapan firmanin altinda kalir.
STRONGEST_SIGNAL_SHARE = 0.35


@dataclass
class ModelConfig:
    """Egitim hattinin tum ayarlari."""

    # --- Tekrar uretilebilirlik ---
    seed: int = 20260902
    model_version: str = MODEL_VERSION

    # --- Veri ---
    data_dir: str = "data/output/parquet"
    out_dir: str = "models"
    report_dir: str = "reports"
    # 2023 (history) bolumu ozellik uretimi icindir. Egitimde kullanilmasi
    # sizinti YARATMAZ (tamami valid/test oncesidir) fakat dokumantasyonda
    # ilan edilen protokol train = 2024Q1-2025Q2'dir. Varsayilan: kullanma.
    train_on_history: bool = False
    # history bolumunun ilk ceyreklerinde gecikmeli ozellikler bostur.
    history_min_signal_count: int = 4

    # --- Konformal ---
    target_coverage: float = TARGET_COVERAGE
    # Mondrian grubu icin gereken en az kalibrasyon ornegi. Altinda ust gruba
    # dusulur; en ustte global gruba.
    conformal_min_group: int = 60
    # Ince kalibrasyonlu gruplarda aralik bilincli olarak genisletilir.
    conformal_thin_widen: float = 1.15
    # Egitim bolumunde capraz uydurma (cross-fitting) kat sayisi. Kalibrasyon
    # artiklarinin ORNEKLEM DISI olmasi icin gereklidir.
    cv_folds: int = 5
    # Kalibrasyon havuzu:
    #   "pooled"  egitim bolumunun capraz uydurulmus artiklari + valid_b
    #   "valid_b" yalnizca valid_b (donem olarak teste en yakin ornek)
    # Capraz uydurulmus modeller tam modelden biraz zayiftir; artiklari da
    # buyuktur. Havuz genis grup destegi verir ama araligi genisletir. Secim
    # valid_a uzerindeki GOZLENEN KAPSAMA ile yapilir.
    conformal_source: str = "pooled"

    # --- LightGBM: quantile basliklari ---
    q_params: Dict = field(default_factory=lambda: {
        "objective": "quantile",
        "learning_rate": 0.045,
        "num_leaves": 24,
        "min_data_in_leaf": 40,
        "feature_fraction": 0.75,
        "bagging_fraction": 0.80,
        "bagging_freq": 1,
        "lambda_l2": 3.0,
        "max_bin": 127,
        "verbose": -1,
        "deterministic": True,
        "force_row_wise": True,
        "num_threads": 4,
    })
    q_rounds: int = 900
    q_early_stopping: int = 80

    # --- LightGBM: risk (fusion) modeli ---
    # Egitimde yalnizca ~250 pozitif var. Model kucuk ve agir duzenli tutulur.
    risk_params: Dict = field(default_factory=lambda: {
        "objective": "binary",
        "learning_rate": 0.030,
        "num_leaves": 8,
        "min_data_in_leaf": 60,
        "feature_fraction": 0.70,
        "bagging_fraction": 0.80,
        "bagging_freq": 1,
        "lambda_l1": 0.5,
        "lambda_l2": 8.0,
        "max_bin": 63,
        "verbose": -1,
        "deterministic": True,
        "force_row_wise": True,
        "num_threads": 4,
    })
    risk_rounds: int = 1200
    # Fusion tohum toplulugunun uye sayisi. 1 = tek booster.
    risk_seeds: int = 5
    risk_early_stopping: int = 120
    # Erken durdurma metrigi. Siralamayi olcen metrik secilir; kayip degil.
    risk_metric: str = "average_precision"

    # --- Degerlendirme ---
    eval_ks: Tuple[int, ...] = (25, 50, 100, 200)
    bootstrap_n: int = 2000

    def to_dict(self) -> dict:
        return asdict(self)


def band_for(score: float) -> str:
    for level, lo, hi in PRIORITY_BANDS:
        if lo <= score <= hi:
            return level
    return PRIORITY_BANDS[-1][0]


def signal_by_code(code: str) -> Dict:
    for spec in SIGNAL_SPECS:
        if spec["code"] == code:
            return spec
    raise KeyError(code)


__all__ = [
    "MODEL_VERSION",
    "ARTIFACT_SCHEMA_VERSION",
    "TARGET_COVERAGE",
    "TARGET_DERIVED_COLUMNS",
    "EXCLUDED_COLUMNS",
    "SIGNAL_SPECS",
    "SIGNAL_CODES",
    "SIGNAL_RAMP_LOW_PCT",
    "SIGNAL_RAMP_HIGH_PCT",
    "SIGNAL_ACTIVE_THRESHOLD",
    "SCORE_ANCHORS",
    "PRIORITY_BANDS",
    "POLICY_WEIGHTS",
    "STRONGEST_SIGNAL_SHARE",
    "ModelConfig",
    "band_for",
    "signal_by_code",
]
