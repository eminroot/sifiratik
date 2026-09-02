from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import Company, ScoreResult, SignalResult
from app.reference import SECTORS
from app.routers.deps import resolve_period
from app.schemas.dashboard import CompanyQualityRow, Dashboard, DataQualityReport
from app.services import dashboard_service
from app.services.quality_service import FIELD_NAMES

router = APIRouter(tags=["overview"])


@router.get("/dashboard", response_model=Dashboard)
def dashboard(
    period: str = Depends(resolve_period), db: Session = Depends(get_db)
) -> Dashboard:
    """Where the inspection team should spend the period."""
    return dashboard_service.build_dashboard(db, period)


@router.get("/data-quality", response_model=DataQualityReport)
def data_quality(
    period: str = Depends(resolve_period),
    limit: int = 250,
    db: Session = Depends(get_db),
) -> DataQualityReport:
    """What the platform can and cannot see, company by company."""
    rows = dashboard_service.quality_inputs(db, period)

    unavailable = dict(
        db.execute(
            select(ScoreResult.company_id, func.count())
            .join(SignalResult, SignalResult.score_result_id == ScoreResult.id)
            .where(ScoreResult.period == period, SignalResult.available.is_(False))
            .group_by(ScoreResult.company_id)
        ).all()
    )
    levels = dict(
        db.execute(
            select(ScoreResult.company_id, ScoreResult.priority_level).where(
                ScoreResult.period == period
            )
        ).all()
    )

    companies = [
        CompanyQualityRow(
            company_id=row["company"].id,
            company_name=row["company"].company_name,
            sector_label=SECTORS[row["company"].sector]["name"],
            region=row["company"].region,
            quality_score=row["quality"],
            fields=row["states"],
            missing_count=sum(1 for state in row["states"].values() if state == "MISSING"),
            unavailable_signals=unavailable.get(row["company"].id, 0),
            priority_level=levels.get(row["company"].id, "LOW"),
            registry_status=row["company"].registry_status,
        )
        for row in rows
    ]
    companies.sort(key=lambda item: (item.quality_score, -item.unavailable_signals))

    analysed = len(rows)
    return DataQualityReport(
        period=period,
        average_data_quality=round(
            sum(row["quality"] for row in rows) / analysed, 1
        )
        if analysed
        else 0.0,
        companies_analysed=analysed,
        fully_evidenced=sum(1 for row in companies if row.missing_count == 0),
        thin_evidence=sum(1 for row in companies if row.quality_score < 50),
        quality_bands=dashboard_service.quality_bands(db, period),
        field_coverage=dashboard_service.field_coverage(db, period),
        field_labels=FIELD_NAMES,
        signal_availability=dashboard_service.signal_availability(db, period),
        companies=companies[:limit],
        total_companies=db.execute(select(func.count(Company.id))).scalar_one(),
    )
