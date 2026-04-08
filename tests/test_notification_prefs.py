"""Tests for Phase 13.4: Email Notification Preference Center."""
from unittest.mock import MagicMock, patch

import pytest

from conftest import TEST_EMAIL, make_month, make_expense


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_factory(db):
    factory = MagicMock()
    factory.return_value = db
    db.close = MagicMock()
    return factory


# ---------------------------------------------------------------------------
# GET /users/me/notification-preferences
# ---------------------------------------------------------------------------

class TestGetNotificationPreferences:
    def test_returns_defaults_for_new_user(self, auth_client):
        resp = auth_client.get("/users/me/notification-preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["digest_enabled"] is True
        assert data["notif_budget_alerts"] is True
        assert data["notif_milestones"] is True

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/users/me/notification-preferences")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /users/me/notification-preferences
# ---------------------------------------------------------------------------

class TestUpdateNotificationPreferences:
    def test_update_all_three_preferences(self, auth_client):
        resp = auth_client.put(
            "/users/me/notification-preferences",
            json={"digest_enabled": False, "notif_budget_alerts": False, "notif_milestones": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["digest_enabled"] is False
        assert data["notif_budget_alerts"] is False
        assert data["notif_milestones"] is False

    def test_partial_update_only_changes_provided_fields(self, auth_client):
        # First disable everything
        auth_client.put(
            "/users/me/notification-preferences",
            json={"digest_enabled": False, "notif_budget_alerts": False, "notif_milestones": False},
        )
        # Then re-enable only budget alerts
        resp = auth_client.put(
            "/users/me/notification-preferences",
            json={"notif_budget_alerts": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notif_budget_alerts"] is True
        assert data["digest_enabled"] is False       # unchanged
        assert data["notif_milestones"] is False      # unchanged

    def test_preferences_persisted_across_requests(self, auth_client):
        auth_client.put(
            "/users/me/notification-preferences",
            json={"notif_milestones": False},
        )
        resp = auth_client.get("/users/me/notification-preferences")
        assert resp.json()["notif_milestones"] is False

    def test_unauthenticated_returns_401(self, client):
        resp = client.put(
            "/users/me/notification-preferences",
            json={"digest_enabled": False},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Budget alert email respects notif_budget_alerts preference
# ---------------------------------------------------------------------------

class TestBudgetAlertEmailPreference:
    def test_email_suppressed_when_opted_out(self, db, verified_user):
        """check_budget_alerts must NOT send email when notif_budget_alerts=False."""
        verified_user.notif_budget_alerts = False
        db.commit()

        from database import BudgetAlert
        alert = BudgetAlert(user_id=verified_user.id, threshold_pct=80, active=True)
        alert.category = "Housing"
        db.add(alert)
        db.commit()

        month_row = make_month(db, verified_user, month="2026-04")
        make_expense(db, month_row, name="Rent", category="Housing", planned=500.0, actual=450.0)

        sf = _session_factory(db)
        from routers.alerts import check_budget_alerts
        with patch("routers.alerts.send_budget_alert_email") as mock_email:
            check_budget_alerts(sf)

        mock_email.assert_not_called()

    def test_email_sent_when_opted_in(self, db, verified_user):
        """check_budget_alerts MUST send email when notif_budget_alerts=True (default)."""
        from database import BudgetAlert
        alert = BudgetAlert(user_id=verified_user.id, threshold_pct=80, active=True)
        alert.category = "Housing"
        db.add(alert)
        db.commit()

        month_row = make_month(db, verified_user, month="2026-04")
        make_expense(db, month_row, name="Rent", category="Housing", planned=500.0, actual=450.0)

        sf = _session_factory(db)
        from routers.alerts import check_budget_alerts
        with patch("routers.alerts.send_budget_alert_email") as mock_email:
            check_budget_alerts(sf)

        mock_email.assert_called_once()


# ---------------------------------------------------------------------------
# Milestone emails respect notif_milestones preference
# ---------------------------------------------------------------------------

class TestMilestoneEmailPreference:
    def test_milestone_emails_suppressed_when_opted_out(self, db, verified_user):
        """check_milestones must NOT send any emails when notif_milestones=False."""
        verified_user.notif_milestones = False
        db.commit()

        for month in ["2026-01", "2026-02", "2026-03"]:
            make_month(db, verified_user, month=month, total_planned=1000.0, total_actual=800.0)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()

    def test_milestone_emails_sent_when_opted_in(self, db, verified_user):
        """check_milestones MUST send streak email when notif_milestones=True (default)."""
        for month in ["2026-01", "2026-02", "2026-03"]:
            make_month(db, verified_user, month=month, total_planned=1000.0, total_actual=800.0)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_called_once_with(TEST_EMAIL, 3)
