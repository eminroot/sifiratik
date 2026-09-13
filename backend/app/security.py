"""Who is allowed to change something, and who they are when they do.

The prototype is meant to be cloned and run without setup, so by default every
endpoint is open — that is the demo, and `SECURITY.md` says so. What was
missing is a way to close it that does not require rewriting the service.

Set `API_KEY` and the writing endpoints start demanding `X-API-Key`. Reading
stays open, because a queue that cannot be read is not a demo of anything.
Nothing else changes: no key, no gate, same prototype.

`API_KEYS` maps a key to the person holding it:

    API_KEYS=8f2c...:aydin.m,4b91...:kaya.s

With that in place the auditor who signs a decision is the one the key belongs
to, not the name the request body asked for. Attribution stops being a claim
the caller makes about itself. A malformed entry stops the service at startup
(see `config.parse_api_keys`) rather than being skipped, which used to leave
the gate open while it looked shut.

This is a gate, not an identity system. A production deployment belongs behind
the institution's own SSO with role-based access; the point here is that the
service can tell an authenticated caller from an anonymous one at all.
"""

from __future__ import annotations

import hmac
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    """Who the request is acting as."""

    user_id: str
    authenticated: bool

    @property
    def anonymous(self) -> bool:
        return not self.authenticated


ANONYMOUS = Principal(user_id="anonymous", authenticated=False)


def _key_table() -> dict[str, str]:
    """Configured keys, mapped to the user each one stands for."""
    return get_settings().api_key_table


def auth_required() -> bool:
    return get_settings().auth_enabled


def resolve_principal(x_api_key: str | None = Header(default=None)) -> Principal:
    """The caller, whether or not a gate is configured.

    With no keys configured this always returns the anonymous principal and
    nothing is refused — the open prototype. With keys configured a wrong or
    missing key is refused here, before any handler runs.
    """
    table = _key_table()
    if not table:
        return ANONYMOUS

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This endpoint needs an X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Every configured key is compared, as bytes, whatever matched first: the
    # time taken does not depend on which key it was, and a header carrying
    # characters outside ASCII is refused like any other wrong key instead of
    # raising inside compare_digest.
    presented = x_api_key.encode("utf-8", "surrogateescape")
    matched: str | None = None
    for candidate, user in table.items():
        if hmac.compare_digest(candidate.encode("utf-8"), presented):
            matched = user

    if matched is not None:
        return Principal(user_id=matched, authenticated=True)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="That API key is not recognised.",
    )


def require_writer(principal: Principal = Depends(resolve_principal)) -> Principal:
    """Guard for anything that writes, rescores or changes policy."""
    return principal


def acting_user(principal: Principal, requested: str | None) -> str:
    """The name to record against a decision.

    Authenticated: the key's owner, never the body. A request that asks to be
    recorded as somebody else is asking for the one thing an audit trail must
    not allow.

    Open prototype: the requested name, because there is nothing better and
    pretending otherwise would make the trail look more trustworthy than it is.
    """
    if principal.authenticated:
        return principal.user_id
    return (requested or ANONYMOUS.user_id).strip() or ANONYMOUS.user_id


class SlidingWindowLimiter:
    """At most `limit` calls per caller in any `window` seconds, in process.

    Enough to stop one browser tab or one script from spending the
    institution's Gemini quota. A deployment with several workers puts the
    same rule in its gateway, where every worker's traffic is visible.

    Callers are told apart by key owner, or else by address. Behind a reverse
    proxy every request arrives from the proxy, so run uvicorn with
    `--forwarded-allow-ips` set to the proxy's address; otherwise all anonymous
    viewers share one allowance.
    """

    # Past this many tracked callers, the ones idle for a whole window are
    # dropped, so a stream of new addresses cannot grow the table forever.
    PRUNE_ABOVE = 1024

    def __init__(self, window: float = 60.0) -> None:
        self.window = window
        self._calls: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, caller: str, limit: int) -> float | None:
        """Record a call; return the seconds to wait if it is over the limit."""
        now = time.monotonic()
        with self._lock:
            if len(self._calls) > self.PRUNE_ABOVE:
                self._prune(now)
            calls = self._calls.setdefault(caller, deque())
            while calls and now - calls[0] >= self.window:
                calls.popleft()
            if len(calls) >= limit:
                return self.window - (now - calls[0])
            calls.append(now)
            return None

    def _prune(self, now: float) -> None:
        idle = [
            caller
            for caller, calls in self._calls.items()
            if not calls or now - calls[-1] >= self.window
        ]
        for caller in idle:
            del self._calls[caller]


assistant_limiter = SlidingWindowLimiter()

# One limiter for everything that costs something to run. Budgets are kept
# apart by prefixing the operation onto the key, so somebody rescoring the
# population cannot use up the allowance for recording a decision.
cost_limiter = SlidingWindowLimiter()


def _caller(request: Request, principal: Principal) -> str:
    """Who to count this call against.

    A key owner when one is configured. Otherwise the address — which behind a
    reverse proxy is the proxy's, so every anonymous viewer shares one
    allowance. That is the honest answer rather than a defect: telling them
    apart would mean trusting a header the caller writes, and a ceiling a
    caller can rewrite is not a ceiling.
    """
    if principal.authenticated:
        return principal.user_id
    return request.client.host if request.client else "unknown"


def _costly(operation: str, limit: Callable[[Settings], int], refusal: str):
    """A writer guard that also caps how often this operation may run.

    The sign-in for a demonstration is published in its own README, so being
    signed in proves nothing about intent. These ceilings are what stands
    between a stranger who read it and the machine.
    """

    def guard(request: Request, principal: Principal = Depends(require_writer)) -> Principal:
        settings = get_settings()
        wait = cost_limiter.check(f"{operation}:{_caller(request, principal)}", limit(settings))
        if wait is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=refusal,
                headers={"Retry-After": str(max(1, int(wait) + 1))},
            )
        return principal

    guard.__name__ = f"limit_{operation.replace('-', '_')}"
    return guard


def limit_assistant(
    request: Request, principal: Principal = Depends(require_writer)
) -> Principal:
    """The writer guard, plus a ceiling on paid assistant calls."""
    wait = assistant_limiter.check(
        _caller(request, principal), get_settings().assistant_requests_per_minute
    )
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many assistant questions in the last minute. Try again shortly.",
            headers={"Retry-After": str(max(1, int(wait) + 1))},
        )
    return principal


# Rescoring is the expensive one: the whole population through the model, over
# seven seconds a call on the pilot server. The others are cheap per call and
# capped because a decision that costs nothing to make still appends a link to
# the audit chain, and a flooded trail is a trail nobody can read.
limit_scoring_run = _costly(
    "scoring-run",
    lambda s: s.scoring_runs_per_minute,
    "Scoring was re-run too many times in the last minute. Try again shortly.",
)
limit_pilot_run = _costly(
    "pilot-run",
    lambda s: s.pilot_runs_per_minute,
    "The pilot was run too many times in the last minute. Try again shortly.",
)
limit_review = _costly(
    "review",
    lambda s: s.reviews_per_minute,
    "Too many decisions recorded in the last minute. Try again shortly.",
)
