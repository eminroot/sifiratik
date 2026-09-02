"""The scoring contract.

Everything downstream of this module depends on the shapes declared here and
on nothing else. The engine receives plain dataclasses, not ORM objects, so a
model can be trained, evaluated and served without importing the web layer;
and the response the API serialises is identical whichever engine produced it.

    ScoringEngine
        MockScoringEngine   deterministic rules, in use today
        MLScoringEngine     quantile model plus conformal calibration, later

Swapping the engine must never change the payload the frontend receives. If a
field only the ML engine can fill is absent, it is null and the signal that
needed it reports itself unavailable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

STATUS_ACTIVE = "ACTIVE"
STATUS_CLEAR = "CLEAR"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DISABLED = "DISABLED"

POSITION_BELOW = "BELOW"
POSITION_WITHIN = "WITHIN"
POSITION_ABOVE = "ABOVE"


@dataclass(frozen=True)
class CompanyFacts:
    id: int
    company_name: str
    tax_identifier: str
    sector: str
    region: str
    company_size: str
    registry_status: str
    gtip_coverage: float


@dataclass(frozen=True)
class PeriodFacts:
    period: str
    declared_tonnage: float | None
    production_volume: float | None
    import_volume: float | None
    export_volume: float | None
    # Tonnes per material for this period, keyed as in `reference.MATERIALS`.
    # The rule engine has no use for it; the model reads the composition to
    # see whether the reported mix moved without an explanation.
    material_breakdown: dict[str, float] | None = None

    @property
    def basis(self) -> float | None:
        """Output the packaging should scale with: production plus imports."""
        if self.production_volume is None and self.import_volume is None:
            return None
        return (self.production_volume or 0.0) + (self.import_volume or 0.0)

    @property
    def intensity(self) -> float | None:
        """Declared packaging per tonne of output."""
        basis = self.basis
        if not basis or self.declared_tonnage is None:
            return None
        return self.declared_tonnage / basis


@dataclass(frozen=True)
class ObservationFacts:
    period: str
    observed_packaging_tonnage: float
    observation: str
    inspector: str
    observed_at: datetime


@dataclass(frozen=True)
class GtipFacts:
    period: str
    gtip_code: str
    description: str
    quantity_tonnes: float
    packaging_coefficient: float


@dataclass(frozen=True)
class PeerCohort:
    sector: str
    company_size: str
    member_count: int
    median_intensity: float | None
    p25_intensity: float | None
    # Packaging per tonne of *production alone*, excluding imports. The rule
    # engine compares against output as a whole; the model was trained on the
    # production-only ratio, and feeding it a differently defined statistic
    # would move the peer expectation without anyone noticing.
    median_per_production: float | None = None
    p10_per_production: float | None = None
    iqr_per_production: float | None = None


@dataclass(frozen=True)
class DataQuality:
    score: float
    fields: dict[str, str]  # field key -> AVAILABLE | PARTIAL | MISSING
    missing_fields: list[str]
    freshness_days: int
    last_update: datetime


@dataclass(frozen=True)
class ScoringContext:
    company: CompanyFacts
    period: str
    history: list[PeriodFacts]  # ascending by period, current period last
    peers: PeerCohort
    observations: list[ObservationFacts]
    gtip_lines: list[GtipFacts]
    quality: DataQuality
    sector_coefficient: float
    import_coefficient: float
    # The cohort as it stood in the *previous* period. A company must not be
    # compared against a cohort statistic its own declaration helped set, so
    # the model's peer expectation is built from the period before.
    peers_prior: PeerCohort | None = None

    @property
    def current(self) -> PeriodFacts:
        return self.history[-1]

    @property
    def prior(self) -> list[PeriodFacts]:
        return self.history[:-1]

    def same_period_last_year(self) -> PeriodFacts | None:
        if len(self.history) < 5:
            return None
        return self.history[-5]


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #


@dataclass
class SignalOutcome:
    code: str
    key: str
    name: str
    status: str
    available: bool
    score: float | None = None
    explanation: str = ""
    missing_data_reason: str | None = None
    evidence: dict = field(default_factory=dict)
    weight: float = 0.0
    contribution: float = 0.0

    @classmethod
    def unavailable(cls, code: str, key: str, name: str, reason: str) -> SignalOutcome:
        return cls(
            code=code,
            key=key,
            name=name,
            status=STATUS_UNAVAILABLE,
            available=False,
            score=None,
            explanation="",
            missing_data_reason=reason,
        )


@dataclass
class ScoreOutcome:
    company_id: int
    period: str
    priority_score: float
    priority_level: str
    declared_tonnage: float | None
    expected_lower_bound: float
    expected_median: float
    expected_upper_bound: float
    position: str
    shortfall_tonnage: float
    estimated_gekap_gap_try: float
    data_quality_score: float
    signal_coverage: float
    confidence: str
    scoring_engine: str
    model_version: str
    policy_version: str
    signals: list[SignalOutcome]


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EngineInfo:
    name: str
    version: str
    kind: str
    ready: bool
    description: str
    produces_interval: str
    notes: list[str]


class ScoringEngine(ABC):
    """Anything that turns a context into a priority score and its reasons."""

    name: str = "base"
    version: str = "0.0.0"

    @abstractmethod
    def describe(self) -> EngineInfo:
        """What this engine is, and whether it can currently run."""

    @abstractmethod
    def score(self, context: ScoringContext) -> ScoreOutcome:
        """Evaluate one company for one period."""

    def score_many(self, contexts: list[ScoringContext]) -> list[ScoreOutcome]:
        return [self.score(context) for context in contexts]
