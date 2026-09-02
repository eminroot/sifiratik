from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(180), index=True)
    tax_identifier: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(40), index=True)
    region: Mapped[str] = mapped_column(String(40), index=True)
    company_size: Mapped[str] = mapped_column(String(12), index=True)

    # Where the record came from and how complete the upstream picture is.
    registry_status: Mapped[str] = mapped_column(String(20), default="MATCHED")
    has_production_data: Mapped[bool] = mapped_column(Boolean, default=True)
    has_import_data: Mapped[bool] = mapped_column(Boolean, default=True)
    has_gtip_data: Mapped[bool] = mapped_column(Boolean, default=True)
    has_field_data: Mapped[bool] = mapped_column(Boolean, default=False)
    gtip_coverage: Mapped[float] = mapped_column(Float, default=1.0)
    last_data_update: Mapped[datetime] = mapped_column(DateTime, default=_now)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=_now
    )

    declarations = relationship(
        "Declaration", back_populates="company", cascade="all, delete-orphan"
    )
    scores = relationship("ScoreResult", back_populates="company", cascade="all, delete-orphan")
    reviews = relationship("AuditReview", back_populates="company", cascade="all, delete-orphan")
    observations = relationship(
        "FieldObservation", back_populates="company", cascade="all, delete-orphan"
    )
    gtip_lines = relationship("GtipLine", back_populates="company", cascade="all, delete-orphan")
