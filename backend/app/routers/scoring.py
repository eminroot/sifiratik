from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import i18n
from app.config import ScoringPolicy, get_policy
from app.database.database import get_db
from app.security import Principal, limit_scoring_run, require_writer
from app.services import policy_service
from app.routers.deps import known_period, resolve_period
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
    principal: Principal = Depends(limit_scoring_run),
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
        period=known_period(db, request.period) if request.period else period,
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
        # Merged by code: a change to one signal leaves the others as they
        # were. Replacing the list used to drop every signal not named, and a
        # signal with no weight is a signal switched off.
        changes = {w.code: {"code": w.code, "weight": w.weight, "enabled": w.enabled} for w in payload.weights}
        data["weights"] = [changes.pop(item["code"], item) for item in data["weights"]]
        data["weights"] += list(changes.values())
    if payload.min_coverage_for_confidence is not None:
        data["min_coverage_for_confidence"] = payload.min_coverage_for_confidence
    if payload.strongest_signal_share is not None:
        data["strongest_signal_share"] = payload.strongest_signal_share

    # A change that changes nothing is not stored, so the trail records
    # decisions about the policy rather than every request that touched it.
    unchanged = {**current.model_dump(), "version": None} == {**data, "version": None}
    if unchanged:
        return policy_out()

    # The version is unique, and a timestamp alone is not: two changes inside
    # one clock tick got the same one and the second failed with a server
    # error. The random suffix makes it unique whatever the clock resolves.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    data["version"] = f"policy-{stamp}-{uuid.uuid4().hex[:6]}"
    try:
        policy = ScoringPolicy(**data)
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                for item in error.errors(include_url=False, include_context=False)
            ],
        ) from error

    policy_service.apply_policy(db, policy, changed_by=principal.user_id)
    return policy_out()
