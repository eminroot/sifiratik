"""GUS-DEDEKTIV sentetik veri ureteci - konfigurasyon.

Bu modul, veri uretiminin TUM parametrelerini tek yerde toplar.
Amac: tekrar uretilebilirlik. Ayni seed + ayni config = ayni dataset.

ONEMLI TASARIM KURALI
---------------------
Bu modul ve `firms/packaging/observations` modulleri, dedektor (model)
mantigindan BAGIMSIZ tutulmustur. Ureticinin anomali enjeksiyon kurallari
ile dedektorun sinyal kurallari ayni olmamalidir; aksi halde degerlendirme
donguseldir ve asiri iyimser sonuc verir.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple

DATASET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Donem tanimlari
# --------------------------------------------------------------------------
# 2023 = burn-in / gecmis. Ozellik (lag, mevsimsellik) uretmek icin gereklidir,
# skorlanmaz ve degerlendirmeye girmez. Ayrica 2023 GEKAP tarifeleri birincil
# kaynaktan dogrulanamadigi (yil ortasinda Cumhurbaskani Karari ile degisti)
# icin bu donemde parasal GEKAP tutari HESAPLANMAZ.
PERIODS: List[str] = [
    "2023Q1", "2023Q2", "2023Q3", "2023Q4",
    "2024Q1", "2024Q2", "2024Q3", "2024Q4",
    "2025Q1", "2025Q2", "2025Q3", "2025Q4",
    "2026Q1", "2026Q2",
]

SPLIT_MAP: Dict[str, str] = {
    "2023Q1": "history", "2023Q2": "history", "2023Q3": "history", "2023Q4": "history",
    "2024Q1": "train", "2024Q2": "train", "2024Q3": "train", "2024Q4": "train",
    "2025Q1": "train", "2025Q2": "train",
    "2025Q3": "valid", "2025Q4": "valid",
    "2026Q1": "test", "2026Q2": "test",
}

# GEKAP tarifesi birincil/ikincil kaynaktan dogrulanmis yillar
PRICED_YEARS: Tuple[int, ...] = (2024, 2025, 2026)

# --------------------------------------------------------------------------
# Sektorler
# --------------------------------------------------------------------------
SECTORS: Dict[str, Dict] = {
    "gida_icecek": {
        "nace": "C10-C11",
        "pay": 0.26,
        "mevsim_genlik": 0.22,          # yaz pikli
        "mevsim_faz": 2,                # Q3 zirve
        "trend_yillik": 0.030,
        "ihracat_egilimi": (2.0, 6.0),  # Beta(a,b) -> dusuk ihracat payi
        "ithalat_egilimi": (1.5, 8.0),
    },
    "kozmetik": {
        "nace": "C20.42",
        "pay": 0.10,
        "mevsim_genlik": 0.12,
        "mevsim_faz": 3,
        "trend_yillik": 0.045,
        "ihracat_egilimi": (2.5, 4.0),
        "ithalat_egilimi": (2.5, 5.0),
    },
    "ev_temizlik": {
        "nace": "C20.41",
        "pay": 0.09,
        "mevsim_genlik": 0.10,
        "mevsim_faz": 1,
        "trend_yillik": 0.025,
        "ihracat_egilimi": (2.0, 5.0),
        "ithalat_egilimi": (1.5, 7.0),
    },
    "elektronik": {
        "nace": "C26-C27",
        "pay": 0.09,
        "mevsim_genlik": 0.18,
        "mevsim_faz": 4,                # Q4 zirve
        "trend_yillik": 0.050,
        "ihracat_egilimi": (2.5, 3.5),
        "ithalat_egilimi": (4.0, 3.0),  # ithalat bagimliligi yuksek
    },
    "tekstil": {
        "nace": "C13-C14",
        "pay": 0.15,
        "mevsim_genlik": 0.20,
        "mevsim_faz": 4,
        "trend_yillik": -0.010,         # daralan sektor
        "ihracat_egilimi": (5.0, 2.5),  # ihracat agirlikli
        "ithalat_egilimi": (2.0, 6.0),
    },
    "otomotiv_yan_sanayi": {
        "nace": "C29.3",
        "pay": 0.12,
        "mevsim_genlik": 0.09,
        "mevsim_faz": 2,
        "trend_yillik": 0.035,
        "ihracat_egilimi": (4.5, 2.5),
        "ithalat_egilimi": (3.0, 4.0),
    },
    "ilac": {
        "nace": "C21",
        "pay": 0.09,
        "mevsim_genlik": 0.14,
        "mevsim_faz": 1,                # Q1 zirve (kis)
        "trend_yillik": 0.040,
        "ihracat_egilimi": (2.0, 5.0),
        "ithalat_egilimi": (3.0, 4.0),
    },
    "kimya_boya": {
        "nace": "C20.3",
        "pay": 0.10,
        "mevsim_genlik": 0.16,
        "mevsim_faz": 2,
        "trend_yillik": 0.028,
        "ihracat_egilimi": (3.0, 4.0),
        "ithalat_egilimi": (3.0, 4.0),
    },
}

# --------------------------------------------------------------------------
# Olcek bantlari
# --------------------------------------------------------------------------
# NOT: Bantlar calisan sayisi araliklarina dayanan OPERASYONEL segmentlerdir.
# Resmi KOBI tanimindaki ciro esikleri bu datasette KULLANILMAMISTIR.
SIZE_BANDS: Dict[str, Dict] = {
    "mikro":  {"pay": 0.34, "calisan": (1, 9),     "log_olcek_mu": 9.2,  "log_olcek_sigma": 0.55, "beyan_gurultu": 0.150},
    "kucuk":  {"pay": 0.36, "calisan": (10, 49),   "log_olcek_mu": 10.6, "log_olcek_sigma": 0.50, "beyan_gurultu": 0.115},
    "orta":   {"pay": 0.22, "calisan": (50, 249),  "log_olcek_mu": 12.0, "log_olcek_sigma": 0.45, "beyan_gurultu": 0.085},
    "buyuk":  {"pay": 0.08, "calisan": (250, 5000),"log_olcek_mu": 13.4, "log_olcek_sigma": 0.42, "beyan_gurultu": 0.062},
}

GEKAP_MATERIALS: Tuple[str, ...] = ("plastik", "kagit_karton", "cam", "metal", "kompozit", "ahsap")

PROVINCES: Tuple[str, ...] = (
    "Istanbul", "Ankara", "Izmir", "Bursa", "Kocaeli", "Konya", "Gaziantep",
    "Adana", "Antalya", "Manisa", "Kayseri", "Denizli", "Tekirdag", "Sakarya",
    "Mersin", "Balikesir", "Eskisehir", "Samsun", "Hatay", "Corum",
)
# Il paylari: sanayi yogunlasmasini kabaca yansitan sentetik agirliklar
PROVINCE_WEIGHTS: Tuple[float, ...] = (
    0.26, 0.09, 0.09, 0.08, 0.07, 0.04, 0.04,
    0.04, 0.03, 0.03, 0.03, 0.03, 0.03, 0.02,
    0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
)


@dataclass
class GeneratorConfig:
    """Ureticinin tum ayarlari. Degistirilirse dataset_version guncellenmelidir."""

    # --- Tekrar uretilebilirlik ---
    seed: int = 20260902
    dataset_version: str = DATASET_VERSION
    schema_version: str = SCHEMA_VERSION

    # --- Olcek ---
    n_firms: int = 600
    periods: List[str] = field(default_factory=lambda: list(PERIODS))

    # --- SKU / urun agaci ---
    sku_min: int = 3
    sku_max: int = 12
    # Urun agaci (BOM) kapsami: firmalarin ne kadarinin ambalaj agirlik matrisi
    # sisteme tanimlidir. Dusuk kapsam = modelin gozlem gucu dusuk.
    bom_kapsam_beta: Tuple[float, float] = (2.2, 1.6)
    # Eskimis agirlik matrisi olasiligi (hafifletme yapilmis ama matris guncellenmemis)
    eskimis_matris_orani: float = 0.18
    eskimis_matris_sapma: Tuple[float, float] = (0.06, 0.22)  # matris gercekten % kadar agir gosterir

    # --- Anomali ---
    # NOT: Asagidaki uc oran HEDEF degil, TASARIM REFERANSIDIR. Gerceklesen oranlar
    # kayit bazli kosullara bagli oldugu icin farklidir ve Quality_Checks sayfasinda
    # olculerek raporlanir. Gerceklesen tipik degerler: truth=1 ~%7,3 |
    # N10_mesru_gorunum ~%17 | N09_veri_eksikligi ~%3,8.
    anomali_prevalansi: float = 0.070        # gercek eksik beyan egilimi referansi (truth=1)
    mesru_gorunum_orani: float = 0.075       # truth=0 ama riskli GORUNEN (hard negative) referansi
    veri_eksikligi_kuyruk_orani: float = 0.045  # truth=0, ayri kuyruk referansi
    # Eksik beyan siddeti: normal gurultuyle ORTUSSUN diye genis ve alt ucu zayif
    eksik_beyan_siddeti: Tuple[float, float] = (0.05, 0.55)  # min, max oransal eksiklik
    eksik_beyan_beta: Tuple[float, float] = (1.6, 2.6)       # zayif anomaliler daha sik

    # --- Eksik veri mekanizmasi ---
    eksik_ithalat_ihracat_orani: float = 0.12
    eksik_uretim_orani: float = 0.05
    dis_dogrulama_kapsami: float = 0.18      # ERP/onceki denetim kaydi bulunma orani
    sektor_kodu_hatasi_orani: float = 0.035

    # --- Etiket gurultusu ---
    etiket_gurultusu: float = 0.03           # audit sonucunun yanlis kaydedilme olasiligi

    # --- Cikti ---
    out_dir: str = "data/output"
    excel_name: str = "GUS-DEDEKTIV_Dataset_v1.0.xlsx"

    def to_dict(self) -> dict:
        return asdict(self)


# Anomali tipleri - Katman C
# truth_anomaly_flag: 1 = gercek eksik beyan, 0 = eksik beyan YOK
ANOMALY_TYPES: Dict[str, Dict] = {
    "A01_tarihsel_dusus":        {"truth": 1, "aciklama": "Firma kendi gecmis beyan seviyesinden aciklanamayan sekilde dustu"},
    "A02_emsal_alti":            {"truth": 1, "aciklama": "Emsal grubun beklenen araliginin belirgin altinda beyan"},
    "A03_beklenen_fark":         {"truth": 1, "aciklama": "Urun agacindan beklenen tonaj ile beyan arasinda buyuk fark"},
    "A04_faaliyet_uyumsuz":      {"truth": 1, "aciklama": "Uretim artarken ambalaj beyani artmadi veya azaldi"},
    "A05_dis_ticaret_uyumsuz":   {"truth": 1, "aciklama": "Ihracat dususune ragmen ic piyasa beyani artmadi"},
    "A06_mevsimsel_kirilma":     {"truth": 1, "aciklama": "Ceyreklik beyan kalibinda aciklanamayan kirilma"},
    "A07_urun_agaci_uyumsuz":    {"truth": 1, "aciklama": "SKU ve ambalaj matrisi beyani desteklemiyor"},
    "A08_dis_kanit_uyumsuz":     {"truth": 1, "aciklama": "ERP veya onceki denetim kaydiyla celisen beyan"},
    "N09_veri_eksikligi":        {"truth": 0, "aciklama": "Kritik alanlar eksik - risk degerlendirilemiyor, ayri kuyruga gider"},
    "N10_mesru_gorunum":         {"truth": 0, "aciklama": "Mesru nedenle riskli GORUNEN kayit (ihracat, muafiyet, mevsim, gec duzeltme, yeni firma)"},
    "N00_normal":                {"truth": 0, "aciklama": "Normal kayit"},
}

# Mesru gorunum alt nedenleri (yanlis-pozitif ureteci)
LEGITIMATE_CAUSES: Tuple[str, ...] = (
    "ihracat_agirlikli_donem",
    "yasal_muafiyet_istisna",
    "gec_duzeltme_beyannamesi",
    "mevsimsel_uretim_duraklamasi",
    "yeni_firma_kisa_tarihce",
    "sektor_kodu_hatasi",
    "eskimis_ambalaj_agirlik_matrisi",
    "urun_gami_degisikligi",
)
