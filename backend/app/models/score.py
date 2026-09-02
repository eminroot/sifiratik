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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class ScoreResult(Base):
    """The output of one scoring run for one company and period.

    Results are kept rather than recomputed on read so an auditor can always
    see the figures a decision was actually taken on, together with the engine
    and policy version that produced them.
    """

    __tablename__ = "score_results"
    __table_args__ = (UniqueConstraint("company_id", "period", name="uq_score_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(8), index=True)

    priority_score: Mapped[float] = mapped_column(Float, index=True)
    priority_level: Mapped[str] = mapped_column(String(12), index=True)

    declared_tonnage: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_lower_bound: Mapped[float] = mapped_column(Float)
    expected_median: Mapped[float] = mapped_column(Float)
    expected_upper_bound: Mapped[float] = mapped_column(Float)
    position: Mapped[str] = mapped_column(String(12))  # BELOW | WITHIN | ABOVE

    shortfall_tonnage: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_gekap_gap_try: Mapped[float] = mapped_column(Float, default=0.0)

    data_quality_score: Mapped[float] = mapped_column(Float)
    signal_coverage: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(12))

    scoring_engine: Mapped[str] = mapped_column(String(24))
    model_version: Mapped[str] = mapped_column(String(32))
    policy_version: Mapped[str] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="scores")
    signals = relationship(
        "SignalResult",
        back_populates="score_result",
        cascade="all, delete-orphan",
        order_by="SignalResult.signal_code",
    )


class SignalResult(Base):
    """One of the eight independent signals, as evaluated in a scoring run.

    `available` is the field that keeps the platform honest. A signal that could
    not run carries a reason and no score, and is never read as a clean result.
    """

    __tablename__ = "signal_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score_result_id: Mapped[int] = mapped_column(
        ForeignKey("score_results.id", ondelete="CASCADE"), index=True
    )

    signal_code: Mapped[str] = mapped_column(String(4), index=True)
    signal_key: Mapped[str] = mapped_column(String(40))
    signal_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))  # ACTIVE | CLEAR | UNAVAILABLE | DISABLED
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    contribution: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    missing_data_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    score_result = relationship("ScoreResult", back_populates="signals")
