from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

PERIOD_PATTERN = r"^\d{4}Q[1-4]$"

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


class BandIn(BaseModel):
    level: str = Field(max_length=12)
    lower: int = Field(ge=0, le=100)
    upper: int = Field(ge=0, le=100)


class WeightIn(BaseModel):
    code: str = Field(max_length=4)
    # Accepted and ignored: the name comes from the signal catalogue, so a
    # client that echoes PolicyOut back keeps working.
    name: str | None = None
    weight: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    enabled: bool = True


class PolicyUpdate(BaseModel):
    """A change to the scoring policy. Anything left out keeps its value.

    Weights are merged by signal code, so one weight can be changed on its own.
    Bands depend on each other and are replaced as a set of all four. Field
    limits are checked here; how the bands and weights fit together is checked
    by `ScoringPolicy`, and a policy that fails either is refused before it is
    stored or put into service.
    """

    bands: list[BandIn] | None = Field(default=None, max_length=4)
    weights: list[WeightIn] | None = Field(default=None, max_length=8)
    min_coverage_for_confidence: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    strongest_signal_share: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)


class ScoringRunRequest(BaseModel):
    period: str | None = Field(default=None, pattern=PERIOD_PATTERN)
    engine: str | None = Field(default=None, max_length=16)
    company_ids: list[int] | None = Field(default=None, max_length=10_000)


class ScoringRunOut(PlainModel):
    period: str
    engine: str
    model_version: str
    companies_scored: int
    duration_ms: int
    level_counts: dict[str, int]
    ran_at: datetime
