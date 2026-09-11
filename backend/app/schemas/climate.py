from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.company import QueueItem
from app.schemas.scoring import PERIOD_PATTERN

# The largest shortlist a pilot may ask for. Well above any province's
# population, and small enough that the query stays a bounded one.
MAX_SHORTLIST = 1000


class MaterialTonnage(BaseModel):
    key: str
    name: str
    tonnes: float
    # Null when this material's tariff is set per unit, so a weight cannot be
    # valued. The tonnage is still reported; only the money is withheld.
    gekap_value_try: float | None
    priced_by_weight: bool
    co2e_avoided_tonnes: float
    co2e_conservative_tonnes: float


class ChainStep(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    note: str | None = None


class SocialImpact(BaseModel):
    collectors_supported: int
    formal_transitions: int
    insured_workers: int
    insured_days: int
    municipalities: int
    funding_allocated_try: float
    funding_available_try: float
    cost_per_transition_try: float
    worker_years_funded: float
    funding_potential_try: float
    worker_years_potential: float


class ClimateImpact(BaseModel):
    period: str
    companies_analysed: int
    companies_flagged: int
    companies_inspected: int
    records_updated: int
    cities_covered: int
    sectors_covered: int

    additional_tonnage_identified: float
    additional_tonnage_confirmed: float
    tonnage_to_formal_recovery: float
    estimated_gekap_revenue_try: float
    confirmed_gekap_revenue_try: float
    co2e_avoided_tonnes: float

    by_material: list[MaterialTonnage]
    by_region: list[ChainStep]
    impact_chain: list[ChainStep]
    social: SocialImpact


class PilotStep(BaseModel):
    index: int
    key: str
    label: str
    detail: str
    value: str | None = None


class PilotFindings(BaseModel):
    companies_analysed: int
    companies_shortlisted: int
    critical: int
    high: int
    medium: int
    low: int
    additional_tonnage: float
    estimated_gekap_try: float
    co2e_avoided_tonnes: float
    recovery_potential_tonnes: float
    by_material: list[MaterialTonnage]
    signals_unavailable: int
    average_data_quality: float


class PilotConfig(BaseModel):
    name: str
    region: str
    sector: str | None
    period: str
    shortlist_size: int
    simulate_outcomes: bool


class PilotResult(BaseModel):
    config: PilotConfig
    steps: list[PilotStep]
    findings: PilotFindings
    shortlist: list[QueueItem]
    ran_at: datetime


class PilotRunRequest(BaseModel):
    region: str = Field(default="Antalya", max_length=60)
    sector: str | None = Field(default=None, max_length=40)
    shortlist_size: int = Field(default=100, ge=1, le=MAX_SHORTLIST)
    simulate_outcomes: bool = True
    period: str | None = Field(default=None, pattern=PERIOD_PATTERN)
