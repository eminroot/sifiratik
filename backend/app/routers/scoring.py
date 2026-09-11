from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import i18n
from app.config import ScoringPolicy, get_policy
from app.database.database import get_db
from app.security import Principal, require_writer
from app.services import policy_service
from app.routers.deps import resolve_period
from app.routers.transparency import engines_out, policy_out
from app.schemas.scoring import EngineOut, PolicyOut, PolicyUpdate, ScoringRunOut, ScoringRunRequest
from app.scoring.registry import ENGINE_TYPES
from app.services.scoring_service import run_scoring

router = APIRouter(tags=["scoring"])


@router.post("/scoring/run", response_model=ScoringRunOut)
def scoring_run(
    request: ScoringRunRequest,
    period: str = Depends(resolve_period),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_writer),
) -> ScoringRunOut:
    """Re-evaluate the population.

    The engine is selected by name. If the one requested cannot serve, the
    rule engine runs instead and the response says which one produced the
    result, so a caller is never left guessing what the scores came from.
    """
    if request.engine and request.engine not in ENGINE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown engine. Expected one of {', '.join(ENGINE_TYPES)}",
        )

    summary = run_scoring(
        db,
        period=request.period or period,
        engine_name=request.engine,
        company_ids=request.company_ids,
    )
    return ScoringRunOut(
        period=summary.period,
        engine=summary.engine,
        model_version=summary.model_version,
        companies_scored=summary.companies_scored,
        duration_ms=summary.duration_ms,
        level_counts=summary.level_counts,
        ran_at=datetime.now(timezone.utc),
    )


@router.get("/scoring/engines", response_model=list[EngineOut])
def engines(lang: str = Depends(i18n.resolve_lang)) -> list[EngineOut]:
    return engines_out(lang)


@router.get("/scoring/policy", response_model=PolicyOut)
def read_policy() -> PolicyOut:
    return policy_out()


@router.put("/scoring/policy", response_model=PolicyOut)
def update_policy(
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_writer),
) -> PolicyOut:
    """Change thresholds or signal weights without a deployment.

    Scores already stored keep the policy version they were produced under.
    Run the scoring endpoint to apply a new policy to the population.
    """
    current = get_policy()
    data = current.model_dump()

    if payload.bands:
        data["bands"] = [band.model_dump() for band in payload.bands]
    if payload.weights:
        data["weights"] = [
            {"code": w.code, "weight": w.weight, "enabled": w.enabled} for w in payload.weights
        ]
    if payload.min_coverage_for_confidence is not None:
        data["min_coverage_for_confidence"] = payload.min_coverage_for_confidence
    if payload.strongest_signal_share is not None:
        data["strongest_signal_share"] = payload.strongest_signal_share

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    data["version"] = f"policy-{stamp}"
    policy_service.apply_policy(db, ScoringPolicy(**data), changed_by=principal.user_id)
    return policy_out()
