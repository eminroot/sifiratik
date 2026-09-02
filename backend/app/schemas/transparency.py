from __future__ import annotations

from pydantic import BaseModel

from app.schemas.inspection import ChainStatus
from app.schemas.scoring import EngineOut, PolicyOut
from app.schemas.signal import SignalCatalogItem


class Principle(BaseModel):
    title: str
    body: str


class TariffRow(BaseModel):
    key: str
    name: str
    tariff_try_per_kg: float
    co2e_tonnes_avoided_per_tonne: float


class FieldRow(BaseModel):
    key: str
    name: str
    weight: float


class TransparencyReport(BaseModel):
    disclaimer: str
    does: list[str]
    does_not: list[str]
    principles: list[Principle]
    active_engine: str
    engines: list[EngineOut]
    policy: PolicyOut
    signals: list[SignalCatalogItem]
    data_fields: list[FieldRow]
    tariffs: list[TariffRow]
    tariff_year: int
    audit_chain: ChainStatus
