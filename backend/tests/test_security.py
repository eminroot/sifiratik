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


def test_simultaneous_decisions_all_land_on_one_unbroken_chain():
    """Every writer reads the newest sequence number and takes the next one.

    Appended then committed without a retry, 40 decisions from 8 simultaneous
    writers saved 7 and lost 33 to the unique constraint on `sequence`. Each
    lost one was a decision an auditor had taken and the platform refused.
    """
    import threading

    from app.database.database import SessionLocal
    from app.services.audit_chain import commit_with_retry

    writers, failures = 12, []
    barrier = threading.Barrier(writers)

    def write(index: int) -> None:
        session = SessionLocal()
        try:
            barrier.wait()
            commit_with_retry(
                session,
                lambda: append_event(session, company_id=None, user_id=f"w{index}", action="TEST"),
            )
        except Exception as error:  # noqa: BLE001 - anything escaping is the failure
            failures.append(repr(error))
        finally:
            session.close()

    session = SessionLocal()
    before = verify_chain(session)["events_checked"]
    threads = [threading.Thread(target=write, args=(i,)) for i in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    report = verify_chain(session)
    session.close()
    assert not failures
    assert report["intact"] is True
    assert report["events_checked"] == before + writers


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


def test_the_gate_stays_open_until_a_key_is_configured():
    """The prototype has to keep running with no setup."""
    from app.security import auth_required, resolve_principal

    assert auth_required() is False
    assert resolve_principal(None) == ANONYMOUS


# --------------------------------------------------------------------------
# The gate, switched on
# --------------------------------------------------------------------------
@pytest.fixture
def gated(monkeypatch):
    """The service as a deployment with two auditors' keys configured."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "api_keys", "key-aydin:aydin.m,key-kaya:kaya.s")
    yield


def test_a_malformed_key_refuses_to_start_rather_than_opening_the_gate():
    """`API_KEYS=secret` used to be skipped, leaving every write open."""
    from pydantic import ValidationError

    from app.config import Settings, parse_api_keys

    with pytest.raises(ValueError):
        parse_api_keys("my-long-secret-key")
    with pytest.raises(ValueError):
        parse_api_keys("key-aydin:aydin.m,:kaya.s")
    with pytest.raises(ValidationError):
        Settings(api_keys="my-long-secret-key")

    assert parse_api_keys("key-aydin:aydin.m, ,") == {"key-aydin": "aydin.m"}


def test_weak_keys_are_named_by_owner_never_by_value():
    from app.config import weak_key_owners

    table = {"change-me-aydin": "aydin.m", "short": "kaya.s", "x" * 43: "demir.e"}
    assert weak_key_owners(table) == ["aydin.m", "kaya.s"]


def test_a_settings_error_does_not_print_the_secrets():
    """The startup error goes to the logs; the settings input holds every key."""
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError) as caught:
        Settings(api_keys="SECRET-KEY-VALUE", gemini_api_key="SECRET-GEMINI-VALUE")
    message = str(caught.value)
    assert "SECRET-KEY-VALUE" not in message
    assert "SECRET-GEMINI-VALUE" not in message
    assert "key:user" in message


def test_a_gated_service_refuses_writes_without_the_right_key(client, gated):
    body = {"status": "UNDER_REVIEW", "auditor_id": "kaya.s"}

    assert client.get("/api/health").json()["writes"] == "api-key"
    assert client.post("/api/companies/7/review", json=body).status_code == 401
    wrong = client.post("/api/companies/7/review", json=body, headers={"X-API-Key": "guess"})
    assert wrong.status_code == 403
    # Starlette decodes headers as latin-1; a non-ASCII key used to crash
    # compare_digest with a 500 instead of being refused.
    odd = client.post("/api/companies/7/review", json=body, headers={"X-API-Key": "s\xe9cret".encode("latin-1")})
    assert odd.status_code == 403
    # Reading stays open.
    assert client.get("/api/inspection-queue?limit=1").status_code == 200


def test_a_gated_service_signs_with_the_key_not_the_body(client, gated):
    response = client.post(
        "/api/companies/7/review",
        json={"status": "UNDER_REVIEW", "auditor_id": "kaya.s"},
        headers={"X-API-Key": "key-aydin"},
    )
    assert response.status_code == 201
    assert response.json()["auditor_id"] == "aydin.m"


def test_the_open_prototype_says_so(client):
    assert client.get("/api/health").json()["writes"] == "open"


def test_responses_carry_the_basic_security_headers(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    # The interface never uses cookies, so credentialed CORS is not offered.
    assert "access-control-allow-credentials" not in response.headers


# --------------------------------------------------------------------------
# Policy validation
# --------------------------------------------------------------------------
def test_every_score_lands_in_exactly_one_band():
    """A score between two whole-number limits gets the band of the number shown.

    Read as closed ranges on the raw score, 24.03 matched neither LOW (0-24)
    nor MEDIUM (25-49) and fell through to CRITICAL: 317 stored results were
    labelled critical that way, 22 of them in the period being worked. Scores
    are shown as whole numbers, so they are banded as whole numbers too.
    """
    policy = ScoringPolicy()
    cases = {
        0: "LOW", 24.03: "LOW", 24.49: "LOW", 24.5: "MEDIUM", 25: "MEDIUM",
        49.49: "MEDIUM", 49.5: "HIGH", 50: "HIGH", 74.4: "HIGH",
        74.5: "CRITICAL", 75: "CRITICAL", 100: "CRITICAL",
    }
    for score, level in cases.items():
        assert policy.band_for(score) == level, score
    with pytest.raises(ValueError):
        policy.band_for(float("nan"))


def _with(**changes) -> dict:
    return {**ScoringPolicy().model_dump(), **changes}


@pytest.mark.parametrize(
    "payload",
    [
        _with(strongest_signal_share=float("nan")),
        _with(strongest_signal_share=1.5),
        _with(min_coverage_for_confidence=-5),
        _with(weights=[{"code": "E1", "weight": -10, "enabled": True}]),
        _with(weights=[{"code": "E1", "weight": 1e308, "enabled": True}]),
        _with(weights=[{"code": "ZZ", "weight": 0.5, "enabled": True}]),
        _with(weights=[{"code": "E1", "weight": 0.5}, {"code": "E1", "weight": 0.5}]),
        _with(weights=[{"code": "E1", "weight": 0.5, "enabled": False}]),
        _with(bands=[
            {"level": "LOW", "lower": 90, "upper": 10},
            {"level": "MEDIUM", "lower": 25, "upper": 49},
            {"level": "HIGH", "lower": 50, "upper": 74},
            {"level": "CRITICAL", "lower": 75, "upper": 100},
        ]),
        _with(bands=[
            {"level": "LOW", "lower": 0, "upper": 20},
            {"level": "MEDIUM", "lower": 25, "upper": 49},
            {"level": "HIGH", "lower": 50, "upper": 74},
            {"level": "CRITICAL", "lower": 75, "upper": 100},
        ]),
    ],
)
def test_a_policy_that_would_misscore_is_refused(payload):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScoringPolicy(**payload)


def test_the_policy_endpoint_refuses_bad_values_and_keeps_the_old_policy(client):
    before = client.get("/api/scoring/policy").json()["version"]
    for body in (
        {"strongest_signal_share": "NaN"},
        {"min_coverage_for_confidence": -5},
        {"weights": [{"code": "E1", "weight": -10, "enabled": True}]},
        {"weights": [{"code": "ZZ", "weight": 0.5, "enabled": True}]},
        {"bands": [{"level": "LOW", "lower": 90, "upper": 10}]},
    ):
        assert client.put("/api/scoring/policy", json=body).status_code == 422, body
    assert client.get("/api/scoring/policy").json()["version"] == before


def test_the_last_policy_written_is_the_one_restored(db):
    """Two changes in one clock tick share a timestamp; the later one wins."""
    from datetime import datetime

    from app.models import PolicySnapshot

    before = get_policy()
    tick = datetime(2999, 6, 1)
    first = {**before.model_dump(), "version": "policy-tick-1", "strongest_signal_share": 0.2}
    second = {**before.model_dump(), "version": "policy-tick-2", "strongest_signal_share": 0.3}
    for payload in (first, second):
        db.add(PolicySnapshot(version=payload["version"], payload=payload, changed_by="test", created_at=tick))
        db.commit()
    try:
        assert policy_service.load_into_process(db).version == "policy-tick-2"
    finally:
        db.query(PolicySnapshot).filter(PolicySnapshot.version.like("policy-tick-%")).delete()
        db.commit()
        set_policy(before)


def test_changing_one_weight_leaves_the_other_signals_alone(client):
    """Sending one weight used to replace the list, switching seven signals off."""
    before = get_policy()
    try:
        response = client.put(
            "/api/scoring/policy", json={"weights": [{"code": "E1", "weight": 0.25, "enabled": True}]}
        )
        assert response.status_code == 200
        weights = {w["code"]: w for w in response.json()["weights"]}
        assert weights["E1"]["weight"] == 0.25
        assert {code for code, w in weights.items() if w["enabled"] and w["weight"] > 0} == {
            f"E{i}" for i in range(1, 9)
        }
        assert weights["E2"]["weight"] == before.weight_for("E2")
    finally:
        set_policy(before)


def test_a_policy_must_weigh_every_signal():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScoringPolicy(**_with(weights=[{"code": "E1", "weight": 0.5, "enabled": True}]))


def test_two_policy_changes_in_one_second_both_land(client):
    """The version was stamped to the second and unique: the second one failed."""
    before = get_policy()
    try:
        first = client.put("/api/scoring/policy", json={"strongest_signal_share": 0.30})
        second = client.put("/api/scoring/policy", json={"strongest_signal_share": 0.35})
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["version"] != second.json()["version"]
    finally:
        set_policy(before)


def test_an_invalid_stored_policy_does_not_stop_the_service(db):
    """A policy stored before validation existed is skipped, not fatal."""
    from datetime import datetime

    from app.models import PolicySnapshot

    before = get_policy()
    bad = {**before.model_dump(), "version": "policy-legacy-bad", "strongest_signal_share": 7}
    db.add(PolicySnapshot(version="policy-legacy-bad", payload=bad, changed_by="test", created_at=datetime(2999, 1, 1)))
    db.commit()
    try:
        assert policy_service.load_into_process(db).version == before.version
    finally:
        db.query(PolicySnapshot).filter(PolicySnapshot.version == "policy-legacy-bad").delete()
        db.commit()
        set_policy(before)


# --------------------------------------------------------------------------
# The review table, held against the chain
# --------------------------------------------------------------------------
def test_editing_a_review_row_is_caught_by_verification(db):
    """The queue reads standing from audit_reviews; the chain has to cover it."""
    from app.models import AuditReview

    review = db.query(AuditReview).order_by(AuditReview.id.asc()).first()
    original = review.status
    review.status = "NO_ACTION_REQUIRED" if original != "NO_ACTION_REQUIRED" else "UNDER_REVIEW"
    db.commit()
    try:
        report = verify_chain(db)
        assert report["intact"] is False
        assert review.decision_id in report["reason"]
    finally:
        review.status = original
        db.commit()
    assert verify_chain(db)["intact"] is True


def test_deleting_a_review_row_is_caught_by_verification(db):
    from app.models import AuditReview

    review = db.query(AuditReview).order_by(AuditReview.id.asc()).first()
    kept = {column.name: getattr(review, column.name) for column in AuditReview.__table__.columns}
    db.delete(review)
    db.commit()
    try:
        report = verify_chain(db)
        assert report["intact"] is False
        assert "removed from the review table" in report["reason"]
    finally:
        db.add(AuditReview(**kept))
        db.commit()
    assert verify_chain(db)["intact"] is True


# --------------------------------------------------------------------------
# The assistant's spending limit
# --------------------------------------------------------------------------
def test_the_limiter_forgets_idle_callers():
    """A stream of new addresses must not grow the table without end."""
    from app.security import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(window=0.0)
    limiter.PRUNE_ABOVE = 5
    for index in range(50):
        limiter.check(f"10.0.0.{index}", limit=3)
    assert len(limiter._calls) <= 6


def test_the_assistant_is_rate_limited(client, monkeypatch):
    from app.config import get_settings
    from app.security import assistant_limiter

    monkeypatch.setattr(get_settings(), "assistant_requests_per_minute", 2)
    # Never a real, paid call from the test suite, whatever the shell has set.
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    assistant_limiter._calls.clear()
    try:
        codes = [
            client.post("/api/assistant/chat", json={"message": "?"}).status_code
            for _ in range(3)
        ]
    finally:
        assistant_limiter._calls.clear()
    # No Gemini key in tests, so an allowed call answers 503; the third is refused first.
    assert codes[:2] == [503, 503]
    assert codes[2] == 429
