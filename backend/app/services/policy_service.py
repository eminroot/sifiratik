"""Reading and changing the active scoring policy.

The policy used to live only in a module global. That had two consequences
worth naming, because neither announced itself:

  - a restart silently reverted to the defaults, so an authority could change
    the weights, come back the next morning and be scoring on the old ones;
  - under more than one worker each process kept its own copy, so the same
    request could be answered with different thresholds depending on which
    worker picked it up.

The active policy is now a row. The process still keeps the cached object that
`get_policy()` returns — it is read on every scored record and must stay cheap
— but a change writes through to the database and is loaded back at startup.

Every change is also appended to the audit chain. The platform recorded what
auditors decided but not the policy that shaped those decisions; a score is not
explainable without the thresholds that produced it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ScoringPolicy, get_policy, set_policy
from app.models import PolicySnapshot
from app.services.audit_chain import append_event, naive_utc

POLICY_CHANGED = "POLICY_CHANGED"


def load_into_process(db: Session) -> ScoringPolicy:
    """Bring the stored policy into this process. Called once at startup."""
    row = db.execute(
        select(PolicySnapshot).order_by(PolicySnapshot.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    if row is None:
        return get_policy()
    return set_policy(ScoringPolicy(**row.payload))


def apply_policy(db: Session, policy: ScoringPolicy, *, changed_by: str) -> ScoringPolicy:
    """Store a new policy, put it in service and record the change.

    The write happens first. If it fails the process keeps the policy it was
    already running, which is the safer of the two ways to be wrong.
    """
    previous = get_policy()
    now = naive_utc(datetime.now(timezone.utc))

    db.add(
        PolicySnapshot(
            version=policy.version,
            payload=policy.model_dump(),
            changed_by=changed_by,
            created_at=now,
        )
    )
    db.flush()

    append_event(
        db,
        company_id=None,
        user_id=changed_by,
        action=POLICY_CHANGED,
        previous_status=previous.version,
        new_status=policy.version,
        notes="Scoring policy changed.",
        event_data={
            "previous": _summary(previous),
            "current": _summary(policy),
        },
    )
    db.commit()

    return set_policy(policy)


def _summary(policy: ScoringPolicy) -> dict:
    """What changed, small enough to read in the trail."""
    return {
        "version": policy.version,
        "weights": {item.code: item.weight for item in policy.weights if item.enabled},
        "disabled": [item.code for item in policy.weights if not item.enabled],
        "strongest_signal_share": policy.strongest_signal_share,
        "min_coverage_for_confidence": policy.min_coverage_for_confidence,
        "bands": {band.level: [band.lower, band.upper] for band in policy.bands},
    }
