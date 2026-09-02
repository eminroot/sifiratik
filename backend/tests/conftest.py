"""A throwaway database per test session, built the way production is.

The tests run against the imported GÜS panel rather than fixtures written by
hand, because the behaviour worth checking is what the engine does with a
realistic mix of complete and incomplete records.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEMP_DB = Path(tempfile.gettempdir()) / "gus_dedektiv_test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["AUTO_SEED"] = "false"


@pytest.fixture(scope="session", autouse=True)
def database():
    if TEMP_DB.exists():
        TEMP_DB.unlink()

    from app.database.gus_import import bootstrap

    bootstrap(reset=True, verbose=False)
    yield
    from app.database.database import engine

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def client(database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    from app.database.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
