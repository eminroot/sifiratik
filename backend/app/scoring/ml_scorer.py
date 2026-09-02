"""The seat the trained model will take.

Nothing outside this file needs to change when the model arrives. Drop the
artefacts into `backend/models/` and switch SCORING_ENGINE to `ml`; the API
contract, the stored results and the frontend all stay as they are.

Expected artefacts:

    models/quantile_q05.txt        LightGBM booster, 5th percentile
    models/quantile_q50.txt        LightGBM booster, median
    models/quantile_q95.txt        LightGBM booster, 95th percentile
    models/conformal.json          Mondrian residual quantiles, keyed by
                                   (sector, company_size) so the interval is
                                   calibrated per group rather than globally
    models/signals.json            Per-signal thresholds learned on the
                                   training window
    models/manifest.json           {"version": ..., "trained_at": ...,
                                   "feature_order": [...]}

Two rules the implementation has to keep:

1. A feature the model was trained on but cannot be computed for a company
   makes the signals that depend on it unavailable. It must not be imputed to
   a neutral value and scored as if it were observed.
2. The conformal interval widens for groups with thin calibration data. A
   narrow interval on a poorly evidenced company is the failure mode that
   would send auditors to the wrong door.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import ScoringPolicy
from app.scoring.base import EngineInfo, ScoreOutcome, ScoringContext, ScoringEngine

ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "models"
REQUIRED_ARTIFACTS = ("quantile_q05.txt", "quantile_q50.txt", "quantile_q95.txt", "conformal.json")


class EngineNotReady(RuntimeError):
    """Raised when an engine is selected before it can serve."""


class MLScoringEngine(ScoringEngine):
    name = "ml"

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
        return [name for name in REQUIRED_ARTIFACTS if not (ARTIFACT_DIR / name).exists()]

    @property
    def ready(self) -> bool:
        return not self.missing_artifacts()

    def describe(self) -> EngineInfo:
        missing = self.missing_artifacts()
        return EngineInfo(
            name=self.name,
            version=self.version,
            kind="Quantile regression",
            ready=not missing,
            description=(
                "Gradient boosted quantile models over production, import, sector and "
                "history features, with a conformal step that calibrates the interval "
                "separately for each sector and size group."
            ),
            produces_interval="q05, q50 and q95 predictions, widened by the conformal "
            "residual for the company's own group.",
            notes=(
                [
                    "The trained model has not been delivered yet, so the rule engine "
                    "remains in service.",
                    "Switching to it changes no part of the interface: the result carries "
                    "the same fields, and each one still names the evidence behind it.",
                ]
                if missing
                else [f"Trained {self.manifest.get('trained_at', 'date not recorded')}."]
            ),
        )

    # ---------------------------------------------------------------- score --

    def score(self, context: ScoringContext) -> ScoreOutcome:
        missing = self.missing_artifacts()
        if missing:
            raise EngineNotReady(
                "The model engine has no artefacts to load ("
                + ", ".join(missing)
                + "). The rule engine remains in service."
            )

        # Integration point. The implementation returns a ScoreOutcome built
        # exactly as MockScoringEngine.score does, with the interval taken from
        # the quantile models and each signal keeping its availability flag.
        raise EngineNotReady(
            "Artefacts are present but the inference path has not been wired in yet."
        )
