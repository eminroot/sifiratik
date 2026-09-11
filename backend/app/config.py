"""Runtime settings and the tunable parts of the scoring policy.

Thresholds, signal weights and the active engine are deliberately kept out of
the scoring code so an operator can change inspection policy without a deploy,
and so the future ML engine inherits the same policy surface.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# The four bands the interface, the pilot and the impact figures are written
# against, lowest first. A policy may move their limits, not rename them.
BAND_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
SIGNAL_CODES = tuple(f"E{index}" for index in range(1, 9))


def parse_api_keys(api_keys: str, api_key: str = "", api_key_user: str = "") -> dict[str, str]:
    """`key:user,key:user` as a key-to-user table.

    A malformed entry is an error, never a skip. Skipping one used to leave the
    gate open while the operator believed it was shut; refusing to start is the
    only safe way to be wrong about a credential.
    """
    table: dict[str, str] = {}
    for position, entry in enumerate(api_keys.split(","), start=1):
        entry = entry.strip()
        if not entry:
            continue
        key, separator, user = entry.partition(":")
        if not separator or not key.strip() or not user.strip():
            raise ValueError(
                f"API_KEYS entry {position} is not in key:user form. Every key needs the "
                "name of the auditor it belongs to, e.g. API_KEYS=8f2c...:aydin.m"
            )
        table[key.strip()] = user.strip()

    single = api_key.strip()
    if single:
        table.setdefault(single, api_key_user.strip() or "api")
    return table


def weak_key_owners(table: dict[str, str]) -> list[str]:
    """Owners whose key is short or still the example from .env.example.

    Returns names, never keys, so the result can go straight into a log line.
    """
    return sorted(
        user for key, user in table.items() if len(key) < 20 or "change-me" in key.lower()
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # A settings error is printed at startup, into whatever collects the
        # logs. Without this the message carries the input, and the input is
        # every API key and the Gemini key.
        hide_input_in_errors=True,
    )

    app_name: str = "GUS-DEDEKTIV"
    api_prefix: str = "/api"
    database_url: str = f"sqlite:///{(BASE_DIR / 'gus_dedektiv.db').as_posix()}"
    # Where the GÜS panel is read from at import time. Relative paths are
    # resolved against the repository root. The panel is only needed to
    # build the database; the service does not read it while running.
    panel_dir: str = "ml/data/output/csv"
    # The model engine when its artefacts are present; `resolve_engine`
    # falls back to the rule engine when they are not, so a checkout
    # without `backend/models/` still runs.
    scoring_engine: str = "ml"
    auto_seed: bool = True
    seed_random_state: int = 20260101
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    # Writing endpoints are open until a key is configured, so the prototype
    # runs with no setup. Set one of these and POST/PUT start demanding
    # X-API-Key; reading stays open either way. See app/security.py.
    api_key: str = ""
    api_key_user: str = "api"
    # key:user pairs, comma separated — 8f2c...:aydin.m,4b91...:kaya.s
    api_keys: str = ""

    # The in-app assistant. Without a key the endpoint reports itself as
    # unconfigured and the interface hides the panel rather than failing.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: float = 45.0
    # Every question is a paid call on the institution's Gemini key.
    assistant_requests_per_minute: int = Field(default=12, ge=1)

    @model_validator(mode="after")
    def _keys_parse(self) -> "Settings":
        # Parsed once at startup so a malformed key stops the service here,
        # with a message, instead of quietly leaving the gate open.
        parse_api_keys(self.api_keys, self.api_key, self.api_key_user)
        return self

    @property
    def api_key_table(self) -> dict[str, str]:
        return parse_api_keys(self.api_keys, self.api_key, self.api_key_user)

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key_table)

    @property
    def assistant_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --------------------------------------------------------------------------- #
# Scoring policy
# --------------------------------------------------------------------------- #


class PriorityBand(BaseModel):
    level: str
    lower: int = Field(ge=0, le=100)
    upper: int = Field(ge=0, le=100)


class SignalWeight(BaseModel):
    code: str
    weight: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    enabled: bool = True


class ScoringPolicy(BaseModel):
    """Everything an authority can tune without touching the model."""

    version: str = "policy-2026.1"
    bands: list[PriorityBand] = Field(
        default_factory=lambda: [
            PriorityBand(level="LOW", lower=0, upper=24),
            PriorityBand(level="MEDIUM", lower=25, upper=49),
            PriorityBand(level="HIGH", lower=50, upper=74),
            PriorityBand(level="CRITICAL", lower=75, upper=100),
        ]
    )
    weights: list[SignalWeight] = Field(
        default_factory=lambda: [
            SignalWeight(code="E1", weight=0.20),
            SignalWeight(code="E2", weight=0.18),
            SignalWeight(code="E3", weight=0.15),
            SignalWeight(code="E4", weight=0.14),
            SignalWeight(code="E5", weight=0.09),
            SignalWeight(code="E6", weight=0.07),
            SignalWeight(code="E7", weight=0.09),
            SignalWeight(code="E8", weight=0.08),
        ]
    )
    # Below this share of total signal weight the result is flagged as
    # thin evidence. It never lowers the score: absent data is not absolution.
    min_coverage_for_confidence: float = Field(default=0.55, ge=0.0, le=1.0, allow_inf_nan=False)
    # How much of the score the single strongest finding carries, against the
    # weighted average of everything that could be evaluated. Without this a
    # company that is consistently wrong in one way scores below a company
    # that is slightly wrong in several, which is not how a team triages.
    strongest_signal_share: float = Field(default=0.35, ge=0.0, le=1.0, allow_inf_nan=False)
    # Interval half-width floor and the extra width bought by poor data.
    interval_base_spread: float = Field(default=0.20, ge=0.0, le=5.0, allow_inf_nan=False)
    interval_uncertainty_spread: float = Field(default=0.55, ge=0.0, le=5.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _coherent(self) -> "ScoringPolicy":
        """A policy that would score someone wrongly is refused, not stored.

        Bands must be the four known levels, lowest first, meeting end to end
        from 0 to 100. Weights must name known signals, once each, and at least
        one enabled signal must carry weight or nothing could ever be scored.
        """
        bands = sorted(self.bands, key=lambda band: band.lower)
        if tuple(band.level for band in bands) != BAND_LEVELS:
            raise ValueError(f"Bands must be {', '.join(BAND_LEVELS)}, in that order from 0 up.")
        if bands[0].lower != 0 or bands[-1].upper != 100:
            raise ValueError("Bands must start at 0 and end at 100.")
        for band in bands:
            if band.lower > band.upper:
                raise ValueError(f"Band {band.level} ends before it starts.")
        for below, above in zip(bands, bands[1:]):
            if above.lower != below.upper + 1:
                raise ValueError(
                    f"Band {above.level} must start at {below.upper + 1}, "
                    f"straight after {below.level}, with no gap or overlap."
                )
        self.bands = bands

        codes = [item.code for item in self.weights]
        unknown = sorted(set(codes) - set(SIGNAL_CODES))
        if unknown:
            raise ValueError(f"Unknown signal codes: {', '.join(unknown)}.")
        if len(codes) != len(set(codes)):
            raise ValueError("Each signal may appear in the weights only once.")
        missing = [code for code in SIGNAL_CODES if code not in codes]
        if missing:
            # A signal absent from the policy scores as switched off. Switching
            # one off is done with enabled=false, where the trail can see it.
            raise ValueError(f"Every signal needs a weight; missing: {', '.join(missing)}.")
        if not any(item.enabled and item.weight > 0 for item in self.weights):
            raise ValueError("At least one enabled signal must carry weight.")
        return self

    def band_for(self, score: float) -> str:
        """The band a score falls in, read at whole-number precision.

        Bands are written in whole numbers (LOW 0-24, MEDIUM 25-49, ...) and
        every screen shows the score as a whole number, so the score is rounded
        half up first: a 24.6 is shown as 25 and banded MEDIUM, never shown as
        25 beside a LOW label. The bands are then read as thresholds, which
        gives every score exactly one band. Read as closed ranges on the raw
        score, a 24.03 matched neither LOW nor MEDIUM and fell through to the
        most severe band.
        """
        if not math.isfinite(score):
            raise ValueError(f"Cannot band a score of {score!r}.")
        whole = math.floor(score + 0.5)
        bands = sorted(self.bands, key=lambda band: band.lower)
        level = bands[0].level
        for band in bands:
            if whole >= band.lower:
                level = band.level
        return level

    def weight_for(self, code: str) -> float:
        for item in self.weights:
            if item.code == code:
                return item.weight if item.enabled else 0.0
        return 0.0

    def enabled_codes(self) -> list[str]:
        return [item.code for item in self.weights if item.enabled]


_policy = ScoringPolicy()


def get_policy() -> ScoringPolicy:
    return _policy


def set_policy(policy: ScoringPolicy) -> ScoringPolicy:
    global _policy
    _policy = policy
    return _policy


CURRENT_PERIOD = os.getenv("GUS_CURRENT_PERIOD", "2026Q2")
