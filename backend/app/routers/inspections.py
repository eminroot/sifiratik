from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.security import Principal, acting_user, limit_review, require_writer
from app.models import Company
from app.models.audit_event import REVIEW_STATUSES
from app.routers.deps import get_company, resolve_period
from app.schemas.common import Page
from app.schemas.inspection import AuditEventOut, ChainStatus, ReviewOut, ReviewRequest
from app.services import inspection_service
from app.services.audit_chain import verify_chain

router = APIRouter(tags=["inspections"])


@router.post("/companies/{company_id}/review", response_model=ReviewOut, status_code=201)
def record_review(
    payload: ReviewRequest,
    company: Company = Depends(get_company),
    period: str = Depends(resolve_period),
    db: Session = Depends(get_db),
    principal: Principal = Depends(limit_review),
) -> ReviewOut:
    """Record a decision. Appends to the review list and to the audit chain."""
    if payload.status not in REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown status. Expected one of {', '.join(REVIEW_STATUSES)}",
        )
    # A corrected tonnage is what a completed inspection established. On any
    # other decision it would enter the confirmed figures without a visit.
    if (
        payload.confirmed_additional_tonnage is not None
        and payload.status != "INSPECTION_COMPLETED"
    ):
        raise HTTPException(
            status_code=422,
            detail="A confirmed tonnage can only be recorded with INSPECTION_COMPLETED.",
        )
    return inspection_service.record_review(
        db,
        company,
        status=payload.status,
        auditor_id=acting_user(principal, payload.auditor_id),
        notes=payload.notes,
        confirmed_additional_tonnage=payload.confirmed_additional_tonnage,
        period=period,
    )


@router.get("/companies/{company_id}/reviews", response_model=list[ReviewOut])
def company_reviews(
    company: Company = Depends(get_company), db: Session = Depends(get_db)
) -> list[ReviewOut]:
    return inspection_service.reviews_for(db, company.id)


@router.get("/companies/{company_id}/audit-history", response_model=list[AuditEventOut])
def company_audit_history(
    company: Company = Depends(get_company), db: Session = Depends(get_db)
) -> list[AuditEventOut]:
    return inspection_service.events_for(db, company.id)


@router.get("/audit/events", response_model=Page[AuditEventOut])
def audit_events(
    action: str | None = None,
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Page[AuditEventOut]:
    items, total = inspection_service.all_events(db, limit=limit, offset=offset, action=action)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/audit/verify", response_model=ChainStatus)
def verify(db: Session = Depends(get_db)) -> ChainStatus:
    """Recompute every link in the decision log and report the first break."""
    result = verify_chain(db)
    return ChainStatus(**result, verified_at=datetime.now(timezone.utc))
