"""
Pytest configuration and shared fixtures for the Son-of-Mervan test suite.

Strategy:
- Set all required env vars BEFORE importing any app modules.
- Patch alembic.command.upgrade/stamp so they don't run at import time.
- Use SQLite (file-based test_budget.db) so the same DB is visible to both
  the test session and to verify_token / security.py (which opens its own
  SessionLocal connection).
- Wipe all rows before each test via an autouse fixture for isolation.
"""
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet

# ── Env vars MUST be set before any application imports ──────────────────────
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-not-for-production")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_budget.db")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

# ── Patch Alembic so migrations don't execute at module import ────────────────
with patch("alembic.command.upgrade"), patch("alembic.command.stamp"):
    from main import app

from database import (
    Base,
    MonthlyData,
    MonthlyExpense,
    PasswordResetToken,
    RefreshToken,
    SessionLocal,
    User,
    engine,
    get_db,
)
from security import (
    create_access_token,
    create_email_verify_token,
    get_password_hash,
    verify_token,
)
from core.limiter import limiter

import pytest
from starlette.testclient import TestClient

# ── Create all tables once per session (idempotent) ───────────────────────────
Base.metadata.create_all(bind=engine)

# ── Constants ─────────────────────────────────────────────────────────────────
TEST_EMAIL = "user@example.com"
TEST_PASSWORD = "TestPass1!"
TEST_EMAIL_2 = "other@example.com"


# ── DB helpers (importable by test modules) ───────────────────────────────────

def make_month(
    db, user, month="2026-01",
    salary_planned=3000.0, total_planned=1000.0,
    salary_actual=0.0, total_actual=0.0,
):
    """Create a MonthlyData row owned by *user*."""
    m = MonthlyData(user_id=user.id)
    m.month = month
    m.salary_planned = salary_planned
    m.total_planned = total_planned
    m.remaining_planned = salary_planned - total_planned
    m.salary_actual = salary_actual
    m.total_actual = total_actual
    m.remaining_actual = salary_actual - total_actual
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def make_expense(db, month_row, name="Rent", category="Housing",
                 planned=800.0, actual=0.0):
    """Create a MonthlyExpense row under *month_row*."""
    e = MonthlyExpense(monthly_data_id=month_row.id)
    e.name = name
    e.category = category
    e.planned_amount = planned
    e.actual_amount = actual
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    """Truncate every table and reset rate-limit counters before each test."""
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()
    # Reset in-memory rate-limit storage so tests never see stale counters
    limiter.limiter.storage.reset()
    yield


@pytest.fixture
def db(clean_db):
    """Return a live SQLAlchemy session bound to the test database."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def verified_user(db):
    """Create a verified user in the test DB and return the ORM object."""
    user = User(
        email=TEST_EMAIL,
        password_hash=get_password_hash(TEST_PASSWORD),
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def second_user(db):
    """Create a second verified user (different email)."""
    user = User(
        email=TEST_EMAIL_2,
        password_hash=get_password_hash(TEST_PASSWORD),
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client(db):
    """Unauthenticated TestClient with get_db overridden to use the test session."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # Give every request a unique rate-limit key so we never hit 429 in tests
    original_key_func = limiter._key_func
    limiter._key_func = lambda req: str(uuid.uuid4())

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    limiter._key_func = original_key_func
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_client(db, verified_user):
    """Authenticated TestClient: get_db + verify_token both overridden."""
    def override_get_db():
        yield db

    def override_verify_token():
        return verified_user.email

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_token] = override_verify_token

    original_key_func = limiter._key_func
    limiter._key_func = lambda req: str(uuid.uuid4())

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    limiter._key_func = original_key_func
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(verify_token, None)
