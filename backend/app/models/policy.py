"""The active scoring policy, kept where every process can see it.

Thresholds and signal weights are policy, not code: an authority changes them
through the API. That only works if the change survives a restart and reaches
every worker, so the active policy lives in a row rather than in a module
global. The process keeps a cached copy for speed and writes through on change.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class PolicySnapshot(Base):
    """One row per policy version, newest wins.

    Kept as a history rather than a single mutable row: a score stores the
    policy version it was produced under, and that version has to stay
    readable afterwards or the score cannot be explained.
    """

    __tablename__ = "policy_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    changed_by: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
