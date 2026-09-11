from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class ReviewRequest(BaseModel):
    status: str = Field(description="One of the workflow statuses", max_length=28)
    # Recorded as given only while no API key is configured. With keys, the
    # decision is signed by the key's owner and this field is ignored.
    auditor_id: str = Field(default="aydin.m", max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    confirmed_additional_tonnage: float | None = Field(
        default=None,
        ge=0,
        le=1_000_000,
        allow_inf_nan=False,
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
    # False on a log written before anchoring existed: the links still verify,
    # but a cut at the end would not be visible. Said out loud rather than
    # reported as a clean chain.
    anchored: bool = True
