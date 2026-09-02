"""Reading companies out of the database for the queue and the detail pages.

Rank is global to the period, not to whatever filter happens to be applied, so
a company keeps the same rank on the dashboard, in a filtered queue and on its
own page. An auditor who has been told to look at rank 14 should find rank 14.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AuditEvent,
    AuditReview,
    Company,
    Declaration,
    FieldObservation,
    GtipLine,
    ScoreResult,
)
from app.reference import SECTORS
from app.schemas.company import (
    CompanyDetail,
    CompanyHistory,
    CompanyProfile,
    DataQualityOut,
    GtipLineOut,
    HistoryDecision,
    MainReason,
    ObservationOut,
    PeerContext,
    PeriodRow,
    QueueItem,
)
from app.schemas.scoring import ExpectedRange, ScoreOut
from app.schemas.signal import SignalOut
from app.services.quality_service import FIELD_NAMES, build_quality
from app.services.scoring_service import build_peer_index

DEFAULT_STATUS = "AWAITING_REVIEW"


@dataclass
class QueueFilters:
    period: str
    levels: list[str] | None = None
    sectors: list[str] | None = None
    regions: list[str] | None = None
    sizes: list[str] | None = None
    statuses: list[str] | None = None
    quality: str | None = None  # HIGH | MEDIUM | LOW
    search: str | None = None
    sort: str = "priority"
    direction: str = "desc"


QUALITY_BOUNDS = {"HIGH": (75, 101), "MEDIUM": (50, 75), "LOW": (0, 50)}

SORT_COLUMNS = {
    "priority": ScoreResult.priority_score,
    "quality": ScoreResult.data_quality_score,
    "shortfall": ScoreResult.shortfall_tonnage,
    "gap": ScoreResult.estimated_gekap_gap_try,
    "name": Company.company_name,
}


def latest_review_subquery():
    """The id of the most recent decision per company."""
    return (
        select(AuditReview.company_id, func.max(AuditReview.id).label("review_id"))
        .group_by(AuditReview.company_id)
        .subquery()
    )


def rank_subquery(period: str):
    """Global position in the period, before any filtering."""
    return (
        select(
            ScoreResult.company_id.label("company_id"),
            func.row_number()
            .over(
                order_by=(
                    ScoreResult.priority_score.desc(),
                    ScoreResult.estimated_gekap_gap_try.desc(),
                    ScoreResult.company_id.asc(),
                )
            )
            .label("rank"),
        )
        .where(ScoreResult.period == period)
        .subquery()
    )


def base_queue_query(period: str) -> Select:
    latest = latest_review_subquery()
    ranks = rank_subquery(period)
    return (
        select(
            Company,
            ScoreResult,
            func.coalesce(AuditReview.status, DEFAULT_STATUS).label("review_status"),
            ranks.c.rank,
        )
        .join(ScoreResult, and_(ScoreResult.company_id == Company.id, ScoreResult.period == period))
        .join(ranks, ranks.c.company_id == Company.id)
        .outerjoin(latest, latest.c.company_id == Company.id)
        .outerjoin(AuditReview, AuditReview.id == latest.c.review_id)
        .options(selectinload(ScoreResult.signals))
    )


def apply_filters(query: Select, filters: QueueFilters) -> Select:
    if filters.levels:
        query = query.where(ScoreResult.priority_level.in_(filters.levels))
    if filters.sectors:
        query = query.where(Company.sector.in_(filters.sectors))
    if filters.regions:
        query = query.where(Company.region.in_(filters.regions))
    if filters.sizes:
        query = query.where(Company.company_size.in_(filters.sizes))
    if filters.statuses:
        if DEFAULT_STATUS in filters.statuses:
            query = query.where(
                or_(
                    AuditReview.status.in_(filters.statuses),
                    AuditReview.status.is_(None),
                )
            )
        else:
            query = query.where(AuditReview.status.in_(filters.statuses))
    if filters.quality and filters.quality in QUALITY_BOUNDS:
        low, high = QUALITY_BOUNDS[filters.quality]
        query = query.where(
            ScoreResult.data_quality_score >= low, ScoreResult.data_quality_score < high
        )
    if filters.search:
        needle = f"%{filters.search.strip()}%"
        query = query.where(
            or_(Company.company_name.ilike(needle), Company.tax_identifier.ilike(needle))
        )
    return query


def apply_sort(query: Select, filters: QueueFilters) -> Select:
    column = SORT_COLUMNS.get(filters.sort, ScoreResult.priority_score)
    order = column.asc() if filters.direction == "asc" else column.desc()
    return query.order_by(order, ScoreResult.estimated_gekap_gap_try.desc(), Company.id.asc())


def _main_reason(score: ScoreResult) -> MainReason | None:
    active = [s for s in score.signals if s.available and s.status == "ACTIVE"]
    if not active:
        return None
    top = max(active, key=lambda s: s.contribution)
    return MainReason(
        code=top.signal_code,
        name=top.signal_name,
        contribution=top.contribution,
        explanation=top.explanation,
    )


def to_queue_item(company: Company, score: ScoreResult, review_status: str, rank: int) -> QueueItem:
    return QueueItem(
        rank=rank,
        company_id=company.id,
        company_name=company.company_name,
        tax_identifier=company.tax_identifier,
        sector=company.sector,
        sector_label=SECTORS[company.sector]["name"],
        region=company.region,
        company_size=company.company_size,
        priority_score=score.priority_score,
        priority_level=score.priority_level,
        main_reason=_main_reason(score),
        declared_tonnage=score.declared_tonnage,
        expected_median=score.expected_median,
        shortfall_tonnage=score.shortfall_tonnage,
        estimated_gekap_gap_try=score.estimated_gekap_gap_try,
        data_quality_score=score.data_quality_score,
        confidence=score.confidence,
        active_signals=sum(1 for s in score.signals if s.status == "ACTIVE"),
        unavailable_signals=sum(1 for s in score.signals if not s.available),
        review_status=review_status,
        registry_status=company.registry_status,
    )


def queue(db: Session, filters: QueueFilters, limit: int = 50, offset: int = 0) -> tuple[list[QueueItem], int]:
    query = apply_filters(base_queue_query(filters.period), filters)

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.execute(count_query).scalar_one()

    rows = db.execute(apply_sort(query, filters).limit(limit).offset(offset)).all()
    return [to_queue_item(c, s, status, rank) for c, s, status, rank in rows], total


def top_queue(db: Session, period: str, limit: int = 8) -> list[QueueItem]:
    items, _ = queue(db, QueueFilters(period=period), limit=limit, offset=0)
    return items


# --------------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------------- #


def _profile(company: Company) -> CompanyProfile:
    return CompanyProfile(
        id=company.id,
        company_name=company.company_name,
        tax_identifier=company.tax_identifier,
        sector=company.sector,
        sector_label=SECTORS[company.sector]["name"],
        region=company.region,
        company_size=company.company_size,
        registry_status=company.registry_status,
        last_data_update=company.last_data_update,
        created_at=company.created_at,
    )


def score_out(score: ScoreResult) -> ScoreOut:
    return ScoreOut(
        period=score.period,
        priority_score=score.priority_score,
        priority_level=score.priority_level,
        expected=ExpectedRange(
            lower=score.expected_lower_bound,
            median=score.expected_median,
            upper=score.expected_upper_bound,
            declared=score.declared_tonnage,
            position=score.position,
            shortfall_tonnage=score.shortfall_tonnage,
            estimated_gekap_gap_try=score.estimated_gekap_gap_try,
        ),
        data_quality_score=score.data_quality_score,
        signal_coverage=score.signal_coverage,
        confidence=score.confidence,
        scoring_engine=score.scoring_engine,
        model_version=score.model_version,
        policy_version=score.policy_version,
        created_at=score.created_at,
        signals=[
            SignalOut(
                code=s.signal_code,
                key=s.signal_key,
                name=s.signal_name,
                status=s.status,
                available=s.available,
                score=s.score,
                weight=s.weight,
                contribution=s.contribution,
                explanation=s.explanation,
                missing_data_reason=s.missing_data_reason,
                evidence=s.evidence,
            )
            for s in sorted(score.signals, key=lambda x: x.signal_code)
        ],
        active_signals=sum(1 for s in score.signals if s.status == "ACTIVE"),
        unavailable_signals=sum(1 for s in score.signals if not s.available),
    )


def current_status(db: Session, company_id: int) -> str:
    review = db.execute(
        select(AuditReview)
        .where(AuditReview.company_id == company_id)
        .order_by(AuditReview.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return review.status if review else DEFAULT_STATUS


def detail(db: Session, company: Company, period: str) -> CompanyDetail:
    score = db.execute(
        select(ScoreResult)
        .options(selectinload(ScoreResult.signals))
        .where(ScoreResult.company_id == company.id, ScoreResult.period == period)
    ).scalar_one_or_none()

    declarations = (
        db.execute(
            select(Declaration)
            .where(Declaration.company_id == company.id, Declaration.period <= period)
            .order_by(Declaration.period.asc())
        )
        .scalars()
        .all()
    )
    observations = (
        db.execute(
            select(FieldObservation)
            .where(FieldObservation.company_id == company.id)
            .order_by(FieldObservation.period.desc())
        )
        .scalars()
        .all()
    )
    gtip_lines = (
        db.execute(
            select(GtipLine)
            .where(GtipLine.company_id == company.id, GtipLine.period == period)
            .order_by(GtipLine.gtip_code.asc())
        )
        .scalars()
        .all()
    )

    quality = build_quality(company, list(declarations), list(observations), bool(gtip_lines))
    current = declarations[-1] if declarations and declarations[-1].period == period else None

    peer_index = build_peer_index(db, period)
    cohort = peer_index.get((company.sector, company.company_size))
    basis = ((current.production_volume or 0.0) + (current.import_volume or 0.0)) if current else 0.0
    own_intensity = (
        current.declared_packaging_tonnage / basis
        if current and current.declared_packaging_tonnage and basis
        else None
    )

    ranks = rank_subquery(period)
    rank = db.execute(select(ranks.c.rank).where(ranks.c.company_id == company.id)).scalar_one_or_none()
    total_ranked = db.execute(
        select(func.count()).select_from(ScoreResult).where(ScoreResult.period == period)
    ).scalar_one()

    return CompanyDetail(
        company=_profile(company),
        score=score_out(score) if score else None,
        quality=DataQualityOut(
            score=quality.score,
            fields=quality.fields,
            field_labels=FIELD_NAMES,
            missing_fields=quality.missing_fields,
            freshness_days=quality.freshness_days,
            last_update=quality.last_update,
        ),
        peers=PeerContext(
            sector=company.sector,
            company_size=company.company_size,
            member_count=cohort.member_count if cohort else 0,
            company_intensity_kg_per_tonne=round(own_intensity * 1000, 2) if own_intensity else None,
            median_intensity_kg_per_tonne=(
                round(cohort.median_intensity * 1000, 2)
                if cohort and cohort.median_intensity
                else None
            ),
        ),
        review_status=current_status(db, company.id),
        current_period=PeriodRow(
            period=current.period,
            declared_tonnage=current.declared_packaging_tonnage,
            production_volume=current.production_volume,
            import_volume=current.import_volume,
            export_volume=current.export_volume,
        )
        if current
        else None,
        material_breakdown=current.material_breakdown if current else None,
        observations=[ObservationOut.model_validate(o) for o in observations],
        gtip_lines=[GtipLineOut.model_validate(g) for g in gtip_lines],
        rank=rank,
        total_ranked=total_ranked,
    )


def history(db: Session, company: Company) -> CompanyHistory:
    declarations = (
        db.execute(
            select(Declaration)
            .where(Declaration.company_id == company.id)
            .order_by(Declaration.period.asc())
        )
        .scalars()
        .all()
    )
    scores = {
        s.period: s
        for s in db.execute(select(ScoreResult).where(ScoreResult.company_id == company.id))
        .scalars()
        .all()
    }
    observations = (
        db.execute(
            select(FieldObservation)
            .where(FieldObservation.company_id == company.id)
            .order_by(FieldObservation.period.asc())
        )
        .scalars()
        .all()
    )
    events = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.company_id == company.id)
            .order_by(AuditEvent.created_at.desc())
        )
        .scalars()
        .all()
    )

    rows: list[PeriodRow] = []
    for declaration in declarations:
        score = scores.get(declaration.period)
        rows.append(
            PeriodRow(
                period=declaration.period,
                declared_tonnage=declaration.declared_packaging_tonnage,
                production_volume=declaration.production_volume,
                import_volume=declaration.import_volume,
                export_volume=declaration.export_volume,
                expected_lower=score.expected_lower_bound if score else None,
                expected_median=score.expected_median if score else None,
                expected_upper=score.expected_upper_bound if score else None,
                priority_score=score.priority_score if score else None,
                priority_level=score.priority_level if score else None,
                position=score.position if score else None,
            )
        )

    return CompanyHistory(
        company=_profile(company),
        periods=rows,
        observations=[ObservationOut.model_validate(o) for o in observations],
        decisions=[
            HistoryDecision(
                decision_id=e.decision_id,
                action=e.action,
                previous_status=e.previous_status,
                new_status=e.new_status,
                user_id=e.user_id,
                notes=e.notes,
                created_at=e.created_at,
            )
            for e in events
        ],
    )
