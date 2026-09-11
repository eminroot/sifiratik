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
    # Null where the tariff is set per unit rather than per kilogram, which is
    # the case for wood. A tonnage cannot be turned into a liability there, and
    # the interface says so instead of showing a rate that does not exist.
    tariff_try_per_kg: float | None
    tariff_basis: str
    tariff_source_id: str | None = None
    co2e_tonnes_avoided_per_tonne: float
    # The same factor with the assumption that does not carry to Turkey taken
    # out. For paper that is forest carbon, which is most of the headline.
    co2e_conservative_per_tonne: float
    co2e_factor_id: str
    co2e_geography: str


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
