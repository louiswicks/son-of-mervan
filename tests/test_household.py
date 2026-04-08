"""
Tests for Phase 8.2: Multi-User Household Accounts

Covers:
- Create household
- Get my household (owner + member)
- Invite member by email (token generated, email no-op in dev)
- Join via token (success, expired, wrong email, already member)
- Remove member (owner only)
- Dissolve household (owner only)
- Combined budget view
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from database import (
    Household,
    HouseholdInvite,
    HouseholdMembership,
    MonthlyData,
    User,
    get_db,
)
from security import get_password_hash, verify_token
from core.limiter import limiter

# Re-use the conftest app import
from tests.conftest import make_month

# ── Helper to make a second auth client ──────────────────────────────────────

@pytest.fixture
def second_auth_client(db, second_user):
    """Authenticated TestClient for the second user."""
    from main import app

    def override_get_db():
        yield db

    def override_verify_token():
        return second_user.email

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_token] = override_verify_token

    original_key_func = limiter._key_func
    limiter._key_func = lambda req: str(uuid.uuid4())

    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    limiter._key_func = original_key_func
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(verify_token, None)


# ── Create household ──────────────────────────────────────────────────────────

def test_create_household(auth_client):
    r = auth_client.post("/households", json={"name": "Test Family"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test Family"
    assert len(data["members"]) == 1
    assert data["members"][0]["role"] == "owner"


def test_create_household_empty_name(auth_client):
    r = auth_client.post("/households", json={"name": "   "})
    assert r.status_code == 422


def test_create_second_household_fails(auth_client):
    auth_client.post("/households", json={"name": "First"})
    r = auth_client.post("/households", json={"name": "Second"})
    assert r.status_code == 409


# ── Get my household ──────────────────────────────────────────────────────────

def test_get_household_not_member(auth_client):
    r = auth_client.get("/households/me")
    assert r.status_code == 404


def test_get_household_owner(auth_client):
    auth_client.post("/households", json={"name": "My House"})
    r = auth_client.get("/households/me")
    assert r.status_code == 200
    assert r.json()["name"] == "My House"


# ── Invite member ─────────────────────────────────────────────────────────────

def test_invite_member(auth_client, second_user):
    auth_client.post("/households", json={"name": "Home"})
    r = auth_client.post("/households/invite", json={"email": second_user.email})
    assert r.status_code == 204


def test_invite_self_fails(auth_client, verified_user):
    auth_client.post("/households", json={"name": "Home"})
    r = auth_client.post("/households/invite", json={"email": verified_user.email})
    assert r.status_code == 422


def test_invite_non_owner_fails(db, second_auth_client, verified_user, second_user):
    # Build a household with verified_user as owner, second_user as member
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.add(HouseholdMembership(household_id=household.id, user_id=second_user.id, role="member"))
    db.commit()

    third_email = "third@example.com"
    r = second_auth_client.post("/households/invite", json={"email": third_email})
    assert r.status_code == 403


# ── Join household ────────────────────────────────────────────────────────────

def _make_invite(db, household, invitee_email, expired=False):
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = (
        datetime.utcnow() - timedelta(hours=1)
        if expired
        else datetime.utcnow() + timedelta(days=7)
    )
    invite = HouseholdInvite(
        household_id=household.id,
        invitee_email=invitee_email,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    return raw


def test_join_household(db, second_auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.commit()

    token = _make_invite(db, household, second_user.email)
    r = second_auth_client.post("/households/join", json={"token": token})
    assert r.status_code == 200
    data = r.json()
    assert any(m["user_id"] == second_user.id for m in data["members"])


def test_join_expired_invite(db, second_auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.commit()

    token = _make_invite(db, household, second_user.email, expired=True)
    r = second_auth_client.post("/households/join", json={"token": token})
    assert r.status_code == 410


def test_join_wrong_email(db, second_auth_client, verified_user, second_user):
    """Invite is addressed to a different email — second_user cannot accept."""
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.commit()

    token = _make_invite(db, household, "someone.else@example.com")
    r = second_auth_client.post("/households/join", json={"token": token})
    assert r.status_code == 403


def test_join_already_member(db, second_auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.add(HouseholdMembership(household_id=household.id, user_id=second_user.id, role="member"))
    db.commit()

    token = _make_invite(db, household, second_user.email)
    r = second_auth_client.post("/households/join", json={"token": token})
    assert r.status_code == 409


# ── Remove member ─────────────────────────────────────────────────────────────

def test_remove_member(db, auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.add(HouseholdMembership(household_id=household.id, user_id=second_user.id, role="member"))
    db.commit()

    r = auth_client.delete(f"/households/members/{second_user.id}")
    assert r.status_code == 204

    # Confirm removal
    r2 = auth_client.get("/households/me")
    member_ids = [m["user_id"] for m in r2.json()["members"]]
    assert second_user.id not in member_ids


def test_remove_self_fails(db, auth_client, verified_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.commit()

    r = auth_client.delete(f"/households/members/{verified_user.id}")
    assert r.status_code == 422


def test_member_cannot_remove_member(db, second_auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.add(HouseholdMembership(household_id=household.id, user_id=second_user.id, role="member"))
    db.commit()

    r = second_auth_client.delete(f"/households/members/{verified_user.id}")
    assert r.status_code == 403


# ── Dissolve household ────────────────────────────────────────────────────────

def test_dissolve_household(db, auth_client, verified_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.commit()

    r = auth_client.delete("/households")
    assert r.status_code == 204

    r2 = auth_client.get("/households/me")
    assert r2.status_code == 404


def test_member_cannot_dissolve(db, second_auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.add(HouseholdMembership(household_id=household.id, user_id=second_user.id, role="member"))
    db.commit()

    r = second_auth_client.delete("/households")
    assert r.status_code == 403


# ── Combined budget view ──────────────────────────────────────────────────────

def test_household_budget_combined(db, auth_client, verified_user, second_user):
    household = Household(owner_id=verified_user.id, name="Home")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.add(HouseholdMembership(household_id=household.id, user_id=second_user.id, role="member"))
    db.commit()

    # Give each member budget data for the same month
    make_month(db, verified_user, month="2026-03", salary_planned=3000, total_planned=1000,
               salary_actual=3000, total_actual=900)
    make_month(db, second_user, month="2026-03", salary_planned=2500, total_planned=800,
               salary_actual=2500, total_actual=750)

    r = auth_client.get("/households/budget", params={"month": "2026-03"})
    assert r.status_code == 200
    data = r.json()

    assert data["combined_salary_planned"] == 5500.0
    assert data["combined_salary_actual"] == 5500.0
    assert data["combined_expenses_actual"] == 1650.0
    assert len(data["members"]) == 2


def test_household_budget_missing_month(db, auth_client, verified_user):
    """Member with no data for that month should contribute zeros."""
    household = Household(owner_id=verified_user.id, name="Solo")
    db.add(household)
    db.flush()
    db.add(HouseholdMembership(household_id=household.id, user_id=verified_user.id, role="owner"))
    db.commit()

    r = auth_client.get("/households/budget", params={"month": "2026-06"})
    assert r.status_code == 200
    data = r.json()
    assert data["combined_salary_actual"] == 0.0
