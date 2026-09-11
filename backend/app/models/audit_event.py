from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

REVIEW_STATUSES = [
    "AWAITING_REVIEW",
    "MARKED_FOR_INSPECTION",
    "UNDER_REVIEW",
    "INFORMATION_REQUESTED",
    "INSPECTION_COMPLETED",
    "NO_ACTION_REQUIRED",
]

CLOSED_STATUSES = {"INSPECTION_COMPLETED", "NO_ACTION_REQUIRED"}


class AuditReview(Base):
    """The current standing of a company in the inspection workflow."""

    __tablename__ = "audit_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    # The filing period this review is about. A review is always about a
    # declaration, and without the period a confirmed correction cannot be set
    # against the shortfall that prompted the inspection.
    period: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(28), default="AWAITING_REVIEW", index=True)
    auditor_id: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    # Recorded when an inspection closes with a corrected tonnage.
    confirmed_additional_tonnage: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="reviews")


class AuditEvent(Base):
    """An append-only record of every decision taken in the platform.

    Each row carries the hash of the row before it, so altering or removing a
    historical decision breaks the chain from that point forward and the
    verification endpoint reports exactly where.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[str] = mapped_column(String(60), index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(28), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(28), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    previous_hash: Mapped[str] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ChainAnchor(Base):
    """Where the chain is supposed to end.

    Linking each event to the one before it catches an edit or a deletion in
    the middle of the log: the next link stops matching. It cannot catch a cut
    at the end, because what is left is a shorter chain that still agrees with
    itself. This row holds the sequence number and digest the log should end
    on, so a truncation shows up as a mismatch rather than as a clean bill.

    It lives in the same database as the log it guards, so it raises the cost
    of tampering rather than removing it. Production keeps the anchor outside
    the database — WORM storage or the institution's own log infrastructure.
    """

    __tablename__ = "audit_chain_anchor"

    # One row, always. The fixed id makes that an invariant the database
    # enforces rather than something the code has to remember.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_sequence: Mapped[int] = mapped_column(Integer, default=0)
    head_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime)
