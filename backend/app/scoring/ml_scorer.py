"""The trained model, in service.

Drop the artefacts into `backend/models/` and set `SCORING_ENGINE=ml`. The API
contract, the stored results and the frontend all stay as they are: this engine
returns the same `ScoreOutcome` the rule engine returns, filled from a
different calculation.

    models/quantile_hist_q05.txt   own-history quantile head
    models/quantile_hist_q50.txt
    models/quantile_hist_q95.txt
    models/quantile_peer_q05.txt   peer-and-output quantile head
    models/quantile_peer_q50.txt
    models/quantile_peer_q95.txt
    models/risk_model*.txt         the signal fusion ensemble
    models/conformal.json          Mondrian CQR widening per (sector, size)
    models/signals.json            per-signal scale learned on the training window
    models/calibration.json        blend weight, isotonic fit, score map
    models/manifest.json           version, feature order, categories, metrics

`ml_runtime` reads them and `ml_features` fills the row; this module is only
the join between that and the scoring contract.

Three rules the implementation keeps:

1. A feature the model was trained on but which this service does not hold is
   left missing. It is never imputed to a neutral value and scored as though
   it had been observed, and the signals that needed it report themselves
   unavailable with the reason.

2. The conformal interval widens for groups with thin calibration data. A
   narrow interval on a poorly evidenced company is the failure mode that
   would send auditors to the wrong door.

3. A signal switched off in the active policy is switched off in the model
   too: its inputs are masked before the fusion runs, so the score does not
   quietly keep using evidence the operator withdrew.

The eight checks the interface names are the eight the model carries, under
their own codes. The mapping is `SIGNAL_SOURCE` below.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import ScoringPolicy
from app.reference import SIGNAL_CATALOG, gekap_value_try
from app.scoring.base import (
    POSITION_ABOVE,
    POSITION_BELOW,
    POSITION_WITHIN,
    STATUS_ACTIVE,
    STATUS_CLEAR,
    STATUS_DISABLED,
    STATUS_UNAVAILABLE,
    EngineInfo,
    ScoreOutcome,
    ScoringContext,
    ScoringEngine,
    SignalOutcome,
)
from app.scoring.ml_features import build_features
from app.scoring.ml_runtime import (
    ArtifactError,
    MLRuntime,
    Prediction,
    SignalReading,
    lgb,
)

ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "models"

REQUIRED_ARTIFACTS = (
    "quantile_hist_q05.txt",
    "quantile_hist_q50.txt",
    "quantile_hist_q95.txt",
    "quantile_peer_q05.txt",
    "quantile_peer_q50.txt",
    "quantile_peer_q95.txt",
    "risk_model.txt",
    "conformal.json",
    "signals.json",
    "calibration.json",
    "manifest.json",
)

# Which of the model's signals answers each of the interface's eight checks.
# Seven line up exactly. E6 is the loosest fit: the rule engine reads rounding
# and repetition in the amounts, while the model reads how the reported
# material composition moves between periods. Both ask whether the reported
# figures are internally consistent, which is why E6 is named for the question
# rather than for either method, and the explanation says which one ran.
SIGNAL_SOURCE: dict[str, str] = {
    "E1": "S1",  # against the company's own history
    "E2": "S5",  # against the volume placed on the domestic market
    "E3": "S2",  # against the peer cohort
    "E4": "S4",  # against the movement in output
    "E5": "S6",  # against its own seasonal pattern
    "E6": "S7",  # against the reported material composition
    "E7": "S8",  # against field inspection records
    "E8": "S3",  # against the packaging the customs lines imply
}

SIGNAL_NAMES: dict[str, str] = {
    "E1": "Historical shortfall",
    "E2": "Structural shortfall",
    "E3": "Peer deviation",
    "E4": "Production and declaration mismatch",
    "E5": "Temporal inconsistency",
    "E6": "Reporting pattern",
    "E7": "Field contradiction",
    "E8": "Customs tariff evidence",
}

UNAVAILABLE_REASONS: dict[str, str] = {
    "E1": (
        "Fewer than three earlier periods carry both a declared amount and an "
        "output figure, so the company has no baseline of its own."
    ),
    "E2": (
        "Import or export volume is missing for this period, so the volume "
        "placed on the domestic market cannot be derived."
    ),
    "E3": (
        "Fewer than five comparable companies filed in the previous period, so "
        "there is no cohort to measure against."
    ),
    "E4": "No earlier output figure, so movement in production cannot be compared.",
    "E5": (
        "This quarter has not been reported before, so there is no seasonal "
        "pattern to compare against."
    ),
    "E6": (
        "The material breakdown is missing in this period or the one before, so "
        "the composition cannot be compared."
    ),
    "E7": "No field inspection record covers this period.",
    "E8": "No customs lines are on file for this period, so no packaging is implied.",
}

ACTIVE_THRESHOLD = 22.0


class EngineNotReady(RuntimeError):
    """Raised when an engine is selected before it can serve."""


def _tonnes(value: float | None) -> str:
    if value is None:
        return "no figure"
    return f"{value:,.0f} t" if abs(value) >= 100 else f"{value:,.1f} t"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


ABSENCE_RAISED_PRIORITY = (
    " Files where this check cannot be run have more often held a confirmed "
    "shortfall, so its absence raised the priority here rather than lowering it."
)


def _share_out_contributions(
    outcomes: list[SignalOutcome], readings: dict[str, SignalReading]
) -> None:
    """Turn SHAP values into the percentages the panel shows.

    Only the evidence that pushed the file *up* the queue takes a share: the
    question this panel answers is what put the file in front of the auditor.
    Evidence that pulled the score down is real, but it explains why the file
    ranks where it does, not why it was raised.

    A check that could **not** run still takes a share when its absence is what
    raised the score. The model learns that from the data — a company with no
    product tree on file is more often the one with a shortfall — and an
    auditor has to be able to see that this is why the file is here. Hiding it
    would leave a file ranked high with a blank panel, and would quietly
    reintroduce the rule the whole system exists to reject: that missing data
    reads as nothing to find.

    A file whose every signal pulled downwards has nothing to share out, and
    every contribution is zero rather than an invented split of nothing.
    """
    positive = {
        outcome.code: max(0.0, readings[SIGNAL_SOURCE[outcome.code]].contribution)
        for outcome in outcomes
        if outcome.status != STATUS_DISABLED and outcome.code in SIGNAL_SOURCE
    }
    total = sum(positive.values())
    for outcome in outcomes:
        if total <= 0 or outcome.code not in positive:
            outcome.contribution = 0.0
            continue
        outcome.contribution = round(positive[outcome.code] / total * 100.0, 1)
        if (
            outcome.status == STATUS_UNAVAILABLE
            and outcome.contribution > 0
            and outcome.missing_data_reason
            and ABSENCE_RAISED_PRIORITY not in outcome.missing_data_reason
        ):
            outcome.missing_data_reason += ABSENCE_RAISED_PRIORITY


class MLScoringEngine(ScoringEngine):
    name = "ml"

    _runtime: MLRuntime | None = None
    _runtime_key: tuple[str, float] | None = None

    def __init__(self, policy: ScoringPolicy) -> None:
        self.policy = policy
        self.manifest = self._read_manifest()
        self.version = self.manifest.get("version", "ml-unreleased")

    # ----------------------------------------------------------------- meta --

    @staticmethod
    def _read_manifest() -> dict:
        manifest = ARTIFACT_DIR / "manifest.json"
        if not manifest.exists():
            return {}
        try:
            return json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def missing_artifacts(self) -> list[str]:
        """What stops this engine serving, named so the reason is reportable.

        The runtime dependency is listed alongside the files. `resolve_engine`
        decides on readiness before a request is served, so a deployment
        without lightgbm has to fall back to the rule engine there rather than
        fail once scoring is already under way.
        """
        missing = [name for name in REQUIRED_ARTIFACTS if not (ARTIFACT_DIR / name).exists()]
        if lgb is None:
            missing.append("lightgbm (not installed)")
        return missing

    @property
    def ready(self) -> bool:
        return not self.missing_artifacts()

    def describe(self) -> EngineInfo:
        missing = self.missing_artifacts()
        metrics = self.manifest.get("metrics", {}) or {}
        test = metrics.get("test", {}) or {}
        conformal = metrics.get("konformal", {}) or {}

        notes: list[str]
        if missing:
            notes = [
                "lightgbm is not installed, so the model cannot run."
                if lgb is None
                else "The trained model has not been delivered yet.",
                "The rule engine remains in service.",
                "Switching to it changes no part of the interface: the result carries "
                "the same fields, and each one still names the evidence behind it.",
            ]
        else:
            notes = [
                f"Trained {self.manifest.get('trained_at', 'date not recorded')} on "
                f"dataset {self.manifest.get('data_version', 'unrecorded')}.",
                "Measured on a held-out later period, never on the data it was fitted to.",
            ]
            if test.get("Precision@100") is not None:
                low, high = (test.get("Precision@100_CI") or [None, None])[:2]
                span = f" (95% CI {low}-{high})" if low is not None else ""
                notes.append(
                    f"Of the 100 highest ranked files, {test['Precision@100']:.0%} held "
                    f"a confirmed shortfall{span}, against a base rate of "
                    f"{test.get('prevalans', 0):.1%}."
                )
            if conformal.get("gozlenen_test") is not None:
                notes.append(
                    f"The expected range is calibrated for "
                    f"{conformal.get('hedef_kapsama', 0.9):.0%} coverage and held "
                    f"{conformal['gozlenen_test']:.1%} on the held-out period."
                )
            notes.append(
                "Trained on synthetic data. These figures are not evidence of "
                "performance on real declarations."
            )

        return EngineInfo(
            name=self.name,
            version=self.version,
            kind="Quantile regression with signal fusion",
            ready=not missing,
            description=(
                "Two gradient boosted quantile models — one on the company's own "
                "filing history, one on its peers and output — blended and calibrated "
                "so the expected range holds its stated coverage within each sector "
                "and size group. Eight evidence signals are then combined by a second "
                "model, and each result reports how much every signal contributed."
            ),
            produces_interval=(
                "A conformal prediction interval around the expected declaration, "
                "widened per sector and size group and for companies whose group has "
                "thin calibration data."
            ),
            notes=notes,
        )

    # -------------------------------------------------------------- runtime --

    def _load_runtime(self) -> MLRuntime:
        """Load once per process, and reload when the artefacts change.

        The boosters are immutable and take a moment to parse, so they are held
        on the class. The key is the manifest's version and its modification
        time, which means dropping a new model in is picked up without a
        restart but an unchanged one is never re-read.
        """
        manifest_path = ARTIFACT_DIR / "manifest.json"
        key = (str(self.manifest.get("version", "")), manifest_path.stat().st_mtime)
        if MLScoringEngine._runtime is None or MLScoringEngine._runtime_key != key:
            MLScoringEngine._runtime = MLRuntime.load(ARTIFACT_DIR)
            MLScoringEngine._runtime_key = key
        return MLScoringEngine._runtime

    def _disabled_codes(self) -> list[str]:
        return [
            SIGNAL_SOURCE[item["code"]]
            for item in SIGNAL_CATALOG
            if self.policy.weight_for(item["code"]) <= 0 and item["code"] in SIGNAL_SOURCE
        ]

    # ---------------------------------------------------------------- score --

    def score(self, context: ScoringContext) -> ScoreOutcome:
        return self.score_many([context])[0]

    def score_many(self, contexts: list[ScoringContext]) -> list[ScoreOutcome]:
        missing = self.missing_artifacts()
        if missing:
            raise EngineNotReady(
                "The model engine has no artefacts to load ("
                + ", ".join(missing)
                + "). The rule engine remains in service."
            )
        if not contexts:
            return []

        try:
            runtime = self._load_runtime()
        except ArtifactError as error:
            raise EngineNotReady(str(error)) from error

        rows = [build_features(context) for context in contexts]
        predictions = runtime.predict(rows, disabled=self._disabled_codes())
        return [
            self._outcome(context, row, prediction)
            for context, row, prediction in zip(contexts, rows, predictions)
        ]

    def _outcome(
        self, context: ScoringContext, row: dict, prediction: Prediction
    ) -> ScoreOutcome:
        declared = context.current.declared_tonnage
        declared_value = declared if declared is not None else 0.0

        lower, median, upper = prediction.lower, prediction.median, prediction.upper
        if declared is None or declared_value < lower:
            position = POSITION_BELOW
        elif declared_value > upper:
            position = POSITION_ABOVE
        else:
            position = POSITION_WITHIN

        # Measured against the bottom of the interval, not its middle, so the
        # unexplained amount is the part the calibrated range cannot account for.
        shortfall = max(0.0, lower - declared_value)
        signals = self._signals(context, row, prediction)

        covered = sum(s.weight for s in signals if s.available)
        total = sum(s.weight for s in signals) or 1.0
        coverage = round(covered / total, 4)

        # Banded on the figure that is stored and shown, not on the raw one, so
        # a stored 25.00 can never carry the band of a raw 24.998.
        priority = round(prediction.priority_score, 2)

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
            estimated_gekap_gap_try=round(
                gekap_value_try(shortfall, context.company.sector), 2
            ),
            data_quality_score=context.quality.score,
            signal_coverage=coverage,
            confidence=self._confidence(coverage, context.quality.score),
            scoring_engine=self.name,
            model_version=self.version,
            policy_version=self.policy.version,
            signals=signals,
        )

    def _confidence(self, coverage: float, quality_score: float) -> str:
        if coverage < self.policy.min_coverage_for_confidence or quality_score < 45:
            return "LOW"
        if coverage >= 0.75 and quality_score >= 70:
            return "HIGH"
        return "MEDIUM"

    # -------------------------------------------------------------- signals --

    def _signals(
        self, context: ScoringContext, row: dict, prediction: Prediction
    ) -> list[SignalOutcome]:
        readings = {reading.code: reading for reading in prediction.signals}
        outcomes: list[SignalOutcome] = []

        for definition in SIGNAL_CATALOG:
            code = definition["code"]
            weight = self.policy.weight_for(code)
            source = SIGNAL_SOURCE.get(code)
            name = SIGNAL_NAMES.get(code, definition["name"])

            if weight <= 0 or source is None:
                outcomes.append(
                    SignalOutcome(
                        code=code,
                        key=definition["key"],
                        name=name,
                        status=STATUS_DISABLED,
                        available=False,
                        missing_data_reason="Signal switched off in the active policy.",
                    )
                )
                continue

            reading = readings[source]
            if not reading.available or reading.score is None:
                outcome = SignalOutcome.unavailable(
                    code,
                    definition["key"],
                    name,
                    reason=UNAVAILABLE_REASONS.get(
                        code, "The inputs this check needs are not on file."
                    ),
                )
                outcome.weight = weight
                outcomes.append(outcome)
                continue

            outcome = SignalOutcome(
                code=code,
                key=definition["key"],
                name=name,
                status=STATUS_ACTIVE if reading.score >= ACTIVE_THRESHOLD else STATUS_CLEAR,
                available=True,
                score=round(reading.score, 1),
                weight=weight,
            )
            outcome.explanation, outcome.evidence = self._describe(
                code, source, context, row, prediction, reading
            )
            outcome.evidence["model_signal"] = source
            outcome.evidence["deviation_percentile"] = round(reading.score / 100.0, 3)
            outcomes.append(outcome)

        _share_out_contributions(outcomes, readings)
        return outcomes

    def _describe(
        self,
        code: str,
        source: str,
        context: ScoringContext,
        row: dict,
        prediction: Prediction,
        reading: SignalReading,
    ) -> tuple[str, dict]:
        """One sentence and the numbers behind it.

        Written from a template rather than generated. The same inputs always
        produce the same sentence, every figure in it comes from the row that
        was scored, and there is nothing in it a reader cannot check.
        """
        declared = context.current.declared_tonnage
        fired = (reading.score or 0.0) >= ACTIVE_THRESHOLD
        # The signal's own statistic, as the model computed it: the shortfall
        # against that signal's expectation, expressed as a share of it.
        shortfall = reading.raw if reading.raw == reading.raw else None

        if code == "E1":
            expected = prediction.hist_median
            evidence = {
                "declared": declared,
                "expected_from_own_history": round(expected, 1),
                "baseline_periods": int(row.get("f_s1_history_len") or 0),
            }
            if fired:
                return (
                    f"Declared {_tonnes(declared)} where this company's own filing "
                    f"history implies {_tonnes(expected)}, "
                    f"{_pct(max(shortfall or 0.0, 0.0))} below it.",
                    evidence,
                )
            return (
                f"Declared {_tonnes(declared)} against {_tonnes(expected)} implied by "
                "its own history. No material shortfall.",
                evidence,
            )

        if code == "E2":
            domestic = row.get("f_s5_domestic_derived")
            evidence = {
                "declared": declared,
                "domestic_supply_tonnes": (
                    round(domestic, 1) if domestic is not None else None
                ),
                "ratio_vs_own_history": (
                    round(row.get("f_s5_dpd_vs_hist"), 3)
                    if row.get("f_s5_dpd_vs_hist") is not None
                    else None
                ),
            }
            if fired:
                return (
                    "Packaging declared per tonne placed on the domestic market is "
                    f"{_pct(max(shortfall or 0.0, 0.0))} below this company's own "
                    "past level.",
                    evidence,
                )
            return (
                "Packaging per tonne placed on the domestic market is in line with "
                "this company's own past level.",
                evidence,
            )

        if code == "E3":
            expected = prediction.peer_median
            cohort = context.peers_prior
            evidence = {
                "declared": declared,
                "expected_from_peers": round(expected, 1),
                "peer_count": cohort.members_per_production if cohort else 0,
            }
            if fired:
                return (
                    f"Peers of the same sector and size imply {_tonnes(expected)}; the "
                    f"declaration is {_tonnes(declared)}, "
                    f"{_pct(max(shortfall or 0.0, 0.0))} below.",
                    evidence,
                )
            return (
                f"Against a peer expectation of {_tonnes(expected)}, the declaration "
                "sits within the cohort's range.",
                evidence,
            )

        if code == "E4":
            output = row.get("f_s4_prod_yoy")
            window = "year on year"
            if output is None:
                output, window = row.get("f_s4_prod_qoq"), "against the previous period"
            movement = row.get("f_s1_decl_yoy")
            if movement is None:
                movement = row.get("f_s1_decl_qoq")
            evidence = {
                "output_change": round(output, 3) if output is not None else None,
                "declaration_change": (
                    round(movement, 3) if movement is not None else None
                ),
                "window": window,
            }
            if fired and output is not None and movement is not None:
                return (
                    f"Output moved {_pct(output)} {window} while the packaging "
                    f"declaration moved {_pct(movement)}.",
                    evidence,
                )
            return ("Output and declared volume moved together.", evidence)

        if code == "E5":
            evidence = {
                "own_quarter_mean": (
                    round(row.get("f_s6_own_quarter_mean_prev"), 5)
                    if row.get("f_s6_own_quarter_mean_prev") is not None
                    else None
                ),
                "residual": (
                    round(row.get("f_s6_seasonal_resid"), 3)
                    if row.get("f_s6_seasonal_resid") is not None
                    else None
                ),
            }
            if fired:
                return (
                    "Against this company's own pattern for this quarter the "
                    f"declaration is {_pct(max(shortfall or 0.0, 0.0))} low, which "
                    "seasonality does not explain.",
                    evidence,
                )
            return ("No break in the company's quarterly pattern.", evidence)

        if code == "E6":
            shift = row.get("f_s7_mix_shift_l1")
            evidence = {"composition_shift": round(shift, 3) if shift is not None else None}
            if fired:
                return (
                    "The reported material composition shifted by "
                    f"{shift:.2f} against the previous period without a matching "
                    "change in output.",
                    evidence,
                )
            return (
                "Material composition is consistent with the previous period.",
                evidence,
            )

        if code == "E7":
            gap = row.get("f_s8_external_gap_abs")
            observed = (
                declared + gap if gap is not None and declared is not None else None
            )
            evidence = {"declared": declared, "observed_on_site": observed}
            if fired:
                return (
                    f"A field inspection recorded {_tonnes(observed)} against a "
                    f"declaration of {_tonnes(declared)}, "
                    f"{_pct(max(shortfall or 0.0, 0.0))} below it.",
                    evidence,
                )
            return ("Field inspection records agree with the declaration.", evidence)

        if code == "E8":
            partial = row.get("f_s3_bom_expected")
            coverage = row.get("f_s3_bom_coverage")
            expected = (
                partial / coverage if partial is not None and coverage else None
            )
            evidence = {
                "declared": declared,
                "implied_by_customs_lines": (
                    round(expected, 1) if expected is not None else None
                ),
                "line_coverage": coverage,
            }
            if fired:
                return (
                    f"The customs lines imply {_tonnes(expected)} of packaging "
                    f"({_pct(coverage or 0.0)} of the range covered) against a "
                    f"declaration of {_tonnes(declared)}, "
                    f"{_pct(max(shortfall or 0.0, 0.0))} below it.",
                    evidence,
                )
            return (
                f"The declaration is in line with the {_tonnes(expected)} implied by "
                "the customs lines.",
                evidence,
            )

        return ("", {})


__all__ = ["MLScoringEngine", "EngineNotReady", "SIGNAL_SOURCE", "ARTIFACT_DIR"]
