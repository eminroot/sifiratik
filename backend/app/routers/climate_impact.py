from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import i18n
from app.database.database import get_db
from app.reference import SECTORS
from app.security import Principal, require_writer
from app.routers.deps import known_period, resolve_period
from app.schemas.climate import MAX_SHORTLIST, ClimateImpact, PilotResult, PilotRunRequest
from app.services import climate_service, pilot_service

router = APIRouter(tags=["impact"])


def _known_sector(sector: str | None) -> str | None:
    # The pilot names the sector it was scoped to; an unknown one used to be
    # looked up regardless and fail with a server error.
    if sector and sector not in SECTORS:
        raise HTTPException(
            status_code=422, detail=f"Unknown sector. Expected one of {', '.join(SECTORS)}"
        )
    return sector or None


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
    region: str = Query(default="Antalya", max_length=60),
    sector: str | None = Query(default=None, max_length=40),
    shortlist_size: int = Query(default=100, ge=1, le=MAX_SHORTLIST),
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
) -> PilotResult:
    """The pilot as currently configured, computed but not recorded."""
    request = PilotRunRequest(
        region=region,
        sector=_known_sector(sector),
        shortlist_size=shortlist_size,
        simulate_outcomes=True,
    )
    return pilot_service.run_pilot(db, request, period, persist=False, lang=lang)


@router.post("/cop31/pilot/run", response_model=PilotResult, status_code=201)
def run_pilot(
    request: PilotRunRequest,
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_writer),
) -> PilotResult:
    """Execute the pilot and record the run."""
    target = known_period(db, request.period) if request.period else period
    request.sector = _known_sector(request.sector)
    return pilot_service.run_pilot(db, request, target, persist=True, lang=lang)
