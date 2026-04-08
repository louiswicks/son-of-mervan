"""
Tests for GET /forecast (cashflow forecasting).

Coverage targets:
  routers/forecast.py — default projection, salary_override, recurring expenses,
                         deficit detection, edge cases, auth enforcement.
"""
from datetime import datetime, timedelta

import pytest

from database import RecurringExpense


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recurring(
    db,
    user,
    name="Rent",
    category="Housing",
    planned_amount=500.0,
    frequency="monthly",
    start_date=None,
    end_date=None,
):
    if start_date is None:
        start_date = datetime(2024, 1, 1)
    r = RecurringExpense(user_id=user.id, frequency=frequency, start_date=start_date, end_date=end_date)
    r.name = name
    r.category = category
    r.planned_amount = planned_amount
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestForecastBasic:
    def test_returns_200_with_default_3_months(self, auth_client):
        r = auth_client.get("/forecast")
        assert r.status_code == 200
        body = r.json()
        assert body["months"] == 3
        assert len(body["projection"]) == 3

    def test_months_param_respected(self, auth_client):
        r = auth_client.get("/forecast?months=6")
        assert r.status_code == 200
        assert r.json()["months"] == 6
        assert len(r.json()["projection"]) == 6

    def test_months_out_of_range_rejected(self, auth_client):
        r = auth_client.get("/forecast?months=13")
        assert r.status_code == 422

    def test_projection_keys_present(self, auth_client):
        r = auth_client.get("/forecast")
        assert r.status_code == 200
        first = r.json()["projection"][0]
        for key in ("month", "projected_income", "projected_expenses", "projected_balance", "running_balance", "deficit"):
            assert key in first

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/forecast")
        assert r.status_code in (401, 403)


class TestForecastSalary:
    def test_no_data_returns_zero_income(self, auth_client):
        r = auth_client.get("/forecast")
        assert r.status_code == 200
        assert r.json()["monthly_income"] == 0.0

    def test_salary_override_used_when_provided(self, auth_client):
        r = auth_client.get("/forecast?salary_override=4000")
        assert r.status_code == 200
        body = r.json()
        assert body["monthly_income"] == 4000.0
        for month in body["projection"]:
            assert month["projected_income"] == 4000.0

    def test_salary_from_latest_month_data(self, auth_client, db, verified_user):
        from tests.conftest import make_month
        make_month(db, verified_user, month="2025-01", salary_planned=2500.0)
        make_month(db, verified_user, month="2025-06", salary_planned=3500.0)
        r = auth_client.get("/forecast")
        assert r.status_code == 200
        # Should use the latest month (2025-06) salary
        assert r.json()["monthly_income"] == 3500.0

    def test_salary_override_beats_stored_salary(self, auth_client, db, verified_user):
        from tests.conftest import make_month
        make_month(db, verified_user, month="2025-01", salary_planned=2000.0)
        r = auth_client.get("/forecast?salary_override=5000")
        assert r.json()["monthly_income"] == 5000.0


class TestForecastRecurring:
    def test_monthly_recurring_deducted(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user, planned_amount=500.0, frequency="monthly")
        r = auth_client.get("/forecast?salary_override=2000&months=1")
        assert r.status_code == 200
        month = r.json()["projection"][0]
        assert month["projected_expenses"] == 500.0
        assert month["projected_balance"] == 1500.0

    def test_deficit_flagged_when_expenses_exceed_income(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user, planned_amount=3000.0, frequency="monthly")
        r = auth_client.get("/forecast?salary_override=2000&months=1")
        assert r.status_code == 200
        month = r.json()["projection"][0]
        assert month["deficit"] is True
        assert month["projected_balance"] < 0

    def test_no_deficit_when_income_covers_expenses(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user, planned_amount=500.0, frequency="monthly")
        r = auth_client.get("/forecast?salary_override=2000&months=1")
        month = r.json()["projection"][0]
        assert month["deficit"] is False

    def test_expired_recurring_excluded(self, auth_client, db, verified_user):
        past = datetime.utcnow() - timedelta(days=10)
        _make_recurring(
            db, verified_user, planned_amount=1000.0, frequency="monthly",
            end_date=past,
        )
        r = auth_client.get("/forecast?salary_override=2000&months=1")
        month = r.json()["projection"][0]
        assert month["projected_expenses"] == 0.0

    def test_yearly_recurring_amortised(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user, planned_amount=1200.0, frequency="yearly")
        r = auth_client.get("/forecast?salary_override=2000&months=1")
        month = r.json()["projection"][0]
        # 1200 / 12 = 100 per month
        assert abs(month["projected_expenses"] - 100.0) < 0.01

    def test_running_balance_accumulates(self, auth_client, db, verified_user):
        r = auth_client.get("/forecast?salary_override=1000&months=3")
        projection = r.json()["projection"]
        # No recurring expenses so each month saves 1000
        assert abs(projection[0]["running_balance"] - 1000.0) < 0.01
        assert abs(projection[1]["running_balance"] - 2000.0) < 0.01
        assert abs(projection[2]["running_balance"] - 3000.0) < 0.01

    def test_multiple_recurring_summed(self, auth_client, db, verified_user):
        _make_recurring(db, verified_user, name="Rent", planned_amount=800.0, frequency="monthly")
        _make_recurring(db, verified_user, name="Netflix", category="Entertainment", planned_amount=15.0, frequency="monthly")
        r = auth_client.get("/forecast?salary_override=2000&months=1")
        month = r.json()["projection"][0]
        assert abs(month["projected_expenses"] - 815.0) < 0.01
