"""
Tests for debt payoff calculator endpoints.

Coverage targets:
  routers/debts.py — GET/POST/PUT/DELETE /debts
                     GET /debts/payoff-plan
"""
import pytest

from database import Debt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_debt(
    db,
    user,
    name="Credit Card",
    balance=5000.0,
    interest_rate=0.18,
    minimum_payment=150.0,
):
    d = Debt(user_id=user.id, interest_rate=interest_rate, minimum_payment=minimum_payment)
    d.name = name
    d.balance = balance
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


_VALID_DEBT = {
    "name": "Car Loan",
    "balance": 12000.0,
    "interest_rate": 0.06,
    "minimum_payment": 250.0,
}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestDebtsList:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/debts")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_own_debts(self, auth_client, db, verified_user):
        _make_debt(db, verified_user)
        r = auth_client.get("/debts")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "Credit Card"

    def test_list_excludes_deleted(self, auth_client, db, verified_user):
        d = _make_debt(db, verified_user)
        from datetime import datetime
        d.deleted_at = datetime.utcnow()
        db.commit()
        r = auth_client.get("/debts")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_excludes_other_users_debts(self, auth_client, db, second_user):
        _make_debt(db, second_user, name="Not Mine")
        r = auth_client.get("/debts")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestDebtsCreate:
    def test_create_returns_201(self, auth_client):
        r = auth_client.post("/debts", json=_VALID_DEBT)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Car Loan"
        assert data["balance"] == 12000.0
        assert data["interest_rate"] == 0.06
        assert data["minimum_payment"] == 250.0
        assert "id" in data

    def test_create_negative_balance_rejected(self, auth_client):
        payload = {**_VALID_DEBT, "balance": -500.0}
        r = auth_client.post("/debts", json=payload)
        assert r.status_code == 422

    def test_create_invalid_interest_rate_rejected(self, auth_client):
        payload = {**_VALID_DEBT, "interest_rate": 3.0}
        r = auth_client.post("/debts", json=payload)
        assert r.status_code == 422

    def test_create_zero_minimum_payment_rejected(self, auth_client):
        payload = {**_VALID_DEBT, "minimum_payment": 0.0}
        r = auth_client.post("/debts", json=payload)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestDebtsUpdate:
    def test_update_balance(self, auth_client, db, verified_user):
        d = _make_debt(db, verified_user)
        r = auth_client.put(f"/debts/{d.id}", json={"balance": 4500.0})
        assert r.status_code == 200
        assert r.json()["balance"] == 4500.0

    def test_update_wrong_user_returns_404(self, auth_client, db, second_user):
        d = _make_debt(db, second_user)
        r = auth_client.put(f"/debts/{d.id}", json={"balance": 1000.0})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDebtsDelete:
    def test_delete_returns_204(self, auth_client, db, verified_user):
        d = _make_debt(db, verified_user)
        r = auth_client.delete(f"/debts/{d.id}")
        assert r.status_code == 204
        # Confirm soft-deleted
        r2 = auth_client.get("/debts")
        assert r2.json() == []

    def test_delete_wrong_user_returns_404(self, auth_client, db, second_user):
        d = _make_debt(db, second_user)
        r = auth_client.delete(f"/debts/{d.id}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Payoff plan
# ---------------------------------------------------------------------------

class TestPayoffPlan:
    def test_empty_debts_returns_zero_plan(self, auth_client):
        r = auth_client.get("/debts/payoff-plan?strategy=snowball")
        assert r.status_code == 200
        data = r.json()
        assert data["months"] == []
        assert data["total_interest_paid"] == 0.0
        assert data["payoff_months"] == 0

    def test_invalid_strategy_rejected(self, auth_client):
        r = auth_client.get("/debts/payoff-plan?strategy=magic")
        assert r.status_code == 422

    def test_snowball_single_debt_pays_off(self, auth_client, db, verified_user):
        # $1000 at 12% APR, $100/month minimum — should pay off in ~11 months
        _make_debt(
            db, verified_user,
            name="Small Card",
            balance=1000.0,
            interest_rate=0.12,
            minimum_payment=100.0,
        )
        r = auth_client.get("/debts/payoff-plan?strategy=snowball")
        assert r.status_code == 200
        data = r.json()
        assert data["payoff_months"] > 0
        assert data["payoff_months"] < 15  # sanity check
        assert data["total_interest_paid"] > 0
        # Last month should show zero balance
        last_month = data["months"][-1]
        assert all(d["remaining_balance"] == 0.0 for d in last_month["debts"])

    def test_avalanche_less_interest_than_snowball(self, auth_client, db, verified_user):
        # Avalanche should pay less total interest than snowball when rates differ
        # Use one small high-rate debt and one large low-rate debt
        _make_debt(db, verified_user, name="Small High Rate", balance=800.0, interest_rate=0.24, minimum_payment=120.0)
        _make_debt(db, verified_user, name="Large Low Rate", balance=3000.0, interest_rate=0.05, minimum_payment=80.0)

        r_av = auth_client.get("/debts/payoff-plan?strategy=avalanche")
        assert r_av.status_code == 200
        total_interest_avalanche = r_av.json()["total_interest_paid"]

        r_sw = auth_client.get("/debts/payoff-plan?strategy=snowball")
        assert r_sw.status_code == 200
        total_interest_snowball = r_sw.json()["total_interest_paid"]

        # Avalanche minimises interest; snowball may cost more or equal
        assert total_interest_avalanche <= total_interest_snowball

    def test_snowball_orders_by_lowest_balance_first(self, auth_client, db, verified_user):
        # Two debts — snowball should pay low-balance one first
        _make_debt(db, verified_user, name="Big Debt", balance=5000.0, interest_rate=0.15, minimum_payment=100.0)
        _make_debt(db, verified_user, name="Small Debt", balance=500.0, interest_rate=0.15, minimum_payment=50.0)
        r = auth_client.get("/debts/payoff-plan?strategy=snowball")
        assert r.status_code == 200
        data = r.json()
        small_zeros_at = None
        big_zeros_at = None
        for m in data["months"]:
            for d in m["debts"]:
                if d["name"] == "Small Debt" and d["remaining_balance"] == 0.0 and small_zeros_at is None:
                    small_zeros_at = m["month"]
                if d["name"] == "Big Debt" and d["remaining_balance"] == 0.0 and big_zeros_at is None:
                    big_zeros_at = m["month"]
        assert small_zeros_at is not None
        assert big_zeros_at is not None
        assert small_zeros_at <= big_zeros_at
