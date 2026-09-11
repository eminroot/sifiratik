"""The contract the frontend is written against, and the audit trail."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditEvent
from app.services.audit_chain import verify_chain


def test_every_read_endpoint_answers(client):
    paths = [
        "/api/health",
        "/api/meta/reference",
        "/api/dashboard",
        "/api/inspection-queue?limit=5",
        "/api/companies?limit=5",
        "/api/companies/1",
        "/api/companies/1/history",
        "/api/companies/1/signals",
        "/api/companies/1/reviews",
        "/api/companies/1/audit-history",
        "/api/data-quality",
        "/api/climate-impact",
        "/api/cop31/pilot",
        "/api/transparency",
        "/api/scoring/engines",
        "/api/scoring/policy",
        "/api/audit/events?limit=5",
        "/api/audit/verify",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_queue_is_ordered_and_ranked(client):
    payload = client.get("/api/inspection-queue?limit=25").json()
    scores = [item["priority_score"] for item in payload["items"]]
    assert scores == sorted(scores, reverse=True)
    assert [item["rank"] for item in payload["items"]] == list(range(1, len(scores) + 1))


def test_rank_survives_filtering(client):
    """A company keeps the rank it was given for the period, filtered or not."""
    by_id: dict[int, int] = {}
    offset = 0
    while True:
        page = client.get(f"/api/inspection-queue?limit=200&offset={offset}").json()
        by_id.update({item["company_id"]: item["rank"] for item in page["items"]})
        offset += len(page["items"])
        if offset >= page["total"] or not page["items"]:
            break
    assert len(by_id) == page["total"]

    filtered = client.get("/api/inspection-queue?level=CRITICAL&limit=50").json()["items"]
    assert filtered
    for item in filtered:
        assert item["rank"] == by_id[item["company_id"]]


def test_every_score_names_its_engine_and_policy(client):
    detail = client.get("/api/companies/1").json()
    score = detail["score"]
    assert score["scoring_engine"]
    assert score["model_version"]
    assert score["policy_version"]
    assert len(score["signals"]) == 8


def test_signals_report_availability_not_silence(client):
    signals = client.get("/api/companies/1/signals").json()
    for signal in signals:
        if signal["available"]:
            assert signal["score"] is not None
        else:
            assert signal["score"] is None
            assert signal["missing_data_reason"]


def test_recording_a_review_extends_the_chain(client, db):
    before = verify_chain(db)
    assert before["intact"]

    response = client.post(
        "/api/companies/2/review",
        json={
            "status": "MARKED_FOR_INSPECTION",
            "auditor_id": "demir.e",
            "notes": "Packaging store to be counted.",
        },
    )
    assert response.status_code == 201
    decision_id = response.json()["decision_id"]

    after = verify_chain(db)
    assert after["intact"]
    assert after["total_events"] == before["total_events"] + 1

    history = client.get("/api/companies/2/audit-history").json()
    assert history[0]["decision_id"] == decision_id
    assert history[0]["new_status"] == "MARKED_FOR_INSPECTION"


def test_tampering_breaks_the_chain(client, db):
    event = db.execute(
        select(AuditEvent).order_by(AuditEvent.sequence.asc()).limit(1)
    ).scalar_one()
    original = event.notes

    event.notes = "Rewritten after the fact"
    db.commit()
    broken = verify_chain(db)

    event.notes = original
    db.commit()

    assert broken["intact"] is False
    assert broken["broken_at"] == event.sequence
    assert verify_chain(db)["intact"] is True


def test_unknown_review_status_is_rejected(client):
    response = client.post(
        "/api/companies/3/review", json={"status": "CASE_CLOSED", "auditor_id": "aydin.m"}
    )
    assert response.status_code == 422


def test_scoring_run_reports_the_engine_that_produced_the_result(client):
    """A caller is never left guessing what the scores came from."""
    for requested in ("ml", "mock"):
        response = client.post("/api/scoring/run", json={"engine": requested})
        assert response.status_code == 200
        body = response.json()
        assert body["companies_scored"] > 0
        assert body["engine"] in {"ml", "mock"}
        assert body["model_version"]


def test_an_engine_that_cannot_serve_falls_back_to_the_rules(client, monkeypatch):
    """A model with no artefacts must not take the service down with it."""
    from app.scoring import ml_scorer

    monkeypatch.setattr(
        ml_scorer.MLScoringEngine, "missing_artifacts", lambda self: ["manifest.json"]
    )
    response = client.post("/api/scoring/run", json={"engine": "ml"})

    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "mock"
    assert body["companies_scored"] > 0


def test_two_rescoring_runs_at_once_both_succeed(client):
    """Two people pressing "rescore" together both get their answer."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post("/api/scoring/run", json={}), range(2)))
    assert [r.status_code for r in responses] == [200, 200]


def test_unknown_engine_is_rejected(client):
    response = client.post("/api/scoring/run", json={"engine": "guesswork"})
    assert response.status_code == 422


def test_pilot_keeps_projection_apart_from_outcome(client):
    payload = client.get("/api/cop31/pilot?region=Antalya").json()
    findings = payload["findings"]
    assert findings["companies_shortlisted"] <= findings["companies_analysed"]
    # Recovery is a projection off confirmed outcomes, so it can never exceed
    # the tonnage that was identified in the first place.
    assert findings["recovery_potential_tonnes"] <= findings["additional_tonnage"]
    assert len(payload["steps"]) == 9


def test_climate_separates_identified_from_confirmed(client):
    """A projection is never reported as an outcome.

    The two headline tonnages cover different ground: one is the period being
    worked now, the other is every filing already inspected. Neither bounds the
    other, so the check is that they stay separate figures, that anything
    carried forward comes only from what inspections established, and that the
    chain names the point where the scope changes.
    """
    payload = client.get("/api/climate-impact").json()

    assert payload["additional_tonnage_identified"] >= 0
    assert payload["additional_tonnage_confirmed"] >= 0
    # Recovery and emissions are carried from confirmed tonnage alone.
    assert payload["tonnage_to_formal_recovery"] <= payload["additional_tonnage_confirmed"]
    if payload["additional_tonnage_confirmed"] == 0:
        assert payload["co2e_avoided_tonnes"] == 0

    chain = {step["key"]: step for step in payload["impact_chain"]}
    assert {"identified", "inspected", "confirmed", "recovery"} <= set(chain)
    # The chain has to say where the scope changes, because the step before it
    # is the period being worked and the step after is every period already
    # worked. Confirmed tonnage is deliberately not bounded by the flagged
    # figure: the shortfall is measured against the bottom of the expected
    # range, so inspections routinely establish more than was claimed.
    assert "inspected" in chain["inspected"]["note"]
    assert chain["inspected"]["value"] >= 0


def test_data_quality_marks_every_field(client):
    payload = client.get("/api/data-quality").json()
    keys = {row["key"] for row in payload["field_coverage"]}
    for company in payload["companies"][:40]:
        assert set(company["fields"]) == keys
        assert all(
            state in {"AVAILABLE", "PARTIAL", "MISSING"} for state in company["fields"].values()
        )


def test_transparency_states_the_limits(client):
    payload = client.get("/api/transparency").json()
    assert "not a legal conclusion" in payload["disclaimer"]
    assert payload["does"] and payload["does_not"]
    assert len(payload["signals"]) == 8
    assert payload["audit_chain"]["intact"] is True


def test_unknown_period_is_a_404(client):
    assert client.get("/api/dashboard?period=1999Q9").status_code == 404


# --------------------------------------------------------------------------
# A decision is about one filing
# --------------------------------------------------------------------------
def test_a_decision_on_an_earlier_filing_does_not_close_this_one(client, db):
    """120 of 131 high-priority files once showed as closed on the strength
    of an inspection of a different quarter. This quarter's filing has not been
    looked at until someone looks at it."""
    from app.models import AuditReview
    from app.services.scoring_service import latest_period

    current = latest_period(db)
    # A company other tests have not already decided on for this period.
    decided_now = select(AuditReview.company_id).where(AuditReview.period == current)
    closed_before = (
        db.execute(
            select(AuditReview)
            .where(
                AuditReview.period < current,
                AuditReview.status.in_(("NO_ACTION_REQUIRED", "INSPECTION_COMPLETED")),
                AuditReview.company_id.not_in(decided_now),
            )
            .order_by(AuditReview.id.desc())
        )
        .scalars()
        .first()
    )
    assert closed_before is not None, "the seed is meant to include closed inspections"
    company_id = closed_before.company_id

    now = client.get(f"/api/companies/{company_id}?period={current}").json()
    then = client.get(f"/api/companies/{company_id}?period={closed_before.period}").json()
    assert now["review_status"] == "AWAITING_REVIEW"
    assert then["review_status"] == closed_before.status


def test_every_standing_in_the_queue_was_decided_for_that_period(client, db):
    from app.models import AuditReview
    from app.services.scoring_service import latest_period

    current = latest_period(db)
    decided = {
        company_id
        for (company_id,) in db.execute(
            select(AuditReview.company_id).where(AuditReview.period == current)
        )
    }
    items = client.get(f"/api/inspection-queue?period={current}&limit=200").json()["items"]
    for item in items:
        if item["review_status"] != "AWAITING_REVIEW":
            assert item["company_id"] in decided


def test_a_recorded_decision_carries_its_period(client, db):
    from app.models import AuditReview
    from app.services.scoring_service import all_periods

    earlier = all_periods(db)[-3]
    response = client.post(
        f"/api/companies/11/review?period={earlier}",
        json={"status": "INFORMATION_REQUESTED", "auditor_id": "demir.e"},
    )
    assert response.status_code == 201
    row = db.execute(
        select(AuditReview).where(AuditReview.decision_id == response.json()["decision_id"])
    ).scalar_one()
    assert row.period == earlier
    assert client.get(f"/api/companies/11?period={earlier}").json()["review_status"] == "INFORMATION_REQUESTED"
    assert verify_chain(db)["intact"] is True


def test_a_confirmed_tonnage_needs_a_completed_inspection(client):
    response = client.post(
        "/api/companies/12/review",
        json={"status": "UNDER_REVIEW", "confirmed_additional_tonnage": 40.0},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Periods and sizes named in a request body
# --------------------------------------------------------------------------
def test_a_period_in_the_body_is_checked_like_one_in_the_query(client):
    assert client.post("/api/scoring/run", json={"period": "2099Q1"}).status_code == 404
    assert client.post("/api/scoring/run", json={"period": "anything"}).status_code == 422
    assert client.post("/api/cop31/pilot/run", json={"period": "2099Q1"}).status_code == 404


def test_an_unknown_sector_is_refused_not_a_server_error(client):
    assert client.get("/api/cop31/pilot?sector=nonexistent").status_code == 422
    assert client.post("/api/cop31/pilot/run", json={"sector": "nonexistent"}).status_code == 422
    assert client.get("/api/cop31/pilot?sector=tekstil").status_code == 200


def test_input_that_cannot_be_echoed_is_still_refused_cleanly(client):
    """NaN, 1e309 and a lone surrogate used to turn a 422 into a 500, because
    the default error response repeats the input and cannot encode it."""
    headers = {"Content-Type": "application/json"}
    for path, method, body in (
        ("/api/scoring/policy", "PUT", '{"strongest_signal_share": NaN}'),
        ("/api/companies/9/review", "POST", '{"status": "INSPECTION_COMPLETED", "confirmed_additional_tonnage": 1e309}'),
        ("/api/companies/9/review", "POST", '{"notes": "\\ud800"}'),
    ):
        response = client.request(method, path, content=body, headers=headers)
        assert response.status_code == 422, (path, body)
        assert "input" not in response.json()["detail"][0]


def test_a_policy_change_that_changes_nothing_is_not_recorded(client, db):
    from app.models import AuditEvent

    before = db.query(AuditEvent).count()
    version = client.get("/api/scoring/policy").json()["version"]
    assert client.put("/api/scoring/policy", json={}).json()["version"] == version
    db.expire_all()
    assert db.query(AuditEvent).count() == before


def test_the_pilot_shortlist_is_bounded(client):
    assert client.get("/api/cop31/pilot?shortlist_size=0").status_code == 422
    assert client.get("/api/cop31/pilot?shortlist_size=1000000").status_code == 422
    assert client.post("/api/cop31/pilot/run", json={"shortlist_size": -1}).status_code == 422
