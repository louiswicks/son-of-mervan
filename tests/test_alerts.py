"""
Tests for budget alerts and notifications endpoints.

Coverage targets:
  routers/alerts.py — GET/POST/PUT/DELETE /budget-alerts
                       GET /notifications, PATCH /notifications/{id}/read,
                       PATCH /notifications/read-all, DELETE /notifications/{id}
"""
from datetime import datetime

import pytest

from tests.conftest import make_month, make_expense, TEST_EMAIL
from database import BudgetAlert, Notification


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(db, user, category="Housing", threshold_pct=80, active=True):
    a = BudgetAlert(user_id=user.id, threshold_pct=threshold_pct, active=active)
    a.category = category
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_notification(db, user, title="Test Alert", message="You hit 80%"):
    n = Notification(user_id=user.id, type="budget_alert")
    n.title = title
    n.message = message
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


# ---------------------------------------------------------------------------
# Budget Alerts
# ---------------------------------------------------------------------------

class TestBudgetAlertsRead:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/budget-alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_own_alerts(self, auth_client, db, verified_user):
        _make_alert(db, verified_user, category="Food")
        _make_alert(db, verified_user, category="Housing")
        r = auth_client.get("/budget-alerts")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_list_excludes_deleted(self, auth_client, db, verified_user):
        a = _make_alert(db, verified_user)
        a.deleted_at = datetime.utcnow()
        db.commit()
        r = auth_client.get("/budget-alerts")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_excludes_other_user(self, auth_client, db, second_user):
        _make_alert(db, second_user)
        r = auth_client.get("/budget-alerts")
        assert r.status_code == 200
        assert r.json() == []


class TestBudgetAlertsCreate:
    def test_create_returns_201(self, auth_client):
        r = auth_client.post("/budget-alerts", json={"category": "Food", "threshold_pct": 75})
        assert r.status_code == 201
        body = r.json()
        assert body["category"] == "Food"
        assert body["threshold_pct"] == 75
        assert body["active"] is True

    def test_create_default_threshold(self, auth_client):
        r = auth_client.post("/budget-alerts", json={"category": "Housing"})
        assert r.status_code == 201
        assert r.json()["threshold_pct"] == 80

    def test_create_any_category_now_accepted(self, auth_client):
        """Categories are now user-defined — any string ≤50 chars is valid."""
        r = auth_client.post("/budget-alerts", json={"category": "CustomCat", "threshold_pct": 80})
        assert r.status_code == 201

    def test_create_category_too_long_returns_422(self, auth_client):
        r = auth_client.post("/budget-alerts", json={"category": "X" * 51, "threshold_pct": 80})
        assert r.status_code == 422

    def test_unauthenticated(self, client):
        r = client.post("/budget-alerts", json={"category": "Food"})
        assert r.status_code in (401, 403)


class TestBudgetAlertsUpdate:
    def test_update_threshold(self, auth_client, db, verified_user):
        a = _make_alert(db, verified_user, threshold_pct=80)
        r = auth_client.put(f"/budget-alerts/{a.id}", json={"threshold_pct": 90})
        assert r.status_code == 200
        assert r.json()["threshold_pct"] == 90

    def test_update_active_flag(self, auth_client, db, verified_user):
        a = _make_alert(db, verified_user)
        r = auth_client.put(f"/budget-alerts/{a.id}", json={"active": False})
        assert r.status_code == 200
        assert r.json()["active"] is False

    def test_update_wrong_user_returns_404(self, auth_client, db, second_user):
        a = _make_alert(db, second_user)
        r = auth_client.put(f"/budget-alerts/{a.id}", json={"threshold_pct": 90})
        assert r.status_code == 404

    def test_update_nonexistent_returns_404(self, auth_client):
        r = auth_client.put("/budget-alerts/99999", json={"threshold_pct": 90})
        assert r.status_code == 404


class TestBudgetAlertsDelete:
    def test_delete_returns_204(self, auth_client, db, verified_user):
        a = _make_alert(db, verified_user)
        r = auth_client.delete(f"/budget-alerts/{a.id}")
        assert r.status_code == 204

    def test_delete_soft_deletes(self, auth_client, db, verified_user):
        a = _make_alert(db, verified_user)
        auth_client.delete(f"/budget-alerts/{a.id}")
        db.refresh(a)
        assert a.deleted_at is not None

    def test_delete_wrong_user_returns_404(self, auth_client, db, second_user):
        a = _make_alert(db, second_user)
        r = auth_client.delete(f"/budget-alerts/{a.id}")
        assert r.status_code == 404

    def test_deleted_alert_not_listed(self, auth_client, db, verified_user):
        a = _make_alert(db, verified_user)
        auth_client.delete(f"/budget-alerts/{a.id}")
        r = auth_client.get("/budget-alerts")
        assert r.json() == []


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class TestNotificationsList:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/notifications")
        assert r.status_code == 200
        body = r.json()
        # Response key is either "notifications" or "items" depending on schema
        items_key = "notifications" if "notifications" in body else "items"
        assert items_key in body
        assert "unread_count" in body
        assert body[items_key] == []
        assert body["unread_count"] == 0

    def test_list_returns_own_notifications(self, auth_client, db, verified_user):
        _make_notification(db, verified_user)
        r = auth_client.get("/notifications")
        body = r.json()
        items_key = "notifications" if "notifications" in body else "items"
        assert len(body[items_key]) == 1
        assert body["unread_count"] == 1

    def test_list_excludes_other_user(self, auth_client, db, second_user):
        _make_notification(db, second_user)
        r = auth_client.get("/notifications")
        body = r.json()
        items_key = "notifications" if "notifications" in body else "items"
        assert body[items_key] == []


class TestNotificationMarkRead:
    def test_mark_single_read(self, auth_client, db, verified_user):
        n = _make_notification(db, verified_user)
        r = auth_client.patch(f"/notifications/{n.id}/read")
        assert r.status_code == 200
        assert r.json()["read_at"] is not None

    def test_mark_read_wrong_user_returns_404(self, auth_client, db, second_user):
        n = _make_notification(db, second_user)
        r = auth_client.patch(f"/notifications/{n.id}/read")
        assert r.status_code == 404

    def test_mark_all_read(self, auth_client, db, verified_user):
        _make_notification(db, verified_user)
        _make_notification(db, verified_user, title="Second")
        r = auth_client.patch("/notifications/read-all")
        assert r.status_code == 204
        # Confirm unread count is now 0
        r2 = auth_client.get("/notifications")
        assert r2.json().get("unread_count") == 0


class TestNotificationDelete:
    def test_delete_returns_204(self, auth_client, db, verified_user):
        n = _make_notification(db, verified_user)
        r = auth_client.delete(f"/notifications/{n.id}")
        assert r.status_code == 204

    def test_delete_wrong_user_returns_404(self, auth_client, db, second_user):
        n = _make_notification(db, second_user)
        r = auth_client.delete(f"/notifications/{n.id}")
        assert r.status_code == 404

    def test_deleted_not_listed(self, auth_client, db, verified_user):
        n = _make_notification(db, verified_user)
        auth_client.delete(f"/notifications/{n.id}")
        r = auth_client.get("/notifications")
        body = r.json()
        items_key = "notifications" if "notifications" in body else "items"
        assert body[items_key] == []
