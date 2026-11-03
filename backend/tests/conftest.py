import os
import tempfile
from pathlib import Path

import pytest

# Tests truncate tables, so they must never run against the real database.
if not os.environ.get("TEST_DATABASE_URL"):
    pytest.exit("Set TEST_DATABASE_URL to a disposable database to run the tests.", returncode=2)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="chirp-media-")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture(scope="session")
def migrated():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")


@pytest.fixture(autouse=True)
def clean_db(migrated):
    from app.db import engine

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE posts, users RESTART IDENTITY CASCADE"))


def _client() -> TestClient:
    from app.main import app

    return TestClient(app, headers={"X-Requested-With": "fetch"})


@pytest.fixture
def make_client():
    clients = []

    def factory() -> TestClient:
        c = _client()
        clients.append(c)
        return c

    yield factory
    for c in clients:
        c.close()


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def register(client: TestClient, username: str = "alice", **overrides):
    payload = {
        "email": f"{username}@example.com",
        "username": username,
        "password": "s3cretpass",
        "first_name": "Alice",
        "last_name": "Liddell",
        "age": 30,
        "address": "1 Rabbit Hole Lane, Wonderland",
    }
    payload.update(overrides)
    return client.post("/api/auth/register", json=payload)
