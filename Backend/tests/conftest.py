from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_app.db import get_database_path
from backend_app.main import create_app


@pytest.fixture()
def app(tmp_path: Path):
    db_path = tmp_path / "test_compute_rental.db"
    return create_app(str(db_path))


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_path() -> Path:
    return get_database_path()
