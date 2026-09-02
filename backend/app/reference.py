"""Domain reference data.

GEKAP tariffs follow the 2026 schedule published under the Environmental Law
circular. Packaging intensities are the ratio of packaging placed on the market
to product output for a sector, and are the anchor that the structural signals
compare a declaration against.
"""

from __future__ import annotations

from typing import TypedDict

# --------------------------------------------------------------------------- #
# Materials
# --------------------------------------------------------------------------- #


class Material(TypedDict):
    key: str
    name: str
    tariff_try_per_kg: float
    co2e_tonnes_avoided_per_tonne: float


MATERIALS: dict[str, Material] = {
    "plastic": {
        "key": "plastic",
        "name": "Plastic",
        "tariff_try_per_kg": 7.00,
        "co2e_tonnes_avoided_per_tonne": 1.90,
    },
    "paper": {
        "key": "paper",
        "name": "Paper and cardboard",
        "tariff_try_per_kg": 3.30,
        "co2e_tonnes_avoided_per_tonne": 0.90,
    },
    "glass": {
        "key": "glass",
        "name": "Glass",
        "tariff_try_per_kg": 3.30,
        "co2e_tonnes_avoided_per_tonne": 0.35,
    },
    "metal": {
        "key": "metal",
        "name": "Metal",
        "tariff_try_per_kg": 8.00,
        "co2e_tonnes_avoided_per_tonne": 3.60,
    },
    "composite": {
        "key": "composite",
        "name": "Composite",
        "tariff_try_per_kg": 8.00,
        "co2e_tonnes_avoided_per_tonne": 1.10,
    },
    "wood": {
        "key": "wood",
        "name": "Wood",
        "tariff_try_per_kg": 3.30,
        "co2e_tonnes_avoided_per_tonne": 0.45,
    },
}

MATERIAL_ORDER = ["plastic", "paper", "glass", "metal", "composite", "wood"]


# --------------------------------------------------------------------------- #
# Sectors
# --------------------------------------------------------------------------- #


class Sector(TypedDict):
    key: str
    name: str
    packaging_per_production: float
    packaging_per_import: float
    material_mix: dict[str, float]
    gtip_families: list[str]


SECTORS: dict[str, Sector] = {
    "beverage": {
        "key": "beverage",
        "name": "Beverage",
        "packaging_per_production": 0.092,
        "packaging_per_import": 0.061,
        "material_mix": {"plastic": 0.44, "glass": 0.26, "metal": 0.16, "paper": 0.10, "composite": 0.04},
        "gtip_families": ["2202", "2201", "2009"],
    },
    "food": {
        "key": "food",
        "name": "Packaged food",
        "packaging_per_production": 0.078,
        "packaging_per_import": 0.052,
        "material_mix": {"plastic": 0.38, "paper": 0.31, "metal": 0.13, "glass": 0.10, "composite": 0.08},
        "gtip_families": ["1905", "0402", "2005", "1806"],
    },
    "cosmetics": {
        "key": "cosmetics",
        "name": "Cosmetics and personal care",
        "packaging_per_production": 0.148,
        "packaging_per_import": 0.104,
        "material_mix": {"plastic": 0.58, "paper": 0.22, "glass": 0.13, "metal": 0.07},
        "gtip_families": ["3304", "3305", "3307"],
    },
    "cleaning": {
        "key": "cleaning",
        "name": "Detergent and cleaning",
        "packaging_per_production": 0.121,
        "packaging_per_import": 0.083,
        "material_mix": {"plastic": 0.64, "paper": 0.24, "metal": 0.08, "composite": 0.04},
        "gtip_families": ["3402", "3401", "3405"],
    },
    "pharma": {
        "key": "pharma",
        "name": "Pharmaceutical",
        "packaging_per_production": 0.163,
        "packaging_per_import": 0.128,
        "material_mix": {"paper": 0.42, "plastic": 0.31, "composite": 0.15, "glass": 0.12},
        "gtip_families": ["3004", "3005", "3006"],
    },
    "electronics": {
        "key": "electronics",
        "name": "Electrical and electronic",
        "packaging_per_production": 0.061,
        "packaging_per_import": 0.058,
        "material_mix": {"paper": 0.47, "plastic": 0.28, "wood": 0.15, "composite": 0.10},
        "gtip_families": ["8418", "8516", "8528", "8471"],
    },
    "textile": {
        "key": "textile",
        "name": "Textile and apparel",
        "packaging_per_production": 0.034,
        "packaging_per_import": 0.029,
        "material_mix": {"plastic": 0.51, "paper": 0.41, "wood": 0.08},
        "gtip_families": ["6109", "6203", "6302"],
    },
    "chemicals": {
        "key": "chemicals",
        "name": "Chemical and industrial",
        "packaging_per_production": 0.047,
        "packaging_per_import": 0.041,
        "material_mix": {"plastic": 0.42, "metal": 0.26, "wood": 0.19, "paper": 0.13},
        "gtip_families": ["3208", "2710", "3814"],
    },
    "agriculture": {
        "key": "agriculture",
        "name": "Agriculture and fresh produce",
        "packaging_per_production": 0.055,
        "packaging_per_import": 0.038,
        "material_mix": {"paper": 0.39, "plastic": 0.34, "wood": 0.27},
        "gtip_families": ["0805", "0702", "0806"],
    },
    "construction": {
        "key": "construction",
        "name": "Construction materials",
        "packaging_per_production": 0.021,
        "packaging_per_import": 0.018,
        "material_mix": {"paper": 0.44, "plastic": 0.32, "wood": 0.24},
        "gtip_families": ["6810", "2523", "7005"],
    },
}

SECTOR_ORDER = list(SECTORS.keys())


# --------------------------------------------------------------------------- #
# Geography and size
# --------------------------------------------------------------------------- #

REGIONS = [
    "Antalya",
    "İstanbul",
    "İzmir",
    "Bursa",
    "Kocaeli",
    "Ankara",
    "Konya",
    "Gaziantep",
    "Adana",
    "Mersin",
    "Denizli",
    "Manisa",
    "Kayseri",
    "Tekirdağ",
    "Samsun",
]

COMPANY_SIZES = ["MICRO", "SMALL", "MEDIUM", "LARGE"]

SIZE_PRODUCTION_RANGE: dict[str, tuple[float, float]] = {
    "MICRO": (90.0, 460.0),
    "SMALL": (460.0, 2_400.0),
    "MEDIUM": (2_400.0, 11_000.0),
    "LARGE": (11_000.0, 62_000.0),
}


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
        "summary": "Declared packaging against the volume the company's own output and imports imply.",
        "inputs": ["Production volume", "Import volume", "Sector coefficients"],
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
        "summary": "Packaging implied by declared GTIP lines against the packaging reported.",
        "inputs": ["GTIP customs lines", "Packaging coefficients"],
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
    {"key": "gtip", "name": "GTIP customs lines", "weight": 0.18},
    {"key": "field", "name": "Field inspection records", "weight": 0.12},
    {"key": "registry", "name": "Registry match", "weight": 0.08},
]


# --------------------------------------------------------------------------- #
# Climate and social conversion factors
# --------------------------------------------------------------------------- #

RECOVERY_CAPTURE_RATE = 0.72
"""Share of newly identified tonnage that realistically reaches formal recovery."""

SOCIAL_FUND_SHARE = 0.12
"""Share of recovered GEKAP revenue earmarked for collector formalisation."""

COLLECTOR_ANNUAL_COST_TRY = 342_000.0
"""Cost of formalising one collector for a year, insurance included."""

INSURED_DAYS_PER_COLLECTOR = 248


def material_mix_for(sector_key: str) -> dict[str, float]:
    return SECTORS[sector_key]["material_mix"]


def gekap_value_try(tonnes: float, sector_key: str) -> float:
    """Value a packaging tonnage at the 2026 tariff, using the sector mix."""
    mix = material_mix_for(sector_key)
    return sum(
        tonnes * share * 1000.0 * MATERIALS[material]["tariff_try_per_kg"]
        for material, share in mix.items()
    )


def co2e_avoided_tonnes(tonnes: float, sector_key: str) -> float:
    mix = material_mix_for(sector_key)
    return sum(
        tonnes * share * MATERIALS[material]["co2e_tonnes_avoided_per_tonne"]
        for material, share in mix.items()
    )


def material_split(tonnes: float, sector_key: str) -> dict[str, float]:
    mix = material_mix_for(sector_key)
    return {material: tonnes * share for material, share in mix.items()}
