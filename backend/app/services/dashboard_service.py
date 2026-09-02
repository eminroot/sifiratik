"""Population level views: the executive dashboard and the data quality page."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_policy
from app.models import (
    Company,
    Declaration,
    FieldObservation,
    GtipLine,
    ScoreResult,
    SignalResult,
)
from app.reference import DATA_FIELDS, SIGNAL_BY_CODE
from app.schemas.dashboard import (
    CoverageRow,
    Dashboard,
    LevelBreakdown,
    QualityBand,
    StatusBreakdown,
)
from app.schemas.signal import SignalAvailability
from app.scoring.registry import resolve_engine
from app.services.company_service import top_queue
from app.services.inspection_service import (
    CLOSED,
    IN_PROGRESS,
    STATUS_LABELS,
    status_counts,
)
from app.services.quality_service import states_from

QUALITY_BANDS = [
    ("Complete", 85, 101),
    ("Good", 70, 85),
    ("Partial", 50, 70),
    ("Thin", 0, 50),
]


def level_breakdown(db: Session, period: str) -> tuple[list[LevelBreakdown], int]:
    rows = db.execute(
        select(ScoreResult.priority_level, func.count())
        .where(ScoreResult.period == period)
        .group_by(ScoreResult.priority_level)
    ).all()
    counts = dict(rows)
    total = sum(counts.values()) or 1
    order = [band.level for band in get_policy().bands][::-1]
    return (
        [
            LevelBreakdown(
                level=level,
                count=counts.get(level, 0),
                share=round(counts.get(level, 0) / total * 100, 1),
            )
            for level in order
        ],
        sum(counts.values()),
    )


def signal_availability(db: Session, period: str) -> list[SignalAvailability]:
    rows = db.execute(
        select(
            SignalResult.signal_code,
            func.count(),
            func.sum(case((SignalResult.available.is_(True), 1), else_=0)),
            func.sum(case((SignalResult.status == "ACTIVE", 1), else_=0)),
        )
        .join(ScoreResult, ScoreResult.id == SignalResult.score_result_id)
        .where(ScoreResult.period == period)
        .group_by(SignalResult.signal_code)
    ).all()

    reasons = db.execute(
        select(SignalResult.signal_code, SignalResult.missing_data_reason)
        .join(ScoreResult, ScoreResult.id == SignalResult.score_result_id)
        .where(ScoreResult.period == period, SignalResult.available.is_(False))
    ).all()

    by_code: dict[str, Counter] = {}
    for code, reason in reasons:
        if reason:
            by_code.setdefault(code, Counter())[reason] += 1

    out = []
    for code, total, evaluated, active in sorted(rows):
        evaluated = int(evaluated or 0)
        common = by_code.get(code)
        out.append(
            SignalAvailability(
                code=code,
                name=SIGNAL_BY_CODE[code]["name"],
                evaluated=evaluated,
                unavailable=total - evaluated,
                active=int(active or 0),
                availability_rate=round(evaluated / total * 100, 1) if total else 0.0,
                top_reason=common.most_common(1)[0][0] if common else None,
            )
        )
    return out


def quality_inputs(db: Session, period: str) -> list[dict]:
    """One row per company with everything the field verdicts need."""
    declared_counts = (
        select(
            Declaration.company_id.label("company_id"),
            func.count().label("declared_count"),
        )
        .where(Declaration.declared_packaging_tonnage.isnot(None), Declaration.period <= period)
        .group_by(Declaration.company_id)
        .subquery()
    )
    observation_counts = (
        select(
            FieldObservation.company_id.label("company_id"),
            func.count().label("observation_count"),
        )
        .group_by(FieldObservation.company_id)
        .subquery()
    )
    gtip_counts = (
        select(GtipLine.company_id.label("company_id"), func.count().label("line_count"))
        .where(GtipLine.period == period)
        .group_by(GtipLine.company_id)
        .subquery()
    )
    current = (
        select(
            Declaration.company_id.label("company_id"),
            Declaration.production_volume,
            Declaration.import_volume,
        )
        .where(Declaration.period == period)
        .subquery()
    )

    rows = db.execute(
        select(
            Company,
            func.coalesce(declared_counts.c.declared_count, 0),
            func.coalesce(observation_counts.c.observation_count, 0),
            func.coalesce(gtip_counts.c.line_count, 0),
            current.c.production_volume,
            current.c.import_volume,
            ScoreResult.data_quality_score,
        )
        .join(ScoreResult, ScoreResult.company_id == Company.id)
        .outerjoin(declared_counts, declared_counts.c.company_id == Company.id)
        .outerjoin(observation_counts, observation_counts.c.company_id == Company.id)
        .outerjoin(gtip_counts, gtip_counts.c.company_id == Company.id)
        .outerjoin(current, current.c.company_id == Company.id)
        .where(ScoreResult.period == period)
    ).all()

    out = []
    for company, declared, observations, lines, production, imports, quality in rows:
        out.append(
            {
                "company": company,
                "quality": quality,
                "states": states_from(
                    has_production_data=company.has_production_data,
                    has_current_production=production is not None,
                    has_import_data=company.has_import_data,
                    has_current_import=imports is not None,
                    history_count=declared,
                    has_gtip_data=company.has_gtip_data,
                    has_gtip_for_period=lines > 0,
                    gtip_coverage=company.gtip_coverage,
                    has_observations=observations > 0,
                    registry_status=company.registry_status,
                ),
            }
        )
    return out


def field_coverage(db: Session, period: str) -> list[CoverageRow]:
    rows = quality_inputs(db, period)
    total = len(rows) or 1

    coverage = []
    for field in DATA_FIELDS:
        counts = Counter(row["states"][field["key"]] for row in rows)
        available = counts.get("AVAILABLE", 0)
        partial = counts.get("PARTIAL", 0)
        coverage.append(
            CoverageRow(
                key=field["key"],
                label=field["name"],
                available=available,
                partial=partial,
                missing=counts.get("MISSING", 0),
                coverage=round((available + partial * 0.55) / total * 100, 1),
            )
        )
    return coverage


def quality_bands(db: Session, period: str) -> list[QualityBand]:
    scores = (
        db.execute(select(ScoreResult.data_quality_score).where(ScoreResult.period == period))
        .scalars()
        .all()
    )
    return [
        QualityBand(
            label=label,
            lower=low,
            upper=high - 1,
            count=sum(1 for score in scores if low <= score < high),
        )
        for label, low, high in QUALITY_BANDS
    ]


def build_dashboard(db: Session, period: str) -> Dashboard:
    engine = resolve_engine()
    levels, analysed = level_breakdown(db, period)

    exposure_rows = (
        db.execute(
            select(ScoreResult.estimated_gekap_gap_try, ScoreResult.priority_level)
            .where(ScoreResult.period == period)
            .order_by(ScoreResult.priority_score.desc(), ScoreResult.estimated_gekap_gap_try.desc())
        )
        .all()
    )
    flagged_gaps = [gap for gap, level in exposure_rows if level in ("HIGH", "CRITICAL")]
    total_exposure = sum(flagged_gaps)
    top_50_exposure = sum(gap for gap, _ in exposure_rows[:50])

    tonnage = db.execute(
        select(func.coalesce(func.sum(ScoreResult.shortfall_tonnage), 0.0)).where(
            ScoreResult.period == period,
            ScoreResult.priority_level.in_(("HIGH", "CRITICAL")),
        )
    ).scalar_one()

    statuses = status_counts(db, period)
    average_quality = db.execute(
        select(func.avg(ScoreResult.data_quality_score)).where(ScoreResult.period == period)
    ).scalar_one()

    without_declaration = db.execute(
        select(func.count())
        .select_from(ScoreResult)
        .where(ScoreResult.period == period, ScoreResult.declared_tonnage.is_(None))
    ).scalar_one()

    return Dashboard(
        period=period,
        generated_at=datetime.now(timezone.utc),
        scoring_engine=engine.name,
        model_version=engine.version,
        policy_version=get_policy().version,
        companies_analysed=analysed,
        by_level=levels,
        by_status=[
            StatusBreakdown(status=status, label=STATUS_LABELS[status], count=count)
            for status, count in statuses.items()
        ],
        awaiting_review=statuses.get("AWAITING_REVIEW", 0),
        reviewed=sum(count for status, count in statuses.items() if status in CLOSED),
        in_progress=sum(count for status, count in statuses.items() if status in IN_PROGRESS),
        additional_tonnage_identified=round(float(tonnage), 1),
        estimated_gekap_gap_try=round(total_exposure, 2),
        exposure_in_top_50_try=round(top_50_exposure, 2),
        exposure_share_in_top_50=round(top_50_exposure / total_exposure * 100, 1)
        if total_exposure
        else 0.0,
        average_data_quality=round(float(average_quality or 0), 1),
        quality_bands=quality_bands(db, period),
        field_coverage=field_coverage(db, period),
        signal_availability=signal_availability(db, period),
        priority_queue=top_queue(db, period, limit=10),
        regions_covered=db.execute(select(func.count(func.distinct(Company.region)))).scalar_one(),
        sectors_covered=db.execute(select(func.count(func.distinct(Company.sector)))).scalar_one(),
        companies_without_declaration=without_declaration,
    )
