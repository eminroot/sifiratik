"""Signing in to the site, and asking whether you are.

Three endpoints, all reachable without a session, because they are how a
signed-out caller gets one. Everything else is behind `app/gate.py`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app import gate
from app.schemas.auth import LoginRequest, SessionOut

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("gus")


@router.get("/status", response_model=SessionOut)
def session_status(request: Request) -> SessionOut:
    """Whether the site is gated, and whether this caller is through it.

    The interface asks this before it draws anything: unguarded, it goes
    straight to the queue; guarded and signed out, it draws the sign-in form.
    """
    if not gate.enabled():
        return SessionOut(enabled=False, authenticated=True, user=None)
    user = gate.signed_in_as(request)
    return SessionOut(enabled=True, authenticated=user is not None, user=user)


@router.post("/login", response_model=SessionOut)
def login(payload: LoginRequest, response: Response) -> SessionOut:
    if not gate.enabled():
        # Nothing to sign in to. Said plainly rather than pretending to
        # accept a password that is not being checked against anything.
        return SessionOut(enabled=False, authenticated=True, user=None)

    if gate.check_credentials(payload.username, payload.password):
        response.set_cookie(
            value=gate.issue(payload.username.strip()),
            max_age=None,  # A session cookie: gone when the browser closes.
            **gate.cookie_settings(),
        )
        return SessionOut(enabled=True, authenticated=True, user=payload.username.strip())

    # Checked first, refused second: a viewer who knows the password is never
    # turned away because somebody else has been guessing.
    wait = gate.note_failure()
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-ins. Try again shortly.",
            headers={"Retry-After": str(max(1, int(wait) + 1))},
        )

    # One message for a wrong name and a wrong password, so the reply cannot
    # be used to find out which half was right.
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Wrong username or password.",
    )


@router.post("/logout", response_model=SessionOut)
def logout(response: Response) -> SessionOut:
    # Cleared with the attributes it was set with; a browser ignores a
    # deletion that does not match the cookie's path and flags.
    response.delete_cookie(**gate.cookie_settings())
    return SessionOut(enabled=gate.enabled(), authenticated=not gate.enabled(), user=None)
