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
the caller makes about itself.

This is a gate, not an identity system. A production deployment belongs behind
the institution's own SSO with role-based access; the point here is that the
service can tell an authenticated caller from an anonymous one at all.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings


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
    settings = get_settings()
    table: dict[str, str] = {}

    for entry in settings.api_keys.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        key, _, user = entry.partition(":")
        if key.strip() and user.strip():
            table[key.strip()] = user.strip()

    single = settings.api_key.strip()
    if single:
        table.setdefault(single, settings.api_key_user.strip() or "api")

    return table


def auth_required() -> bool:
    return bool(_key_table())


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

    # Compared without short-circuiting so a wrong key takes the same time as
    # a right one.
    for candidate, user in table.items():
        if hmac.compare_digest(candidate, x_api_key):
            return Principal(user_id=user, authenticated=True)

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
