"""The review workflow.

A decision is never edited in place. Each action appends a review row and a
chained audit event, so the standing of a filing is the newest row for it and
the reasoning behind it is the whole list.

A decision is about one company's declaration for one period. The standing of
this quarter's filing is decided on this quarter's filing; an inspection that
closed last quarter is history, not an answer to the filing in front of the
auditor now.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, AuditReview, Company, ScoreResult
from app.models.audit_event import REVIEW_STATUSES
from app.schemas.inspection import AuditEventOut, ReviewOut
from app.services.audit_chain import append_event, commit_with_retry, new_decision_id
from app.services.company_service import current_status

STATUS_LABELS = {
    "AWAITING_REVIEW": "Awaiting review",
    "MARKED_FOR_INSPECTION": "Marked for inspection",
    "UNDER_REVIEW": "Under review",
    "INFORMATION_REQUESTED": "Information requested",
    "INSPECTION_COMPLETED": "Inspection completed",
    "NO_ACTION_REQUIRED": "No action required",
}

CLOSED = {"INSPECTION_COMPLETED", "NO_ACTION_REQUIRED"}
IN_PROGRESS = {"MARKED_FOR_INSPECTION", "UNDER_REVIEW", "INFORMATION_REQUESTED"}


def record_review(
    db: Session,
    company: Company,
    status: str,
    auditor_id: str,
    notes: str | None,
    confirmed_additional_tonnage: float | None,
    period: str,
) -> ReviewOut:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Unknown review status: {status}")

    company_id = company.id
    score = db.execute(
        select(ScoreResult).where(
            ScoreResult.company_id == company_id, ScoreResult.period == period
        )
    ).scalar_one_or_none()
    score_data = {
        "priority_score": score.priority_score if score else None,
        "priority_level": score.priority_level if score else None,
    }

    def write() -> AuditReview:
        # Built afresh on every attempt: a retry after a sequence collision
        # starts from the chain and the standing as they are now.
        previous = current_status(db, company_id, period)
        now = datetime.now(timezone.utc)
        decision_id = new_decision_id()

        review = AuditReview(
            company_id=company_id,
            period=period,
            status=status,
            auditor_id=auditor_id,
            notes=notes,
            decision_id=decision_id,
            confirmed_additional_tonnage=confirmed_additional_tonnage,
            created_at=now,
            updated_at=now,
        )
        db.add(review)

        append_event(
            db,
            company_id=company_id,
            user_id=auditor_id,
            action="STATUS_CHANGE",
            previous_status=previous,
            new_status=status,
            notes=notes,
            decision_id=decision_id,
            event_data={
                "period": period,
                **score_data,
                "confirmed_additional_tonnage": confirmed_additional_tonnage,
            },
            created_at=now,
        )
        return review

    review = commit_with_retry(db, write)
    db.refresh(review)
    return ReviewOut.model_validate(review)


def reviews_for(db: Session, company_id: int) -> list[ReviewOut]:
    rows = (
        db.execute(
            select(AuditReview)
            .where(AuditReview.company_id == company_id)
            .order_by(AuditReview.id.desc())
        )
        .scalars()
        .all()
    )
    return [ReviewOut.model_validate(row) for row in rows]


def events_for(db: Session, company_id: int) -> list[AuditEventOut]:
    rows = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.company_id == company_id)
            .order_by(AuditEvent.sequence.desc())
        )
        .scalars()
        .all()
    )
    return [AuditEventOut.model_validate(row) for row in rows]


def all_events(
    db: Session, limit: int = 60, offset: int = 0, action: str | None = None
) -> tuple[list[AuditEventOut], int]:
    query = select(AuditEvent, Company.company_name).outerjoin(
        Company, Company.id == AuditEvent.company_id
    )
    if action:
        query = query.where(AuditEvent.action == action)

    total = db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    ).scalar_one()

    rows = db.execute(
        query.order_by(AuditEvent.sequence.desc()).limit(limit).offset(offset)
    ).all()

    items = []
    for event, company_name in rows:
        item = AuditEventOut.model_validate(event)
        item.company_name = company_name
        items.append(item)
    return items, total


def status_counts(db: Session, period: str) -> dict[str, int]:
    """How the period's scored filings are distributed across the workflow."""
    from app.services.company_service import latest_review_subquery

    latest = latest_review_subquery(period)
    rows = db.execute(
        select(
            func.coalesce(AuditReview.status, "AWAITING_REVIEW"),
            func.count(Company.id),
        )
        .select_from(Company)
        .join(ScoreResult, ScoreResult.company_id == Company.id)
        .outerjoin(latest, latest.c.company_id == Company.id)
        .outerjoin(AuditReview, AuditReview.id == latest.c.review_id)
        .where(ScoreResult.period == period)
        .group_by(func.coalesce(AuditReview.status, "AWAITING_REVIEW"))
    ).all()

    counts = {status: 0 for status in REVIEW_STATUSES}
    for status, count in rows:
        counts[status] = count
    return counts
