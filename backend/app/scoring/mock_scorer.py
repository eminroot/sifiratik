"""Deterministic rule engine.

This is the engine in service until the quantile model lands. It is not random:
every score traces back to a comparison an auditor could repeat by hand, and
the same inputs always produce the same output. That matters twice over, first
because a prioritisation an auditor cannot reproduce is not evidence, and
second because it gives the ML work a baseline to beat.

Each signal answers one question and reports one of three states: it fired, it
did not fire, or it could not be evaluated. The third state is never folded
into the second.
"""

from __future__ import annotations

import statistics
from collections import Counter

from app.config import ScoringPolicy
from app.reference import SIGNAL_CATALOG, gekap_value_try
from app.scoring.base import (
    POSITION_ABOVE,
    POSITION_BELOW,
    POSITION_WITHIN,
    STATUS_ACTIVE,
    STATUS_CLEAR,
    STATUS_DISABLED,
    EngineInfo,
    ScoreOutcome,
    ScoringContext,
    ScoringEngine,
    SignalOutcome,
)

MODEL_VERSION = "mock-2026.1.3"

# A signal has to clear this to be reported as firing rather than quiet.
ACTIVE_THRESHOLD = 22.0


def _ramp(value: float, low: float, high: float) -> float:
    """Map a deviation onto 0-100, flat below `low` and saturated above `high`."""
    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return (value - low) / (high - low) * 100.0


_WORD = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}


def _needs(count: int, singular: str, plural: str, needed: int, purpose: str) -> str:
    """State what is missing in the same grammar whether it is none or a few."""
    if count == 0:
        head = f"No {singular} is on file"
    elif count == 1:
        head = f"Only one {singular} is on file"
    else:
        head = f"Only {count} {plural} are on file"
    return f"{head}. {_WORD.get(needed, needed)} are needed to {purpose}."


def _tonnes(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f} t"
    return f"{value:,.1f} t"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


class MockScoringEngine(ScoringEngine):
    name = "mock"
    version = MODEL_VERSION

    def __init__(self, policy: ScoringPolicy) -> None:
        self.policy = policy

    # ----------------------------------------------------------------- meta --

    def describe(self) -> EngineInfo:
        return EngineInfo(
            name=self.name,
            version=self.version,
            kind="Rule based",
            ready=True,
            description=(
                "Eight independent comparisons against the company's own history, "
                "its output, its peer group and its customs lines."
            ),
            produces_interval="Sector coefficients adjusted by the company's own "
            "declaration behaviour, widened where inputs are incomplete.",
            notes=[
                "Deterministic: identical inputs give identical scores.",
                "A signal without inputs is reported as unavailable and carries no weight.",
                "The interval widens as data quality falls rather than narrowing on assumptions.",
            ],
        )

    # ---------------------------------------------------------------- score --

    def score(self, context: ScoringContext) -> ScoreOutcome:
        current = context.current
        declared = current.declared_tonnage
        declared_value = declared if declared is not None else 0.0

        lower, median, upper = self._expected_interval(context)

        if declared is None or declared_value < lower:
            position = POSITION_BELOW
        elif declared_value > upper:
            position = POSITION_ABOVE
        else:
            position = POSITION_WITHIN

        # Deliberately conservative: the unexplained amount is measured against
        # the bottom of the interval, not its middle.
        shortfall = max(0.0, lower - declared_value)
        gekap_gap = gekap_value_try(shortfall, context.company.sector)

        signals = self._evaluate_signals(context, median)
        priority, coverage, confidence = self._aggregate(signals, context.quality.score)

        return ScoreOutcome(
            company_id=context.company.id,
            period=context.period,
            priority_score=priority,
            priority_level=self.policy.band_for(priority),
            declared_tonnage=declared,
            expected_lower_bound=round(lower, 1),
            expected_median=round(median, 1),
            expected_upper_bound=round(upper, 1),
            position=position,
            shortfall_tonnage=round(shortfall, 1),
            estimated_gekap_gap_try=round(gekap_gap, 2),
            data_quality_score=context.quality.score,
            signal_coverage=coverage,
            confidence=confidence,
            scoring_engine=self.name,
            model_version=self.version,
            policy_version=self.policy.version,
            signals=signals,
        )

    # ------------------------------------------------------------ interval --

    def _structural_expectation(self, context: ScoringContext) -> float:
        current = context.current
        production = current.production_volume or 0.0
        imports = current.import_volume or 0.0
        return production * context.sector_coefficient + imports * context.import_coefficient

    def _expected_interval(self, context: ScoringContext) -> tuple[float, float, float]:
        """Where a comparable, consistently reporting company would land.

        The anchor is what the company's own output implies. Its own history
        then nudges the anchor, because packaging design genuinely differs
        between firms, but only within a bounded range so a company cannot
        talk the expectation down simply by under-reporting for long enough.
        """
        structural = self._structural_expectation(context)
        basis = context.current.basis or 0.0

        prior_intensities = [p.intensity for p in context.prior if p.intensity is not None]
        own_factor = 1.0
        if len(prior_intensities) >= 3 and basis > 0 and structural > 0:
            own_median = _median(prior_intensities) or 0.0
            reference_intensity = structural / basis
            if reference_intensity > 0:
                own_factor = min(1.35, max(0.75, own_median / reference_intensity))

        median = structural * own_factor
        if median <= 0:
            # No usable output figures. Fall back on the company's own volumes
            # so the interval is still anchored to something observed.
            declared_history = [p.declared_tonnage for p in context.prior if p.declared_tonnage]
            median = (_median(declared_history) or 0.0) or 0.0

        half = self.policy.interval_base_spread + self.policy.interval_uncertainty_spread * (
            1.0 - context.quality.score / 100.0
        )
        half = min(0.75, half)

        return max(0.0, median * (1 - half)), median, median * (1 + half)

    # ------------------------------------------------------------- signals --

    def _evaluate_signals(self, context: ScoringContext, expected_median: float) -> list[SignalOutcome]:
        handlers = {
            "E1": self._historical_shortfall,
            "E2": self._structural_shortfall,
            "E3": self._peer_deviation,
            "E4": self._production_mismatch,
            "E5": self._temporal_inconsistency,
            "E6": self._numerical_pattern,
            "E7": self._field_contradiction,
            "E8": self._gtip_evidence,
        }

        outcomes: list[SignalOutcome] = []
        for definition in SIGNAL_CATALOG:
            code = definition["code"]
            weight = self.policy.weight_for(code)
            if weight <= 0:
                outcomes.append(
                    SignalOutcome(
                        code=code,
                        key=definition["key"],
                        name=definition["name"],
                        status=STATUS_DISABLED,
                        available=False,
                        missing_data_reason="Signal switched off in the active policy.",
                    )
                )
                continue

            outcome = handlers[code](context, expected_median)
            outcome.weight = weight
            if outcome.available and outcome.score is not None:
                outcome.status = STATUS_ACTIVE if outcome.score >= ACTIVE_THRESHOLD else STATUS_CLEAR
            outcomes.append(outcome)

        return outcomes

    @staticmethod
    def _new(code: str) -> SignalOutcome:
        definition = next(item for item in SIGNAL_CATALOG if item["code"] == code)
        return SignalOutcome(
            code=code,
            key=definition["key"],
            name=definition["name"],
            status=STATUS_CLEAR,
            available=True,
        )

    # E1 ---------------------------------------------------------------------

    def _historical_shortfall(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E1", "HISTORICAL_SHORTFALL", "Historical shortfall")
        current = context.current
        prior_intensities = [p.intensity for p in context.prior if p.intensity is not None]

        if len(prior_intensities) < 3:
            return SignalOutcome.unavailable(
                *definition,
                reason=_needs(
                    len(prior_intensities),
                    "earlier period with both a declared amount and an output figure",
                    "earlier periods with both a declared amount and an output figure",
                    3,
                    "establish a baseline",
                ),
            )
        basis = current.basis
        if not basis:
            return SignalOutcome.unavailable(
                *definition,
                reason="No output volume for this period, so the baseline cannot be applied.",
            )

        baseline_intensity = _median(prior_intensities) or 0.0
        expected = baseline_intensity * basis
        declared = current.declared_tonnage or 0.0
        ratio = declared / expected if expected > 0 else 1.0
        gap = 1 - ratio

        outcome = self._new("E1")
        outcome.score = round(_ramp(gap, 0.06, 0.55), 1)
        outcome.evidence = {
            "declared": round(declared, 1),
            "expected_from_own_history": round(expected, 1),
            "baseline_periods": len(prior_intensities),
            "gap_ratio": round(gap, 3),
        }
        if gap > 0:
            outcome.explanation = (
                f"Declared {_tonnes(declared)} where this company's own pattern over "
                f"{len(prior_intensities)} periods implies {_tonnes(expected)}, "
                f"a shortfall of {_pct(gap)}."
            )
        else:
            outcome.explanation = (
                f"Declared {_tonnes(declared)} against {_tonnes(expected)} implied by its own "
                "recent pattern. No shortfall against its own history."
            )
        return outcome

    # E2 ---------------------------------------------------------------------

    def _structural_shortfall(self, context: ScoringContext, expected_median: float) -> SignalOutcome:
        definition = ("E2", "STRUCTURAL_SHORTFALL", "Structural shortfall")
        current = context.current

        if current.production_volume is None and current.import_volume is None:
            return SignalOutcome.unavailable(
                *definition,
                reason="Neither production nor import volume is available for this period.",
            )
        if expected_median <= 0:
            return SignalOutcome.unavailable(
                *definition, reason="Reported output is zero, so no packaging volume is implied."
            )

        declared = current.declared_tonnage
        outcome = self._new("E2")
        if declared is None:
            outcome.score = 100.0
            outcome.evidence = {
                "declared": None,
                "expected": round(expected_median, 1),
                "no_declaration": True,
            }
            outcome.explanation = (
                f"Output of {_tonnes(current.basis or 0.0)} implies roughly "
                f"{_tonnes(expected_median)} of packaging, and no declaration was filed for "
                "this period."
            )
            return outcome

        ratio = declared / expected_median
        gap = 1 - ratio
        outcome.score = round(_ramp(gap, 0.05, 0.60), 1)
        outcome.evidence = {
            "declared": round(declared, 1),
            "expected": round(expected_median, 1),
            "production": current.production_volume,
            "imports": current.import_volume,
            "gap_ratio": round(gap, 3),
        }
        if gap > 0:
            outcome.explanation = (
                f"Output of {_tonnes(current.basis or 0.0)} implies about "
                f"{_tonnes(expected_median)} of packaging. The declaration is "
                f"{_tonnes(declared)}, {_pct(gap)} below that."
            )
        else:
            outcome.explanation = (
                f"The declaration of {_tonnes(declared)} sits in line with the "
                f"{_tonnes(expected_median)} implied by reported output."
            )
        return outcome

    # E3 ---------------------------------------------------------------------

    def _peer_deviation(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E3", "PEER_DEVIATION", "Peer deviation")
        peers = context.peers
        intensity = context.current.intensity

        if peers.member_count < 5 or peers.median_intensity is None:
            return SignalOutcome.unavailable(
                *definition,
                reason=_needs(
                    peers.member_count,
                    "other company in this sector and size class",
                    "other companies in this sector and size class",
                    5,
                    "compare against the cohort",
                ),
            )
        if intensity is None:
            return SignalOutcome.unavailable(
                *definition,
                reason="Packaging intensity cannot be computed without output volume.",
            )

        ratio = intensity / peers.median_intensity
        gap = 1 - ratio
        outcome = self._new("E3")
        outcome.score = round(_ramp(gap, 0.08, 0.60), 1)
        outcome.evidence = {
            "company_intensity_kg_per_tonne": round(intensity * 1000, 2),
            "peer_median_kg_per_tonne": round(peers.median_intensity * 1000, 2),
            "peer_count": peers.member_count,
            "gap_ratio": round(gap, 3),
        }
        if gap > 0:
            outcome.explanation = (
                f"Reports {intensity * 1000:.1f} kg of packaging per tonne of output against a "
                f"median of {peers.median_intensity * 1000:.1f} kg across "
                f"{peers.member_count} comparable companies, {_pct(gap)} lower."
            )
        else:
            outcome.explanation = (
                f"Reports {intensity * 1000:.1f} kg per tonne against a peer median of "
                f"{peers.median_intensity * 1000:.1f} kg. In line with the cohort."
            )
        return outcome

    # E4 ---------------------------------------------------------------------

    def _production_mismatch(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E4", "PRODUCTION_MISMATCH", "Production and declaration mismatch")
        current = context.current
        reference = context.same_period_last_year()
        window = "year on year"

        if reference is None and len(context.prior) >= 1:
            reference = context.prior[-1]
            window = "against the previous period"

        if reference is None:
            return SignalOutcome.unavailable(
                *definition, reason="No earlier period to compare movement against."
            )
        if not reference.basis or not current.basis:
            return SignalOutcome.unavailable(
                *definition, reason="Output volume is missing in one of the two periods compared."
            )
        if not reference.declared_tonnage or current.declared_tonnage is None:
            return SignalOutcome.unavailable(
                *definition, reason="A declared amount is missing in one of the two periods compared."
            )

        output_change = current.basis / reference.basis - 1
        declared_change = current.declared_tonnage / reference.declared_tonnage - 1
        divergence = output_change - declared_change

        outcome = self._new("E4")
        # Only rising output that the declaration failed to follow is a concern.
        score = _ramp(divergence, 0.06, 0.60) if output_change > 0.04 else 0.0
        outcome.score = round(score, 1)
        outcome.evidence = {
            "reference_period": reference.period,
            "output_change": round(output_change, 3),
            "declared_change": round(declared_change, 3),
            "divergence": round(divergence, 3),
            "window": window,
        }
        if score > 0:
            outcome.explanation = (
                f"Output rose {_pct(output_change)} {window} while the declared amount moved "
                f"{_pct(declared_change)}. The two have separated by {_pct(divergence)}."
            )
        elif output_change > 0.04:
            outcome.explanation = (
                f"Output rose {_pct(output_change)} and the declaration followed at "
                f"{_pct(declared_change)}."
            )
        else:
            outcome.explanation = (
                f"Output moved {_pct(output_change)} {window}, with the declaration at "
                f"{_pct(declared_change)}. Nothing to reconcile."
            )
        return outcome

    # E5 ---------------------------------------------------------------------

    def _temporal_inconsistency(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E5", "TEMPORAL_INCONSISTENCY", "Temporal inconsistency")
        series = [p for p in context.history if p.intensity is not None]

        if len(series) < 4:
            return SignalOutcome.unavailable(
                *definition,
                reason=_needs(
                    len(series),
                    "period with both an amount and an output figure",
                    "periods with both an amount and an output figure",
                    4,
                    "judge stability",
                ),
            )

        intensities = [p.intensity for p in series]
        mean = statistics.fmean(intensities)
        spread = statistics.pstdev(intensities) / mean if mean else 0.0

        drops = [
            1 - (intensities[i] / intensities[i - 1])
            for i in range(1, len(intensities))
            if intensities[i - 1] > 0
        ]
        worst_drop = max(drops) if drops else 0.0
        worst_index = drops.index(worst_drop) + 1 if drops else 0

        outcome = self._new("E5")
        outcome.score = round(max(_ramp(spread, 0.12, 0.55), _ramp(worst_drop, 0.18, 0.60)), 1)
        outcome.evidence = {
            "periods": len(series),
            "relative_spread": round(spread, 3),
            "largest_drop": round(worst_drop, 3),
            "largest_drop_period": series[worst_index].period if drops else None,
        }
        if outcome.score >= ACTIVE_THRESHOLD:
            outcome.explanation = (
                f"Packaging intensity swings by {_pct(spread)} across {len(series)} periods, "
                f"with a single drop of {_pct(worst_drop)} at {series[worst_index].period}."
            )
        else:
            outcome.explanation = (
                f"Packaging intensity holds within {_pct(spread)} across {len(series)} periods."
            )
        return outcome

    # E6 ---------------------------------------------------------------------

    def _numerical_pattern(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E6", "NUMERICAL_PATTERN", "Numerical pattern")
        values = [p.declared_tonnage for p in context.history if p.declared_tonnage is not None]

        if len(values) < 4:
            return SignalOutcome.unavailable(
                *definition,
                reason=_needs(
                    len(values),
                    "declared amount",
                    "declared amounts",
                    4,
                    "read a pattern from the figures",
                ),
            )

        rounded = sum(1 for v in values if abs(v - round(v / 5) * 5) < 0.01)
        round_share = rounded / len(values)

        counts = Counter(round(v, 3) for v in values)
        repeated_value, repeated_count = counts.most_common(1)[0]
        repeat_share = repeated_count / len(values) if repeated_count > 1 else 0.0

        indicator = 0.55 * round_share + 0.65 * repeat_share
        outcome = self._new("E6")
        outcome.score = round(_ramp(indicator, 0.30, 0.85), 1)
        outcome.evidence = {
            "periods": len(values),
            "round_number_share": round(round_share, 2),
            "repeated_value": repeated_value if repeat_share else None,
            "repeated_count": repeated_count if repeat_share else 0,
        }

        # Thresholds sit below the level that can make the signal fire, so an
        # active result always carries the observation behind it.
        notes = []
        if round_share >= 0.35:
            notes.append(f"{rounded} of {len(values)} amounts land on an exact multiple of five")
        if repeat_share >= 0.3:
            notes.append(f"{repeated_count} periods report the identical figure of {repeated_value:g} t")
        outcome.explanation = (
            ". ".join(note[0].upper() + note[1:] for note in notes) + "."
            if notes
            else "Reported amounts vary as ordinary measurement would."
        )
        return outcome

    # E7 ---------------------------------------------------------------------

    def _field_contradiction(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E7", "FIELD_CONTRADICTION", "Field contradiction")
        if not context.observations:
            return SignalOutcome.unavailable(
                *definition,
                reason="No site visit has been recorded for this company, so there is nothing to "
                "set the declaration against.",
            )

        latest = max(context.observations, key=lambda o: o.period)
        match = next(
            (p for p in context.history if p.period == latest.period),
            None,
        )
        if match is None or match.declared_tonnage is None:
            return SignalOutcome.unavailable(
                *definition,
                reason=f"A site visit exists for {latest.period} but no declaration was filed for "
                "that period.",
            )
        if latest.observed_packaging_tonnage <= 0:
            # A visit that measured nothing cannot anchor a comparison: every
            # declaration is infinitely above zero. It is not evidence that the
            # declaration is wrong, and it is not evidence that it is right.
            return SignalOutcome.unavailable(
                *definition,
                reason=f"The {latest.period} site visit recorded no packaging, so there is no "
                "measured quantity to set the declaration against.",
            )

        ratio = match.declared_tonnage / latest.observed_packaging_tonnage
        gap = 1 - ratio
        outcome = self._new("E7")
        outcome.score = round(_ramp(gap, 0.05, 0.50), 1)
        outcome.evidence = {
            "period": latest.period,
            "observed": round(latest.observed_packaging_tonnage, 1),
            "declared": round(match.declared_tonnage, 1),
            "inspector": latest.inspector,
            "note": latest.observation,
        }
        if gap > 0:
            outcome.explanation = (
                f"The {latest.period} site visit measured {_tonnes(latest.observed_packaging_tonnage)} "
                f"against {_tonnes(match.declared_tonnage)} declared, {_pct(gap)} lower on paper. "
                f"{latest.observation}"
            )
        else:
            outcome.explanation = (
                f"The {latest.period} site visit measured "
                f"{_tonnes(latest.observed_packaging_tonnage)}, consistent with the "
                f"{_tonnes(match.declared_tonnage)} declared."
            )
        return outcome

    # E8 ---------------------------------------------------------------------

    def _gtip_evidence(self, context: ScoringContext, _: float) -> SignalOutcome:
        definition = ("E8", "GTIP_EVIDENCE", "Customs tariff evidence")
        lines = [line for line in context.gtip_lines if line.period == context.period]

        if not lines:
            return SignalOutcome.unavailable(
                *definition, reason="No customs tariff lines are matched to this company for the period."
            )
        coverage = context.company.gtip_coverage
        if coverage < 0.35:
            return SignalOutcome.unavailable(
                *definition,
                reason=f"Customs lines cover only {_pct(coverage)} of reported output, too little "
                "to imply a packaging volume.",
            )

        implied_in_scope = sum(line.quantity_tonnes * line.packaging_coefficient for line in lines)
        implied_total = implied_in_scope / coverage
        declared = context.current.declared_tonnage or 0.0
        ratio = declared / implied_total if implied_total > 0 else 1.0
        gap = 1 - ratio

        outcome = self._new("E8")
        outcome.score = round(_ramp(gap, 0.05, 0.60), 1)
        outcome.evidence = {
            "lines": len(lines),
            "coverage": round(coverage, 2),
            "implied_packaging": round(implied_total, 1),
            "declared": round(declared, 1),
            "codes": [line.gtip_code for line in lines[:6]],
        }
        if gap > 0:
            outcome.explanation = (
                f"{len(lines)} tariff lines covering {_pct(coverage)} of output imply about "
                f"{_tonnes(implied_total)} of packaging against {_tonnes(declared)} declared."
            )
        else:
            outcome.explanation = (
                f"{len(lines)} tariff lines imply about {_tonnes(implied_total)} of packaging, "
                f"consistent with the {_tonnes(declared)} declared."
            )
        return outcome

    # ----------------------------------------------------------- aggregate --

    def _aggregate(
        self, signals: list[SignalOutcome], quality: float
    ) -> tuple[float, float, str]:
        """Combine the signals that ran, over the weight that was available.

        Weight belonging to a signal that could not run is removed from the
        denominator rather than counted as a zero. A company with half its data
        missing is not half as interesting; it is simply less well evidenced,
        which is what coverage and confidence report.
        """
        enabled = [s for s in signals if s.status != STATUS_DISABLED]
        total_weight = sum(s.weight for s in enabled) or 1.0
        available = [s for s in enabled if s.available and s.score is not None]
        available_weight = sum(s.weight for s in available)

        coverage = round(available_weight / total_weight, 3)

        if not available_weight:
            for signal in signals:
                signal.contribution = 0.0
            return 0.0, coverage, "NONE"

        weighted = sum(s.weight * (s.score or 0.0) for s in available)
        weighted_mean = weighted / available_weight
        strongest = max((s.score or 0.0) for s in available)

        # A company that is consistently wrong in one way should not rank below
        # one that is slightly wrong in four, so the strongest single finding
        # keeps a fixed share of the score alongside the weighted average.
        share = self.policy.strongest_signal_share
        priority = round((1 - share) * weighted_mean + share * strongest, 1)

        for signal in signals:
            share = (signal.weight * (signal.score or 0.0)) / weighted if weighted else 0.0
            signal.contribution = round(share * 100, 1) if signal.available else 0.0

        if coverage >= self.policy.min_coverage_for_confidence and quality >= 65:
            confidence = "HIGH"
        elif coverage >= 0.4 and quality >= 45:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return priority, coverage, confidence
