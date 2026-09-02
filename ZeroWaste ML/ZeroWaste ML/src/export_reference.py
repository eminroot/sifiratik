"""Backend'e referans veri paketi teslimi.

    python src/export_reference.py --out ../../backend/app/reference_data

Backend'in ekranlarinda gorunen her sabit sayinin kaynagi buradan gelir.
Elle yazilmis tarife veya faktor birakmamak icin iki tur dosya yazilir:

KATMAN A - oldugu gibi kopyalanir (gercek, kaynakli acik veri)
    gekap_rates.csv       2024/2025/2026 GEKAP tarifeleri, Resmi Gazete atifli
    climate_factors.csv   EPA WARM v16 faktorleri + senaryo varsayimlari
    source_registry.csv   19 kaynak, dogrudan URL ve erisim tarihi
    macro_anchors.csv     TUIK/CSIDB makro capalari

TURETILMIS - panelden olculur, uydurulmaz
    sector_profile.csv    Sektor basina ambalaj yogunlugu ve malzeme karisimi

`sector_profile.csv` neden turetilir: kural motorunun yapisal beklentisi
"bu sektorde birim uretim basina ne kadar ambalaj" degerine ihtiyac duyar.
Bu deger elle yazilirsa uydurulmus olur; panelin EGITIM PENCERESINDEN
olculurse gozlenmis olur. Olcum yalnizca train bolumunden yapilir - valid ve
test disarida kalir, aksi halde kural motorunun taban cizgisi de
degerlendirme donemini gormus olurdu.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gus_generator.config import GEKAP_MATERIALS, SECTORS, SIZE_BANDS  # noqa: E402

LAYER_A_FILES = (
    "gekap_rates.csv",
    "climate_factors.csv",
    "source_registry.csv",
    "packaging_weight_ranges.csv",
    "macro_anchors.csv",
)

# Ekranda gosterilecek adlar. Bunlar VERI DEGIL ETIKETTIR; olculen hicbir
# buyuklugu degistirmezler.
SECTOR_LABELS: dict[str, dict[str, str]] = {
    "gida_icecek": {"tr": "Gıda ve içecek", "en": "Food and beverage"},
    "kozmetik": {"tr": "Kozmetik ve kişisel bakım", "en": "Cosmetics and personal care"},
    "ev_temizlik": {"tr": "Ev ve temizlik ürünleri", "en": "Household and cleaning"},
    "elektronik": {"tr": "Elektronik", "en": "Electronics"},
    "tekstil": {"tr": "Tekstil ve hazır giyim", "en": "Textile and apparel"},
    "otomotiv_yan_sanayi": {"tr": "Otomotiv yan sanayi", "en": "Automotive supply"},
    "ilac": {"tr": "İlaç", "en": "Pharmaceutical"},
    "kimya_boya": {"tr": "Kimya ve boya", "en": "Chemicals and coatings"},
}

SIZE_LABELS: dict[str, dict[str, str]] = {
    "mikro": {"tr": "Mikro", "en": "Micro"},
    "kucuk": {"tr": "Küçük", "en": "Small"},
    "orta": {"tr": "Orta", "en": "Medium"},
    "buyuk": {"tr": "Büyük", "en": "Large"},
}

MATERIAL_LABELS: dict[str, dict[str, str]] = {
    "plastik": {"tr": "Plastik", "en": "Plastic"},
    "kagit_karton": {"tr": "Kâğıt ve karton", "en": "Paper and cardboard"},
    "cam": {"tr": "Cam", "en": "Glass"},
    "metal": {"tr": "Metal", "en": "Metal"},
    "kompozit": {"tr": "Kompozit", "en": "Composite"},
    "ahsap": {"tr": "Ahşap", "en": "Wood"},
}

# Panel il adlarini ASCII tutar; ekranda dogru yazimlariyla gosterilir.
PROVINCE_LABELS: dict[str, str] = {
    "Istanbul": "İstanbul",
    "Izmir": "İzmir",
    "Tekirdag": "Tekirdağ",
    "Balikesir": "Balıkesir",
    "Corum": "Çorum",
    "Canakkale": "Çanakkale",
    "Kutahya": "Kütahya",
    "Sanliurfa": "Şanlıurfa",
    "Diyarbakir": "Diyarbakır",
    "Aydin": "Aydın",
    "Mugla": "Muğla",
    "Usak": "Uşak",
}


def sector_profile(observations: pd.DataFrame, firms: pd.DataFrame) -> pd.DataFrame:
    """Sektor basina olculen ambalaj yogunlugu ve malzeme karisimi."""
    train = observations[observations["split"] == "train"].copy()
    rows = []

    for sector in SECTORS:
        sub = train[train["sector"] == sector]
        declared = sub["declared_packaging_tonnage"].astype(float)
        production = sub["production_qty"].astype(float)
        imports = sub["import_qty"].astype(float)

        usable = production.notna() & (production > 0) & declared.notna()
        intensity = float(np.median((declared[usable] / production[usable]))) if usable.any() else np.nan

        # Ithalatin ima ettigi ambalaj yogunlugu, ithalat payi yuksek
        # firmalarda uretim yogunluguna gore ayrica olculur.
        heavy = usable & imports.notna() & (imports > 0.25 * production)
        import_intensity = (
            float(np.median(declared[heavy] / (production[heavy] + imports[heavy])))
            if heavy.sum() >= 20
            else intensity
        )

        totals = {
            material: float(sub[f"declared_ton_{material}"].astype(float).sum())
            for material in GEKAP_MATERIALS
        }
        grand = sum(totals.values())
        mix = {m: (v / grand if grand > 0 else 0.0) for m, v in totals.items()}

        rows.append({
            "sector": sector,
            "label_tr": SECTOR_LABELS[sector]["tr"],
            "label_en": SECTOR_LABELS[sector]["en"],
            "nace_code": SECTORS[sector]["nace"],
            "firm_count": int((firms["sector"] == sector).sum()),
            "observation_count": int(len(sub)),
            "packaging_per_production": round(intensity, 6),
            "packaging_per_import": round(import_intensity, 6),
            **{f"mix_{m}": round(mix[m], 6) for m in GEKAP_MATERIALS},
            "veri_sinifi": "derived",
            "generation_method": (
                "Egitim penceresi (train) medyani: beyan tonaji / uretim miktari; "
                "malzeme karisimi ayni pencerede beyan edilen tonajlarin payi"
            ),
        })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backend referans veri paketi")
    parser.add_argument("--out", default="../../backend/app/reference_data")
    parser.add_argument("--data", default="data/output/csv")
    parser.add_argument("--reference", default="data/reference")
    args = parser.parse_args()

    root = Path.cwd()
    out = (root / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    reference_dir = root / args.reference
    copied = []
    for name in LAYER_A_FILES:
        source = reference_dir / name
        if not source.exists():
            print(f"  atlandi (bulunamadi): {name}")
            continue
        shutil.copyfile(source, out / name)
        copied.append(name)

    data_dir = root / args.data
    observations = pd.read_csv(data_dir / "observations.csv", sep=";", encoding="utf-8-sig")
    firms = pd.read_csv(data_dir / "firms.csv", sep=";", encoding="utf-8-sig")

    profile = sector_profile(observations, firms)
    profile.to_csv(out / "sector_profile.csv", sep=";", index=False, encoding="utf-8-sig")

    labels = {
        "sector": SECTOR_LABELS,
        "size_band": SIZE_LABELS,
        "material": MATERIAL_LABELS,
        "province": PROVINCE_LABELS,
        "size_order": list(SIZE_BANDS.keys()),
        "material_order": list(GEKAP_MATERIALS),
    }
    (out / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = json.loads((root / "data" / "output" / "manifest.json").read_text(encoding="utf-8"))
    (out / "MANIFEST.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset_version": manifest.get("dataset_version"),
            "seed": manifest.get("seed"),
            "layer_a_files": copied,
            "derived_files": ["sector_profile.csv"],
            "labels_file": "labels.json",
            "note": (
                "Katman A dosyalari GUS-DEDEKTIV veri deposundan oldugu gibi "
                "kopyalanmistir; elle duzenlenmez. Yeniden uretmek icin: "
                "python src/export_reference.py --out <backend>/app/reference_data"
            ),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Referans paketi yazildi: {out}")
    for name in copied:
        print(f"  {name} (Katman A - oldugu gibi)")
    print("  sector_profile.csv (turetilmis)")
    print("  labels.json, MANIFEST.json")
    print()
    print(profile[["sector", "firm_count", "packaging_per_production",
                   "packaging_per_import"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
