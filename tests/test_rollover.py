"""
Tests for Phase 20.3 — Budget Rollover.

Coverage targets:
  routers/rollover.py — POST /monthly-tracker/{month}/rollover
"""
import pytest

from tests.conftest import make_expense, make_month


class TestRolloverAuth:
    def test_unauthenticated_returns_401(self, client):
        r = client.post("/monthly-tracker/2026-03/rollover")
        assert r.status_code in (401, 403)

    def test_missing_source_month_returns_404(self, auth_client):
        # No MonthlyData row exists for this month
        r = auth_client.post("/monthly-tracker/2026-05/rollover")
        assert r.status_code == 404

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.post("/monthly-tracker/not-a-date/rollover")
        assert r.status_code == 422


class TestRolloverBasic:
    def test_returns_empty_when_no_unspent_budget(self, auth_client, db, verified_user):
        """All expenses fully spent → nothing to roll over."""
        m = make_month(db, verified_user, month="2026-01", salary_planned=2000.0)
        make_expense(db, m, name="Rent", category="Housing", planned=800.0, actual=800.0)
        r = auth_client.post("/monthly-tracker/2026-01/rollover")
        assert r.status_code == 200
        data = r.json()
        assert data["rolled_over_categories"] == []
        assert data["total_rolled_over"] == 0.0

    def test_rolls_over_unspent_expense(self, auth_client, db, verified_user):
        """Unspent £200 on Rent moves into next month's planned amount."""
        m = make_month(db, verified_user, month="2026-02", salary_planned=3000.0)
        make_expense(db, m, name="Rent", category="Housing", planned=1000.0, actual=800.0)
        r = auth_client.post("/monthly-tracker/2026-02/rollover")
        assert r.status_code == 200
        data = r.json()
        assert data["source_month"] == "2026-02"
        assert data["dest_month"] == "2026-03"
        assert data["total_rolled_over"] == pytest.approx(200.0)
        assert len(data["rolled_over_categories"]) == 1
        assert data["rolled_over_categories"][0]["category"] == "Housing"
        assert data["rolled_over_categories"][0]["amount"] == pytest.approx(200.0)

    def test_skips_overspent_categories(self, auth_client, db, verified_user):
        """Expenses where actual >= planned are silently excluded."""
        m = make_month(db, verified_user, month="2026-04", salary_planned=3000.0)
        make_expense(db, m, name="Dining", category="Food", planned=200.0, actual=350.0)
        make_expense(db, m, name="Transport", category="Travel", planned=100.0, actual=80.0)
        r = auth_client.post("/monthly-tracker/2026-04/rollover")
        assert r.status_code == 200
        data = r.json()
        # Only Transport (£20 unspent) should roll over
        assert len(data["rolled_over_categories"]) == 1
        assert data["rolled_over_categories"][0]["category"] == "Travel"
        assert data["total_rolled_over"] == pytest.approx(20.0)

    def test_creates_dest_month_when_absent(self, auth_client, db, verified_user):
        """Next month MonthlyData is created if it does not exist."""
        from database import MonthlyData
        m = make_month(db, verified_user, month="2026-06", salary_planned=2500.0)
        make_expense(db, m, name="Subscriptions", category="Leisure", planned=50.0, actual=30.0)
        r = auth_client.post("/monthly-tracker/2026-06/rollover")
        assert r.status_code == 200
        # Check dest month was created in DB
        dest = (
            db.query(MonthlyData)
            .filter(MonthlyData.user_id == verified_user.id)
            .all()
        )
        dest_months = [d.month for d in dest]
        assert "2026-07" in dest_months

    def test_adds_to_existing_dest_expense(self, auth_client, db, verified_user):
        """Surplus is added to matching expense in next month (same name)."""
        src = make_month(db, verified_user, month="2026-07", salary_planned=3000.0)
        make_expense(db, src, name="Groceries", category="Food", planned=400.0, actual=300.0)
        dst = make_month(db, verified_user, month="2026-08", salary_planned=3000.0)
        make_expense(db, dst, name="Groceries", category="Food", planned=400.0, actual=0.0)
        r = auth_client.post("/monthly-tracker/2026-07/rollover")
        assert r.status_code == 200
        # The destination Groceries row should have planned = 400 + 100 = 500
        db.refresh(dst)
        dst_exp = [e for e in dst.expenses if e.deleted_at is None and e.name == "Groceries"]
        assert len(dst_exp) == 1
        assert dst_exp[0].planned_amount == pytest.approx(500.0)

    def test_creates_new_dest_expense_when_no_match(self, auth_client, db, verified_user):
        """When no matching expense exists in dest, a new row is inserted."""
        src = make_month(db, verified_user, month="2026-09", salary_planned=3000.0)
        make_expense(db, src, name="Gym", category="Health", planned=60.0, actual=0.0)
        dst = make_month(db, verified_user, month="2026-10", salary_planned=3000.0)
        # No "Gym" expense in dst
        r = auth_client.post("/monthly-tracker/2026-09/rollover")
        assert r.status_code == 200
        db.refresh(dst)
        gym_expenses = [e for e in dst.expenses if e.deleted_at is None and e.name == "Gym"]
        assert len(gym_expenses) == 1
        assert gym_expenses[0].planned_amount == pytest.approx(60.0)

    def test_year_boundary_december_to_january(self, auth_client, db, verified_user):
        """Rollover from December correctly wraps to January of next year."""
        m = make_month(db, verified_user, month="2026-12", salary_planned=3000.0)
        make_expense(db, m, name="Bonus Fund", category="Savings", planned=500.0, actual=300.0)
        r = auth_client.post("/monthly-tracker/2026-12/rollover")
        assert r.status_code == 200
        data = r.json()
        assert data["dest_month"] == "2027-01"
        assert data["total_rolled_over"] == pytest.approx(200.0)

    def test_idempotency_no_double_apply(self, auth_client, db, verified_user):
        """Calling rollover twice for the same source month must not double-add."""
        src = make_month(db, verified_user, month="2026-11", salary_planned=3000.0)
        make_expense(db, src, name="Internet", category="Utilities", planned=50.0, actual=30.0)
        dst = make_month(db, verified_user, month="2026-12", salary_planned=3000.0)
        make_expense(db, dst, name="Internet", category="Utilities", planned=50.0, actual=0.0)

        # First call
        r1 = auth_client.post("/monthly-tracker/2026-11/rollover")
        assert r1.status_code == 200
        assert r1.json()["total_rolled_over"] == pytest.approx(20.0)

        # Second call — must return same total without re-applying
        r2 = auth_client.post("/monthly-tracker/2026-11/rollover")
        assert r2.status_code == 200
        assert r2.json()["total_rolled_over"] == pytest.approx(20.0)

        # Planned amount in dest should still be 70 (50 + 20), not 90 (50 + 20 + 20)
        db.refresh(dst)
        internet_exp = [e for e in dst.expenses if e.deleted_at is None and e.name == "Internet"]
        assert len(internet_exp) == 1
        assert internet_exp[0].planned_amount == pytest.approx(70.0)

    def test_data_isolation_between_users(self, auth_client, db, verified_user, second_user):
        """User A cannot trigger a rollover that touches User B's data."""
        # Create a month for second_user (not accessible via auth_client)
        other_month = make_month(db, second_user, month="2026-03", salary_planned=5000.0)
        make_expense(db, other_month, name="Mortgage", category="Housing", planned=2000.0, actual=1500.0)

        # auth_client (verified_user) has no 2026-03 data → 404
        r = auth_client.post("/monthly-tracker/2026-03/rollover")
        assert r.status_code == 404

    def test_response_shape(self, auth_client, db, verified_user):
        """Response contains all required fields with correct types."""
        m = make_month(db, verified_user, month="2026-05", salary_planned=3000.0)
        make_expense(db, m, name="Streaming", category="Leisure", planned=15.0, actual=10.0)
        r = auth_client.post("/monthly-tracker/2026-05/rollover")
        assert r.status_code == 200
        data = r.json()
        assert "source_month" in data
        assert "dest_month" in data
        assert "rolled_over_categories" in data
        assert "total_rolled_over" in data
        assert isinstance(data["rolled_over_categories"], list)
        assert isinstance(data["total_rolled_over"], float)
