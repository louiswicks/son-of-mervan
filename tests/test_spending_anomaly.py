"""Tests for Phase 21.3 — Spending Anomaly Alerts.

Verifies that POST /monthly-tracker/{month} creates a spending_anomaly
Notification when an expense is statistically unusual, and does not create
spurious notifications in edge cases.
"""
import pytest

from conftest import TEST_EMAIL, make_month, make_expense
from database import Notification, MonthlyExpense


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _submit_expense(auth_client, month, name, category, amount, salary=5000):
    return auth_client.post(
        f"/monthly-tracker/{month}",
        json={
            "salary": salary,
            "expenses": [{"name": name, "category": category, "amount": amount}],
        },
    )


def _make_historical_expenses(db, user, base_month_dt, category, amounts):
    """Seed MonthlyExpense rows for the 6 months preceding base_month_dt.

    base_month_dt is a (year, month) tuple for the *current* month.
    amounts is a list of actual_amount values to seed (oldest first).
    """
    from datetime import datetime

    y, m = base_month_dt
    seeded = []
    for i, amount in enumerate(reversed(amounts), start=1):
        mo = m - i
        yr = y + (mo - 1) // 12
        mo = ((mo - 1) % 12) + 1
        month_str = f"{yr:04d}-{mo:02d}"
        month_row = make_month(db, user, month=month_str)
        exp = make_expense(
            db, month_row,
            name=f"Groceries_{i}",
            category=category,
            planned=amount,
            actual=amount,
        )
        seeded.append(exp)
    return seeded


class TestSpendingAnomalyAlerts:
    """8+ tests covering the anomaly notification logic."""

    # ------------------------------------------------------------------
    # Positive cases — notification SHOULD be created
    # ------------------------------------------------------------------

    def test_anomaly_notification_created_when_amount_exceeds_2sigma(
        self, auth_client, db, verified_user
    ):
        """If actual > mean + 2σ and >= 3 historical points, notification is created."""
        # Historical: [100, 110, 90] → mean=100, std≈8.16; threshold ≈ 116.33
        _make_historical_expenses(db, verified_user, (2026, 4), "Groceries", [100, 110, 90])

        r = _submit_expense(auth_client, "2026-04", "Groceries", "Groceries", 200)
        assert r.status_code == 200

        notifs = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).all()
        assert len(notifs) == 1
        assert "Groceries" in notifs[0].title
        assert "200" in notifs[0].message or "200.00" in notifs[0].message

    def test_anomaly_notification_message_contains_average(
        self, auth_client, db, verified_user
    ):
        """Notification message includes historical average."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Dining", [50, 60, 55])
        r = _submit_expense(auth_client, "2026-04", "Dining Out", "Dining", 300)
        assert r.status_code == 200

        notifs = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).all()
        assert len(notifs) == 1
        # Message must mention category and avg
        assert "Dining" in notifs[0].message
        assert "avg" in notifs[0].message

    def test_anomaly_dedup_key_matches_expense_id(
        self, auth_client, db, verified_user
    ):
        """dedup_key must be anomaly_{expense_id}."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Utilities", [30, 35, 28])
        r = _submit_expense(auth_client, "2026-04", "Electric", "Utilities", 200)
        assert r.status_code == 200

        notif = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).first()
        assert notif is not None
        assert notif.dedup_key.startswith("anomaly_")
        expense_id = int(notif.dedup_key.split("_")[1])
        expense = db.query(MonthlyExpense).filter(MonthlyExpense.id == expense_id).first()
        assert expense is not None

    # ------------------------------------------------------------------
    # Negative cases — notification SHOULD NOT be created
    # ------------------------------------------------------------------

    def test_no_notification_when_fewer_than_3_historical_points(
        self, auth_client, db, verified_user
    ):
        """With only 2 historical months, no anomaly notification should fire."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Shopping", [50, 60])
        r = _submit_expense(auth_client, "2026-04", "Shopping spree", "Shopping", 1000)
        assert r.status_code == 200

        count = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count == 0

    def test_no_notification_when_only_one_historical_point(
        self, auth_client, db, verified_user
    ):
        """Single historical data point must not trigger anomaly."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Travel", [200])
        r = _submit_expense(auth_client, "2026-04", "Flight", "Travel", 5000)
        assert r.status_code == 200

        count = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count == 0

    def test_no_notification_when_amount_within_normal_range(
        self, auth_client, db, verified_user
    ):
        """Amount within mean + 2σ must not trigger notification."""
        # Historical: [100, 100, 100] → std = 0 after 3 identical values… use varied
        _make_historical_expenses(db, verified_user, (2026, 4), "Rent", [800, 820, 810])
        # mean≈810, std≈8.16; 820 < 826.33 — no anomaly
        r = _submit_expense(auth_client, "2026-04", "Rent", "Rent", 820)
        assert r.status_code == 200

        count = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count == 0

    def test_no_notification_when_std_is_zero(
        self, auth_client, db, verified_user
    ):
        """All historical amounts identical (std=0) must not trigger notification."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Insurance", [150, 150, 150])
        # mean=150, std=0 → skip
        r = _submit_expense(auth_client, "2026-04", "Insurance", "Insurance", 500)
        assert r.status_code == 200

        count = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count == 0

    def test_no_notification_when_no_historical_data(
        self, auth_client, db, verified_user
    ):
        """Completely new category with zero history must not fire anomaly."""
        r = _submit_expense(auth_client, "2026-04", "New thing", "NewCategory", 9999)
        assert r.status_code == 200

        count = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count == 0

    def test_dedup_key_prevents_duplicate_notification(
        self, auth_client, db, verified_user
    ):
        """Submitting the same anomalous expense twice must not create 2 notifications."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Groceries", [100, 110, 90])

        # First submission — creates the expense + notification
        r1 = _submit_expense(auth_client, "2026-04", "Groceries", "Groceries", 300)
        assert r1.status_code == 200

        count_after_first = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count_after_first == 1

        # Second submission (same expense, same month) — should NOT add another notification
        r2 = _submit_expense(auth_client, "2026-04", "Groceries", "Groceries", 300)
        assert r2.status_code == 200

        count_after_second = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count_after_second == 1

    def test_anomaly_scoped_to_authenticated_user(
        self, auth_client, db, verified_user, second_user
    ):
        """Anomaly notifications must only be created for the authenticated user."""
        # Seed history for second_user (not the auth user)
        _make_historical_expenses(db, second_user, (2026, 4), "Groceries", [100, 110, 90])

        # Auth user has no history for this category
        r = _submit_expense(auth_client, "2026-04", "Groceries", "Groceries", 500)
        assert r.status_code == 200

        # No notification for verified_user (auth user)
        count_auth = db.query(Notification).filter(
            Notification.user_id == verified_user.id,
            Notification.type == "spending_anomaly",
        ).count()
        assert count_auth == 0

    def test_anomaly_endpoint_returns_200_even_when_anomaly_detected(
        self, auth_client, db, verified_user
    ):
        """The main response must succeed regardless of anomaly detection."""
        _make_historical_expenses(db, verified_user, (2026, 4), "Groceries", [100, 110, 90])
        r = _submit_expense(auth_client, "2026-04", "Groceries", "Groceries", 200)
        assert r.status_code == 200
        assert "total_actual" in r.json()
        assert r.json()["total_actual"] == 200.0
