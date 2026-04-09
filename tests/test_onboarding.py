"""Tests for the onboarding endpoints (Phase 17.5) and the legacy flag (Phase 9.2)."""
import pytest

from database import MonthlyExpense, RecurringExpense, SavingsGoal
from tests.conftest import make_month, make_expense


# ---------------------------------------------------------------------------
# GET /onboarding/status  &  POST /onboarding/dismiss  (Phase 17.5)
# ---------------------------------------------------------------------------

class TestOnboardingStatus:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/onboarding/status")
        assert r.status_code in (401, 403)

    def test_fresh_user_all_steps_incomplete(self, auth_client):
        r = auth_client.get("/onboarding/status")
        assert r.status_code == 200
        body = r.json()
        assert body["completed"] is False
        assert body["dismissed"] is False
        for step in body["steps"]:
            assert step["done"] is False

    def test_salary_step_done_after_setting_salary(self, auth_client, db, verified_user):
        make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        r = auth_client.get("/onboarding/status")
        steps = {s["id"]: s["done"] for s in r.json()["steps"]}
        assert steps["set_salary"] is True

    def test_expense_step_done_after_adding_expense(self, auth_client, db, verified_user):
        m = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, m, name="Groceries", category="Food")
        r = auth_client.get("/onboarding/status")
        steps = {s["id"]: s["done"] for s in r.json()["steps"]}
        assert steps["add_expense"] is True

    def test_savings_goal_step_done(self, auth_client, db, verified_user):
        goal = SavingsGoal(user_id=verified_user.id)
        goal.name = "Holiday"
        goal.target_amount = 1000.0
        db.add(goal)
        db.commit()
        r = auth_client.get("/onboarding/status")
        steps = {s["id"]: s["done"] for s in r.json()["steps"]}
        assert steps["add_savings_goal"] is True

    def test_recurring_step_done(self, auth_client, db, verified_user):
        from datetime import date
        rec = RecurringExpense(
            user_id=verified_user.id,
            frequency="monthly",
            start_date=date(2026, 1, 1),
        )
        rec.name = "Netflix"
        rec.category = "Entertainment"
        rec.planned_amount = 100.0
        db.add(rec)
        db.commit()
        r = auth_client.get("/onboarding/status")
        steps = {s["id"]: s["done"] for s in r.json()["steps"]}
        assert steps["add_recurring"] is True

    def test_completed_true_when_dismissed(self, auth_client):
        auth_client.post("/onboarding/dismiss")
        r = auth_client.get("/onboarding/status")
        assert r.json()["completed"] is True
        assert r.json()["dismissed"] is True


class TestOnboardingDismiss:
    def test_unauthenticated_returns_401(self, client):
        r = client.post("/onboarding/dismiss")
        assert r.status_code in (401, 403)

    def test_dismiss_returns_dismissed_true(self, auth_client):
        r = auth_client.post("/onboarding/dismiss")
        assert r.status_code == 200
        assert r.json()["dismissed"] is True

    def test_dismiss_idempotent(self, auth_client):
        auth_client.post("/onboarding/dismiss")
        r = auth_client.post("/onboarding/dismiss")
        assert r.status_code == 200
        assert r.json()["dismissed"] is True


# ---------------------------------------------------------------------------
# GET /users/me — has_completed_onboarding field  (Phase 9.2 legacy)
# ---------------------------------------------------------------------------

class TestOnboardingFlag:
    def test_profile_includes_onboarding_flag(self, auth_client):
        """GET /users/me includes has_completed_onboarding."""
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert "has_completed_onboarding" in r.json()

    def test_new_user_has_onboarding_incomplete(self, auth_client):
        """New users default to has_completed_onboarding=False."""
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is False

    def test_put_sets_onboarding_complete(self, auth_client):
        """PUT /users/me with has_completed_onboarding=True persists the change."""
        r = auth_client.put("/users/me", json={"has_completed_onboarding": True})
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is True

    def test_get_reflects_persisted_onboarding_flag(self, auth_client):
        """Subsequent GET /users/me returns the persisted value."""
        auth_client.put("/users/me", json={"has_completed_onboarding": True})
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is True

    def test_can_reset_onboarding_flag_to_false(self, auth_client):
        """has_completed_onboarding can be toggled back to False."""
        auth_client.put("/users/me", json={"has_completed_onboarding": True})
        r = auth_client.put("/users/me", json={"has_completed_onboarding": False})
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is False

    def test_put_preserves_other_profile_fields(self, auth_client):
        """Setting has_completed_onboarding does not clobber other fields."""
        auth_client.put("/users/me", json={"base_currency": "EUR"})
        r = auth_client.put("/users/me", json={"has_completed_onboarding": True})
        assert r.status_code == 200
        data = r.json()
        assert data["has_completed_onboarding"] is True
        assert data["base_currency"] == "EUR"

    def test_omitting_onboarding_flag_does_not_change_it(self, auth_client):
        """PUT without has_completed_onboarding leaves the existing value."""
        auth_client.put("/users/me", json={"has_completed_onboarding": True})
        # Update only base_currency, leaving onboarding flag alone
        r = auth_client.put("/users/me", json={"base_currency": "USD"})
        assert r.status_code == 200
        data = r.json()
        assert data["has_completed_onboarding"] is True
        assert data["base_currency"] == "USD"

    def test_unauthenticated_get_profile_returns_401(self, client):
        """Unauthenticated requests to GET /users/me are rejected."""
        r = client.get("/users/me")
        assert r.status_code in (401, 403)

    def test_unauthenticated_put_profile_returns_401(self, client):
        """Unauthenticated requests to PUT /users/me are rejected."""
        r = client.put("/users/me", json={"has_completed_onboarding": True})
        assert r.status_code in (401, 403)
