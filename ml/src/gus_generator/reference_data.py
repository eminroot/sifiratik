"""Katman A - gercek acik verilerin yuklenmesi.

Bu modulun urettigi hicbir sayi sentetik DEGILDIR. Tum degerler
`data/reference/*.csv` icindeki, kaynagi ve erisim tarihi kayitli
resmi/acik verilerden gelir.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

import pandas as pd

REF_DIR_DEFAULT = os.path.join("data", "reference")

_SEP = ";"


def _tr_float(value) -> Optional[float]:
    """Turkce ondalik ayraci (virgul) iceren metni float'a cevirir.

    Bos, '-', 'TO_BE_FILLED' gibi degerler icin None doner.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s in {"-", "nan", "None", "TO_BE_FILLED"}:
        return None
    s = s.replace(".", "") if s.count(",") == 1 and s.count(".") > 1 else s
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


class ReferenceData:
    """Butun Katman A tablolarini tek nesnede tutar."""

    def __init__(self, ref_dir: str = REF_DIR_DEFAULT):
        self.ref_dir = ref_dir
        self.sources = self._read("source_registry.csv")
        self.gekap_rates = self._read("gekap_rates.csv")
        self.macro_anchors = self._read("macro_anchors.csv")
        self.climate_factors = self._read("climate_factors.csv")
        self.pack_specs = self._read("packaging_weight_ranges.csv")

        self._prepare_rates()
        self._prepare_pack_specs()
        self._prepare_climate()

    # ------------------------------------------------------------------
    def _read(self, name: str) -> pd.DataFrame:
        path = os.path.join(self.ref_dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Referans dosyasi bulunamadi: {path}. "
                "Depoyu kok dizinden calistirdiginizdan emin olun."
            )
        return pd.read_csv(path, sep=_SEP, dtype=str, keep_default_na=False)

    # ------------------------------------------------------------------
    def _prepare_rates(self) -> None:
        df = self.gekap_rates.copy()
        df["yil"] = df["yil"].astype(int)
        df["tutar_tl_num"] = df["tutar_tl"].map(_tr_float)
        self.gekap_rates = df

        # Agirlik (kg) bazli tarifeler: modelde tonaj -> TL cevriminde kullanilir.
        kg = df[df["birim"] == "kg"].copy()
        mapping = {
            "PLASTIK AMBALAJ": "plastik",
            "METAL AMBALAJ": "metal",
            "KOMPOZIT AMBALAJ": "kompozit",
            "KAGIT KARTON AMBALAJ": "kagit_karton",
            "CAM AMBALAJ": "cam",
        }
        kg["material"] = kg["ana_kategori"].map(mapping)
        kg = kg[kg["material"].notna()]
        # yil -> material -> TL/kg
        self.rate_kg: Dict[int, Dict[str, float]] = {}
        for yil, grp in kg.groupby("yil"):
            self.rate_kg[int(yil)] = dict(zip(grp["material"], grp["tutar_tl_num"]))

        # Ahsap ADET bazlidir; kg tarifesi YOKTUR. Bilincli olarak ayri tutulur.
        ahsap = df[(df["ana_kategori"] == "AHSAP AMBALAJ") & (df["birim"] == "adet")]
        self.rate_ahsap_adet: Dict[int, float] = {
            int(r.yil): r.tutar_tl_num for r in ahsap.itertuples()
        }

    # ------------------------------------------------------------------
    def _prepare_pack_specs(self) -> None:
        df = self.pack_specs.copy()
        for col in ("birim_agirlik_p10_g", "birim_agirlik_p50_g", "birim_agirlik_p90_g"):
            df[col] = df[col].map(_tr_float)
        self.pack_specs = df

    # ------------------------------------------------------------------
    def _prepare_climate(self) -> None:
        df = self.climate_factors.copy()
        df["faktor_metrik_ton_num"] = df["faktor_deger_metrik_ton"].map(_tr_float)
        self.climate_factors = df
        # GEKAP malzemesi -> ana senaryo faktoru (MTCO2E / metrik ton, negatif = azaltim)
        main = {
            "plastik": "CF-001",
            "metal": "CF-004",
            "cam": "CF-006",
            "kagit_karton": "CF-007",
            "kompozit": "CF-009",
            "ahsap": "CF-010",
        }
        idx = df.set_index("factor_id")
        self.co2e_factor_main: Dict[str, float] = {
            mat: float(idx.loc[fid, "faktor_metrik_ton_num"]) for mat, fid in main.items()
        }
        # Muhafazakar alt senaryo (kagit-kartonda orman karbonu haric)
        cons = dict(main)
        cons["kagit_karton"] = "CF-008"
        cons["metal"] = "CF-004"
        cons["plastik"] = "CF-002"
        self.co2e_factor_conservative: Dict[str, float] = {
            mat: float(idx.loc[fid, "faktor_metrik_ton_num"]) for mat, fid in cons.items()
        }

    # ------------------------------------------------------------------
    def gekap_tl_per_ton(self, year: int, material: str) -> Optional[float]:
        """Belirtilen yil ve malzeme icin TL/ton tarifesi.

        Tarifesi birincil/ikincil kaynaktan DOGRULANMAMIS yillar (2023) icin
        None doner. Bu bilincli bir tasarim tercihidir: dogrulanmamis tarife
        UYDURULMAZ.
        """
        if year not in self.rate_kg:
            return None
        tl_per_kg = self.rate_kg[year].get(material)
        if tl_per_kg is None:
            return None
        return tl_per_kg * 1000.0

    def material_share_anchor(self) -> Dict[str, float]:
        """SRC-005 (2023) beyan edilen ambalaj atigi malzeme paylari.

        UYARI: Bu paylar ATIK BEYAN evrenine aittir; piyasaya surulen ambalaj
        evreninin paylari degildir. Datasette yalnizca gercekcilik testinde
        REFERANS olarak kullanilir, uretim hedefi olarak DAYATILMAZ.
        """
        m = self.macro_anchors
        rows = m[(m["donem"] == "2023") & (m["gosterge"].str.contains("Beyan edilen ambalaj atigi"))]
        vals = {}
        total = None
        for r in rows.itertuples():
            v = _tr_float(r.deger)
            if v is None:
                continue
            g = r.gosterge
            if "TOPLAM" in g:
                total = v
            elif "Kagit Karton" in g:
                vals["kagit_karton"] = v
            elif "Plastik" in g:
                vals["plastik"] = v
            elif "Ahsap" in g:
                vals["ahsap"] = v
            elif "Metal" in g:
                vals["metal"] = v
            elif "Kompozit" in g:
                vals["kompozit"] = v
            elif "Cam" in g:
                vals["cam"] = v
        if not total:
            total = sum(vals.values())
        return {k: v / total for k, v in vals.items()}
