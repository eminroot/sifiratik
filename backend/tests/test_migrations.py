"""The migrations have to build the schema the models describe.

SQLite development builds its tables from the models, so a column added to a
model without a migration goes unnoticed until someone follows the PostgreSQL
instructions and the import fails. Seventeen columns drifted that way. This
builds a database from the migrations alone and compares it with the models.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

BACKEND = Path(__file__).resolve().parents[1]


def test_migrations_build_exactly_the_models_schema(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    # In a separate process: env.py reads DATABASE_URL at import, and this
    # process's settings point at the test database.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, "AUTO_SEED": "false"},
        capture_output=True,
        text=True,
        check=True,
    )

    from app import models  # noqa: F401  (registers every mapper)
    from app.database.database import Base

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            differences = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert differences == [], f"models and migrations disagree: {differences}"
