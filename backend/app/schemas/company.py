from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ApiModel
from app.schemas.scoring import ScoreOut


class MainReason(BaseModel):
    code: str
    name: str
    contribution: float
    explanation: str


class QueueItem(BaseModel):
    """One row of the inspection queue."""

    rank: int
    company_id: int
    company_name: str
    tax_identifier: str
    sector: str
    sector_label: str
    region: str
    company_size: str
    priority_score: float
    priority_level: str
    main_reason: MainReason | None
    declared_tonnage: float | None
    expected_median: float
    shortfall_tonnage: float
    estimated_gekap_gap_try: float
    data_quality_score: float
    confidence: str
    active_signals: int
    unavailable_signals: int
    review_status: str
    registry_status: str


class CompanyProfile(ApiModel):
    id: int
    company_name: str
    tax_identifier: str
    sector: str
    sector_label: str
    region: str
    company_size: str
    registry_status: str
    last_data_update: datetime
    created_at: datetime


class PeriodRow(BaseModel):
    period: str
    declared_tonnage: float | None
    production_volume: float | None
    import_volume: float | None
    export_volume: float | None
    expected_lower: float | None = None
    expected_median: float | None = None
    expected_upper: float | None = None
    priority_score: float | None = None
    priority_level: str | None = None
    position: str | None = None


class DataQualityOut(BaseModel):
    score: float
    fields: dict[str, str]
    field_labels: dict[str, str]
    missing_fields: list[str]
    freshness_days: int
    last_update: datetime


class PeerContext(BaseModel):
    sector: str
    company_size: str
    member_count: int
    company_intensity_kg_per_tonne: float | None
    median_intensity_kg_per_tonne: float | None


class ObservationOut(ApiModel):
    period: str
    observed_packaging_tonnage: float
    observation: str
    inspector: str
    observed_at: datetime


class GtipLineOut(ApiModel):
    period: str
    gtip_code: str
    description: str
    quantity_tonnes: float
    packaging_coefficient: float


class CompanyDetail(BaseModel):
    company: CompanyProfile
    score: ScoreOut | None
    quality: DataQualityOut
    peers: PeerContext
    review_status: str
    current_period: PeriodRow | None
    material_breakdown: dict[str, float] | None
    observations: list[ObservationOut]
    gtip_lines: list[GtipLineOut]
    rank: int | None
    total_ranked: int


class CompanyHistory(BaseModel):
    company: CompanyProfile
    periods: list[PeriodRow]
    observations: list[ObservationOut]
    decisions: list["HistoryDecision"]


class HistoryDecision(BaseModel):
    decision_id: str | None
    action: str
    previous_status: str | None
    new_status: str | None
    user_id: str
    notes: str | None
    created_at: datetime


CompanyHistory.model_rebuild()
