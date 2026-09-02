"""What the scoring engine must never get wrong.

These are the properties the platform's credibility rests on, not a sweep of
every branch: absent data stays absent, the interval widens rather than
narrowing on assumptions, and the same inputs always give the same answer.
"""

from __future__ import annotations

import statistics

from sqlalchemy import select

from app.config import get_policy
from app.models import Company, Declaration, ScoreResult, SignalResult
from app.scoring.base import STATUS_CLEAR, STATUS_UNAVAILABLE
from app.scoring.registry import build_engine, resolve_engine
from app.services.scoring_service import build_context, latest_period


def test_engine_is_deterministic(db):
    """The same company scored twice gives the same number, to the decimal."""
    period = latest_period(db)
    company = db.execute(select(Company).limit(1)).scalar_one()
    engine = resolve_engine()

    first = engine.score(build_context(db, company, period))
    second = engine.score(build_context(db, company, period))

    assert first.priority_score == second.priority_score
    assert [s.contribution for s in first.signals] == [s.contribution for s in second.signals]


def test_unavailable_signals_carry_no_score_and_a_reason(db):
    """A check that could not run is never recorded as a check that passed."""
    rows = (
        db.execute(select(SignalResult).where(SignalResult.available.is_(False)).limit(200))
        .scalars()
        .all()
    )
    assert rows, "the seed is meant to include companies with missing inputs"

    for signal in rows:
        assert signal.status in {STATUS_UNAVAILABLE, "DISABLED"}
        assert signal.score is None
        assert signal.missing_data_reason
        assert signal.status != STATUS_CLEAR


def test_a_missing_check_never_lowers_the_score(db):
    """Absent data is not absolution.

    A check that could not run carries no score, but it may still carry a
    contribution: the model is entitled to have learned that files it cannot
    check are the ones worth checking. What it must never do is let the
    absence read as a clean result, so any contribution it carries is positive
    and its reason says the absence is what raised the priority.
    """
    rows = (
        db.execute(select(SignalResult).where(SignalResult.available.is_(False)))
        .scalars()
        .all()
    )
    assert rows

    for signal in rows:
        assert signal.contribution >= 0.0
        if signal.contribution > 0:
            assert signal.score is None
            assert "raised the priority" in (signal.missing_data_reason or "")


def test_unavailable_weight_leaves_the_denominator(db):
    """Missing data must not dilute the score of the checks that did run.

    This is the rule engine's own arithmetic, so it is checked against the
    rule engine rather than against whichever engine is configured.
    """
    period = latest_period(db)
    engine = build_engine("mock")
    company = (
        db.execute(
            select(Company)
            .join(Declaration, Declaration.company_id == Company.id)
            .where(Company.has_field_data.is_(False), Declaration.period == period)
            .limit(1)
        )
        .scalars()
        .first()
    )
    assert company is not None, "the seed is meant to include companies missing inputs"
    result = engine.score(build_context(db, company, period))
    assert result.signal_coverage < 1.0

    available = [s for s in result.signals if s.available]
    weight = sum(s.weight for s in available)
    expected_mean = sum(s.weight * s.score for s in available) / weight
    strongest = max(s.score for s in available)
    share = get_policy().strongest_signal_share

    expected = round((1 - share) * expected_mean + share * strongest, 1)
    assert abs(result.priority_score - expected) < 0.15


def test_contributions_sum_to_a_hundred(db):
    period = latest_period(db)
    results = (
        db.execute(
            select(ScoreResult).where(ScoreResult.period == period, ScoreResult.priority_score > 0)
        )
        .scalars()
        .all()
    )
    assert results

    for result in results[:80]:
        total = sum(s.contribution for s in result.signals)
        assert abs(total - 100.0) < 1.0, f"{result.company_id} contributions sum to {total}"


def test_interval_widens_when_data_is_thin(db):
    """Poor evidence buys a wider range, never a tighter one.

    Stated over the population rather than per company. The rule engine sets
    the width straight from the quality score, so for it the ordering holds
    record by record. The model calibrates the width per group instead, and
    within a group a company's own record can be predicted well or badly; what
    must hold either way is that thin evidence does not buy a narrow interval.
    """
    period = latest_period(db)
    rows = (
        db.execute(
            select(ScoreResult).where(
                ScoreResult.period == period, ScoreResult.expected_median > 0
            )
        )
        .scalars()
        .all()
    )

    widths = [
        (
            row.data_quality_score,
            (row.expected_upper_bound - row.expected_lower_bound) / row.expected_median,
        )
        for row in rows
    ]
    well_evidenced = [w for q, w in widths if q >= 85]
    thin = [w for q, w in widths if q <= 55]

    assert well_evidenced and thin
    assert statistics.median(well_evidenced) < statistics.median(thin)


def test_shortfall_is_measured_against_the_lower_bound(db):
    period = latest_period(db)
    rows = (
        db.execute(
            select(ScoreResult).where(
                ScoreResult.period == period, ScoreResult.shortfall_tonnage > 0
            )
        )
        .scalars()
        .all()
    )
    assert rows

    for row in rows[:60]:
        declared = row.declared_tonnage or 0.0
        assert abs(row.shortfall_tonnage - (row.expected_lower_bound - declared)) < 0.15
        assert row.shortfall_tonnage < row.expected_median - declared + 0.15


def test_a_missing_declaration_is_not_treated_as_zero_risk(db):
    period = latest_period(db)
    rows = (
        db.execute(
            select(ScoreResult).where(
                ScoreResult.period == period, ScoreResult.declared_tonnage.is_(None)
            )
        )
        .scalars()
        .all()
    )
    assert rows, "the seed is meant to include companies that never filed"

    for row in rows:
        assert row.position == "BELOW"
        assert row.priority_score >= 50


def test_an_engine_without_artefacts_falls_back_to_the_rules(monkeypatch):
    """A model that cannot serve hands over rather than failing the request."""
    from app.scoring import ml_scorer

    monkeypatch.setattr(
        ml_scorer.MLScoringEngine, "missing_artifacts", lambda self: ["risk_model.txt"]
    )
    assert build_engine("ml").describe().ready is False
    assert resolve_engine("ml").name == "mock"


def test_both_engines_agree_on_the_shape_of_a_result(db):
    """Swapping the engine must not change the payload the frontend reads."""
    period = latest_period(db)
    company = db.execute(select(Company).limit(1)).scalar_one()
    context = build_context(db, company, period)

    results = {}
    for name in ("mock", "ml"):
        engine = build_engine(name)
        if not engine.describe().ready:
            continue
        results[name] = engine.score(context)

    assert "mock" in results
    for name, outcome in results.items():
        assert outcome.scoring_engine == name
        assert 0.0 <= outcome.priority_score <= 100.0
        assert outcome.priority_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert outcome.confidence in {"LOW", "MEDIUM", "HIGH", "NONE"}
        assert outcome.expected_lower_bound <= outcome.expected_median
        assert outcome.expected_median <= outcome.expected_upper_bound
        assert outcome.position in {"BELOW", "WITHIN", "ABOVE"}
        assert len(outcome.signals) == 8
        assert {s.code for s in outcome.signals} == {f"E{i}" for i in range(1, 9)}
        for signal in outcome.signals:
            if signal.available:
                assert signal.score is not None
                assert signal.explanation
            else:
                assert signal.score is None
                assert signal.missing_data_reason


def test_the_model_reports_its_measured_performance():
    """The engine description carries the figures it was accepted on."""
    engine = build_engine("ml")
    if not engine.describe().ready:
        return
    metrics = engine.manifest.get("metrics", {}).get("test", {})
    assert metrics.get("PR_AUC") is not None
    assert metrics.get("Precision@100") is not None
    notes = " ".join(engine.describe().notes).lower()
    assert "synthetic" in notes, "the synthetic-data limitation must be stated"
