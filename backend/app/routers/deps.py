from __future__ import annotations

from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import Company
from app.services.scoring_service import all_periods, latest_period


def known_period(db: Session, period: str) -> str:
    """`period` if the database holds filings for it, else a 404.

    Shared by the query parameter and by request bodies that name a period, so
    a period in a body cannot reach the scoring run unchecked and leave rows
    behind for a quarter that does not exist.
    """
    if period not in all_periods(db):
        raise HTTPException(status_code=404, detail=f"No records for period {period}")
    return period


def resolve_period(
    period: str | None = Query(default=None, description="Reporting period, defaults to the newest"),
    db: Session = Depends(get_db),
) -> str:
    if period is None:
        return latest_period(db)
    return known_period(db, period)


def get_company(company_id: int, db: Session = Depends(get_db)) -> Company:
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def csv_list(value: str | None) -> list[str] | None:
    """Accept both repeated params and a comma separated list."""
    if not value:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return items or None
