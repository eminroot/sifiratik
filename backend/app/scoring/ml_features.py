"""Turning a ScoringContext into the feature row the model was trained on.

The model was fitted on a firm-quarter panel with its own column names and its
own definitions. This module restates those definitions against the records
this service holds. Every function here has a counterpart in the model
repository's `gus_generator.features`; where a definition differs, it is
because the source data differs, and the difference is written down next to it.

Two rules run through the whole module:

1. **A field that is not held is not invented.** It stays `None`, the model
   sees a missing value, and the signals that depend on it report themselves
   unavailable with a reason. Filling it with a sector average would turn "we
   never received this" into "we checked and it was normal".

2. **Nothing looks forward.** Lags, expanding statistics and the peer cohort
   all come from periods strictly before the one being scored.
"""

from __future__ import annotations

import math
import statistics
from typing import Iterable, Sequence

from app.scoring.base import PeriodFacts, ScoringContext

# The model's sectors are the eight the training panel was built from. The
# service carries ten, of which two have no counterpart: `construction` and
# whatever is added later. Those are passed through as an unknown level rather
# than forced into the nearest label — the model handles an unseen category as
# missing, which is the honest reading, and the conformal step falls back from
# (sector, size) to size alone for the interval.
SECTOR_TO_MODEL: dict[str, str] = {
    "beverage": "gida_icecek",
    "food": "gida_icecek",
    "agriculture": "gida_icecek",
    "cosmetics": "kozmetik",
    "cleaning": "ev_temizlik",
    "pharma": "ilac",
    "electronics": "elektronik",
    "textile": "tekstil",
    "chemicals": "kimya_boya",
}

SIZE_TO_MODEL: dict[str, str] = {
    "MICRO": "mikro",
    "SMALL": "kucuk",
    "MEDIUM": "orta",
    "LARGE": "buyuk",
}

# The training panel names materials in Turkish; declarations name them in
# English. Composition features are computed on the shared six.
MATERIAL_TO_MODEL: dict[str, str] = {
    "plastic": "plastik",
    "paper": "kagit_karton",
    "glass": "cam",
    "metal": "metal",
    "composite": "kompozit",
    "wood": "ahsap",
}

MODEL_MATERIALS = ("plastik", "kagit_karton", "cam", "metal", "kompozit", "ahsap")

MIN_PEER_MEMBERS = 5
MIN_HISTORY_PERIODS = 3
MIN_BOM_COVERAGE = 0.05


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    if abs(denominator) < 1e-9:
        return None
    return numerator / denominator


def _change(current: float | None, earlier: float | None) -> float | None:
    """Relative movement, or None when either end is missing."""
    if current is None or not earlier:
        return None
    return (current - earlier) / earlier


def _median(values: Sequence[float], minimum: int) -> float | None:
    return statistics.median(values) if len(values) >= minimum else None


def _stdev(values: Sequence[float], minimum: int) -> float | None:
    return statistics.stdev(values) if len(values) >= minimum else None


def _quantile(values: Sequence[float], share: float, minimum: int) -> float | None:
    """Linear-interpolation quantile, matching the training panel's definition."""
    if len(values) < minimum:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = share * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _quarter_of(period: str) -> int | None:
    try:
        return int(period[5:])
    except (ValueError, IndexError):
        return None


def _at(history: Sequence[PeriodFacts], lag: int) -> PeriodFacts | None:
    """The period `lag` steps before the current one."""
    index = len(history) - 1 - lag
    return history[index] if 0 <= index < len(history) else None


def _intensity(period: PeriodFacts) -> float | None:
    """Declared packaging per tonne of production alone.

    The rule engine's `PeriodFacts.intensity` divides by production plus
    imports. The model was trained on the production-only ratio, so this is a
    separate function rather than a reuse of that property.
    """
    return _ratio(period.declared_tonnage, period.production_volume)


def _domestic_supply(period: PeriodFacts) -> float | None:
    """Volume placed on the domestic market.

    The training panel subtracts returns as well. Returned goods are not held
    here, so this figure is that much higher for the same company. It shifts
    the level, not the direction, and S5 compares the ratio against the same
    company's own history, where the same omission applies on both sides.
    """
    if period.production_volume is None or period.import_volume is None:
        return None
    return period.production_volume + period.import_volume - (period.export_volume or 0.0)


def _mix(period: PeriodFacts) -> dict[str, float] | None:
    breakdown = period.material_breakdown
    if not breakdown:
        return None
    converted = {
        MATERIAL_TO_MODEL[key]: float(value)
        for key, value in breakdown.items()
        if key in MATERIAL_TO_MODEL and value is not None
    }
    total = sum(converted.values())
    if total <= 0:
        return None
    return {material: converted.get(material, 0.0) / total for material in MODEL_MATERIALS}


# --------------------------------------------------------------------------- #
# The feature row
# --------------------------------------------------------------------------- #


def build_features(context: ScoringContext) -> dict[str, float | str | None]:
    """One firm-quarter row in the model's own vocabulary."""
    current = context.current
    prior = list(context.prior)
    history = list(context.history)

    declared = current.declared_tonnage
    production = current.production_volume
    row: dict[str, float | str | None] = {
        "declared_packaging_tonnage": declared,
        "production_qty": production,
        "sector": SECTOR_TO_MODEL.get(context.company.sector),
        "size_band": SIZE_TO_MODEL.get(context.company.company_size),
    }

    _add_history(row, history, prior, declared, production)
    _add_peers(row, context)
    _add_product_tree(row, context)
    _add_activity(row, history, current)
    _add_trade(row, history, current, declared)
    _add_seasonality(row, history, current)
    _add_composition(row, history, current)
    _add_external(row, context, declared)
    _add_quality(row, context)

    row["f_active_signal_count"] = sum(
        1 for code in range(1, 9) if row.get(f"f_avail_s{code}")
    )
    return row


def _add_history(
    row: dict,
    history: Sequence[PeriodFacts],
    prior: Sequence[PeriodFacts],
    declared: float | None,
    production: float | None,
) -> None:
    for lag in (1, 2, 3, 4):
        earlier = _at(history, lag)
        row[f"f_s1_decl_lag{lag}"] = earlier.declared_tonnage if earlier else None

    row["f_s1_decl_qoq"] = _change(declared, row.get("f_s1_decl_lag1"))
    row["f_s1_decl_yoy"] = _change(declared, row.get("f_s1_decl_lag4"))

    past = [p.declared_tonnage for p in prior if p.declared_tonnage is not None]
    row["f_s1_hist_median"] = _median(past, 2)
    row["f_s1_hist_std"] = _stdev(past, 3)
    row["f_s1_hist_p10"] = _quantile(past, 0.10, 3)
    row["f_s1_history_len"] = float(len(past))

    ratio = _ratio(declared, production)
    row["f_ratio_decl_per_prod"] = ratio
    past_ratios = [r for r in (_intensity(p) for p in prior) if r is not None]
    row["f_s1_ratio_hist_median"] = _median(past_ratios, 2)
    row["f_s1_ratio_hist_std"] = _stdev(past_ratios, 3)

    row["f_avail_s1"] = float(len(past) >= MIN_HISTORY_PERIODS)


def _add_peers(row: dict, context: ScoringContext) -> None:
    cohort = context.peers_prior
    # The cohort size that matters is the number of peers with a usable
    # production-based ratio, which is what the model's peer statistic was
    # computed from - not the number of companies in the sector.
    members = cohort.members_per_production if cohort else 0
    row["f_s2_peer_median_prev"] = cohort.median_per_production if cohort else None
    row["f_s2_peer_p10_prev"] = cohort.p10_per_production if cohort else None
    row["f_s2_peer_iqr_prev"] = cohort.iqr_per_production if cohort else None
    row["f_s2_peer_n_prev"] = float(members)
    row["f_avail_s2"] = float(
        members >= MIN_PEER_MEMBERS and (cohort.median_per_production if cohort else None) is not None
    )


def _add_product_tree(row: dict, context: ScoringContext) -> None:
    """The customs lines stand in for the packaging bill of materials.

    Each line carries the packaging it implies; `gtip_coverage` says how much
    of the company's range those lines account for, and the model scales the
    expectation back up by it. A company with no lines has no product-tree
    expectation at all, which is different from one whose lines imply zero.
    """
    lines = [
        line for line in context.gtip_lines if line.period == context.period
    ]
    coverage = context.company.gtip_coverage
    implied = (
        sum(line.quantity_tonnes * line.packaging_coefficient for line in lines)
        if lines
        else None
    )
    row["f_s3_bom_expected"] = implied
    row["f_s3_bom_coverage"] = coverage
    row["f_avail_s3"] = float(implied is not None)
    row["f_avail_s7"] = float(coverage is not None and coverage > MIN_BOM_COVERAGE)


def _add_activity(row: dict, history: Sequence[PeriodFacts], current: PeriodFacts) -> None:
    for lag in (1, 4):
        earlier = _at(history, lag)
        row[f"f_s4_prod_lag{lag}"] = earlier.production_volume if earlier else None

    row["f_s4_prod_qoq"] = _change(current.production_volume, row.get("f_s4_prod_lag1"))
    row["f_s4_prod_yoy"] = _change(current.production_volume, row.get("f_s4_prod_lag4"))

    for window in ("qoq", "yoy"):
        declaration = row.get(f"f_s1_decl_{window}")
        output = row.get(f"f_s4_prod_{window}")
        row[f"f_s4_divergence_{window}"] = (
            declaration - output if declaration is not None and output is not None else None
        )
    row["f_avail_s4"] = float(row.get("f_s4_prod_qoq") is not None)


def _add_trade(
    row: dict,
    history: Sequence[PeriodFacts],
    current: PeriodFacts,
    declared: float | None,
) -> None:
    gross = (current.production_volume or 0.0) + (current.import_volume or 0.0)
    row["f_s5_export_share"] = _ratio(current.export_volume, gross)
    row["f_s5_import_share"] = _ratio(current.import_volume, gross)
    # Returned goods are not held by this service.
    row["f_s5_return_share"] = None
    row["f_s5_correction_qty"] = None
    row["f_s5_exempt_share"] = None
    # No exemption register is wired in; the flag is a fact, not an estimate,
    # so it is reported as "none recorded" rather than left unknown.
    row["f_s5_exemption_flag"] = 0.0
    row["f_s5_trade_data_missing"] = float(current.import_volume is None)

    domestic = _domestic_supply(current)
    row["f_s5_domestic_derived"] = domestic
    row["f_s5_decl_per_domestic"] = _ratio(declared, domestic)

    previous = _at(history, 1)
    previous_gross = (
        (previous.production_volume or 0.0) + (previous.import_volume or 0.0)
        if previous
        else 0.0
    )
    previous_share = _ratio(previous.export_volume, previous_gross) if previous else None
    row["f_s5_export_share_lag1"] = previous_share
    row["f_s5_export_share_delta"] = (
        row["f_s5_export_share"] - previous_share
        if row["f_s5_export_share"] is not None and previous_share is not None
        else None
    )

    past_dpd = [
        value
        for value in (
            _ratio(p.declared_tonnage, _domestic_supply(p)) for p in history[:-1]
        )
        if value is not None
    ]
    row["f_s5_dpd_hist_median"] = _median(past_dpd, 2)
    row["f_s5_dpd_hist_std"] = _stdev(past_dpd, 3)
    row["f_s5_dpd_vs_hist"] = _ratio(
        row["f_s5_decl_per_domestic"], row["f_s5_dpd_hist_median"]
    )
    row["f_avail_s5"] = float(
        current.import_volume is not None and current.export_volume is not None
    )


def _add_seasonality(
    row: dict, history: Sequence[PeriodFacts], current: PeriodFacts
) -> None:
    quarter = _quarter_of(current.period)
    row["f_s6_quarter"] = float(quarter) if quarter else None

    same_quarter = [
        value
        for value in (
            _intensity(p)
            for p in history[:-1]
            if _quarter_of(p.period) == quarter
        )
        if value is not None
    ]
    mean = statistics.fmean(same_quarter) if same_quarter else None
    row["f_s6_own_quarter_mean_prev"] = mean
    ratio = row.get("f_ratio_decl_per_prod")
    row["f_s6_seasonal_resid"] = (
        (ratio - mean) / mean if ratio is not None and mean else None
    )
    row["f_avail_s6"] = float(mean is not None)


def _add_composition(
    row: dict, history: Sequence[PeriodFacts], current: PeriodFacts
) -> None:
    """Movement in the reported material mix.

    The training panel also carries the age of the packaging weight matrix.
    No such register is wired in here, so the age is unknown and the "stale
    matrix" flag is off rather than guessed — a guess would change the signal
    for every company at once.
    """
    row["f_s7_matrix_age_years"] = None
    row["f_s7_matrix_stale_flag"] = 0.0

    now = _mix(current)
    previous_period = _at(history, 1)
    before = _mix(previous_period) if previous_period else None
    row["f_s7_mix_shift_l1"] = (
        sum(abs(now[material] - before[material]) for material in MODEL_MATERIALS)
        if now and before
        else None
    )


def _add_external(row: dict, context: ScoringContext, declared: float | None) -> None:
    """Field inspection records for this period stand as external evidence."""
    observations = [o for o in context.observations if o.period == context.period]
    latest = max(observations, key=lambda o: o.observed_at) if observations else None
    evidence = latest.observed_packaging_tonnage if latest else None

    row["f_s8_external_available"] = float(evidence is not None)
    row["f_s8_external_gap_abs"] = (
        evidence - declared if evidence is not None and declared is not None else None
    )
    row["f_s8_external_gap_rel"] = (
        _ratio(evidence - declared, evidence)
        if evidence is not None and declared is not None
        else None
    )
    row["f_avail_s8"] = row["f_s8_external_available"]


def _add_quality(row: dict, context: ScoringContext) -> None:
    quality = context.quality
    # The training panel holds the quality score on 0-1; this service holds the
    # same quantity on 0-100.
    score = quality.score / 100.0
    missing = len(quality.missing_fields)

    row["f_data_quality_score"] = score
    row["f_data_freshness_days"] = float(quality.freshness_days)
    row["f_missing_field_count"] = float(missing)
    row["f_data_confidence_level"] = confidence_level(score, missing)
    # No incorporation date is held, so firm age is genuinely unknown.
    row["f_firm_age_years"] = None


def confidence_level(score: float, missing_fields: int) -> str:
    """The training panel's own banding, restated on its 0-1 scale."""
    if score >= 0.72 and missing_fields <= 1:
        return "yuksek"
    if score >= 0.45 and missing_fields <= 3:
        return "orta"
    return "dusuk"


def build_many(contexts: Iterable[ScoringContext]) -> list[dict]:
    return [build_features(context) for context in contexts]


__all__ = [
    "build_features",
    "build_many",
    "confidence_level",
    "SECTOR_TO_MODEL",
    "SIZE_TO_MODEL",
    "MATERIAL_TO_MODEL",
]
