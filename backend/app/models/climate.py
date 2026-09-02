from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class PilotRun(Base):
    """One execution of a scoped pilot: a region, a sector, a ranked shortlist."""

    __tablename__ = "pilot_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(40))
    sector: Mapped[str | None] = mapped_column(String(40), nullable=True)
    period: Mapped[str] = mapped_column(String(8))
    shortlist_size: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(16), default="COMPLETED")
    companies_analysed: Mapped[int] = mapped_column(Integer, default=0)
    companies_shortlisted: Mapped[int] = mapped_column(Integer, default=0)
    simulate_outcomes: Mapped[bool] = mapped_column(default=False)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CollectorProgram(Base):
    """Formalisation ledger for waste collectors, by municipality and period."""

    __tablename__ = "collector_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipality: Mapped[str] = mapped_column(String(60), index=True)
    region: Mapped[str] = mapped_column(String(40), index=True)
    period: Mapped[str] = mapped_column(String(8), index=True)
    collectors_supported: Mapped[int] = mapped_column(Integer, default=0)
    formal_transitions: Mapped[int] = mapped_column(Integer, default=0)
    insured_workers: Mapped[int] = mapped_column(Integer, default=0)
    insured_days: Mapped[int] = mapped_column(Integer, default=0)
    funding_allocated_try: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
