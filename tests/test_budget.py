"""Tests for budget calculation, monthly-tracker, and annual overview endpoints."""
import pytest

from conftest import make_month, make_expense
from database import MonthlyData, MonthlyExpense


STANDARD_EXPENSES = [
    {"name": "Rent", "amount": 800, "category": "Housing"},
    {"name": "Groceries", "amount": 300, "category": "Food"},
]


class TestCalculateBudget:
    def test_readonly_returns_computed_totals(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026-01",
            "monthly_salary": 3000,
            "expenses": STANDARD_EXPENSES,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["committed"] is False
        assert data["id"] is None
        assert data["total_expenses"] == 1100.0
        assert data["remaining_budget"] == 1900.0

    def test_readonly_does_not_save_to_db(self, auth_client, db, verified_user):
        auth_client.post("/calculate-budget", json={
            "month": "2026-02",
            "monthly_salary": 3000,
            "expenses": STANDARD_EXPENSES,
        })
        count = db.query(MonthlyData).filter(MonthlyData.user_id == verified_user.id).count()
        assert count == 0

    def test_commit_saves_month_to_db(self, auth_client, db, verified_user):
        r = auth_client.post("/calculate-budget?commit=true", json={
            "month": "2026-03",
            "monthly_salary": 3000,
            "expenses": STANDARD_EXPENSES,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["committed"] is True
        assert data["id"] is not None

        month = db.query(MonthlyData).filter(MonthlyData.user_id == verified_user.id).first()
        assert month is not None
        assert month.salary_planned == 3000.0
        assert month.total_planned == 1100.0

    def test_commit_saves_expense_rows(self, auth_client, db, verified_user):
        auth_client.post("/calculate-budget?commit=true", json={
            "month": "2026-04",
            "monthly_salary": 3000,
            "expenses": STANDARD_EXPENSES,
        })
        expenses = db.query(MonthlyExpense).all()
        assert len(expenses) == 2

    def test_commit_upserts_existing_expense(self, auth_client, db, verified_user):
        """Re-committing the same expense should update it, not duplicate it."""
        auth_client.post("/calculate-budget?commit=true", json={
            "month": "2026-05",
            "monthly_salary": 3000,
            "expenses": [{"name": "Rent", "amount": 800, "category": "Housing"}],
        })
        auth_client.post("/calculate-budget?commit=true", json={
            "month": "2026-05",
            "monthly_salary": 3000,
            "expenses": [{"name": "Rent", "amount": 900, "category": "Housing"}],
        })

        expenses = db.query(MonthlyExpense).filter(MonthlyExpense.deleted_at == None).all()  # noqa: E711
        housing = [e for e in expenses if e.name == "Rent" and e.category == "Housing"]
        assert len(housing) == 1
        assert housing[0].planned_amount == 900.0

    def test_overspend_recommendation(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026-06",
            "monthly_salary": 1000,
            "expenses": [{"name": "Rent", "amount": 1200, "category": "Housing"}],
        })
        data = r.json()
        assert data["remaining_budget"] == -200.0
        assert any("overspend" in rec.lower() for rec in data["recommendations"])

    def test_good_surplus_recommendation(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026-07",
            "monthly_salary": 3000,
            "expenses": [{"name": "Rent", "amount": 500, "category": "Housing"}],
        })
        data = r.json()
        assert any("excellent" in rec.lower() or "healthy" in rec.lower()
                   for rec in data["recommendations"])

    def test_savings_rate_calculation(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026-08",
            "monthly_salary": 2000,
            "expenses": [{"name": "Rent", "amount": 500, "category": "Housing"}],
        })
        assert r.json()["savings_rate"] == pytest.approx(75.0)

    def test_category_breakdown_in_response(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026-09",
            "monthly_salary": 3000,
            "expenses": STANDARD_EXPENSES,
        })
        cats = r.json()["expenses_by_category"]
        assert "Housing" in cats
        assert "Food" in cats
        assert cats["Housing"] == 800.0

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026/01",
            "monthly_salary": 3000,
            "expenses": [],
        })
        assert r.status_code == 422

    def test_zero_salary_does_not_crash(self, auth_client):
        r = auth_client.post("/calculate-budget", json={
            "month": "2026-10",
            "monthly_salary": 0,
            "expenses": [],
        })
        assert r.status_code == 200
        assert r.json()["savings_rate"] == 0


class TestAnnualOverview:
    def test_empty_year_returns_12_zero_months(self, auth_client):
        r = auth_client.get("/overview/annual?year=2026")
        assert r.status_code == 200
        data = r.json()
        assert len(data["months"]) == 12
        assert all(m["total_planned"] == 0.0 for m in data["months"])
        assert all(m["total_actual"] == 0.0 for m in data["months"])

    def test_returns_data_for_committed_month(self, auth_client, db, verified_user):
        m = make_month(db, verified_user, "2026-03", salary_planned=3500.0,
                       total_planned=1200.0)
        m.total_actual = 1100.0
        db.commit()

        r = auth_client.get("/overview/annual?year=2026")
        data = r.json()
        march = next(mo for mo in data["months"] if mo["month"] == "2026-03")
        assert march["planned_salary"] == 3500.0
        assert march["total_planned"] == 1200.0

    def test_totals_aggregate_across_months(self, auth_client, db, verified_user):
        for mo in ("2026-01", "2026-02"):
            make_month(db, verified_user, mo, salary_planned=3000.0, total_planned=1000.0)

        r = auth_client.get("/overview/annual?year=2026")
        totals = r.json()["totals"]
        assert totals["planned_salary"] == 6000.0
        assert totals["total_planned"] == 2000.0

    def test_months_from_other_years_excluded(self, auth_client, db, verified_user):
        make_month(db, verified_user, "2025-12", salary_planned=3000.0, total_planned=800.0)

        r = auth_client.get("/overview/annual?year=2026")
        totals = r.json()["totals"]
        assert totals["planned_salary"] == 0.0  # 2025 data not included

    def test_defaults_to_current_year_without_param(self, auth_client):
        r = auth_client.get("/overview/annual")
        assert r.status_code == 200
        assert len(r.json()["months"]) == 12

    def test_month_isolation_between_users(self, auth_client, db, second_user):
        """Data from second_user must not appear in auth_client's (verified_user) response."""
        make_month(db, second_user, "2026-06", salary_planned=9999.0)

        r = auth_client.get("/overview/annual?year=2026")
        jan = next(m for m in r.json()["months"] if m["month"] == "2026-06")
        assert jan["planned_salary"] == 0.0
