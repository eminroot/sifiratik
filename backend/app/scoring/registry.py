"""Engine selection.

One place decides which engine is live. Callers ask for a name or take the
configured default, and always get something that satisfies ScoringEngine.
"""

from __future__ import annotations

from app.config import ScoringPolicy, get_policy, get_settings
from app.scoring.base import EngineInfo, ScoringEngine
from app.scoring.ml_scorer import EngineNotReady, MLScoringEngine
from app.scoring.mock_scorer import MockScoringEngine

ENGINE_TYPES: dict[str, type[ScoringEngine]] = {
    "mock": MockScoringEngine,
    "ml": MLScoringEngine,
}


def build_engine(name: str | None = None, policy: ScoringPolicy | None = None) -> ScoringEngine:
    engine_name = (name or get_settings().scoring_engine or "mock").lower()
    if engine_name not in ENGINE_TYPES:
        raise KeyError(f"Unknown scoring engine: {engine_name}")
    return ENGINE_TYPES[engine_name](policy or get_policy())


def resolve_engine(name: str | None = None) -> ScoringEngine:
    """The engine to actually run with.

    A selected engine that cannot serve falls back to the rule engine rather
    than failing the request, and the response says which one produced it.
    """
    engine = build_engine(name)
    if not engine.describe().ready:
        return build_engine("mock")
    return engine


def list_engines() -> list[EngineInfo]:
    return [build_engine(name).describe() for name in ENGINE_TYPES]


__all__ = ["EngineNotReady", "build_engine", "resolve_engine", "list_engines", "ENGINE_TYPES"]
