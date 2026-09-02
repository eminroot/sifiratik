from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_policy
from app.database.database import get_db
from app.models import Company, ScoreResult
from app.models.audit_event import REVIEW_STATUSES
from app.reference import COMPANY_SIZES, DATA_FIELDS, MATERIALS, MATERIAL_ORDER, SECTORS
from app.routers.deps import resolve_period
from app.schemas.common import Option, ReferenceData
from app.services.inspection_service import STATUS_LABELS
from app.services.scoring_service import all_periods

router = APIRouter(tags=["reference"])

SIZE_LABELS = {"MICRO": "Micro", "SMALL": "Small", "MEDIUM": "Medium", "LARGE": "Large"}

LEVEL_LABELS = {
    "LOW": "Low",
    "MEDIUM": "Medium",
    "HIGH": "High",
    "CRITICAL": "Critical",
}


@router.get("/reference", response_model=ReferenceData)
def reference(
    period: str = Depends(resolve_period), db: Session = Depends(get_db)
) -> ReferenceData:
    """Filter values and labels, counted against the current period."""
    sector_counts = dict(
        db.execute(select(Company.sector, func.count()).group_by(Company.sector)).all()
    )
    region_counts = dict(
        db.execute(select(Company.region, func.count()).group_by(Company.region)).all()
    )
    size_counts = dict(
        db.execute(select(Company.company_size, func.count()).group_by(Company.company_size)).all()
    )
    level_counts = dict(
        db.execute(
            select(ScoreResult.priority_level, func.count())
            .where(ScoreResult.period == period)
            .group_by(ScoreResult.priority_level)
        ).all()
    )

    return ReferenceData(
        period=period,
        periods=all_periods(db),
        sectors=[
            Option(value=key, label=sector["name"], count=sector_counts.get(key, 0))
            for key, sector in SECTORS.items()
        ],
        regions=[
            Option(value=region, label=region, count=count)
            for region, count in sorted(region_counts.items(), key=lambda x: -x[1])
        ],
        company_sizes=[
            Option(value=size, label=SIZE_LABELS[size], count=size_counts.get(size, 0))
            for size in COMPANY_SIZES
        ],
        priority_levels=[
            Option(value=band.level, label=LEVEL_LABELS[band.level], count=level_counts.get(band.level, 0))
            for band in reversed(get_policy().bands)
        ],
        review_statuses=[
            Option(value=status, label=STATUS_LABELS[status]) for status in REVIEW_STATUSES
        ],
        data_fields=[Option(value=field["key"], label=field["name"]) for field in DATA_FIELDS],
        materials=[Option(value=key, label=MATERIALS[key]["name"]) for key in MATERIAL_ORDER],
    )
