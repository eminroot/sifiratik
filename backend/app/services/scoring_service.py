"""Turning stored records into scoring contexts, and results back into rows.

The engine never sees the ORM. This module is the only place that knows about
both, which is what lets the model team develop against `ScoringContext` alone.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, select
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
from app.reference import SECTORS
from app.scoring.base import (
    CompanyFacts,
    GtipFacts,
    ObservationFacts,
    PeerCohort,
    PeriodFacts,
    ScoreOutcome,
    ScoringContext,
    ScoringEngine,
)
from app.scoring.registry import resolve_engine
from app.services.quality_service import build_quality


@dataclass
class RunSummary:
    period: str
    engine: str
    model_version: str
    companies_scored: int
    duration_ms: int
    level_counts: dict[str, int]


# --------------------------------------------------------------------------- #
# Context assembly
# --------------------------------------------------------------------------- #


def _period_facts(declaration: Declaration) -> PeriodFacts:
    return PeriodFacts(
        period=declaration.period,
        declared_tonnage=declaration.declared_packaging_tonnage,
        production_volume=declaration.production_volume,
        import_volume=declaration.import_volume,
        export_volume=declaration.export_volume,
        material_breakdown=declaration.material_breakdown,
        return_volume=declaration.return_volume,
        correction_volume=declaration.correction_volume,
        exemption_flag=bool(declaration.exemption_flag),
        exempt_share=declaration.exempt_share,
        bom_expected_tonnage=declaration.bom_expected_tonnage,
        bom_coverage_ratio=declaration.bom_coverage_ratio,
        data_quality_score=declaration.data_quality_score,
        data_freshness_days=declaration.data_freshness_days,
        missing_fields=tuple(
            token for token in (declaration.missing_fields or "").split(";") if token
        ),
    )


def _quantile(values: list[float], share: float) -> float | None:
    """Nearest-rank quantile of an already sorted list."""
    if not values:
        return None
    position = max(0, min(len(values) - 1, int(round(share * (len(values) - 1)))))
    return values[position]


def build_peer_index(db: Session, period: str) -> dict[tuple[str, str], PeerCohort]:
    """Packaging intensity distribution per sector and size class.

    Built from every company that reported both an amount and an output figure
    for the period, so the cohort a company is measured against is the cohort
    that actually filed.

    Two ratios are kept. `*_intensity` divides by production plus imports and
    is what the rule engine compares against. `*_per_production` divides by
    production alone, which is the ratio the model was trained on.
    """
    rows = db.execute(
        select(
            Company.sector,
            Company.company_size,
            Declaration.declared_packaging_tonnage,
            Declaration.production_volume,
            Declaration.import_volume,
        )
        .join(Declaration, Declaration.company_id == Company.id)
        .where(Declaration.period == period)
    ).all()

    buckets: dict[tuple[str, str], list[float]] = {}
    production_buckets: dict[tuple[str, str], list[float]] = {}
    for sector, size, declared, production, imports in rows:
        if declared is None:
            continue
        basis = (production or 0.0) + (imports or 0.0)
        if basis:
            buckets.setdefault((sector, size), []).append(declared / basis)
        if production:
            production_buckets.setdefault((sector, size), []).append(declared / production)

    index: dict[tuple[str, str], PeerCohort] = {}
    for key in set(buckets) | set(production_buckets):
        values = sorted(buckets.get(key, []))
        per_production = sorted(production_buckets.get(key, []))
        p25 = _quantile(per_production, 0.25)
        p75 = _quantile(per_production, 0.75)
        index[key] = PeerCohort(
            sector=key[0],
            company_size=key[1],
            member_count=len(values) or len(per_production),
            median_intensity=statistics.median(values) if values else None,
            p25_intensity=values[max(0, int(len(values) * 0.25) - 1)] if values else None,
            median_per_production=(
                statistics.median(per_production) if per_production else None
            ),
            p10_per_production=_quantile(per_production, 0.10),
            iqr_per_production=(
                p75 - p25 if p25 is not None and p75 is not None else None
            ),
            members_per_production=len(per_production),
        )
    return index


def _empty_cohort(company: Company) -> PeerCohort:
    return PeerCohort(
        sector=company.sector,
        company_size=company.company_size,
        member_count=0,
        median_intensity=None,
        p25_intensity=None,
    )


def previous_period(period: str) -> str | None:
    """The quarter before `period`, or None if it cannot be parsed."""
    try:
        year, quarter = int(period[:4]), int(period[5:])
    except (ValueError, IndexError):
        return None
    if quarter <= 1:
        return f"{year - 1}Q4"
    return f"{year}Q{quarter - 1}"


@dataclass
class PopulationBundle:
    """Everything the whole population needs, fetched once.

    Scoring used to run three queries per company inside the loop — around
    1.800 round trips for 600 companies. The rows are the same; only the
    number of trips to get them changes.
    """

    declarations: dict[int, list[Declaration]]
    observations: dict[int, list[FieldObservation]]
    gtip_lines: dict[int, list[GtipLine]]

    @classmethod
    def empty(cls) -> "PopulationBundle":
        return cls(declarations={}, observations={}, gtip_lines={})


def load_population(db: Session, period: str, company_ids: list[int] | None = None) -> PopulationBundle:
    """Three queries for the whole population instead of three per company."""

    def grouped(statement, key="company_id") -> dict[int, list]:
        out: dict[int, list] = defaultdict(list)
        for row in db.execute(statement).scalars():
            out[getattr(row, key)].append(row)
        return out

    declarations = select(Declaration).where(Declaration.period <= period)
    observations = select(FieldObservation).where(FieldObservation.period <= period)
    gtip = select(GtipLine).where(GtipLine.period == period)

    if company_ids:
        declarations = declarations.where(Declaration.company_id.in_(company_ids))
        observations = observations.where(FieldObservation.company_id.in_(company_ids))
        gtip = gtip.where(GtipLine.company_id.in_(company_ids))

    # Ordering is part of the contract: history is read in period order and
    # the engine's own-history baseline depends on it.
    return PopulationBundle(
        declarations=grouped(declarations.order_by(Declaration.company_id, Declaration.period.asc())),
        observations=grouped(
            observations.order_by(FieldObservation.company_id, FieldObservation.period.asc())
        ),
        gtip_lines=grouped(gtip.order_by(GtipLine.company_id)),
    )


def build_context(
    db: Session,
    company: Company,
    period: str,
    peer_index: dict[tuple[str, str], PeerCohort] | None = None,
    prior_peer_index: dict[tuple[str, str], PeerCohort] | None = None,
    bundle: PopulationBundle | None = None,
) -> ScoringContext | None:
    """Assemble everything the engine needs for one company and period.

    `bundle` carries rows already fetched for the whole population. Without
    it the rows are fetched for this company alone, which is what scoring a
    single record does.
    """
    if bundle is not None:
        declarations = bundle.declarations.get(company.id, [])
        observations = bundle.observations.get(company.id, [])
        gtip_lines = bundle.gtip_lines.get(company.id, [])
    else:
        declarations = (
            db.execute(
                select(Declaration)
                .where(Declaration.company_id == company.id, Declaration.period <= period)
                .order_by(Declaration.period.asc())
            )
            .scalars()
            .all()
        )

        observations = (
            db.execute(
                select(FieldObservation)
                .where(FieldObservation.company_id == company.id, FieldObservation.period <= period)
                .order_by(FieldObservation.period.asc())
            )
            .scalars()
            .all()
        )

        gtip_lines = (
            db.execute(
                select(GtipLine).where(GtipLine.company_id == company.id, GtipLine.period == period)
            )
            .scalars()
            .all()
        )

    history = [_period_facts(d) for d in declarations]

    # A company that never filed still has to be scoreable: the absence of a
    # declaration against known output is itself the finding.
    if not history or history[-1].period != period:
        latest_volumes = declarations[-1] if declarations else None
        history.append(
            PeriodFacts(
                period=period,
                declared_tonnage=None,
                production_volume=latest_volumes.production_volume if latest_volumes else None,
                import_volume=latest_volumes.import_volume if latest_volumes else None,
                export_volume=None,
            )
        )

    if peer_index is None:
        peer_index = build_peer_index(db, period)
    if prior_peer_index is None:
        earlier = previous_period(period)
        prior_peer_index = build_peer_index(db, earlier) if earlier else {}

    key = (company.sector, company.company_size)
    cohort = peer_index.get(key, _empty_cohort(company))
    prior_cohort = prior_peer_index.get(key)

    quality = build_quality(company, list(declarations), list(observations), bool(gtip_lines))
    sector = SECTORS[company.sector]

    return ScoringContext(
        company=CompanyFacts(
            id=company.id,
            company_name=company.company_name,
            tax_identifier=company.tax_identifier,
            sector=company.sector,
            region=company.region,
            company_size=company.company_size,
            registry_status=company.registry_status,
            gtip_coverage=company.gtip_coverage,
            operating_since=company.operating_since,
            weight_matrix_vintage_year=company.weight_matrix_vintage_year,
        ),
        period=period,
        history=history,
        peers=cohort,
        observations=[
            ObservationFacts(
                period=o.period,
                observed_packaging_tonnage=o.observed_packaging_tonnage,
                observation=o.observation,
                inspector=o.inspector,
                observed_at=o.observed_at,
            )
            for o in observations
        ],
        gtip_lines=[
            GtipFacts(
                period=g.period,
                gtip_code=g.gtip_code,
                description=g.description,
                quantity_tonnes=g.quantity_tonnes,
                packaging_coefficient=g.packaging_coefficient,
            )
            for g in gtip_lines
        ],
        quality=quality,
        sector_coefficient=sector["packaging_per_production"],
        import_coefficient=sector["packaging_per_import"],
        peers_prior=prior_cohort,
    )


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def persist_outcome(db: Session, outcome: ScoreOutcome) -> ScoreResult:
    # Clear the signals first and by hand. A bulk delete does not run the ORM
    # cascade, and SQLite reuses the row ids it just freed, so the replacement
    # result would otherwise adopt the previous run's signal rows as well.
    superseded = (
        db.execute(
            select(ScoreResult.id).where(
                ScoreResult.company_id == outcome.company_id,
                ScoreResult.period == outcome.period,
            )
        )
        .scalars()
        .all()
    )
    if superseded:
        db.execute(delete(SignalResult).where(SignalResult.score_result_id.in_(superseded)))
        db.execute(delete(ScoreResult).where(ScoreResult.id.in_(superseded)))

    result = ScoreResult(
        company_id=outcome.company_id,
        period=outcome.period,
        priority_score=outcome.priority_score,
        priority_level=outcome.priority_level,
        declared_tonnage=outcome.declared_tonnage,
        expected_lower_bound=outcome.expected_lower_bound,
        expected_median=outcome.expected_median,
        expected_upper_bound=outcome.expected_upper_bound,
        position=outcome.position,
        shortfall_tonnage=outcome.shortfall_tonnage,
        estimated_gekap_gap_try=outcome.estimated_gekap_gap_try,
        data_quality_score=outcome.data_quality_score,
        signal_coverage=outcome.signal_coverage,
        confidence=outcome.confidence,
        scoring_engine=outcome.scoring_engine,
        model_version=outcome.model_version,
        policy_version=outcome.policy_version,
    )
    result.signals = [
        SignalResult(
            signal_code=signal.code,
            signal_key=signal.key,
            signal_name=signal.name,
            status=signal.status,
            available=signal.available,
            score=signal.score,
            weight=signal.weight,
            contribution=signal.contribution,
            explanation=signal.explanation,
            missing_data_reason=signal.missing_data_reason,
            evidence=signal.evidence or None,
        )
        for signal in outcome.signals
    ]
    db.add(result)
    return result


def score_company(
    db: Session,
    company: Company,
    period: str,
    engine: ScoringEngine | None = None,
    peer_index: dict[tuple[str, str], PeerCohort] | None = None,
    prior_peer_index: dict[tuple[str, str], PeerCohort] | None = None,
) -> ScoreOutcome | None:
    engine = engine or resolve_engine()
    context = build_context(db, company, period, peer_index, prior_peer_index)
    if context is None:
        return None
    return engine.score(context)


def run_scoring(
    db: Session,
    period: str,
    engine_name: str | None = None,
    company_ids: list[int] | None = None,
) -> RunSummary:
    started = time.perf_counter()
    engine = resolve_engine(engine_name)
    peer_index = build_peer_index(db, period)
    earlier = previous_period(period)
    prior_peer_index = build_peer_index(db, earlier) if earlier else {}

    query = select(Company)
    if company_ids:
        query = query.where(Company.id.in_(company_ids))
    companies = db.execute(query).scalars().all()

    bundle = load_population(db, period, company_ids)

    # Assemble every context first, then hand the engine the whole batch. The
    # rule engine is indifferent, but a model engine loads its boosters once
    # and predicts over a matrix instead of a row at a time.
    contexts = [
        context
        for context in (
            build_context(db, company, period, peer_index, prior_peer_index, bundle)
            for company in companies
        )
        if context is not None
    ]

    counts: dict[str, int] = {}
    scored = 0
    for outcome in engine.score_many(contexts):
        persist_outcome(db, outcome)
        counts[outcome.priority_level] = counts.get(outcome.priority_level, 0) + 1
        scored += 1

    db.commit()

    return RunSummary(
        period=period,
        engine=engine.name,
        model_version=engine.version,
        companies_scored=scored,
        duration_ms=int((time.perf_counter() - started) * 1000),
        level_counts=counts,
    )


def latest_period(db: Session) -> str:
    period = db.execute(select(Declaration.period).order_by(Declaration.period.desc()).limit(1)).scalar_one_or_none()
    if period:
        return period
    from app.config import CURRENT_PERIOD

    return CURRENT_PERIOD


def all_periods(db: Session) -> list[str]:
    return list(
        db.execute(select(Declaration.period).distinct().order_by(Declaration.period.asc()))
        .scalars()
        .all()
    )


def active_policy_version() -> str:
    return get_policy().version
