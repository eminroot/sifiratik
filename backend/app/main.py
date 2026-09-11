"""GUS-DEDEKTIV API.

An inspection prioritisation service for GEKAP declarations. It ranks
companies by how strongly the available evidence suggests a human should look
at them, and reports what that evidence was.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings, weak_key_owners
from app.database.database import create_all
from app.routers import (
    assistant,
    climate_impact,
    companies,
    dashboard,
    inspections,
    meta,
    scoring,
    transparency,
)

settings = get_settings()
log = logging.getLogger("gus")


def writes_mode() -> str:
    return "api-key" if settings.auth_enabled else "open"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Said at every start, so an operator never has to guess whether the gate
    # is up: an open prototype is fine on a laptop and wrong on a network.
    if settings.auth_enabled:
        log.warning("Writing endpoints require X-API-Key (%d key(s) configured).", len(settings.api_key_table))
        for owner in weak_key_owners(settings.api_key_table):
            log.warning(
                "The API key for %s is short or still the example from .env.example; "
                "replace it with a long random value (e.g. python -c \"import secrets; "
                "print(secrets.token_urlsafe(32))\").",
                owner,
            )
    else:
        log.warning(
            "Writing endpoints are OPEN: no API_KEYS configured. Fine for a local demo; "
            "set API_KEYS before exposing this service to a network."
        )

    create_all()
    if settings.auto_seed:
        from app.database.gus_import import bootstrap

        bootstrap(verbose=False)

    # The stored policy outranks the defaults compiled into the process, or a
    # restart would quietly put the old thresholds back into service.
    from app.database.database import SessionLocal
    from app.services import policy_service

    db = SessionLocal()
    try:
        policy_service.load_into_process(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="GUS-DEDEKTIV",
    description=(
        "Inspection prioritisation for packaging declarations. Scores rank companies "
        "for human review. They are not findings of non-compliance."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# The interface authenticates with a header, never a cookie, so credentialed
# cross-origin requests have nothing to carry and are not allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Say where and why a request was refused, without repeating it back.

    The default response echoes the offending input. When that input is NaN,
    an out-of-range number or a broken character, it cannot be written as
    JSON, and the refusal itself failed as a server error; echoing caller
    input is also nothing a client needs in order to fix its request.
    """
    def safe(part):
        # A lone surrogate in a field name or message cannot be encoded either.
        return part if isinstance(part, int) else str(part).encode("utf-8", "replace").decode("utf-8")

    detail = [
        {
            "loc": [safe(part) for part in error.get("loc", ())],
            "msg": safe(error.get("msg", "")),
            "type": safe(error.get("type", "")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response

for router in (
    dashboard.router,
    companies.router,
    inspections.router,
    climate_impact.router,
    transparency.router,
    scoring.router,
    assistant.router,
):
    app.include_router(router, prefix=settings.api_prefix)

app.include_router(meta.router, prefix=f"{settings.api_prefix}/meta")


@app.get("/api/health", tags=["reference"])
def health() -> dict:
    from app.scoring.registry import resolve_engine

    engine = resolve_engine()
    return {
        "status": "ok",
        "engine": engine.name,
        "model_version": engine.version,
        # Whether decisions, rescoring and policy changes need X-API-Key. The
        # interface reads this to decide whether to ask for a key.
        "writes": writes_mode(),
    }
