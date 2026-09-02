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
    unfiltered = client.get("/api/inspection-queue?limit=200").json()["items"]
    by_id = {item["company_id"]: item["rank"] for item in unfiltered}

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
    payload = client.get("/api/climate-impact").json()
    assert payload["additional_tonnage_confirmed"] <= payload["additional_tonnage_identified"]
    assert payload["tonnage_to_formal_recovery"] <= payload["additional_tonnage_confirmed"]
    assert payload["confirmed_gekap_revenue_try"] <= payload["estimated_gekap_revenue_try"]


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
