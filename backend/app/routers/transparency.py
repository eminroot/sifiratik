"""What the platform claims, and what it refuses to claim.

The text lives here rather than in the interface so that the limits of the
system are served by the same API that serves its results, and cannot drift
apart from the policy actually in force.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import i18n
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


def engines_out(lang: str) -> list[EngineOut]:
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
            description=i18n.engine_string(info.description, lang),
            produces_interval=i18n.engine_string(info.produces_interval, lang),
            notes=i18n.engine_notes(info.notes, lang),
        )
        for info in list_engines()
    ]


@router.get("/transparency", response_model=TransparencyReport)
def transparency(
    lang: str = Depends(i18n.resolve_lang), db: Session = Depends(get_db)
) -> TransparencyReport:
    policy = get_policy()
    return TransparencyReport(
        disclaimer=i18n.text("disclaimer", lang),
        does=i18n.string_list("does", lang),
        does_not=i18n.string_list("does_not", lang),
        principles=[
            Principle(title=title, body=body) for title, body in i18n.principles(lang)
        ],
        active_engine=resolve_engine().name,
        engines=engines_out(lang),
        policy=policy_out(),
        signals=[
            SignalCatalogItem(
                code=item["code"],
                key=item["key"],
                name=item["name"],
                summary=i18n.signal_summary(item["code"], item["summary"], lang),
                inputs=i18n.signal_inputs(item["inputs"], lang),
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
