"""What the platform claims, and what it refuses to claim.

The text lives here rather than in the interface so that the limits of the
system are served by the same API that serves its results, and cannot drift
apart from the policy actually in force.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_policy
from app.database.database import get_db
from app.reference import DATA_FIELDS, MATERIALS, MATERIAL_ORDER, SIGNAL_CATALOG
from app.schemas.inspection import ChainStatus
from app.schemas.scoring import BandOut, EngineOut, PolicyOut, WeightOut
from app.schemas.signal import SignalCatalogItem
from app.schemas.transparency import FieldRow, Principle, TariffRow, TransparencyReport
from app.scoring.registry import list_engines, resolve_engine
from app.services.audit_chain import verify_chain

router = APIRouter(tags=["transparency"])

DISCLAIMER = (
    "The priority score is an inspection prioritisation indicator. It is not a probability "
    "of violation and not a legal conclusion. Final decisions remain with authorised human "
    "auditors."
)

DOES = [
    "Ranks companies for inspection using the data already held about them.",
    "Compares a declaration with the same company's earlier filings.",
    "Compares a declaration with companies of similar sector, size and output.",
    "States which evidence produced each result and how much it contributed.",
    "Reports when a check could not be run, and why.",
    "Keeps every auditor decision in a log that cannot be quietly edited.",
]

DOES_NOT = [
    "Decide whether a company has broken the law.",
    "Issue penalties or start proceedings.",
    "Treat a low score as a finding of compliance.",
    "Treat missing data as evidence of good standing.",
    "Replace the judgement of the inspector who visits the site.",
]


def policy_out() -> PolicyOut:
    policy = get_policy()
    names = {item["code"]: item["name"] for item in SIGNAL_CATALOG}
    return PolicyOut(
        version=policy.version,
        bands=[BandOut(level=b.level, lower=b.lower, upper=b.upper) for b in policy.bands],
        weights=[
            WeightOut(code=w.code, name=names[w.code], weight=w.weight, enabled=w.enabled)
            for w in policy.weights
        ],
        min_coverage_for_confidence=policy.min_coverage_for_confidence,
        strongest_signal_share=policy.strongest_signal_share,
        interval_base_spread=policy.interval_base_spread,
        interval_uncertainty_spread=policy.interval_uncertainty_spread,
    )


def engines_out() -> list[EngineOut]:
    # The configured engine and the serving engine differ whenever the
    # configured one is not ready, so the flag reports the one actually in use.
    serving = resolve_engine().name
    return [
        EngineOut(
            name=info.name,
            version=info.version,
            kind=info.kind,
            ready=info.ready,
            active=info.name == serving,
            description=info.description,
            produces_interval=info.produces_interval,
            notes=info.notes,
        )
        for info in list_engines()
    ]


@router.get("/transparency", response_model=TransparencyReport)
def transparency(db: Session = Depends(get_db)) -> TransparencyReport:
    policy = get_policy()
    return TransparencyReport(
        disclaimer=DISCLAIMER,
        does=DOES,
        does_not=DOES_NOT,
        principles=[
            Principle(
                title="Absent evidence is not clean evidence",
                body="A check that cannot run is reported as unavailable and its weight is "
                "removed from the calculation. It is never recorded as a check that passed.",
            ),
            Principle(
                title="The interval widens when the inputs are thin",
                body="An expected range is only as tight as the data behind it. Where records "
                "are incomplete the range opens up, so a company is not flagged on the strength "
                "of a figure the platform never had.",
            ),
            Principle(
                title="Every score is reproducible",
                body="Each result carries the engine, the model version and the policy version "
                "that produced it, and the comparisons behind each signal are stated in full.",
            ),
            Principle(
                title="Decisions are appended, not overwritten",
                body="Changing a company's standing writes a new record linked to the one before "
                "it. Altering the history breaks the chain and the check reports where.",
            ),
        ],
        active_engine=resolve_engine().name,
        engines=engines_out(),
        policy=policy_out(),
        signals=[
            SignalCatalogItem(
                code=item["code"],
                key=item["key"],
                name=item["name"],
                summary=item["summary"],
                inputs=item["inputs"],
                weight=policy.weight_for(item["code"]),
                enabled=item["code"] in policy.enabled_codes(),
            )
            for item in SIGNAL_CATALOG
        ],
        data_fields=[FieldRow(**field) for field in DATA_FIELDS],
        tariffs=[
            TariffRow(
                key=key,
                name=MATERIALS[key]["name"],
                tariff_try_per_kg=MATERIALS[key]["tariff_try_per_kg"],
                co2e_tonnes_avoided_per_tonne=MATERIALS[key]["co2e_tonnes_avoided_per_tonne"],
            )
            for key in MATERIAL_ORDER
        ],
        tariff_year=2026,
        audit_chain=ChainStatus(**verify_chain(db), verified_at=datetime.now(timezone.utc)),
    )
