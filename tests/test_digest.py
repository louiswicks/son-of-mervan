"""Tests for Phase 9.1: Monthly Budget Email Digest."""
from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from conftest import TEST_EMAIL, TEST_PASSWORD, make_expense, make_month
from database import MonthlyData, MonthlyExpense, User
from security import get_password_hash


# ---------------------------------------------------------------------------
# GET /users/me — digest_enabled field
# ---------------------------------------------------------------------------

class TestDigestEnabledField:
    def test_profile_includes_digest_enabled_default_true(self, auth_client):
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        data = r.json()
        assert "digest_enabled" in data
        assert data["digest_enabled"] is True

    def test_put_profile_disables_digest(self, auth_client):
        r = auth_client.put("/users/me", json={"digest_enabled": False})
        assert r.status_code == 200
        assert r.json()["digest_enabled"] is False

    def test_put_profile_re_enables_digest(self, auth_client):
        # Disable first
        auth_client.put("/users/me", json={"digest_enabled": False})
        # Re-enable
        r = auth_client.put("/users/me", json={"digest_enabled": True})
        assert r.status_code == 200
        assert r.json()["digest_enabled"] is True

    def test_get_profile_reflects_persisted_digest_setting(self, auth_client):
        auth_client.put("/users/me", json={"digest_enabled": False})
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert r.json()["digest_enabled"] is False

    def test_put_profile_preserves_other_fields(self, auth_client):
        r = auth_client.put("/users/me", json={"digest_enabled": False, "base_currency": "USD"})
        assert r.status_code == 200
        data = r.json()
        assert data["digest_enabled"] is False
        assert data["base_currency"] == "USD"


# ---------------------------------------------------------------------------
# send_monthly_digests scheduler job
# ---------------------------------------------------------------------------

class TestSendMonthlyDigests:
    """Unit tests for the send_monthly_digests() function in main.py."""

    @pytest.fixture
    def session_factory(self, db):
        """A session factory that returns the test DB session."""
        factory = MagicMock()
        factory.return_value = db
        # Prevent db.close() from terminating the test session
        db.close = MagicMock()
        return factory

    def _prev_month(self):
        """Return the previous month as 'YYYY-MM'."""
        today = date.today()
        if today.month == 1:
            return f"{today.year - 1:04d}-12"
        return f"{today.year:04d}-{today.month - 1:02d}"

    def test_sends_digest_for_opted_in_user_with_data(self, db, session_factory, verified_user):
        month = self._prev_month()
        month_rec = make_month(db, verified_user, month=month, salary_planned=3000.0)
        month_rec.salary_actual = 3000.0
        db.commit()
        make_expense(db, month_rec, name="Rent", category="Housing", planned=800.0, actual=900.0)
        make_expense(db, month_rec, name="Food", category="Food", planned=300.0, actual=250.0)

        from main import send_monthly_digests

        with patch("email_utils.send_monthly_digest_email") as mock_send:
            send_monthly_digests(session_factory)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args[1] if mock_send.call_args[1] else {}
        args = mock_send.call_args[0]
        # Accept either positional or keyword call
        to_email = kwargs.get("to_email") or args[0]
        assert to_email == TEST_EMAIL
        sent_month = kwargs.get("month") or args[1]
        assert sent_month == month

    def test_skips_user_with_no_data_for_previous_month(self, db, session_factory, verified_user):
        # User has NO monthly data — should not receive a digest
        from main import send_monthly_digests

        with patch("email_utils.send_monthly_digest_email") as mock_send:
            send_monthly_digests(session_factory)

        mock_send.assert_not_called()

    def test_skips_opted_out_user(self, db, session_factory, verified_user):
        month = self._prev_month()
        make_month(db, verified_user, month=month)
        verified_user.digest_enabled = False
        db.commit()

        from main import send_monthly_digests

        with patch("email_utils.send_monthly_digest_email") as mock_send:
            send_monthly_digests(session_factory)

        mock_send.assert_not_called()

    def test_skips_deleted_user(self, db, session_factory, verified_user):
        from datetime import datetime

        month = self._prev_month()
        make_month(db, verified_user, month=month)
        verified_user.deleted_at = datetime.utcnow()
        db.commit()

        from main import send_monthly_digests

        with patch("email_utils.send_monthly_digest_email") as mock_send:
            send_monthly_digests(session_factory)

        mock_send.assert_not_called()

    def test_over_budget_categories_included(self, db, session_factory, verified_user):
        month = self._prev_month()
        month_rec = make_month(db, verified_user, month=month, salary_planned=3000.0)
        month_rec.salary_actual = 3000.0
        db.commit()
        # Housing: actual > planned → over budget
        make_expense(db, month_rec, name="Rent", category="Housing", planned=800.0, actual=1000.0)
        # Food: within budget
        make_expense(db, month_rec, name="Groceries", category="Food", planned=400.0, actual=350.0)

        from main import send_monthly_digests

        with patch("email_utils.send_monthly_digest_email") as mock_send:
            send_monthly_digests(session_factory)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1] if mock_send.call_args[1] else {}
        call_args = mock_send.call_args[0]
        over_budget = call_kwargs.get("over_budget") or call_args[5]
        assert "Housing" in over_budget
        assert "Food" not in over_budget

    def test_sends_digests_to_multiple_users(self, db, session_factory, verified_user, second_user):
        month = self._prev_month()
        make_month(db, verified_user, month=month)
        make_month(db, second_user, month=month)

        from main import send_monthly_digests

        with patch("email_utils.send_monthly_digest_email") as mock_send:
            send_monthly_digests(session_factory)

        assert mock_send.call_count == 2


# ---------------------------------------------------------------------------
# send_monthly_digest_email — dev mode (no SendGrid key)
# ---------------------------------------------------------------------------

class TestSendMonthlyDigestEmailDevMode:
    def test_logs_instead_of_calling_sendgrid_when_no_key(self, caplog):
        from email_utils import send_monthly_digest_email

        with patch("email_utils.SENDGRID_API_KEY", None):
            import logging
            with caplog.at_level(logging.INFO, logger="email_utils"):
                send_monthly_digest_email(
                    to_email="user@example.com",
                    month="2026-03",
                    income=3000.0,
                    total_spent=2500.0,
                    savings_rate=16.7,
                    top_categories=[("Housing", 1000.0), ("Food", 400.0)],
                    over_budget=["Housing"],
                    currency="GBP",
                )

        assert any("Monthly digest" in r.message or "digest" in r.message.lower() for r in caplog.records)
