"""Tamper-evident audit trail.

Every decision is appended with the hash of the decision before it. Editing or
deleting a past event through the application, or by hand-editing a row,
changes its hash and every link after it, and verification names the first
sequence number where the chain stops agreeing with itself.

    event n-1  ->  sha256(payload)  ->  previous_hash of event n

What this does not do is protect the log from someone who can write to the
database and is willing to recompute every digest after the one they change:
the hash is unkeyed and the anchor lives in the same database. Pinning the
head digest somewhere they cannot write (WORM storage, the institution's own
log) is what closes that, and `head_hash` in the verification report is the
value to pin. SECURITY.md says the same.

The digest covers the fields a decision is actually made of. Adding a field to
the payload is a format change, so GENESIS_HASH carries a version marker.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import AuditEvent, AuditReview, ChainAnchor

GENESIS_HASH = "0" * 64
CHAIN_FORMAT = "gus-chain-v1"

# Actions that carry a workflow decision, each mirrored by a row in
# audit_reviews under the same decision_id.
DECISION_ACTIONS = frozenset({"STATUS_CHANGE", "REVIEW_CLOSED"})

T = TypeVar("T")


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
    # Under PostgreSQL this holds every other appender at the anchor row until
    # this transaction ends, so they take sequence numbers one after another
    # instead of colliding. SQLite has no row locks and drops the clause;
    # there, commit_with_retry absorbs the collision.
    db.execute(select(ChainAnchor).where(ChainAnchor.id == 1).with_for_update())
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


def commit_with_retry(db: Session, write: Callable[[], T], attempts: int = 8) -> T:
    """Run `write` and commit it, starting over if another writer got there first.

    `append_event` reads the newest sequence number and takes the next one.
    Two decisions saved at the same moment can both read the same number; the
    unique constraint on `sequence` refuses the second, and rather than handing
    that to the caller as a server error the whole write is rolled back and
    run again against the chain as it now stands. `write` must build its rows
    from scratch each time it is called.

    A busy SQLite is retried the same way. It refuses a writer that cannot get
    the lock in time with `OperationalError`, which is the same situation as a
    lost race and wants the same answer; letting it through meant a decision
    could be dropped for no reason but timing.

    Waiting a random moment before trying again matters more than the number of
    attempts. Writers that collide once have just been serialised by the same
    lock, so retrying in step collides them again; the jitter is what breaks
    them apart. Without it, a handful of simultaneous decisions could burn
    every attempt against each other and fail as a server error.
    """
    for attempt in range(1, attempts + 1):
        try:
            result = write()
            db.commit()
            return result
        except (IntegrityError, OperationalError):
            db.rollback()
            if attempt == attempts:
                raise
            time.sleep(random.uniform(0.01, 0.05) * attempt)
    raise RuntimeError("unreachable")  # pragma: no cover


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

    mismatch = _review_mismatch(db)
    if mismatch is not None:
        sequence, reason = mismatch
        return {
            "intact": False,
            "events_checked": checked,
            "total_events": checked,
            "broken_at": sequence,
            "reason": reason,
            "head_hash": None,
            "anchored": anchor is not None,
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


def _same_tonnage(left: float | None, right: float | None) -> bool:
    # The seed records a zero correction in the chain and none in the table.
    return abs(round(left or 0.0, 3) - round(right or 0.0, 3)) < 1e-9


def _review_mismatch(db: Session) -> tuple[int | None, str] | None:
    """The first review row that no longer says what the chain recorded.

    The queue reads a company's standing from `audit_reviews`, not from the
    chain, so a chain that verifies says nothing about the standing unless the
    two are held against each other: an edited status, a review with no
    decision behind it, or a decision whose review has been deleted all change
    what the queue shows while every link still matches.

    Run only after the chain has verified, so the events it compares against
    are known to be the ones that were written. Both passes are joins streamed
    from the database; like the walk above, neither holds the log in memory.

    A review written before reviews carried a period is checked on everything
    else; its period is taken as unknown rather than as a mismatch.
    """
    decision_event = (AuditEvent.decision_id == AuditReview.decision_id) & AuditEvent.action.in_(
        DECISION_ACTIONS
    )

    pairs = db.execute(
        select(AuditReview, AuditEvent)
        .outerjoin(AuditEvent, decision_event)
        .order_by(AuditReview.id.asc())
        .execution_options(yield_per=500)
    )
    for review, event in pairs:
        if event is None:
            return None, (
                f"Decision {review.decision_id} is in the review table but was never "
                "recorded in the chain."
            )
        data = event.event_data or {}
        if (
            review.company_id != event.company_id
            or review.auditor_id != event.user_id
            or review.status != event.new_status
            or (review.notes or None) != (event.notes or None)
            or not _same_tonnage(
                review.confirmed_additional_tonnage, data.get("confirmed_additional_tonnage")
            )
            or (review.period is not None and review.period != data.get("period"))
        ):
            return event.sequence, (
                f"The review table no longer matches decision {review.decision_id} "
                "as recorded in the chain."
            )

    removed = db.execute(
        select(AuditEvent.sequence, AuditEvent.decision_id)
        .outerjoin(AuditReview, decision_event)
        .where(
            AuditEvent.action.in_(DECISION_ACTIONS),
            AuditEvent.decision_id.isnot(None),
            AuditReview.id.is_(None),
        )
        .order_by(AuditEvent.sequence.asc())
        .limit(1)
    ).first()
    if removed is not None:
        sequence, decision_id = removed
        return sequence, (
            f"Decision {decision_id} is in the chain but has been removed from the review table."
        )
    return None


def chain_length(db: Session) -> int:
    return db.execute(select(func.count(AuditEvent.id))).scalar_one()
