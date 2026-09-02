from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class ReviewRequest(BaseModel):
    status: str = Field(description="One of the workflow statuses")
    auditor_id: str = Field(default="aydin.m", max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    confirmed_additional_tonnage: float | None = Field(
        default=None,
        ge=0,
        description="Recorded when an inspection closes with a corrected amount",
    )


class ReviewOut(ApiModel):
    id: int
    company_id: int
    status: str
    auditor_id: str
    notes: str | None
    decision_id: str
    confirmed_additional_tonnage: float | None
    created_at: datetime
    updated_at: datetime


class AuditEventOut(ApiModel):
    sequence: int
    company_id: int | None
    company_name: str | None = None
    user_id: str
    action: str
    previous_status: str | None
    new_status: str | None
    notes: str | None
    decision_id: str | None
    event_data: dict | None
    previous_hash: str
    current_hash: str
    created_at: datetime


class ChainStatus(BaseModel):
    intact: bool
    events_checked: int
    total_events: int
    broken_at: int | None
    reason: str | None
    head_hash: str | None
    verified_at: datetime


class QueueStats(BaseModel):
    total: int
    by_level: dict[str, int]
    by_status: dict[str, int]
