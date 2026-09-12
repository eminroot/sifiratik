"""The sign-in in front of the site.

The gate is what stands between a public address and every declaration in the
demo, so what is checked here is mostly what it refuses: unsigned callers,
forged cookies, and the ways a session could be made to outlive itself.

The app is built once per test with credentials in place rather than through
the shared `client` fixture, because `get_settings` is cached for the process
and the rest of the suite runs against an open service on purpose.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER = "test-only-user"
PASSWORD = "test-only-password-not-used-anywhere"
SECRET = "test-only-signing-key"


@pytest.fixture
def gated(monkeypatch):
    """A service with the gate closed, and its module reloaded to see it."""
    from app.config import get_settings

    monkeypatch.setenv("SITE_USER", USER)
    monkeypatch.setenv("SITE_PASSWORD", PASSWORD)
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    get_settings.cache_clear()

    from app import gate

    gate.login_limiter._calls.clear()
    yield gate
    get_settings.cache_clear()


@pytest.fixture
def client(gated):
    """A small app carrying the real middleware, without the whole API."""
    from app.main import site_gate
    from app.routers import auth

    app = FastAPI()
    app.middleware("http")(site_gate)
    app.include_router(auth.router, prefix="/api")

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        return {"secret": "the queue"}

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    with TestClient(app) as test_client:
        yield test_client


def sign_in(client) -> None:
    response = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# What it refuses
# --------------------------------------------------------------------------- #


def test_data_is_refused_without_a_session(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 401
    assert "the queue" not in response.text


def test_health_stays_reachable(client):
    """Render calls it to decide whether the deploy came up.

    A gate that fails the health check takes the service down with it.
    """
    assert client.get("/api/health").status_code == 200


def test_status_is_reachable_so_the_form_can_be_drawn(client):
    body = client.get("/api/auth/status").json()
    assert body == {"enabled": True, "authenticated": False, "user": None}


@pytest.mark.parametrize(
    "username,password",
    [
        (USER, "wrong"),
        ("wrong", PASSWORD),
        ("wrong", "wrong"),
        (USER, PASSWORD.upper()),
        (USER, PASSWORD + " "),
        ("", ""),
    ],
)
def test_wrong_credentials_are_refused(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert client.get("/api/dashboard").status_code == 401


def test_the_refusal_does_not_say_which_half_was_wrong(client):
    """Naming the half that was right turns one secret into two easier ones."""
    wrong_user = client.post("/api/auth/login", json={"username": "nope", "password": PASSWORD})
    wrong_password = client.post("/api/auth/login", json={"username": USER, "password": "nope"})
    assert wrong_user.json()["detail"] == wrong_password.json()["detail"]


# --------------------------------------------------------------------------- #
# What it allows
# --------------------------------------------------------------------------- #


def test_signing_in_opens_the_data(client):
    sign_in(client)
    assert client.get("/api/dashboard").json() == {"secret": "the queue"}
    assert client.get("/api/auth/status").json()["authenticated"] is True


def test_the_cookie_is_not_readable_by_script_or_sent_across_sites(client):
    """An injected script must not be able to read it out, and a page on
    another site must not be able to act with it."""
    response = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


def test_signing_out_closes_it_again(client):
    sign_in(client)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/dashboard").status_code == 401


# --------------------------------------------------------------------------- #
# The cookie itself
# --------------------------------------------------------------------------- #


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_a_genuine_cookie_reads_back(gated):
    assert gated.read(gated.issue(USER)) == USER


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "garbage",
        "no-dot-in-here",
        b64(b'{"u":"attacker","exp":9999999999}'),
        b64(b'{"u":"attacker","exp":9999999999}') + ".",
        b64(b'{"u":"attacker","exp":9999999999}') + "." + b64(b"x" * 32),
    ],
)
def test_a_forged_cookie_is_nobody(gated, token):
    assert gated.read(token) is None


def test_an_edited_payload_loses_its_signature(gated):
    """The name is signed, so it cannot be swapped for somebody else's."""
    _, _, signature = gated.issue(USER).partition(".")
    edited = b64(json.dumps({"u": "attacker", "exp": int(time.time()) + 999}).encode())
    assert gated.read(f"{edited}.{signature}") is None


def test_an_expired_cookie_is_refused_even_though_it_is_genuine(gated):
    """Correctly signed and out of time is still out of time."""
    payload = b64(json.dumps({"u": USER, "exp": int(time.time()) - 1}).encode())
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    assert gated.read(f"{payload}.{b64(signature)}") is None


def test_a_cookie_from_another_secret_is_refused(gated, monkeypatch):
    from app.config import get_settings

    token = gated.issue(USER)
    monkeypatch.setenv("SESSION_SECRET", "a-completely-different-secret")
    get_settings.cache_clear()
    assert gated.read(token) is None


# --------------------------------------------------------------------------- #
# Which paths the gate covers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    ["/api/dashboard", "/api/companies/1", "/docs", "/redoc", "/openapi.json"],
)
def test_data_and_documentation_are_behind_the_gate(gated, path):
    assert gated.path_is_public(path) is False


@pytest.mark.parametrize(
    "path",
    ["/api/health", "/api/auth/login", "/api/auth/status", "/", "/queue", "/assets/index-abc.js"],
)
def test_the_form_and_what_draws_it_stay_reachable(gated, path):
    assert gated.path_is_public(path) is True


# --------------------------------------------------------------------------- #
# Failed attempts
# --------------------------------------------------------------------------- #


def test_guessing_is_throttled(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LOGIN_ATTEMPTS_PER_MINUTE", "3")
    get_settings.cache_clear()

    codes = [
        client.post("/api/auth/login", json={"username": USER, "password": "no"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[-1] == 429


def test_the_right_password_is_never_refused_for_somebody_elses_guessing(client, monkeypatch):
    """The budget is shared, because callers cannot be told apart behind a
    proxy. It may only ever slow an attacker down, never lock out a viewer."""
    from app.config import get_settings

    monkeypatch.setenv("LOGIN_ATTEMPTS_PER_MINUTE", "2")
    get_settings.cache_clear()

    for _ in range(6):
        client.post("/api/auth/login", json={"username": USER, "password": "no"})

    response = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    assert response.status_code == 200
    assert client.get("/api/dashboard").status_code == 200


# --------------------------------------------------------------------------- #
# Unconfigured
# --------------------------------------------------------------------------- #


def test_without_credentials_nothing_is_gated(monkeypatch):
    """A checkout runs with no setup, exactly as it did before the gate."""
    from app.config import get_settings

    monkeypatch.delenv("SITE_USER", raising=False)
    monkeypatch.delenv("SITE_PASSWORD", raising=False)
    get_settings.cache_clear()

    from app import gate

    assert gate.enabled() is False
    get_settings.cache_clear()


@pytest.mark.parametrize("user,password", [(USER, ""), ("", PASSWORD), ("", "")])
def test_half_a_credential_does_not_close_the_gate(monkeypatch, user, password):
    """Better plainly open than seeming shut with a password nobody set."""
    from app.config import get_settings

    monkeypatch.setenv("SITE_USER", user)
    monkeypatch.setenv("SITE_PASSWORD", password)
    get_settings.cache_clear()

    from app import gate

    assert gate.enabled() is False
    get_settings.cache_clear()
