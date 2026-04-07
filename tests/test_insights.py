"""
Tests for spending insights endpoints.

Coverage targets:
  routers/insights.py — GET /insights/monthly-summary
                         GET /insights/trends
                         GET /insights/heatmap
"""
import pytest

from tests.conftest import make_month, make_expense


class TestMonthlySummary:
    def test_empty_month_returns_200(self, auth_client):
        r = auth_client.get("/insights/monthly-summary?month=2026-01")
        assert r.status_code == 200

    def test_missing_month_param_returns_422(self, auth_client):
        r = auth_client.get("/insights/monthly-summary")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.get("/insights/monthly-summary?month=January")
        assert r.status_code == 422

    def test_with_data_returns_summary(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-03", salary_planned=3000.0, total_planned=1500.0)
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=850.0)
        make_expense(db, month, name="Groceries", category="Food", planned=400.0, actual=300.0)

        r = auth_client.get("/insights/monthly-summary?month=2026-03")
        assert r.status_code == 200
        body = r.json()
        # Response should contain per-category data or insights list
        assert isinstance(body, dict)

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/monthly-summary?month=2026-01")
        assert r.status_code in (401, 403)

    def test_only_own_data(self, auth_client, db, second_user):
        month = make_month(db, second_user, month="2026-01")
        make_expense(db, month, name="BigRent", category="Housing", planned=2000.0, actual=2000.0)

        r = auth_client.get("/insights/monthly-summary?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        # The authenticated user has no data for this month — net_income or categories should reflect that
        assert isinstance(body, dict)


class TestTrends:
    def test_empty_returns_200(self, auth_client):
        r = auth_client.get("/insights/trends")
        assert r.status_code == 200

    def test_default_months(self, auth_client):
        r = auth_client.get("/insights/trends")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    def test_custom_months_param(self, auth_client):
        r = auth_client.get("/insights/trends?months=3")
        assert r.status_code == 200

    def test_invalid_months_too_small(self, auth_client):
        r = auth_client.get("/insights/trends?months=1")
        assert r.status_code == 422

    def test_invalid_months_too_large(self, auth_client):
        r = auth_client.get("/insights/trends?months=25")
        assert r.status_code == 422

    def test_with_data(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, m1, name="Rent", category="Housing", planned=800.0, actual=800.0)
        m2 = make_month(db, verified_user, month="2026-02", salary_planned=3000.0)
        make_expense(db, m2, name="Rent", category="Housing", planned=800.0, actual=900.0)

        r = auth_client.get("/insights/trends?months=6")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    def test_unauthenticated(self, client):
        r = client.get("/insights/trends")
        assert r.status_code in (401, 403)


class TestHeatmap:
    def test_empty_returns_200(self, auth_client):
        r = auth_client.get("/insights/heatmap")
        assert r.status_code == 200

    def test_returns_year_key(self, auth_client):
        r = auth_client.get("/insights/heatmap?year=2026")
        assert r.status_code == 200
        body = r.json()
        assert "year" in body

    def test_invalid_year(self, auth_client):
        r = auth_client.get("/insights/heatmap?year=notayear")
        assert r.status_code == 422

    def test_with_data(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-04")
        make_expense(db, month, name="Coffee", category="Food", planned=50.0, actual=60.0)

        r = auth_client.get("/insights/heatmap?year=2026")
        assert r.status_code == 200
        body = r.json()
        assert int(body["year"]) == 2026

    def test_unauthenticated(self, client):
        r = client.get("/insights/heatmap")
        assert r.status_code in (401, 403)


class TestSpendingPace:
    def test_missing_month_returns_422(self, auth_client):
        r = auth_client.get("/insights/pace")
        assert r.status_code == 422

    def test_invalid_month_returns_422(self, auth_client):
        r = auth_client.get("/insights/pace?month=not-a-month")
        assert r.status_code == 422

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/pace?month=2026-04")
        assert r.status_code in (401, 403)

    def test_empty_month_returns_200_with_expected_keys(self, auth_client):
        r = auth_client.get("/insights/pace?month=2026-04")
        assert r.status_code == 200
        body = r.json()
        assert "month" in body
        assert "days_elapsed" in body
        assert "days_in_month" in body
        assert "categories" in body
        assert "overall" in body
        assert "warnings" in body

    def test_future_month_returns_zero_days_elapsed(self, auth_client):
        r = auth_client.get("/insights/pace?month=2099-12")
        assert r.status_code == 200
        body = r.json()
        assert body["days_elapsed"] == 0
        assert body["warnings"] == []

    def test_with_overspending_data_generates_warning(self, auth_client, db, verified_user):
        # Use current month so days_elapsed > 0
        from datetime import datetime
        now = datetime.utcnow()
        month_str = f"{now.year:04d}-{now.month:02d}"

        month = make_month(db, verified_user, month=month_str, salary_planned=3000.0, total_planned=500.0)
        # Actual already exceeds planned — pace will project over budget
        make_expense(db, month, name="Rent", category="Housing", planned=100.0, actual=500.0)

        r = auth_client.get(f"/insights/pace?month={month_str}")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["categories"], dict)
        assert isinstance(body["warnings"], list)
        # Housing should be flagged because 500 actual >> 100 planned
        warning_cats = [w["category"] for w in body["warnings"]]
        assert "Housing" in warning_cats

    def test_within_budget_produces_no_warning(self, auth_client, db, verified_user):
        from datetime import datetime
        now = datetime.utcnow()
        month_str = f"{now.year:04d}-{now.month:02d}"

        month = make_month(db, verified_user, month=month_str, salary_planned=3000.0)
        # Very low actual vs high planned — pace projection will be well under planned
        make_expense(db, month, name="Food", category="Food", planned=1000.0, actual=1.0)

        r = auth_client.get(f"/insights/pace?month={month_str}")
        assert r.status_code == 200
        body = r.json()
        food_warnings = [w for w in body["warnings"] if w["category"] == "Food"]
        assert food_warnings == []

    def test_only_own_data(self, auth_client, db, second_user):
        from datetime import datetime
        now = datetime.utcnow()
        month_str = f"{now.year:04d}-{now.month:02d}"

        month = make_month(db, second_user, month=month_str)
        make_expense(db, month, name="BigSpend", category="Housing", planned=100.0, actual=9999.0)

        r = auth_client.get(f"/insights/pace?month={month_str}")
        assert r.status_code == 200
        body = r.json()
        # Authenticated user has no data, so no Housing warning from second_user
        warning_cats = [w["category"] for w in body["warnings"]]
        assert "Housing" not in warning_cats
