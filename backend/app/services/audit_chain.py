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

from app.models import AuditEvent, ChainAnchor

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
    _move_anchor(db, event.sequence, event.current_hash)
    return event


def _move_anchor(db: Session, sequence: int, head_hash: str) -> None:
    """Record where the log is now supposed to end."""
    anchor = db.get(ChainAnchor, 1)
    now = naive_utc(datetime.now(timezone.utc))
    if anchor is None:
        db.add(ChainAnchor(id=1, last_sequence=sequence, head_hash=head_hash, updated_at=now))
    else:
        anchor.last_sequence = sequence
        anchor.head_hash = head_hash
        anchor.updated_at = now
    db.flush()


def read_anchor(db: Session) -> ChainAnchor | None:
    return db.get(ChainAnchor, 1)


def verify_chain(db: Session) -> dict:
    """Walk the log and report the first place it stops verifying.

    Two different failures are checked. A link that does not match its
    predecessor, or a digest that does not match its own content, means an
    event was edited or removed from the middle. A log that verifies cleanly
    but ends before the anchor means it was cut at the end — which the links
    alone cannot see, because a truncated chain still agrees with itself.
    """
    previous_hash = GENESIS_HASH
    checked = 0
    last_sequence = 0

    def broken(sequence: int, reason: str, total: int) -> dict:
        return {
            "intact": False,
            "events_checked": sequence,
            "total_events": total,
            "broken_at": sequence,
            "reason": reason,
            "head_hash": None,
            "anchored": read_anchor(db) is not None,
        }

    # Streamed: verification must not need the whole log in memory.
    events = db.execute(
        select(AuditEvent).order_by(AuditEvent.sequence.asc()).execution_options(yield_per=500)
    ).scalars()

    for event in events:
        if event.previous_hash != previous_hash:
            total = chain_length(db)
            return broken(event.sequence, "The link to the previous decision does not match.", total)
        if compute_hash(previous_hash, event_payload(event)) != event.current_hash:
            total = chain_length(db)
            return broken(
                event.sequence, "The stored digest does not match the content of the decision.", total
            )
        previous_hash = event.current_hash
        last_sequence = event.sequence
        checked += 1

    anchor = read_anchor(db)
    head = previous_hash if checked else GENESIS_HASH

    if anchor is not None and (anchor.last_sequence != last_sequence or anchor.head_hash != head):
        return {
            "intact": False,
            "events_checked": checked,
            "total_events": checked,
            "broken_at": last_sequence + 1,
            "reason": (
                f"The log ends at decision {last_sequence}, but the anchor expects "
                f"{anchor.last_sequence}. Decisions were removed from the end."
            ),
            "head_hash": None,
            "anchored": True,
        }

    return {
        "intact": True,
        "events_checked": checked,
        "total_events": checked,
        "broken_at": None,
        "reason": None,
        "head_hash": head,
        "anchored": anchor is not None,
    }


def chain_length(db: Session) -> int:
    return db.execute(select(func.count(AuditEvent.id))).scalar_one()
