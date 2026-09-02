"""Tamper-evident audit trail.

Every decision is appended with the hash of the decision before it, so the log
can be checked without trusting the database it sits in. Editing or deleting a
past event changes its hash and every link after it, and verification names the
first sequence number where the chain stops agreeing with itself.

    event n-1  ->  sha256(payload)  ->  previous_hash of event n

The digest covers the fields a decision is actually made of. Adding a field to
the payload is a format change, so GENESIS_HASH carries a version marker.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent

GENESIS_HASH = "0" * 64
CHAIN_FORMAT = "gus-chain-v1"


def naive_utc(moment: datetime) -> datetime:
    """The timestamp exactly as the column will store it.

    The audit columns are naive, so an aware value would hash one way going in
    and another coming back out, and the chain would fail its own check.
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(previous_hash: str, payload: dict) -> str:
    body = _canonical({"format": CHAIN_FORMAT, "previous": previous_hash, "event": payload})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def event_payload(event: AuditEvent) -> dict:
    return {
        "sequence": event.sequence,
        "company_id": event.company_id,
        "user_id": event.user_id,
        "action": event.action,
        "previous_status": event.previous_status,
        "new_status": event.new_status,
        "notes": event.notes,
        "decision_id": event.decision_id,
        "event_data": event.event_data,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def new_decision_id() -> str:
    return f"DEC-{uuid.uuid4().hex[:10].upper()}"


def append_event(
    db: Session,
    *,
    company_id: int | None,
    user_id: str,
    action: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    notes: str | None = None,
    decision_id: str | None = None,
    event_data: dict | None = None,
    created_at: datetime | None = None,
) -> AuditEvent:
    last = db.execute(select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1)).scalar_one_or_none()
    sequence = (last.sequence + 1) if last else 1
    previous_hash = last.current_hash if last else GENESIS_HASH

    event = AuditEvent(
        sequence=sequence,
        company_id=company_id,
        user_id=user_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        notes=notes,
        decision_id=decision_id,
        event_data=event_data,
        previous_hash=previous_hash,
        current_hash="",
        created_at=naive_utc(created_at or datetime.now(timezone.utc)),
    )
    event.current_hash = compute_hash(previous_hash, event_payload(event))
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Walk the log and report the first place it stops verifying."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.sequence.asc())).scalars().all()

    previous_hash = GENESIS_HASH
    for event in events:
        if event.previous_hash != previous_hash:
            return {
                "intact": False,
                "events_checked": event.sequence,
                "total_events": len(events),
                "broken_at": event.sequence,
                "reason": "The link to the previous decision does not match.",
                "head_hash": None,
            }
        expected = compute_hash(previous_hash, event_payload(event))
        if expected != event.current_hash:
            return {
                "intact": False,
                "events_checked": event.sequence,
                "total_events": len(events),
                "broken_at": event.sequence,
                "reason": "The stored digest does not match the content of the decision.",
                "head_hash": None,
            }
        previous_hash = event.current_hash

    return {
        "intact": True,
        "events_checked": len(events),
        "total_events": len(events),
        "broken_at": None,
        "reason": None,
        "head_hash": previous_hash if events else GENESIS_HASH,
    }


def chain_length(db: Session) -> int:
    return db.execute(select(func.count(AuditEvent.id))).scalar_one()
