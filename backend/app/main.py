"""GUS-DEDEKTIV API.

An inspection prioritisation service for GEKAP declarations. It ranks
companies by how strongly the available evidence suggests a human should look
at them, and reports what that evidence was.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    if settings.auto_seed:
        from app.database.gus_import import bootstrap

        bootstrap(verbose=False)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok", "engine": engine.name, "model_version": engine.version}
