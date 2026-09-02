from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    """One registered obligor.

    Identity is tokenised: `tax_identifier` carries the panel's firm token, not
    a real VKN. The architecture requires the real identifier to stay inside
    the authority's own boundary, and nothing in this platform needs it — every
    comparison the engine makes is against the company's own history and its
    cohort, both of which the token addresses perfectly well.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(180), index=True)
    tax_identifier: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(40), index=True)
    region: Mapped[str] = mapped_column(String(40), index=True)
    company_size: Mapped[str] = mapped_column(String(12), index=True)

    # Registry attributes carried on the declaration file itself.
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    main_product_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    primary_packaging_material: Mapped[str | None] = mapped_column(String(24), nullable=True)
    operating_since: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Year the packaging weight matrix was last revised. A matrix left to age
    # is why a product tree can imply the wrong tonnage in good faith, so the
    # engine reads it rather than assuming the matrix is current.
    weight_matrix_vintage_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_maturity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

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
