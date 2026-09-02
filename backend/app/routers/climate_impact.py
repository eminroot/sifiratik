from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import i18n
from app.database.database import get_db
from app.routers.deps import resolve_period
from app.schemas.climate import ClimateImpact, PilotResult, PilotRunRequest
from app.services import climate_service, pilot_service

router = APIRouter(tags=["impact"])


@router.get("/climate-impact", response_model=ClimateImpact)
def climate_impact(
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
) -> ClimateImpact:
    """What better prioritisation turned into, from tonnage through to emissions."""
    return climate_service.climate_impact(db, period, lang)


@router.get("/cop31/pilot", response_model=PilotResult)
def pilot(
    region: str = "Antalya",
    sector: str | None = None,
    shortlist_size: int = 100,
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
) -> PilotResult:
    """The pilot as currently configured, computed but not recorded."""
    request = PilotRunRequest(
        region=region, sector=sector, shortlist_size=shortlist_size, simulate_outcomes=True
    )
    return pilot_service.run_pilot(db, request, period, persist=False, lang=lang)


@router.post("/cop31/pilot/run", response_model=PilotResult, status_code=201)
def run_pilot(
    request: PilotRunRequest,
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
) -> PilotResult:
    """Execute the pilot and record the run."""
    return pilot_service.run_pilot(
        db, request, request.period or period, persist=True, lang=lang
    )
