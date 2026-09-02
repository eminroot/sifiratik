"""What the scoring engine must never get wrong.

These are the properties the platform's credibility rests on, not a sweep of
every branch: absent data stays absent, the interval widens rather than
narrowing on assumptions, and the same inputs always give the same answer.
"""

from __future__ import annotations

from sqlalchemy import select

from app.config import get_policy
from app.models import Company, ScoreResult, SignalResult
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
        assert signal.status == STATUS_UNAVAILABLE
        assert signal.score is None
        assert signal.missing_data_reason
        assert signal.contribution == 0.0
        assert signal.status != STATUS_CLEAR


def test_unavailable_weight_leaves_the_denominator(db):
    """Missing data must not dilute the score of the checks that did run."""
    period = latest_period(db)
    result = (
        db.execute(
            select(ScoreResult)
            .where(ScoreResult.period == period, ScoreResult.signal_coverage < 1.0)
            .order_by(ScoreResult.priority_score.desc())
            .limit(1)
        )
        .scalar_one()
    )

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
    """A poorly evidenced company gets a wider range, never a tighter one."""
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
    assert max(well_evidenced) < min(thin)


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


def test_model_engine_is_not_ready_and_falls_back():
    """Selecting the unreleased engine serves the rule engine, and says so."""
    ml = build_engine("ml")
    assert ml.describe().ready is False
    assert resolve_engine("ml").name == "mock"
