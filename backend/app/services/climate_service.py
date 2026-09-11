"""Climate and social impact.

Two numbers are kept apart throughout. Identified tonnage is what the analysis
suggests is unaccounted for; confirmed tonnage is what an inspection actually
established. Only confirmed tonnage is carried into recovery, revenue and
emissions figures, because a projection presented as an outcome is how impact
reporting loses its credibility.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import i18n
from app.models import AuditReview, CollectorProgram, Company, ScoreResult
from app.reference import (
    COLLECTOR_ANNUAL_COST_TRY,
    MATERIALS,
    MATERIAL_ORDER,
    RECOVERY_CAPTURE_RATE,
    SOCIAL_FUND_SHARE,
    co2e_avoided_tonnes,
    gekap_value_try,
    material_split,
)
from app.schemas.climate import (
    ChainStep,
    ClimateImpact,
    MaterialTonnage,
    SocialImpact,
)
from app.services.company_service import latest_review_subquery

FLAGGED_LEVELS = ("HIGH", "CRITICAL")


def material_rows(tonnage_by_sector: dict[str, float]) -> list[MaterialTonnage]:
    totals: dict[str, float] = {key: 0.0 for key in MATERIAL_ORDER}
    for sector, tonnes in tonnage_by_sector.items():
        for material, amount in material_split(tonnes, sector).items():
            totals[material] += amount

    rows = []
    for key in MATERIAL_ORDER:
        tonnes = totals[key]
        if tonnes <= 0:
            continue
        material = MATERIALS[key]
        rate = material["tariff_try_per_kg"]
        rows.append(
            MaterialTonnage(
                key=key,
                name=material["name"],
                tonnes=round(tonnes, 1),
                # Wood is charged per unit of packaging, not per kilogram, so a
                # tonnage cannot be turned into a liability for it. The tonnage
                # is still reported; the money is left unset rather than filled
                # with a rate that does not exist.
                gekap_value_try=round(tonnes * 1000 * rate, 2) if rate is not None else None,
                priced_by_weight=rate is not None,
                co2e_avoided_tonnes=round(
                    tonnes * RECOVERY_CAPTURE_RATE * material["co2e_tonnes_avoided_per_tonne"], 1
                ),
                co2e_conservative_tonnes=round(
                    tonnes * RECOVERY_CAPTURE_RATE * material["co2e_conservative_per_tonne"], 1
                ),
            )
        )
    return sorted(rows, key=lambda row: row.tonnes, reverse=True)


def social_impact(db: Session, funding_available: float, funding_potential: float) -> SocialImpact:
    """What a collector formalisation programme would cost, against what one
    has actually done.

    The achieved side is read from the programme ledger, which is empty until
    a municipality runs one. It stays empty rather than being filled in: no
    collector has been supported by this platform, and reporting otherwise
    would be the clearest possible overclaim.

    The funded side is a costing, not a commitment. Additional GEKAP revenue
    does not reach waste collectors by itself — that takes a budget line and a
    legal instrument — so these figures say what a programme of a given size
    would need, and the interface labels them that way.
    """
    row = db.execute(
        select(
            func.coalesce(func.sum(CollectorProgram.collectors_supported), 0),
            func.coalesce(func.sum(CollectorProgram.formal_transitions), 0),
            func.coalesce(func.sum(CollectorProgram.insured_workers), 0),
            func.coalesce(func.sum(CollectorProgram.insured_days), 0),
            func.coalesce(func.sum(CollectorProgram.funding_allocated_try), 0.0),
            func.count(func.distinct(CollectorProgram.municipality)),
        )
    ).one()

    collectors, transitions, insured, days, funding, municipalities = row
    return SocialImpact(
        collectors_supported=int(collectors),
        formal_transitions=int(transitions),
        insured_workers=int(insured),
        insured_days=int(days),
        municipalities=int(municipalities),
        funding_allocated_try=round(float(funding), 2),
        funding_available_try=round(funding_available, 2),
        cost_per_transition_try=COLLECTOR_ANNUAL_COST_TRY,
        worker_years_funded=round(funding_available / COLLECTOR_ANNUAL_COST_TRY, 1),
        funding_potential_try=round(funding_potential, 2),
        worker_years_potential=round(funding_potential / COLLECTOR_ANNUAL_COST_TRY, 1),
    )


def climate_impact(db: Session, period: str, lang: str = "en") -> ClimateImpact:
    rows = db.execute(
        select(
            Company.sector,
            Company.region,
            ScoreResult.priority_level,
            ScoreResult.shortfall_tonnage,
            ScoreResult.estimated_gekap_gap_try,
        )
        .join(ScoreResult, ScoreResult.company_id == Company.id)
        .where(ScoreResult.period == period)
    ).all()

    identified_by_sector: dict[str, float] = {}
    identified_by_region: dict[str, float] = {}
    identified = 0.0
    estimated_revenue = 0.0
    flagged = 0

    for sector, region, level, shortfall, gap in rows:
        if level not in FLAGGED_LEVELS or shortfall <= 0:
            continue
        flagged += 1
        identified += shortfall
        estimated_revenue += gap
        identified_by_sector[sector] = identified_by_sector.get(sector, 0.0) + shortfall
        identified_by_region[region] = identified_by_region.get(region, 0.0) + shortfall

    # Closed inspections, each paired with the shortfall that was flagged on
    # the very filing it examined. The two figures on this page cover
    # different ground — one is the period being worked now, the other is
    # every period already worked — so the funnel below is built on the
    # inspected files, where a confirmed correction can be set against the
    # shortfall that prompted the visit.
    latest = latest_review_subquery()
    confirmed_rows = db.execute(
        select(
            Company.sector,
            AuditReview.confirmed_additional_tonnage,
            ScoreResult.shortfall_tonnage,
        )
        .select_from(Company)
        .join(latest, latest.c.company_id == Company.id)
        .join(AuditReview, AuditReview.id == latest.c.review_id)
        .outerjoin(
            ScoreResult,
            (ScoreResult.company_id == AuditReview.company_id)
            & (ScoreResult.period == AuditReview.period),
        )
        .where(AuditReview.status == "INSPECTION_COMPLETED")
    ).all()

    confirmed_by_sector: dict[str, float] = {}
    confirmed = 0.0
    confirmed_revenue = 0.0
    co2e = 0.0
    flagged_on_inspected = 0.0
    for sector, tonnes, flagged_shortfall in confirmed_rows:
        flagged_on_inspected += flagged_shortfall or 0.0
        if not tonnes:
            continue
        confirmed += tonnes
        confirmed_by_sector[sector] = confirmed_by_sector.get(sector, 0.0) + tonnes
        confirmed_revenue += gekap_value_try(tonnes, sector)
        co2e += co2e_avoided_tonnes(tonnes * RECOVERY_CAPTURE_RATE, sector)

    inspected = len(confirmed_rows)
    records_updated = sum(1 for _, tonnes, _flagged in confirmed_rows if tonnes)

    analysed = db.execute(
        select(func.count()).select_from(ScoreResult).where(ScoreResult.period == period)
    ).scalar_one()
    regions = db.execute(select(func.count(func.distinct(Company.region)))).scalar_one()
    sectors = db.execute(select(func.count(func.distinct(Company.sector)))).scalar_one()

    to_recovery = confirmed * RECOVERY_CAPTURE_RATE
    # Two separate figures, never added together: what closed inspections have
    # actually recovered, and what the open cases would add if they close.
    funding_available = confirmed_revenue * SOCIAL_FUND_SHARE
    funding_potential = estimated_revenue * SOCIAL_FUND_SHARE

    region_rows = sorted(identified_by_region.items(), key=lambda item: item[1], reverse=True)[:8]

    def step(key: str, part: str, **params) -> str:
        return i18n.phrase(i18n.CHAIN_STEPS, key, part, lang, **params)

    impact_chain = [
        ChainStep(
            key="analysed",
            label=step("analysed", "label"),
            value=float(analysed),
            unit="companies",
            note=step("analysed", "note", period=period),
        ),
        ChainStep(
            key="flagged",
            label=step("flagged", "label"),
            value=float(flagged),
            unit="companies",
            note=step("flagged", "note"),
        ),
        ChainStep(
            key="identified",
            label=step("identified", "label"),
            value=round(identified, 1),
            unit="tonnes",
            note=step("identified", "note"),
        ),
        ChainStep(
            key="inspected",
            label=step("inspected", "label"),
            value=round(flagged_on_inspected, 1),
            unit="tonnes",
            note=step("inspected", "note", count=inspected),
        ),
        ChainStep(
            key="confirmed",
            label=step("confirmed", "label"),
            value=round(confirmed, 1),
            unit="tonnes",
            note=step("confirmed", "note"),
        ),
        ChainStep(
            key="recovery",
            label=step("recovery", "label"),
            value=round(to_recovery, 1),
            unit="tonnes",
            note=step("recovery", "note", share=int(RECOVERY_CAPTURE_RATE * 100)),
        ),
        ChainStep(
            key="co2e",
            label=step("co2e", "label"),
            value=round(co2e, 1),
            unit="t CO2e",
            note=step("co2e", "note"),
        ),
    ]

    return ClimateImpact(
        period=period,
        companies_analysed=analysed,
        companies_flagged=flagged,
        companies_inspected=inspected,
        records_updated=records_updated,
        cities_covered=regions,
        sectors_covered=sectors,
        additional_tonnage_identified=round(identified, 1),
        additional_tonnage_confirmed=round(confirmed, 1),
        tonnage_to_formal_recovery=round(to_recovery, 1),
        estimated_gekap_revenue_try=round(estimated_revenue, 2),
        confirmed_gekap_revenue_try=round(confirmed_revenue, 2),
        co2e_avoided_tonnes=round(co2e, 1),
        by_material=material_rows(confirmed_by_sector or identified_by_sector),
        by_region=[
            ChainStep(key=region, label=region, value=round(tonnes, 1), unit="tonnes")
            for region, tonnes in region_rows
        ],
        impact_chain=impact_chain,
        social=social_impact(db, funding_available, funding_potential),
    )
