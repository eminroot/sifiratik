from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Declaration(Base):
    """One GEKAP declaration period for one company.

    Production, import and export volumes are tonnes of product. The declared
    tonnage is packaging placed on the market, which is what the tariff applies
    to. Any of the volume columns may be null: a missing upstream feed is a
    normal state and the scoring engine has to say so rather than assume zero.
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
    material_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
