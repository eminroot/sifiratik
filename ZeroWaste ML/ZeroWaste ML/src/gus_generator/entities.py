"""Katman B - sentetik firma ana tablosu ve urun/ambalaj matrisi.

Buradaki her satir SENTETIKTIR. Hicbir gercek firma, marka veya vergi
kimlik numarasi kullanilmamistir. `firm_id` tokenize edilmis takma kimliktir.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .config import (
    GeneratorConfig,
    SECTORS,
    SIZE_BANDS,
    PROVINCES,
    PROVINCE_WEIGHTS,
    GEKAP_MATERIALS,
)
from .reference_data import ReferenceData

_Z90 = 1.2815515655446004  # standart normalin %90 kuantili


def lognormal_params_from_quantiles(p10: float, p50: float, p90: float) -> Tuple[float, float]:
    """p10/p50/p90 araligindan log-normal (mu, sigma) parametrelerini cikarir.

    mu    = ln(p50)
    sigma = (ln(p90) - ln(p10)) / (2 * z_0.90)
    """
    mu = float(np.log(p50))
    sigma = float((np.log(p90) - np.log(p10)) / (2.0 * _Z90))
    return mu, max(sigma, 1e-3)


def build_firms(cfg: GeneratorConfig, rng: np.random.Generator) -> pd.DataFrame:
    """Sentetik firma ana tablosunu uretir."""
    n = cfg.n_firms

    sector_names = list(SECTORS.keys())
    sector_p = np.array([SECTORS[s]["pay"] for s in sector_names], dtype=float)
    sector_p = sector_p / sector_p.sum()
    sectors = rng.choice(sector_names, size=n, p=sector_p)

    band_names = list(SIZE_BANDS.keys())
    band_p = np.array([SIZE_BANDS[b]["pay"] for b in band_names], dtype=float)
    band_p = band_p / band_p.sum()
    bands = rng.choice(band_names, size=n, p=band_p)

    prov_p = np.array(PROVINCE_WEIGHTS, dtype=float)
    prov_p = prov_p / prov_p.sum()
    provinces = rng.choice(PROVINCES, size=n, p=prov_p)

    rows: List[Dict] = []
    for i in range(n):
        sec = str(sectors[i])
        band = str(bands[i])
        scfg = SECTORS[sec]
        bcfg = SIZE_BANDS[band]

        # Uretim olcegi (birim/ceyrek) - log-normal
        scale = float(np.exp(rng.normal(bcfg["log_olcek_mu"], bcfg["log_olcek_sigma"])))

        # Faaliyet baslangici: cogu eski, bir kismi yeni (kisa tarihce -> zor vaka)
        u = rng.random()
        if u < 0.06:
            operating_since = int(rng.integers(2024, 2026))   # cok yeni
        elif u < 0.16:
            operating_since = int(rng.integers(2021, 2024))
        else:
            operating_since = int(rng.integers(1985, 2021))

        export_orientation = float(rng.beta(*scfg["ihracat_egilimi"]))
        import_dependency = float(rng.beta(*scfg["ithalat_egilimi"]))

        # Veri olgunlugu: eksik veri ve BOM kapsamini surukler.
        # Buyuk firmalar sistematik olarak daha iyi veri saglar (MAR mekanizmasi).
        band_bonus = {"mikro": -0.18, "kucuk": -0.06, "orta": 0.06, "buyuk": 0.18}[band]
        data_maturity = float(np.clip(rng.beta(2.4, 2.0) + band_bonus, 0.02, 0.99))

        bom_coverage = float(np.clip(rng.beta(*cfg.bom_kapsam_beta) * (0.45 + 0.75 * data_maturity), 0.0, 1.0))

        # --- LATENT alanlar: Model_Ready'ye ASLA aktarilmaz ---
        # Beyan davranisi tipi. Ureticinin ic degiskenidir.
        p_type = rng.random()
        if p_type < 0.72:
            compliance_type = "uyumlu"
        elif p_type < 0.86:
            compliance_type = "ozensiz"          # yuksek gurultu, ama kasitli eksiklik yok
        elif p_type < 0.95:
            compliance_type = "gec_duzeltici"    # donem kaydirmali beyan
        else:
            compliance_type = "sistematik_eksik"  # kronik dusuk beyan egilimi

        # Ambalaj agirlik matrisi surumu (eskimis matris -> sistematik sapma)
        stale = rng.random() < cfg.eskimis_matris_orani
        bom_vintage = int(rng.integers(2019, 2022)) if stale else int(rng.integers(2023, 2027))

        # Sektor kodu hatasi (emsal grubu bozar -> yanlis-pozitif ureteci)
        sector_code_error = bool(rng.random() < cfg.sektor_kodu_hatasi_orani)
        reported_sector = sec
        if sector_code_error:
            others = [s for s in sector_names if s != sec]
            reported_sector = str(rng.choice(others))

        primary_material = str(rng.choice(
            GEKAP_MATERIALS,
            p=_sector_material_prior(sec),
        ))

        rows.append({
            "firm_id": f"SYN-FRM-{i + 1:06d}",
            "is_synthetic": True,
            "province": str(provinces[i]),
            "sector": reported_sector,               # BEYAN EDILEN sektor (hatali olabilir)
            "sector_true": sec,                       # gercek sektor - LATENT
            "nace_code": SECTORS[reported_sector]["nace"],
            "size_band": band,
            "employee_band": f"{bcfg['calisan'][0]}-{bcfg['calisan'][1]}",
            "operating_since": operating_since,
            "main_product_group": _sector_product_group(sec),
            "primary_packaging_material": primary_material,
            "export_orientation": round(export_orientation, 4),
            "import_dependency": round(import_dependency, 4),
            "data_maturity_score": round(data_maturity, 4),
            "bom_coverage_ratio": round(bom_coverage, 4),
            "bom_matrix_vintage_year": bom_vintage,
            "sector_code_error_flag": sector_code_error,
            "data_source_type": "synthetic",
            "generation_method": "config.SECTORS + config.SIZE_BANDS ile parametrize log-normal olcek; Beta dagilimli dis ticaret ve veri olgunlugu",
            "source_ids": "SYN-GEN-01",
            # --- LATENT (Firms sayfasinda YAYINLANMAZ) ---
            "lat_scale": scale,
            "lat_compliance_type": compliance_type,
            "lat_stale_bom": stale,
        })

    return pd.DataFrame(rows)


def _sector_material_prior(sector: str) -> np.ndarray:
    """Sektorun agirlikli ambalaj malzemesi egilimi (GEKAP_MATERIALS sirasinda)."""
    # sira: plastik, kagit_karton, cam, metal, kompozit, ahsap
    table = {
        "gida_icecek":         [0.38, 0.20, 0.14, 0.14, 0.10, 0.04],
        "kozmetik":            [0.52, 0.28, 0.14, 0.02, 0.03, 0.01],
        "ev_temizlik":         [0.62, 0.26, 0.02, 0.04, 0.04, 0.02],
        "elektronik":          [0.14, 0.58, 0.01, 0.06, 0.15, 0.06],
        "tekstil":             [0.42, 0.48, 0.01, 0.02, 0.04, 0.03],
        "otomotiv_yan_sanayi": [0.16, 0.44, 0.01, 0.20, 0.05, 0.14],
        "ilac":                [0.20, 0.48, 0.12, 0.03, 0.15, 0.02],
        "kimya_boya":          [0.34, 0.24, 0.03, 0.26, 0.03, 0.10],
    }
    p = np.array(table[sector], dtype=float)
    return p / p.sum()


def _sector_product_group(sector: str) -> str:
    return {
        "gida_icecek": "Gida ve icecek urunleri",
        "kozmetik": "Kozmetik ve kisisel bakim",
        "ev_temizlik": "Ev temizlik urunleri",
        "elektronik": "Elektrikli ve elektronik esya",
        "tekstil": "Tekstil ve hazir giyim",
        "otomotiv_yan_sanayi": "Otomotiv yan sanayi parcalari",
        "ilac": "Ilac ve tibbi urunler",
        "kimya_boya": "Kimyasal urunler ve boya",
    }[sector]


def build_product_packaging(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    firms: pd.DataFrame,
    ref: ReferenceData,
) -> pd.DataFrame:
    """Her firma icin sentetik SKU / urun agaci / ambalaj agirlik matrisi.

    ONEMLI: GTIP kodu yalnizca URUN SINIFLANDIRMA BAGLAMI saglar.
    Ambalaj agirligi GTIP kodundan TURETILMEZ; ayri bir sentetik agirlik
    matrisinden (SYN-BOM-01) dagilim olarak cekilir.
    """
    specs = ref.pack_specs
    rows: List[Dict] = []

    for f in firms.itertuples():
        sec = f.sector_true
        pool = specs[(specs["sektor"] == sec) | (specs["sektor"] == "ORTAK")]
        if pool.empty:
            pool = specs[specs["sektor"] == "ORTAK"]

        n_sku = int(rng.integers(cfg.sku_min, cfg.sku_max + 1))
        n_sku = min(n_sku, len(pool))
        chosen = pool.sample(n=n_sku, random_state=int(rng.integers(0, 2**31 - 1)))

        # SKU karisim paylari (Dirichlet -> bazi firmalar tek SKU agirlikli)
        alpha = np.full(n_sku, float(rng.uniform(0.6, 2.5)))
        shares = rng.dirichlet(alpha)

        for k, (spec, share) in enumerate(zip(chosen.itertuples(), shares)):
            mu, sigma = lognormal_params_from_quantiles(
                spec.birim_agirlik_p10_g, spec.birim_agirlik_p50_g, spec.birim_agirlik_p90_g
            )
            true_w = float(np.exp(rng.normal(mu, sigma)))

            # Sisteme KAYITLI agirlik: eskimis matriste gercekten daha agir gorunur
            if f.bom_matrix_vintage_year < 2023:
                bias = float(rng.uniform(*cfg.eskimis_matris_sapma))
                recorded_w = true_w * (1.0 + bias)
                matrix_status = "eskimis"
            else:
                recorded_w = true_w * float(np.exp(rng.normal(0.0, 0.02)))
                matrix_status = "guncel"

            rows.append({
                "sku_id": f"{f.firm_id}-SKU{k + 1:02d}",
                "firm_id": f.firm_id,
                "pack_spec_id": spec.pack_spec_id,
                "product_group": spec.urun_grubu,
                "packaging_role": spec.ambalaj_rolu,
                "gekap_material": spec.gekap_malzeme,
                "pack_format": spec.pack_format,
                "gtip6_context": spec.gtip6_baglam,
                "gtip6_description": spec.gtip6_aciklama,
                "gtip_note": "GTIP yalnizca urun siniflandirma baglamidir; ambalaj agirligi GTIP'ten turetilmemistir",
                "sku_volume_share": round(float(share), 6),
                "unit_pack_weight_g_true": round(true_w, 3),
                "unit_pack_weight_g_recorded": round(recorded_w, 3),
                "weight_matrix_status": matrix_status,
                "weight_matrix_vintage_year": int(f.bom_matrix_vintage_year),
                "weight_dist_p10_g": spec.birim_agirlik_p10_g,
                "weight_dist_p50_g": spec.birim_agirlik_p50_g,
                "weight_dist_p90_g": spec.birim_agirlik_p90_g,
                "weight_distribution": "lognormal(mu=ln(p50), sigma=(ln(p90)-ln(p10))/(2*1.2816))",
                "data_source_type": "synthetic",
                "source_ids": "SYN-BOM-01;SYN-GEN-01",
            })

    return pd.DataFrame(rows)
