"""Test fixtures for MES service.

Requires a running Postgres (factorylm-mes-db) or TEST_DATABASE_URL env var.

Run:
    docker compose up factorylm-mes-db -d
    cd services/mes
    DATABASE_URL="postgresql://mes:meslocal@localhost:5433/mes_core" pytest tests/ -v
"""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Allow override via env var; fall back to local compose default
DATABASE_URL = os.environ.get(
    "FACTORYLM_DATABASE_URL",
    "postgresql://mes:meslocal@localhost:5434/mes_core",
)


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()
