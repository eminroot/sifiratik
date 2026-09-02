from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import PlainModel
from app.schemas.company import QueueItem
from app.schemas.signal import SignalAvailability


class LevelBreakdown(BaseModel):
    level: str
    count: int
    share: float


class StatusBreakdown(BaseModel):
    status: str
    label: str
    count: int


class QualityBand(BaseModel):
    label: str
    lower: int
    upper: int
    count: int


class CoverageRow(BaseModel):
    key: str
    label: str
    available: int
    partial: int
    missing: int
    coverage: float


class Dashboard(PlainModel):
    period: str
    generated_at: datetime
    scoring_engine: str
    model_version: str
    policy_version: str

    companies_analysed: int
    by_level: list[LevelBreakdown]
    by_status: list[StatusBreakdown]
    awaiting_review: int
    reviewed: int
    in_progress: int

    additional_tonnage_identified: float
    estimated_gekap_gap_try: float
    exposure_in_top_50_try: float
    exposure_share_in_top_50: float

    average_data_quality: float
    quality_bands: list[QualityBand]
    field_coverage: list[CoverageRow]
    signal_availability: list[SignalAvailability]

    priority_queue: list[QueueItem]
    regions_covered: int
    sectors_covered: int
    companies_without_declaration: int


class CompanyQualityRow(BaseModel):
    company_id: int
    company_name: str
    sector: str
    sector_label: str
    region: str
    quality_score: float
    fields: dict[str, str]
    missing_count: int
    unavailable_signals: int
    priority_level: str
    registry_status: str


class DataQualityReport(BaseModel):
    period: str
    average_data_quality: float
    companies_analysed: int
    fully_evidenced: int
    thin_evidence: int
    quality_bands: list[QualityBand]
    field_coverage: list[CoverageRow]
    field_labels: dict[str, str]
    signal_availability: list[SignalAvailability]
    companies: list[CompanyQualityRow]
    total_companies: int
