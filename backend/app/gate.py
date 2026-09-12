"""One shared sign-in in front of the whole site.

A deployment sits on a public address, and without this anything that finds
that address can read every declaration in the demo. The gate is a door: one
username, one password, set by whoever runs the deployment. Everyone let in is
the same viewer. It is not an identity system and does not try to be — who
signed a decision is still decided by `API_KEYS` in `app/security.py`.

Two properties matter more than the size of it:

Enforced at the API, not in the interface. A gate a browser draws is a gate a
script walks around, so the check lives here and the data endpoints refuse
without it. The built interface is still served to anyone who asks, because a
login form has to come from somewhere; it carries no data, and every figure on
it arrives from an endpoint behind this check.

Closed only when configured. With `SITE_USER` and `SITE_PASSWORD` unset, this
module returns "open" and changes nothing, so a checkout still runs with no
setup. The deployment sets them.

The session is a cookie carrying its own signature. Nothing is stored
server-side, which means a restart does not sign anyone out as long as
`SESSION_SECRET` is set, and there is no session table to grow.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time

from fastapi import Request

from app.config import get_settings
from app.security import SlidingWindowLimiter

log = logging.getLogger("gus")

COOKIE_NAME = "gus_session"

# Reachable without signing in. The health check is here because Render calls
# it to decide whether the deploy came up, and a gate that fails the health
# check takes the service down with it. It reports status and engine, never
# data. The auth paths are how a signed-out caller signs in at all.
PUBLIC_API_PATHS = frozenset(
    {
        "/api/health",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/logout",
    }
)

# Gated alongside the data, because between them they describe every endpoint
# the service has.
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")

# Wrong passwords are counted here. Callers cannot be told apart behind a
# proxy without trusting a header they write themselves, so this is one budget
# for everyone — see `note_failure` for why that cannot lock anybody out.
login_limiter = SlidingWindowLimiter()
_FAILURES = "login-failures"

_process_secret = ""


def _secret() -> bytes:
    """The key the cookie is signed with.

    Configured, it survives restarts and deploys. Unconfigured, one is made
    here for the life of the process: sessions then end whenever the process
    does, which is safe but looks like a random sign-out.
    """
    global _process_secret
    configured = get_settings().session_secret.strip()
    if configured:
        return configured.encode("utf-8")
    if not _process_secret:
        _process_secret = secrets.token_urlsafe(32)
        log.warning(
            "No SESSION_SECRET is set, so sessions are signed with a key made at "
            "startup and everyone is signed out whenever the service restarts."
        )
    return _process_secret.encode("utf-8")


def enabled() -> bool:
    return get_settings().gate_enabled


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #


def check_credentials(username: str, password: str) -> bool:
    """Whether these are the configured pair, compared in constant time.

    Both halves are always compared, and the results combined afterwards, so
    the time taken says nothing about which half was wrong — a loop that
    returned early on the username would let the username be found one
    character at a time.
    """
    settings = get_settings()
    if not settings.gate_enabled:
        return False

    user_ok = hmac.compare_digest(
        settings.site_user.strip().encode("utf-8"),
        username.strip().encode("utf-8", "surrogateescape"),
    )
    password_ok = hmac.compare_digest(
        settings.site_password.encode("utf-8"),
        password.encode("utf-8", "surrogateescape"),
    )
    return user_ok and password_ok


def note_failure() -> float | None:
    """Record a wrong password; the seconds to wait if too many have piled up.

    Only failures are counted, and only after the password has been checked, so
    somebody who knows the password is never turned away by a stranger's
    guessing. That is the whole reason the budget can be shared: it slows a
    script down without ever standing between a viewer and the site.

    It is not what makes guessing hopeless. A long random password is.
    """
    return login_limiter.check(_FAILURES, get_settings().login_attempts_per_minute)


# --------------------------------------------------------------------------- #
# The session cookie
# --------------------------------------------------------------------------- #


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(username: str) -> str:
    """A signed cookie value carrying the name and when it stops being valid."""
    payload = json.dumps(
        {"u": username, "exp": int(time.time()) + get_settings().session_hours * 3600},
        separators=(",", ":"),
    ).encode("utf-8")
    body = _b64(payload)
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def read(token: str | None) -> str | None:
    """The name in a cookie that is genuine and unexpired, else None.

    The signature is checked before the contents are read, so a forged or
    edited payload never reaches the JSON parser.
    """
    if not token or "." not in token:
        return None
    body, _, presented = token.partition(".")
    try:
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(presented)):
            return None
        claims = json.loads(_unb64(body))
    except (ValueError, UnicodeDecodeError):
        # A cookie from an older secret, a truncated one, or somebody's
        # experiment. All the same answer: not signed in.
        return None

    if not isinstance(claims, dict):
        return None
    if int(claims.get("exp", 0)) <= time.time():
        return None
    user = claims.get("u")
    return user if isinstance(user, str) and user else None


def signed_in_as(request: Request) -> str | None:
    return read(request.cookies.get(COOKIE_NAME))


def cookie_settings() -> dict:
    """How the cookie is set, in one place so login and logout agree.

    httponly keeps it away from any script on the page, so an injected one
    cannot read it out. samesite=lax keeps the browser from attaching it to a
    request another site started, which is what would otherwise let a page
    elsewhere post a decision as a signed-in viewer.
    """
    settings = get_settings()
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.session_cookie_secure,
        "path": "/",
    }


# --------------------------------------------------------------------------- #
# The check itself
# --------------------------------------------------------------------------- #


def path_is_public(path: str) -> bool:
    """Whether a path is reachable without signing in.

    Everything outside /api and the documentation is the built interface: the
    shell, the stylesheet, the bundle. Those are served to anyone, because the
    sign-in form is one of them. They carry no data.
    """
    if path in PUBLIC_API_PATHS:
        return True
    if path.startswith("/api/"):
        return False
    return not any(path == doc or path.startswith(doc) for doc in DOC_PATHS)
