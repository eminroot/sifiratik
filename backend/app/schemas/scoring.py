from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ApiModel, PlainModel
from app.schemas.signal import SignalOut


class ExpectedRange(BaseModel):
    lower: float
    median: float
    upper: float
    declared: float | None
    position: str
    shortfall_tonnage: float
    estimated_gekap_gap_try: float


class ScoreOut(ApiModel):
    """The full result of one scoring run for one company.

    The shape is fixed by the scoring contract, not by the engine. Whatever
    produces it, the interface reads the same fields.
    """

    period: str
    priority_score: float
    priority_level: str
    expected: ExpectedRange
    data_quality_score: float
    signal_coverage: float
    confidence: str
    scoring_engine: str
    model_version: str
    policy_version: str
    created_at: datetime
    signals: list[SignalOut]
    active_signals: int
    unavailable_signals: int


class EngineOut(BaseModel):
    name: str
    version: str
    kind: str
    ready: bool
    active: bool
    description: str
    produces_interval: str
    notes: list[str]


class BandOut(BaseModel):
    level: str
    lower: int
    upper: int


class WeightOut(BaseModel):
    code: str
    name: str
    weight: float
    enabled: bool


class PolicyOut(BaseModel):
    version: str
    bands: list[BandOut]
    weights: list[WeightOut]
    min_coverage_for_confidence: float
    strongest_signal_share: float
    interval_base_spread: float
    interval_uncertainty_spread: float


class PolicyUpdate(BaseModel):
    bands: list[BandOut] | None = None
    weights: list[WeightOut] | None = None
    min_coverage_for_confidence: float | None = None
    strongest_signal_share: float | None = None


class ScoringRunRequest(BaseModel):
    period: str | None = None
    engine: str | None = None
    company_ids: list[int] | None = None


class ScoringRunOut(PlainModel):
    period: str
    engine: str
    model_version: str
    companies_scored: int
    duration_ms: int
    level_counts: dict[str, int]
    ran_at: datetime
