from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiModel(BaseModel):
    # `model_version` is a domain field here, not a pydantic namespace clash.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class PlainModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Option(BaseModel):
    value: str
    label: str
    count: int | None = None


class ReferenceData(BaseModel):
    """Everything the interface needs to build its filters and labels.

    Served rather than hard coded on the client so that adding a sector or
    renaming a level is a backend change only.
    """

    period: str
    periods: list[str]
    sectors: list[Option]
    regions: list[Option]
    company_sizes: list[Option]
    priority_levels: list[Option]
    review_statuses: list[Option]
    data_fields: list[Option]
    materials: list[Option]
