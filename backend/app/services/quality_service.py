"""Data quality.

The score answers one question: how much of the picture do we actually have on
this company? It is reported next to every priority score and it is never used
to move that score up or down. A well evidenced low priority and a thinly
evidenced low priority are different things, and the interface has to be able
to tell them apart.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import Company, Declaration, FieldObservation
from app.reference import DATA_FIELDS
from app.scoring.base import DataQuality

AVAILABLE = "AVAILABLE"
PARTIAL = "PARTIAL"
MISSING = "MISSING"

_FACTOR = {AVAILABLE: 1.0, PARTIAL: 0.55, MISSING: 0.0}

FIELD_NAMES = {item["key"]: item["name"] for item in DATA_FIELDS}


def states_from(
    *,
    has_production_data: bool,
    has_current_production: bool,
    has_import_data: bool,
    has_current_import: bool,
    history_count: int,
    has_gtip_data: bool,
    has_gtip_for_period: bool,
    gtip_coverage: float,
    has_observations: bool,
    registry_status: str,
) -> dict[str, str]:
    """The per-field verdict, from primitives rather than ORM rows.

    Taking primitives keeps one definition of what counts as available, so the
    company page and the population view can never drift apart.
    """
    if has_production_data and has_current_production:
        production = AVAILABLE
    elif has_production_data:
        production = PARTIAL
    else:
        production = MISSING

    if not has_import_data:
        imports = MISSING
    elif has_current_import:
        imports = AVAILABLE
    else:
        imports = PARTIAL

    if history_count >= 6:
        history = AVAILABLE
    elif history_count >= 3:
        history = PARTIAL
    else:
        history = MISSING

    if not has_gtip_data or not has_gtip_for_period:
        gtip = MISSING
    elif gtip_coverage >= 0.8:
        gtip = AVAILABLE
    elif gtip_coverage >= 0.35:
        gtip = PARTIAL
    else:
        gtip = MISSING

    registry = {
        "MATCHED": AVAILABLE,
        "PARTIAL": PARTIAL,
        "UNREGISTERED": MISSING,
    }.get(registry_status, PARTIAL)

    return {
        "production": production,
        "import": imports,
        "history": history,
        "gtip": gtip,
        "field": AVAILABLE if has_observations else MISSING,
        "registry": registry,
    }


def field_states(
    company: Company,
    declarations: list[Declaration],
    observations: list[FieldObservation],
    has_gtip_for_period: bool,
) -> dict[str, str]:
    current = declarations[-1] if declarations else None
    return states_from(
        has_production_data=company.has_production_data,
        has_current_production=current is not None and current.production_volume is not None,
        has_import_data=company.has_import_data,
        has_current_import=current is not None and current.import_volume is not None,
        history_count=sum(1 for d in declarations if d.declared_packaging_tonnage is not None),
        has_gtip_data=company.has_gtip_data,
        has_gtip_for_period=has_gtip_for_period,
        gtip_coverage=company.gtip_coverage,
        has_observations=bool(observations),
        registry_status=company.registry_status,
    )


def build_quality(
    company: Company,
    declarations: list[Declaration],
    observations: list[FieldObservation],
    has_gtip_for_period: bool,
) -> DataQuality:
    states = field_states(company, declarations, observations, has_gtip_for_period)

    raw = sum(item["weight"] * _FACTOR[states[item["key"]]] for item in DATA_FIELDS)
    score = raw * 100

    last_update = company.last_data_update
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    freshness_days = max(0, (datetime.now(timezone.utc) - last_update).days)

    # Stale inputs are still inputs, so the penalty is bounded and small.
    if freshness_days > 180:
        score -= min(8.0, (freshness_days - 180) / 45.0)

    score = round(max(0.0, min(100.0, score)), 1)

    return DataQuality(
        score=score,
        fields=states,
        missing_fields=[FIELD_NAMES[key] for key, state in states.items() if state == MISSING],
        freshness_days=freshness_days,
        last_update=last_update,
    )
