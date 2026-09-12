from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import PlainModel


class LoginRequest(BaseModel):
    # Bounded so a request cannot make the service hash a megabyte. Generous
    # enough that a long passphrase is not rejected for being long.
    username: str = Field(max_length=120)
    password: str = Field(max_length=256)


class SessionOut(PlainModel):
    # Whether the site asks for a sign-in at all. False on a checkout with no
    # credentials configured, and the interface then draws no form.
    enabled: bool
    authenticated: bool
    user: str | None = None
