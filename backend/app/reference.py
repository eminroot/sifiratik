"""Domain reference data.

Nothing in this module is typed in by hand. Every tariff, factor and
coefficient is read from `app/reference_data/`, which is delivered by the
model repository:

    gekap_rates.csv       2024-2026 GEKAP tariffs, cited to the Official Gazette
    climate_factors.csv   EPA WARM v16 factors, with their assumptions and
                          their stated uncertainty
    source_registry.csv   19 sources, each with a URL and an access date
    macro_anchors.csv     national waste-stream anchors
    sector_profile.csv    packaging intensity and material mix, *measured* on
                          the training window of the panel rather than assumed
    labels.json           display names, which are labels and not data

Regenerate with, from the model repository:

    python src/export_reference.py --out ../../backend/app/reference_data

Two things this file will not do, because the source data does not support
them:

* **Wood is not priced by tonnage.** The 2026 tariff for wood packaging is
  set per unit, not per kilogram, so a tonnage cannot be converted to a
  liability. `gekap_value_try` prices the rest and reports the share it had
  to leave out, rather than inventing a per-kilogram rate.
* **Avoided CO2e is a scenario, never a measurement.** The factors are US
  specific and carry the WARM label verbatim. Paper is reported twice —
  once as published and once excluding forest carbon, which is roughly 97%
  of its figure and is specific to US forestry.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

DATA_DIR = Path(__file__).resolve().parent / "reference_data"

TARIFF_YEAR = 2026


class ReferenceDataMissing(RuntimeError):
    """The delivered reference package is absent or incomplete."""


def _rows(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        raise ReferenceDataMissing(
            f"{name} is missing from {DATA_DIR}. Regenerate the reference package "
            "with `python src/export_reference.py` in the model repository."
        )
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def _decimal(value: str | None) -> float | None:
    """Parse a Turkish-formatted decimal, where the comma is the separator."""
    if value is None:
        return None
    text = value.strip().replace(".", "").replace(",", ".") if "," in value else value.strip()
    if not text or text in {"-", "TO_BE_FILLED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _labels() -> dict:
    path = DATA_DIR / "labels.json"
    if not path.exists():
        raise ReferenceDataMissing(f"labels.json is missing from {DATA_DIR}.")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Materials
# --------------------------------------------------------------------------- #

# Which tariff line prices a tonne of each material. Only the per-kilogram
# lines can value a tonnage; the wood line is per unit and is deliberately
# absent from this map.
_TARIFF_CATEGORY = {
    "plastik": ("PLASTIK AMBALAJ", "Digerleri (Poset Haric)"),
    "kagit_karton": ("KAGIT KARTON AMBALAJ", "Kagit-Karton Ambalaj"),
    "cam": ("CAM AMBALAJ", "Digerleri"),
    "metal": ("METAL AMBALAJ", "Digerleri"),
    "kompozit": ("KOMPOZIT AMBALAJ", "Digerleri"),
}

# The WARM factor that stands for each material, and the conservative variant
# where the published one leans on an assumption that may not carry to Turkey.
_FACTOR_ID = {
    "plastik": "CF-001",
    "metal": "CF-004",
    "cam": "CF-006",
    "kagit_karton": "CF-007",
    "kompozit": "CF-009",
    "ahsap": "CF-010",
}
_CONSERVATIVE_FACTOR_ID = {"kagit_karton": "CF-008"}


class Material(TypedDict):
    key: str
    name: str
    name_tr: str
    tariff_try_per_kg: float | None
    tariff_basis: str
    tariff_source_id: str | None
    co2e_tonnes_avoided_per_tonne: float
    co2e_conservative_per_tonne: float
    co2e_factor_id: str
    co2e_factor_year: str
    co2e_geography: str
    co2e_uncertainty: str
    co2e_label: str


@lru_cache(maxsize=1)
def _materials() -> dict[str, Material]:
    rates = _rows("gekap_rates.csv")
    factors = {row["factor_id"]: row for row in _rows("climate_factors.csv")}
    labels = _labels()

    tariffs: dict[tuple[str, str], dict] = {}
    for row in rates:
        if int(row["yil"]) != TARIFF_YEAR or row["birim"] != "kg":
            continue
        tariffs[(row["ana_kategori"], row["alt_kategori"])] = row

    out: dict[str, Material] = {}
    for key in labels["material_order"]:
        category = _TARIFF_CATEGORY.get(key)
        tariff_row = tariffs.get(category) if category else None
        factor = factors[_FACTOR_ID[key]]
        conservative = factors.get(_CONSERVATIVE_FACTOR_ID.get(key, ""), factor)

        # WARM publishes avoided emissions as negative numbers. The interface
        # talks about how much is avoided, so the sign is flipped once, here.
        published = -(_decimal(factor["faktor_deger_metrik_ton"]) or 0.0)
        floor = -(_decimal(conservative["faktor_deger_metrik_ton"]) or 0.0)

        out[key] = Material(
            key=key,
            name=labels["material"][key]["en"],
            name_tr=labels["material"][key]["tr"],
            tariff_try_per_kg=_decimal(tariff_row["tutar_tl"]) if tariff_row else None,
            tariff_basis="per_kg" if tariff_row else "per_unit",
            tariff_source_id=tariff_row["source_id"] if tariff_row else None,
            co2e_tonnes_avoided_per_tonne=round(published, 4),
            co2e_conservative_per_tonne=round(min(published, floor), 4),
            co2e_factor_id=factor["factor_id"],
            co2e_factor_year=factor["faktor_yili"],
            co2e_geography=factor["cografi_kapsam"],
            co2e_uncertainty=factor["belirsizlik"],
            co2e_label=factor["etiket"],
        )
    return out


MATERIALS: dict[str, Material] = _materials()
MATERIAL_ORDER: list[str] = list(_labels()["material_order"])

PRICED_MATERIALS: tuple[str, ...] = tuple(
    key for key, item in MATERIALS.items() if item["tariff_try_per_kg"] is not None
)
UNPRICED_MATERIALS: tuple[str, ...] = tuple(
    key for key in MATERIAL_ORDER if key not in PRICED_MATERIALS
)


# --------------------------------------------------------------------------- #
# Sectors
# --------------------------------------------------------------------------- #


class Sector(TypedDict):
    key: str
    name: str
    name_tr: str
    nace_code: str
    packaging_per_production: float
    packaging_per_import: float
    material_mix: dict[str, float]
    firm_count: int
    basis: str


@lru_cache(maxsize=1)
def _sectors() -> dict[str, Sector]:
    out: dict[str, Sector] = {}
    for row in _rows("sector_profile.csv"):
        key = row["sector"]
        mix = {
            material: float(row[f"mix_{material}"])
            for material in MATERIAL_ORDER
            if row.get(f"mix_{material}")
        }
        out[key] = Sector(
            key=key,
            name=row["label_en"],
            name_tr=row["label_tr"],
            nace_code=row["nace_code"],
            packaging_per_production=float(row["packaging_per_production"]),
            packaging_per_import=float(row["packaging_per_import"]),
            material_mix={m: v for m, v in mix.items() if v > 0},
            firm_count=int(row["firm_count"]),
            basis=row["generation_method"],
        )
    return out


SECTORS: dict[str, Sector] = _sectors()
SECTOR_ORDER: list[str] = list(SECTORS.keys())


# --------------------------------------------------------------------------- #
# Geography and size
# --------------------------------------------------------------------------- #

PROVINCE_LABELS: dict[str, str] = dict(_labels()["province"])


def region_label(province: str) -> str:
    """The province as it is written, from the ASCII key the panel carries."""
    return PROVINCE_LABELS.get(province, province)


COMPANY_SIZES: list[str] = list(_labels()["size_order"])
SIZE_LABELS: dict[str, dict[str, str]] = dict(_labels()["size_band"])


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #


class Source(TypedDict):
    source_id: str
    institution: str
    kind: str
    title: str
    period: str
    url: str
    accessed: str
    licence: str
    limitations: str
    verification: str


@lru_cache(maxsize=1)
def _sources() -> dict[str, Source]:
    return {
        row["source_id"]: Source(
            source_id=row["source_id"],
            institution=row["kurum"],
            kind=row["kaynak_turu"],
            title=row["baslik"],
            period=row["donem"],
            url=row["url"],
            accessed=row["erisim_tarihi"],
            licence=row["lisans_kullanim_kosulu"],
            limitations=row["sinirlamalar"],
            verification=row["dogrulama_durumu"],
        )
        for row in _rows("source_registry.csv")
    }


SOURCES: dict[str, Source] = _sources()


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #


class SignalDef(TypedDict):
    code: str
    key: str
    name: str
    summary: str
    inputs: list[str]


SIGNAL_CATALOG: list[SignalDef] = [
    {
        "code": "E1",
        "key": "HISTORICAL_SHORTFALL",
        "name": "Historical shortfall",
        "summary": "Declared packaging against the company's own established declaration behaviour.",
        "inputs": ["Declaration history", "Production volume"],
    },
    {
        "code": "E2",
        "key": "STRUCTURAL_SHORTFALL",
        "name": "Structural shortfall",
        "summary": "Declared packaging against the volume the company placed on the domestic market.",
        "inputs": ["Production volume", "Import volume", "Export volume"],
    },
    {
        "code": "E3",
        "key": "PEER_DEVIATION",
        "name": "Peer deviation",
        "summary": "Packaging intensity against comparable companies in the same sector and size class.",
        "inputs": ["Peer cohort", "Production volume"],
    },
    {
        "code": "E4",
        "key": "PRODUCTION_MISMATCH",
        "name": "Production and declaration mismatch",
        "summary": "Movement in output compared with movement in the declared amount.",
        "inputs": ["Production volume", "Import volume", "Declaration history"],
    },
    {
        "code": "E5",
        "key": "TEMPORAL_INCONSISTENCY",
        "name": "Temporal inconsistency",
        "summary": "Stability of the declared packaging intensity across reporting periods.",
        "inputs": ["Declaration history"],
    },
    {
        "code": "E6",
        "key": "NUMERICAL_PATTERN",
        "name": "Reporting pattern",
        # Deliberately broader than either engine's own wording. The rule
        # engine reads rounding and repetition in the amounts; the model reads
        # how the reported material composition moves between periods. Both
        # ask the same question — whether the reported figures are internally
        # consistent — and the label has to be true of whichever one ran.
        "summary": "Internal consistency of the reported figures themselves, in how "
        "they are composed and how they move between periods.",
        "inputs": ["Declaration history", "Material breakdown"],
    },
    {
        "code": "E7",
        "key": "FIELD_CONTRADICTION",
        "name": "Field contradiction",
        "summary": "Site observations set against what the company reported for the same period.",
        "inputs": ["Field inspection records"],
    },
    {
        "code": "E8",
        "key": "GTIP_EVIDENCE",
        "name": "Customs tariff evidence",
        "summary": "Packaging implied by the declared product tree against the packaging reported.",
        "inputs": ["Product tree", "Packaging weight matrix"],
    },
]

SIGNAL_BY_CODE = {item["code"]: item for item in SIGNAL_CATALOG}


# --------------------------------------------------------------------------- #
# Data quality
# --------------------------------------------------------------------------- #

DATA_FIELDS = [
    {"key": "production", "name": "Production volume", "weight": 0.22},
    {"key": "import", "name": "Import volume", "weight": 0.16},
    {"key": "history", "name": "Declaration history", "weight": 0.24},
    {"key": "gtip", "name": "Product tree", "weight": 0.18},
    {"key": "field", "name": "Field inspection records", "weight": 0.12},
    {"key": "registry", "name": "Registry match", "weight": 0.08},
]


# --------------------------------------------------------------------------- #
# Climate and social conversion
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _recovery_scenarios() -> dict[str, dict]:
    """The recovery rates the potential-impact chain is run at.

    All three are Turkish figures from the source registry, not assumptions
    made here. The middle one is the reported national rate; the others bound
    it. Nothing in the interface may present any of them as achieved.
    """
    wanted = {
        "geri_kazanim_orani_senaryo_alt": "low",
        "geri_kazanim_orani_senaryo_orta": "central",
        "geri_kazanim_orani_senaryo_ust": "high",
    }
    out: dict[str, dict] = {}
    for row in _rows("climate_factors.csv"):
        name = wanted.get(row["malzeme_gekap"])
        if not name:
            continue
        out[name] = {
            "rate": (_decimal(row["faktor_deger_metrik_ton"]) or 0.0) / 100.0,
            "year": row["faktor_yili"],
            "geography": row["cografi_kapsam"],
            "source_id": row["source_id"],
            "assumption": row["varsayim"],
        }
    return out


RECOVERY_SCENARIOS: dict[str, dict] = _recovery_scenarios()

RECOVERY_CAPTURE_RATE: float = RECOVERY_SCENARIOS["central"]["rate"]
"""Share of newly identified tonnage that reaches formal recovery.

The reported national recovery rate, not an assumption made here. Used only
in scenario figures, which the interface labels as scenarios.
"""

# The two figures below have no source in the registry. They are policy
# parameters, and the architecture is explicit that no claim may be made that
# additional GEKAP revenue is transferred to waste collectors: that needs a
# budget and a legal instrument. They are kept so the pilot page can show what
# a programme of a given size would cost, and the page states they are inputs
# an authority sets rather than anything measured here.
SOCIAL_FUND_SHARE = 0.12
"""Share of recovered revenue a programme would need. Policy input, unsourced."""

COLLECTOR_ANNUAL_COST_TRY = 342_000.0
"""Annual cost of formalising one collector. Policy input, unsourced."""


def material_mix_for(sector_key: str) -> dict[str, float]:
    return SECTORS[sector_key]["material_mix"]


def priced_share(sector_key: str) -> float:
    """The share of a sector's packaging that the tariff can value by weight."""
    mix = material_mix_for(sector_key)
    total = sum(mix.values()) or 1.0
    return sum(share for material, share in mix.items() if material in PRICED_MATERIALS) / total


def gekap_value_try(tonnes: float, sector_key: str) -> float:
    """Value a packaging tonnage at the current tariff, using the sector mix.

    Materials whose tariff is set per unit rather than per kilogram are left
    out: their liability cannot be derived from a weight. `priced_share` says
    how much of the sector was valued, so a caller can report the gap instead
    of quietly under-stating it.
    """
    mix = material_mix_for(sector_key)
    return sum(
        tonnes * share * 1000.0 * (MATERIALS[material]["tariff_try_per_kg"] or 0.0)
        for material, share in mix.items()
        if material in PRICED_MATERIALS
    )


def co2e_avoided_tonnes(tonnes: float, sector_key: str, conservative: bool = False) -> float:
    """Scenario CO2e for a tonnage. Never a measured reduction.

    With `conservative`, paper is valued excluding forest carbon, which is
    where roughly 97% of its published figure comes from and which is
    specific to US forestry.
    """
    field = "co2e_conservative_per_tonne" if conservative else "co2e_tonnes_avoided_per_tonne"
    mix = material_mix_for(sector_key)
    return sum(tonnes * share * MATERIALS[material][field] for material, share in mix.items())


def material_split(tonnes: float, sector_key: str) -> dict[str, float]:
    mix = material_mix_for(sector_key)
    return {material: tonnes * share for material, share in mix.items()}
