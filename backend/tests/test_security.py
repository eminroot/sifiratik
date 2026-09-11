"""The properties the security work was done for.

Each test here stands for a way the platform could mislead the person reading
it: a log that reports itself intact after being cut, a policy change nobody
recorded, a decision signed with somebody else's name.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.config import ScoringPolicy, get_policy, set_policy
from app.models import AuditEvent, ChainAnchor
from app.security import ANONYMOUS, Principal, acting_user
from app.services import policy_service
from app.services.audit_chain import append_event, read_anchor, verify_chain


# --------------------------------------------------------------------------
# The chain
# --------------------------------------------------------------------------
def test_chain_notices_decisions_cut_from_the_end(db):
    """Links catch an edit in the middle. Only the anchor catches a cut tail.

    A truncated log is still internally consistent: every remaining link
    matches the one before it. Without somewhere to record where the log is
    supposed to end, deleting the last decisions reads as a clean chain --
    which is the failure that matters most, because it is the cheapest one to
    perform.
    """
    for index in range(4):
        append_event(db, company_id=None, user_id="denetci", action="TEST", notes=f"karar {index}")
    db.commit()

    assert verify_chain(db)["intact"] is True
    head = read_anchor(db)
    assert head is not None

    last = head.last_sequence
    db.execute(delete(AuditEvent).where(AuditEvent.sequence > last - 2))
    db.commit()

    report = verify_chain(db)
    assert report["intact"] is False
    assert report["broken_at"] == last - 1
    assert "removed from the end" in report["reason"]


def test_a_log_without_an_anchor_says_so_rather_than_claiming_intact(db):
    """An older log still verifies, but not against truncation. Say which."""
    append_event(db, company_id=None, user_id="denetci", action="TEST")
    db.commit()

    db.query(ChainAnchor).delete()
    db.commit()

    report = verify_chain(db)
    assert report["intact"] is True
    assert report["anchored"] is False


def test_verification_reports_the_head_it_ends_on(db):
    """The head digest is what an external system would pin the log to."""
    append_event(db, company_id=None, user_id="denetci", action="TEST")
    db.commit()

    report = verify_chain(db)
    assert report["head_hash"] == read_anchor(db).head_hash


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------
def test_a_policy_change_is_written_to_the_chain(db):
    """Scores cannot be explained without the thresholds that produced them.

    The platform recorded what auditors decided but not the policy that shaped
    those decisions, so a score could change between two readings with nothing
    in the trail to say why.
    """
    before = get_policy()
    changed = ScoringPolicy(**{**before.model_dump(), "version": "policy-test-1", "strongest_signal_share": 0.5})

    try:
        policy_service.apply_policy(db, changed, changed_by="kaya.s")

        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == policy_service.POLICY_CHANGED)
            .order_by(AuditEvent.sequence.desc())
            .first()
        )
        assert event is not None
        assert event.user_id == "kaya.s"
        assert event.previous_status == before.version
        assert event.new_status == "policy-test-1"
        assert event.event_data["current"]["strongest_signal_share"] == 0.5
        assert verify_chain(db)["intact"] is True
    finally:
        set_policy(before)


def test_a_stored_policy_survives_a_restart(db):
    """A module global reverted on restart, silently putting the old one back."""
    before = get_policy()
    changed = ScoringPolicy(**{**before.model_dump(), "version": "policy-test-2", "strongest_signal_share": 0.11})

    try:
        policy_service.apply_policy(db, changed, changed_by="kaya.s")

        # What a fresh process would do: defaults in memory, stored policy on disk.
        set_policy(ScoringPolicy())
        assert get_policy().strongest_signal_share != 0.11

        policy_service.load_into_process(db)
        assert get_policy().version == "policy-test-2"
        assert get_policy().strongest_signal_share == 0.11
    finally:
        set_policy(before)


# --------------------------------------------------------------------------
# Attribution
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "principal, requested, expected",
    [
        (Principal(user_id="aydin.m", authenticated=True), "kaya.s", "aydin.m"),
        (Principal(user_id="aydin.m", authenticated=True), None, "aydin.m"),
        (ANONYMOUS, "kaya.s", "kaya.s"),
        (ANONYMOUS, None, "anonymous"),
        (ANONYMOUS, "   ", "anonymous"),
    ],
)
def test_an_authenticated_caller_cannot_sign_as_somebody_else(principal, requested, expected):
    """The body asks; the key decides.

    Open prototype: there is no identity, so the requested name is recorded and
    the trail is honest about being unattributed. With a key configured the
    body is ignored -- a request asking to be logged as another auditor is
    asking for the one thing an audit trail must refuse.
    """
    assert acting_user(principal, requested) == expected


def test_the_gate_is_shut_until_a_key_is_configured():
    """The prototype has to keep running with no setup."""
    from app.security import auth_required, resolve_principal

    assert auth_required() is False
    assert resolve_principal(None) == ANONYMOUS
