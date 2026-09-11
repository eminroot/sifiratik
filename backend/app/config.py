"""Runtime settings and the tunable parts of the scoring policy.

Thresholds, signal weights and the active engine are deliberately kept out of
the scoring code so an operator can change inspection policy without a deploy,
and so the future ML engine inherits the same policy surface.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "GUS-DEDEKTIV"
    api_prefix: str = "/api"
    database_url: str = f"sqlite:///{(BASE_DIR / 'gus_dedektiv.db').as_posix()}"
    # Where the GÜS panel is read from at import time. Relative paths are
    # resolved against the repository root. The panel is only needed to
    # build the database; the service does not read it while running.
    panel_dir: str = "ml/data/output/csv"
    # The model engine when its artefacts are present; `resolve_engine`
    # falls back to the rule engine when they are not, so a checkout
    # without `backend/models/` still runs.
    scoring_engine: str = "ml"
    auto_seed: bool = True
    seed_random_state: int = 20260101
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    # The in-app assistant. Without a key the endpoint reports itself as
    # unconfigured and the interface hides the panel rather than failing.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: float = 45.0

    @property
    def assistant_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --------------------------------------------------------------------------- #
# Scoring policy
# --------------------------------------------------------------------------- #


class PriorityBand(BaseModel):
    level: str
    lower: int
    upper: int


class SignalWeight(BaseModel):
    code: str
    weight: float
    enabled: bool = True


class ScoringPolicy(BaseModel):
    """Everything an authority can tune without touching the model."""

    version: str = "policy-2026.1"
    bands: list[PriorityBand] = Field(
        default_factory=lambda: [
            PriorityBand(level="LOW", lower=0, upper=24),
            PriorityBand(level="MEDIUM", lower=25, upper=49),
            PriorityBand(level="HIGH", lower=50, upper=74),
            PriorityBand(level="CRITICAL", lower=75, upper=100),
        ]
    )
    weights: list[SignalWeight] = Field(
        default_factory=lambda: [
            SignalWeight(code="E1", weight=0.20),
            SignalWeight(code="E2", weight=0.18),
            SignalWeight(code="E3", weight=0.15),
            SignalWeight(code="E4", weight=0.14),
            SignalWeight(code="E5", weight=0.09),
            SignalWeight(code="E6", weight=0.07),
            SignalWeight(code="E7", weight=0.09),
            SignalWeight(code="E8", weight=0.08),
        ]
    )
    # Below this share of total signal weight the result is flagged as
    # thin evidence. It never lowers the score: absent data is not absolution.
    min_coverage_for_confidence: float = 0.55
    # How much of the score the single strongest finding carries, against the
    # weighted average of everything that could be evaluated. Without this a
    # company that is consistently wrong in one way scores below a company
    # that is slightly wrong in several, which is not how a team triages.
    strongest_signal_share: float = 0.35
    # Interval half-width floor and the extra width bought by poor data.
    interval_base_spread: float = 0.20
    interval_uncertainty_spread: float = 0.55

    def band_for(self, score: float) -> str:
        for band in self.bands:
            if band.lower <= score <= band.upper:
                return band.level
        return self.bands[-1].level

    def weight_for(self, code: str) -> float:
        for item in self.weights:
            if item.code == code:
                return item.weight if item.enabled else 0.0
        return 0.0

    def enabled_codes(self) -> list[str]:
        return [item.code for item in self.weights if item.enabled]


_policy = ScoringPolicy()


def get_policy() -> ScoringPolicy:
    return _policy


def set_policy(policy: ScoringPolicy) -> ScoringPolicy:
    global _policy
    _policy = policy
    return _policy


CURRENT_PERIOD = os.getenv("GUS_CURRENT_PERIOD", "2026Q2")
