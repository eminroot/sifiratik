from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Declaration(Base):
    """One GEKAP declaration period for one company.

    Production, import, export and return volumes are units of product as the
    obligor reports them; the declared tonnage is packaging placed on the
    market, in tonnes, which is what the tariff applies to. The two are
    different units on purpose — the ratio between them is the packaging
    intensity every structural check is built on.

    Any column may be null. A missing upstream feed is a normal state, and the
    scoring engine has to report it as missing rather than read it as zero.
    """

    __tablename__ = "declarations"
    __table_args__ = (UniqueConstraint("company_id", "period", name="uq_declaration_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(8), index=True)

    declared_packaging_tonnage: Mapped[float | None] = mapped_column(Float, nullable=True)
    production_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    import_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    export_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    material_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Adjustments the obligor filed against this period, and any exemption
    # claimed. Both legitimately lower a declaration, so a check that ignored
    # them would raise findings against companies that did nothing wrong.
    correction_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    exemption_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    exempt_share: Mapped[float | None] = mapped_column(Float, nullable=True)

    # What the registered product tree implies, and how much of the company's
    # range those entries cover. The expectation is only ever as complete as
    # the coverage, so the two travel together.
    bom_expected_tonnage: Mapped[float | None] = mapped_column(Float, nullable=True)
    bom_coverage_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # The tariff liability as filed. `gekap_rate_status` says whether the
    # period could be priced at all: tariffs that could not be verified from
    # the primary text leave the amount unset rather than estimated.
    gekap_amount_try: Mapped[float | None] = mapped_column(Float, nullable=True)
    gekap_rate_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Completeness of this filing, carried on the record rather than inferred.
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_freshness_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_fields: Mapped[str | None] = mapped_column(String(400), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="declarations")


class FieldObservation(Base):
    """What an inspector recorded on site, for the periods where anyone went."""

    __tablename__ = "field_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(8), index=True)
    observed_packaging_tonnage: Mapped[float] = mapped_column(Float)
    observation: Mapped[str] = mapped_column(String(400))
    inspector: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime)

    company = relationship("Company", back_populates="observations")


class GtipLine(Base):
    """A customs tariff line with the packaging coefficient attached to it."""

    __tablename__ = "gtip_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(8), index=True)
    gtip_code: Mapped[str] = mapped_column(String(12))
    description: Mapped[str] = mapped_column(String(160))
    quantity_tonnes: Mapped[float] = mapped_column(Float)
    packaging_coefficient: Mapped[float] = mapped_column(Float)

    company = relationship("Company", back_populates="gtip_lines")
