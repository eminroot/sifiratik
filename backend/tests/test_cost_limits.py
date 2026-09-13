"""Ceilings on the endpoints that cost something to run.

The demonstration publishes its own sign-in, so being signed in says nothing
about intent: everyone through the door is a stranger. What stops one of them
from spending the machine is not the gate but these ceilings, and rescoring is
the one that matters — the whole population through the model, seven seconds a
call on the pilot server against a third of a second for everything else.

Budgets are set low here rather than run to the real ones, because the point
under test is that a ceiling exists and refuses, not how high it sits.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.security import cost_limiter


@pytest.fixture(autouse=True)
def clean_budgets():
    """Each test starts with the allowance untouched."""
    cost_limiter._calls.clear()
    yield
    cost_limiter._calls.clear()
    get_settings.cache_clear()


@pytest.fixture
def tight(monkeypatch):
    monkeypatch.setenv("SCORING_RUNS_PER_MINUTE", "2")
    monkeypatch.setenv("PILOT_RUNS_PER_MINUTE", "2")
    monkeypatch.setenv("REVIEWS_PER_MINUTE", "2")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_rescoring_is_capped(client, tight):
    """The expensive one. Left open, a script turns a demo into a load test."""
    codes = [
        client.post("/api/scoring/run", json={}).status_code for _ in range(4)
    ]
    assert codes[:2] == [200, 200]
    assert codes[2] == 429
    assert codes[3] == 429


def test_the_refusal_says_when_to_come_back(client, tight):
    for _ in range(2):
        client.post("/api/scoring/run", json={})
    refused = client.post("/api/scoring/run", json={})
    assert refused.status_code == 429
    # Without this a client has to guess, and guessing means retrying at once.
    assert int(refused.headers["Retry-After"]) >= 1
    assert "shortly" in refused.json()["detail"]


def test_recording_a_decision_is_capped(client, tight):
    """Cheap per call, but each one appends a link to the audit chain, and a
    flooded trail is a trail nobody can read."""
    body = {"status": "UNDER_REVIEW", "auditor_id": "aydin.m", "notes": "test"}
    codes = [
        client.post(f"/api/companies/{i}/review", json=body).status_code
        for i in range(1, 5)
    ]
    assert codes[:2] == [201, 201]
    assert codes[2:] == [429, 429]


def test_running_the_pilot_is_capped(client, tight):
    codes = [
        client.post("/api/cop31/pilot/run", json={"region": "Antalya"}).status_code
        for _ in range(4)
    ]
    assert codes[:2] == [201, 201]
    assert codes[2:] == [429, 429]


def test_each_operation_has_its_own_allowance(client, tight):
    """Somebody rescoring the population must not use up the allowance for
    recording a decision; they are separate budgets, not one shared pool."""
    for _ in range(3):
        client.post("/api/scoring/run", json={})
    assert client.post("/api/scoring/run", json={}).status_code == 429

    recorded = client.post(
        "/api/companies/11/review",
        json={"status": "UNDER_REVIEW", "auditor_id": "aydin.m", "notes": "test"},
    )
    assert recorded.status_code == 201


def test_reading_is_never_capped(client, tight):
    """Whatever a stranger is doing to the write endpoints, the queue stays
    readable: a demonstration that refuses to show its own data is worse than
    one somebody rescored too often."""
    for _ in range(4):
        client.post("/api/scoring/run", json={})
    for path in ("/api/dashboard", "/api/inspection-queue?limit=3", "/api/companies?limit=3"):
        assert client.get(path).status_code == 200


def test_ordinary_use_never_reaches_the_shipped_ceilings(client):
    """The defaults have to be invisible to somebody using the platform.

    A ceiling that a judge trips by clicking a button twice is a ceiling that
    turned into a bug report.
    """
    settings = get_settings()
    assert settings.scoring_runs_per_minute >= 3
    assert settings.reviews_per_minute >= 20
    assert settings.pilot_runs_per_minute >= 10

    body = {"status": "UNDER_REVIEW", "auditor_id": "aydin.m", "notes": "test"}
    codes = [
        client.post(f"/api/companies/{i}/review", json=body).status_code
        for i in range(20, 32)
    ]
    assert all(code == 201 for code in codes)
