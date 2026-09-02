"""The scoped pilot.

A pilot is the whole platform pointed at one province and one sector: load the
records, score them, rank them, publish the shortlist with its reasons, and
carry the result through to the impact figures. Nothing here is a separate
demonstration path, which is the point of running one.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditReview,
    CollectorProgram,
    Company,
    Declaration,
    GtipLine,
    PilotRun,
    ScoreResult,
)
from app.reference import (
    RECOVERY_CAPTURE_RATE,
    SECTORS,
    SOCIAL_FUND_SHARE,
    co2e_avoided_tonnes,
)
from app.schemas.climate import (
    PilotConfig,
    PilotFindings,
    PilotResult,
    PilotRunRequest,
    PilotStep,
)
from app.services.climate_service import material_rows
from app.services.company_service import QueueFilters, latest_review_subquery, queue
from app.scoring.registry import resolve_engine

PILOT_NAME = "COP31 Antalya Packaging Transparency Pilot"
DEFAULT_REGION = "Antalya"


def _confirmation_ratio(db: Session, period: str) -> float:
    """How much of what was identified, inspections have actually confirmed.

    Taken from the closed inspections in the system rather than assumed, so the
    projection moves as real outcomes come in.
    """
    latest = latest_review_subquery()
    rows = db.execute(
        select(AuditReview.confirmed_additional_tonnage, ScoreResult.shortfall_tonnage)
        .select_from(AuditReview)
        .join(latest, latest.c.review_id == AuditReview.id)
        .join(ScoreResult, ScoreResult.company_id == AuditReview.company_id)
        .where(
            ScoreResult.period == period,
            AuditReview.status == "INSPECTION_COMPLETED",
            AuditReview.confirmed_additional_tonnage.isnot(None),
        )
    ).all()

    identified = sum(row[1] for row in rows if row[1])
    confirmed = sum(row[0] for row in rows if row[0])
    if identified <= 0:
        return 0.0
    return min(1.2, confirmed / identified)


def run_pilot(db: Session, request: PilotRunRequest, period: str, persist: bool = True) -> PilotResult:
    engine = resolve_engine()
    region = request.region or DEFAULT_REGION
    sector = request.sector

    in_scope = select(Company.id).where(Company.region == region)
    if sector:
        in_scope = in_scope.where(Company.sector == sector)
    scope_ids = set(db.execute(in_scope).scalars().all())

    declarations = db.execute(
        select(func.count())
        .select_from(Declaration)
        .where(Declaration.company_id.in_(scope_ids))
    ).scalar_one()
    gtip_lines = db.execute(
        select(func.count()).select_from(GtipLine).where(GtipLine.company_id.in_(scope_ids))
    ).scalar_one()

    filters = QueueFilters(
        period=period,
        regions=[region],
        sectors=[sector] if sector else None,
    )
    shortlist, analysed = queue(db, filters, limit=request.shortlist_size, offset=0)

    levels = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    tonnage_by_sector: dict[str, float] = {}
    tonnage = 0.0
    exposure = 0.0
    unavailable = 0
    quality_total = 0.0

    for item in shortlist:
        levels[item.priority_level] = levels.get(item.priority_level, 0) + 1
        tonnage += item.shortfall_tonnage
        exposure += item.estimated_gekap_gap_try
        unavailable += item.unavailable_signals
        quality_total += item.data_quality_score
        if item.shortfall_tonnage > 0:
            tonnage_by_sector[item.sector] = (
                tonnage_by_sector.get(item.sector, 0.0) + item.shortfall_tonnage
            )

    ratio = _confirmation_ratio(db, period) if request.simulate_outcomes else 0.0
    recovery = tonnage * ratio * RECOVERY_CAPTURE_RATE
    co2e = sum(
        co2e_avoided_tonnes(amount * ratio * RECOVERY_CAPTURE_RATE, sector_key)
        for sector_key, amount in tonnage_by_sector.items()
    )

    municipalities = db.execute(
        select(func.count(func.distinct(CollectorProgram.municipality))).where(
            CollectorProgram.region == region
        )
    ).scalar_one()

    findings = PilotFindings(
        companies_analysed=analysed,
        companies_shortlisted=len(shortlist),
        critical=levels.get("CRITICAL", 0),
        high=levels.get("HIGH", 0),
        medium=levels.get("MEDIUM", 0),
        low=levels.get("LOW", 0),
        additional_tonnage=round(tonnage, 1),
        estimated_gekap_try=round(exposure, 2),
        co2e_avoided_tonnes=round(co2e, 1),
        recovery_potential_tonnes=round(recovery, 1),
        by_material=material_rows(tonnage_by_sector),
        signals_unavailable=unavailable,
        average_data_quality=round(quality_total / len(shortlist), 1) if shortlist else 0.0,
    )

    sector_label = SECTORS[sector]["name"] if sector else "All sectors"
    steps = [
        PilotStep(
            index=1,
            key="region",
            label="Pilot region set",
            detail=f"{region} province, {municipalities} participating municipalities.",
            value=region,
        ),
        PilotStep(
            index=2,
            key="sector",
            label="Sector scope set",
            detail="Packaging intensive sectors carry the largest declaration gaps."
            if not sector
            else f"Scoped to {sector_label}.",
            value=sector_label,
        ),
        PilotStep(
            index=3,
            key="load",
            label="Records loaded",
            detail=f"{declarations:,} declaration periods and {gtip_lines:,} customs lines "
            f"across {len(scope_ids)} companies.",
            value=f"{len(scope_ids)} companies",
        ),
        PilotStep(
            index=4,
            key="analyse",
            label="Analysis run",
            detail=f"Eight signals evaluated per company for {period}.",
            value=engine.version,
        ),
        PilotStep(
            index=5,
            key="shortlist",
            label="Shortlist produced",
            detail=f"{findings.critical} critical and {findings.high} high priority in the "
            f"top {len(shortlist)}.",
            value=f"Top {len(shortlist)}",
        ),
        PilotStep(
            index=6,
            key="reasons",
            label="Reasons attached",
            detail=f"{unavailable} signal evaluations could not be run and are marked "
            "unavailable rather than clear.",
            value=f"{findings.average_data_quality:.0f}% mean data quality",
        ),
        PilotStep(
            index=7,
            key="outcomes",
            label="Outcomes applied",
            detail=f"Closed inspections in the system have confirmed {ratio * 100:.0f}% of the "
            "tonnage they were sent to check."
            if ratio
            else "Outcome projection switched off for this run.",
            value=f"{ratio * 100:.0f}% confirmed" if ratio else "off",
        ),
        PilotStep(
            index=8,
            key="impact",
            label="Impact calculated",
            detail=f"{findings.recovery_potential_tonnes:,.0f} t into formal recovery, "
            f"{findings.co2e_avoided_tonnes:,.0f} t CO2e avoided.",
            value=f"{findings.estimated_gekap_try / 1_000_000:,.1f}M TL at stake",
        ),
        PilotStep(
            index=9,
            key="publish",
            label="Published to impact dashboard",
            detail=f"{SOCIAL_FUND_SHARE * 100:.0f}% of recovered contribution is earmarked for "
            "collector formalisation.",
            value="Live",
        ),
    ]

    config = PilotConfig(
        name=PILOT_NAME if region == DEFAULT_REGION else f"{region} packaging transparency pilot",
        region=region,
        sector=sector,
        period=period,
        shortlist_size=request.shortlist_size,
        simulate_outcomes=request.simulate_outcomes,
    )
    result = PilotResult(
        config=config,
        steps=steps,
        findings=findings,
        shortlist=shortlist,
        ran_at=datetime.now(timezone.utc),
    )

    if persist:
        db.add(
            PilotRun(
                name=config.name,
                region=region,
                sector=sector,
                period=period,
                shortlist_size=request.shortlist_size,
                status="COMPLETED",
                companies_analysed=analysed,
                companies_shortlisted=len(shortlist),
                simulate_outcomes=request.simulate_outcomes,
                results=findings.model_dump(),
            )
        )
        db.commit()

    return result


def last_run(db: Session) -> PilotRun | None:
    return db.execute(select(PilotRun).order_by(PilotRun.id.desc()).limit(1)).scalar_one_or_none()
