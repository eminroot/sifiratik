from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ApiModel


class SignalOut(ApiModel):
    code: str
    key: str
    name: str
    status: str
    available: bool
    score: float | None
    weight: float
    contribution: float
    explanation: str
    missing_data_reason: str | None
    evidence: dict | None = None


class SignalCatalogItem(BaseModel):
    code: str
    key: str
    name: str
    summary: str
    inputs: list[str]
    weight: float
    enabled: bool


class SignalAvailability(BaseModel):
    """How often each signal can actually be evaluated across the population."""

    code: str
    name: str
    evaluated: int
    unavailable: int
    active: int
    availability_rate: float
    top_reason: str | None
