from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import Company
from app.routers.deps import csv_list, get_company, resolve_period
from app.schemas.common import Page
from app.schemas.company import CompanyDetail, CompanyHistory, QueueItem
from app.schemas.signal import SignalOut
from app.services import company_service
from app.services.company_service import QueueFilters

router = APIRouter(tags=["companies"])


def _filters(
    period: str,
    level: str | None,
    sector: str | None,
    region: str | None,
    size: str | None,
    status: str | None,
    quality: str | None,
    search: str | None,
    sort: str,
    direction: str,
) -> QueueFilters:
    return QueueFilters(
        period=period,
        levels=csv_list(level),
        sectors=csv_list(sector),
        regions=csv_list(region),
        sizes=csv_list(size),
        statuses=csv_list(status),
        quality=quality,
        search=search,
        sort=sort,
        direction=direction,
    )


@router.get("/inspection-queue", response_model=Page[QueueItem])
def inspection_queue(
    period: str = Depends(resolve_period),
    level: str | None = Query(default=None, description="LOW, MEDIUM, HIGH, CRITICAL"),
    sector: str | None = None,
    region: str | None = None,
    size: str | None = None,
    status: str | None = None,
    quality: str | None = Query(default=None, description="HIGH, MEDIUM or LOW completeness"),
    search: str | None = None,
    sort: str = Query(default="priority"),
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Page[QueueItem]:
    """The operational queue, highest priority first."""
    filters = _filters(period, level, sector, region, size, status, quality, search, sort, direction)
    items, total = company_service.queue(db, filters, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/companies", response_model=Page[QueueItem])
def list_companies(
    period: str = Depends(resolve_period),
    level: str | None = None,
    sector: str | None = None,
    region: str | None = None,
    size: str | None = None,
    status: str | None = None,
    quality: str | None = None,
    search: str | None = None,
    sort: str = "priority",
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Page[QueueItem]:
    filters = _filters(period, level, sector, region, size, status, quality, search, sort, direction)
    items, total = company_service.queue(db, filters, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/companies/{company_id}", response_model=CompanyDetail)
def company_detail(
    company: Company = Depends(get_company),
    period: str = Depends(resolve_period),
    db: Session = Depends(get_db),
) -> CompanyDetail:
    return company_service.detail(db, company, period)


@router.get("/companies/{company_id}/history", response_model=CompanyHistory)
def company_history(
    company: Company = Depends(get_company),
    db: Session = Depends(get_db),
) -> CompanyHistory:
    return company_service.history(db, company)


@router.get("/companies/{company_id}/signals", response_model=list[SignalOut])
def company_signals(
    company: Company = Depends(get_company),
    period: str = Depends(resolve_period),
    db: Session = Depends(get_db),
) -> list[SignalOut]:
    detail = company_service.detail(db, company, period)
    if detail.score is None:
        raise HTTPException(status_code=404, detail=f"No result for {period}")
    return detail.score.signals
