"""
Tests for recurring expense endpoints.

Coverage targets:
  routers/recurring.py — GET/POST/PUT/DELETE /recurring-expenses
                          POST /recurring-expenses/generate
"""
from datetime import datetime

import pytest

from database import RecurringExpense


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_recurring(db, user, name="Netflix", category="Entertainment",
                    planned_amount=15.0, frequency="monthly",
                    start_date=None):
    if start_date is None:
        start_date = datetime(2026, 1, 1)
    r = RecurringExpense(user_id=user.id, frequency=frequency, start_date=start_date)
    r.name = name
    r.category = category
    r.planned_amount = planned_amount
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


_VALID_PAYLOAD = {
    "name": "Gym",
    "category": "Healthcare",
    "planned_amount": 50.0,
    "frequency": "monthly",
    "start_date": "2026-01-01T00:00:00",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecurringExpensesList:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/recurring-expenses")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_own(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user)
        r = auth_client.get("/recurring-expenses")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_list_excludes_deleted(self, auth_client, db, verified_user):
        rec = _make_recurring(db, verified_user)
        rec.deleted_at = datetime.utcnow()
        db.commit()
        r = auth_client.get("/recurring-expenses")
        assert r.json() == []

    def test_list_excludes_other_user(self, auth_client, db, second_user):
        _make_recurring(db, second_user)
        r = auth_client.get("/recurring-expenses")
        assert r.json() == []

    def test_unauthenticated(self, client):
        r = client.get("/recurring-expenses")
        assert r.status_code in (401, 403)


class TestRecurringExpensesCreate:
    def test_create_returns_201(self, auth_client):
        r = auth_client.post("/recurring-expenses", json=_VALID_PAYLOAD)
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Gym"
        assert body["frequency"] == "monthly"

    def test_create_daily_frequency(self, auth_client):
        payload = {**_VALID_PAYLOAD, "frequency": "daily", "name": "Coffee"}
        r = auth_client.post("/recurring-expenses", json=payload)
        assert r.status_code == 201

    def test_create_yearly_frequency(self, auth_client):
        payload = {**_VALID_PAYLOAD, "frequency": "yearly", "name": "Renewal"}
        r = auth_client.post("/recurring-expenses", json=payload)
        assert r.status_code == 201

    def test_create_invalid_frequency(self, auth_client):
        payload = {**_VALID_PAYLOAD, "frequency": "biweekly"}
        r = auth_client.post("/recurring-expenses", json=payload)
        assert r.status_code == 422

    def test_create_unauthenticated(self, client):
        r = client.post("/recurring-expenses", json=_VALID_PAYLOAD)
        assert r.status_code in (401, 403)


class TestRecurringExpensesUpdate:
    def test_update_amount(self, auth_client, db, verified_user):
        rec = _make_recurring(db, verified_user)
        r = auth_client.put(f"/recurring-expenses/{rec.id}", json={"planned_amount": 25.0})
        assert r.status_code == 200
        assert r.json()["planned_amount"] == 25.0

    def test_update_name(self, auth_client, db, verified_user):
        rec = _make_recurring(db, verified_user)
        r = auth_client.put(f"/recurring-expenses/{rec.id}", json={"name": "Spotify"})
        assert r.status_code == 200
        assert r.json()["name"] == "Spotify"

    def test_update_wrong_user_returns_403(self, auth_client, db, second_user):
        rec = _make_recurring(db, second_user)
        r = auth_client.put(f"/recurring-expenses/{rec.id}", json={"name": "Hijacked"})
        assert r.status_code == 403

    def test_update_nonexistent_returns_404(self, auth_client):
        r = auth_client.put("/recurring-expenses/99999", json={"name": "Ghost"})
        assert r.status_code == 404

    def test_update_invalid_frequency(self, auth_client, db, verified_user):
        rec = _make_recurring(db, verified_user)
        r = auth_client.put(f"/recurring-expenses/{rec.id}", json={"frequency": "quarterly"})
        assert r.status_code == 422


class TestRecurringExpensesDelete:
    def test_delete_returns_204(self, auth_client, db, verified_user):
        rec = _make_recurring(db, verified_user)
        r = auth_client.delete(f"/recurring-expenses/{rec.id}")
        assert r.status_code == 204

    def test_delete_soft_deletes(self, auth_client, db, verified_user):
        rec = _make_recurring(db, verified_user)
        auth_client.delete(f"/recurring-expenses/{rec.id}")
        db.refresh(rec)
        assert rec.deleted_at is not None

    def test_delete_wrong_user_returns_403(self, auth_client, db, second_user):
        rec = _make_recurring(db, second_user)
        r = auth_client.delete(f"/recurring-expenses/{rec.id}")
        assert r.status_code == 403

    def test_delete_nonexistent_returns_404(self, auth_client):
        r = auth_client.delete("/recurring-expenses/99999")
        assert r.status_code == 404


class TestRecurringGenerate:
    def test_generate_returns_200(self, auth_client):
        r = auth_client.post("/recurring-expenses/generate")
        assert r.status_code == 200
        body = r.json()
        assert "generated" in body

    def test_generate_with_monthly_recurring(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user, frequency="monthly")
        r = auth_client.post("/recurring-expenses/generate")
        assert r.status_code == 200

    def test_generate_unauthenticated(self, client):
        r = client.post("/recurring-expenses/generate")
        assert r.status_code in (401, 403)
