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

from app import i18n
from app.models import (
    AuditReview,
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

DEFAULT_REGION = "Antalya"


def _confirmation_ratio(db: Session, period: str) -> float:
    """How much of what was identified, inspections have actually confirmed.

    Taken from the closed inspections in the system rather than assumed, so the
    projection moves as real outcomes come in. Each confirmed correction is set
    against the shortfall flagged on the filing that inspection examined, and
    only filings up to the period being piloted count, so a pilot of a past
    quarter is not projected from outcomes that came after it.
    """
    latest = latest_review_subquery()
    rows = db.execute(
        select(AuditReview.confirmed_additional_tonnage, ScoreResult.shortfall_tonnage)
        .select_from(AuditReview)
        .join(latest, latest.c.review_id == AuditReview.id)
        .join(
            ScoreResult,
            (ScoreResult.company_id == AuditReview.company_id)
            & (ScoreResult.period == AuditReview.period),
        )
        .where(
            AuditReview.period <= period,
            AuditReview.status == "INSPECTION_COMPLETED",
            AuditReview.confirmed_additional_tonnage.isnot(None),
        )
    ).all()

    identified = sum(row[1] for row in rows if row[1])
    confirmed = sum(row[0] for row in rows if row[0])
    if identified <= 0:
        return 0.0
    return min(1.2, confirmed / identified)


def run_pilot(
    db: Session,
    request: PilotRunRequest,
    period: str,
    persist: bool = True,
    lang: str = "en",
) -> PilotResult:
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

    # The scope of the pilot is the obligors in the province, counted from the
    # register. It used to be read off the collector programme ledger, which
    # described a programme nobody has run.
    municipalities = db.execute(
        select(func.count()).select_from(Company).where(Company.region == region)
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

    def say(key: str, part: str, **params) -> str:
        return i18n.phrase(i18n.PILOT_STEPS, key, part, lang, **params)

    sector_label = (
        SECTORS[sector]["name"] if sector else say("sector", "all")
    )
    steps = [
        PilotStep(
            index=1,
            key="region",
            label=say("region", "label"),
            detail=say("region", "detail", region=region, municipalities=municipalities),
            value=region,
        ),
        PilotStep(
            index=2,
            key="sector",
            label=say("sector", "label"),
            detail=say("sector", "detail")
            if not sector
            else say("sector", "scoped", sector=sector_label),
            value=sector_label,
        ),
        PilotStep(
            index=3,
            key="load",
            label=say("load", "label"),
            detail=say(
                "load",
                "detail",
                declarations=f"{declarations:,}",
                lines=f"{gtip_lines:,}",
                companies=len(scope_ids),
            ),
            value=say("load", "value", companies=len(scope_ids)),
        ),
        PilotStep(
            index=4,
            key="analyse",
            label=say("analyse", "label"),
            detail=say("analyse", "detail", period=period),
            value=engine.version,
        ),
        PilotStep(
            index=5,
            key="shortlist",
            label=say("shortlist", "label"),
            detail=say(
                "shortlist",
                "detail",
                critical=findings.critical,
                high=findings.high,
                size=len(shortlist),
            ),
            value=say("shortlist", "value", size=len(shortlist)),
        ),
        PilotStep(
            index=6,
            key="reasons",
            label=say("reasons", "label"),
            detail=say("reasons", "detail", count=unavailable),
            value=say("reasons", "value", quality=f"{findings.average_data_quality:.0f}"),
        ),
        PilotStep(
            index=7,
            key="outcomes",
            label=say("outcomes", "label"),
            detail=say("outcomes", "detail", ratio=f"{ratio * 100:.0f}")
            if ratio
            else say("outcomes", "off"),
            value=say("outcomes", "value", ratio=f"{ratio * 100:.0f}")
            if ratio
            else say("outcomes", "valueOff"),
        ),
        PilotStep(
            index=8,
            key="impact",
            label=say("impact", "label"),
            detail=say(
                "impact",
                "detail",
                tonnes=i18n.tonnes(findings.recovery_potential_tonnes, lang),
                co2e=i18n.tonnes(findings.co2e_avoided_tonnes, lang),
            ),
            value=say("impact", "value", value=i18n.lira(findings.estimated_gekap_try, lang)),
        ),
        PilotStep(
            index=9,
            key="publish",
            label=say("publish", "label"),
            detail=say("publish", "detail", share=f"{SOCIAL_FUND_SHARE * 100:.0f}"),
            value=say("publish", "value"),
        ),
    ]

    config = PilotConfig(
        name=i18n.pilot_name(lang, region, DEFAULT_REGION),
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
