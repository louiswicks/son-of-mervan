"""Tests for Phase 12.5: Milestone Email Notifications."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from conftest import TEST_EMAIL, make_month
from database import (
    Debt,
    MilestoneNotificationSent,
    SavingsContribution,
    SavingsGoal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_month_under(db, user, month: str):
    """Create a MonthlyData row where actual <= planned (under budget)."""
    return make_month(db, user, month=month, total_planned=1000.0, total_actual=800.0)


def make_month_over(db, user, month: str):
    """Create a MonthlyData row where actual > planned (over budget)."""
    return make_month(db, user, month=month, total_planned=1000.0, total_actual=1200.0)


def _session_factory(db):
    """Return a mock session factory that yields the test DB session."""
    factory = MagicMock()
    factory.return_value = db
    db.close = MagicMock()
    return factory


def _sent_types(db, user_id) -> set:
    rows = db.query(MilestoneNotificationSent).filter(
        MilestoneNotificationSent.user_id == user_id
    ).all()
    return {r.milestone_type for r in rows}


# ---------------------------------------------------------------------------
# Streak milestone tests
# ---------------------------------------------------------------------------

class TestStreakMilestones:
    def test_sends_streak_3_email_at_three_consecutive_months(self, db, verified_user):
        for i, month in enumerate(["2026-01", "2026-02", "2026-03"]):
            make_month_under(db, verified_user, month)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_called_once_with(TEST_EMAIL, 3)
        assert "streak_3" in _sent_types(db, verified_user.id)

    def test_no_streak_email_when_under_threshold(self, db, verified_user):
        for month in ["2026-01", "2026-02"]:
            make_month_under(db, verified_user, month)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()

    def test_does_not_resend_streak_email_on_second_run(self, db, verified_user):
        for month in ["2026-01", "2026-02", "2026-03"]:
            make_month_under(db, verified_user, month)

        sf = _session_factory(db)
        from routers.milestones import check_milestones

        with patch("routers.milestones.send_streak_milestone_email"):
            check_milestones(sf)

        # Second run — should not send again
        with patch("routers.milestones.send_streak_milestone_email") as mock_second:
            check_milestones(sf)

        mock_second.assert_not_called()

    def test_streak_broken_by_over_budget_month_suppresses_email(self, db, verified_user):
        make_month_under(db, verified_user, "2026-01")
        make_month_under(db, verified_user, "2026-02")
        make_month_over(db, verified_user, "2026-03")  # breaks the streak

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()

    def test_sends_streak_6_email_at_six_months(self, db, verified_user):
        months = [
            "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
        ]
        for month in months:
            make_month_under(db, verified_user, month)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        sent_thresholds = {call.args[1] for call in mock_send.call_args_list}
        assert 3 in sent_thresholds
        assert 6 in sent_thresholds

    def test_skips_deleted_users(self, db, verified_user):
        for month in ["2026-01", "2026-02", "2026-03"]:
            make_month_under(db, verified_user, month)
        verified_user.deleted_at = datetime.utcnow()
        db.commit()

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_streak_milestone_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Savings goal milestone tests
# ---------------------------------------------------------------------------

class TestSavingsGoalMilestones:
    def _make_goal(self, db, user, name="Holiday Fund", target=1000.0):
        goal = SavingsGoal(user_id=user.id)
        goal.name = name
        goal.target_amount = target
        db.add(goal)
        db.commit()
        db.refresh(goal)
        return goal

    def _add_contribution(self, db, goal, amount: float):
        c = SavingsContribution(goal_id=goal.id)
        c.amount = amount
        db.add(c)
        db.commit()

    def test_sends_email_when_goal_fully_funded(self, db, verified_user):
        goal = self._make_goal(db, verified_user, target=500.0)
        self._add_contribution(db, goal, 300.0)
        self._add_contribution(db, goal, 200.0)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_savings_goal_complete_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == "Holiday Fund"
        assert f"savings_goal_{goal.id}" in _sent_types(db, verified_user.id)

    def test_no_email_when_goal_underfunded(self, db, verified_user):
        goal = self._make_goal(db, verified_user, target=500.0)
        self._add_contribution(db, goal, 200.0)  # only 40% funded

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_savings_goal_complete_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()

    def test_does_not_resend_savings_goal_email(self, db, verified_user):
        goal = self._make_goal(db, verified_user, target=100.0)
        self._add_contribution(db, goal, 100.0)

        sf = _session_factory(db)
        from routers.milestones import check_milestones

        with patch("routers.milestones.send_savings_goal_complete_email"):
            check_milestones(sf)

        with patch("routers.milestones.send_savings_goal_complete_email") as mock_second:
            check_milestones(sf)

        mock_second.assert_not_called()

    def test_skips_deleted_savings_goals(self, db, verified_user):
        goal = self._make_goal(db, verified_user, target=100.0)
        self._add_contribution(db, goal, 200.0)
        goal.deleted_at = datetime.utcnow()
        db.commit()

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_savings_goal_complete_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Debt-free milestone tests
# ---------------------------------------------------------------------------

class TestDebtFreeMilestone:
    def _make_debt(self, db, user, balance: float, name="Credit Card"):
        d = Debt(user_id=user.id, interest_rate=0.18, minimum_payment=25.0)
        d.name = name
        d.balance = balance
        db.add(d)
        db.commit()
        db.refresh(d)
        return d

    def test_sends_email_when_all_debts_zero(self, db, verified_user):
        self._make_debt(db, verified_user, balance=0.0)
        self._make_debt(db, verified_user, balance=0.0, name="Car Loan")

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_debt_payoff_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_called_once_with(TEST_EMAIL)
        assert "debt_free" in _sent_types(db, verified_user.id)

    def test_no_email_when_debt_remains(self, db, verified_user):
        self._make_debt(db, verified_user, balance=500.0)

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_debt_payoff_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()

    def test_no_email_when_user_has_no_debts(self, db, verified_user):
        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_debt_payoff_email") as mock_send:
            check_milestones(sf)

        mock_send.assert_not_called()

    def test_does_not_resend_debt_free_email(self, db, verified_user):
        self._make_debt(db, verified_user, balance=0.0)

        sf = _session_factory(db)
        from routers.milestones import check_milestones

        with patch("routers.milestones.send_debt_payoff_email"):
            check_milestones(sf)

        with patch("routers.milestones.send_debt_payoff_email") as mock_second:
            check_milestones(sf)

        mock_second.assert_not_called()

    def test_ignores_deleted_debts_for_debt_free_check(self, db, verified_user):
        d = self._make_debt(db, verified_user, balance=500.0)
        d.deleted_at = datetime.utcnow()
        db.commit()

        sf = _session_factory(db)
        from routers.milestones import check_milestones
        with patch("routers.milestones.send_debt_payoff_email") as mock_send:
            check_milestones(sf)

        # deleted debt not counted — user effectively has no debts
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Email dev-mode (no SendGrid key) tests
# ---------------------------------------------------------------------------

class TestMilestoneEmailDevMode:
    def test_streak_email_noop_without_sendgrid_key(self, caplog):
        import logging
        from email_utils import send_streak_milestone_email

        with patch("email_utils.SENDGRID_API_KEY", None):
            with caplog.at_level(logging.INFO, logger="email_utils"):
                send_streak_milestone_email("user@example.com", 3)

        assert any("streak" in r.message.lower() or "milestone" in r.message.lower() for r in caplog.records)

    def test_savings_goal_email_noop_without_sendgrid_key(self, caplog):
        import logging
        from email_utils import send_savings_goal_complete_email

        with patch("email_utils.SENDGRID_API_KEY", None):
            with caplog.at_level(logging.INFO, logger="email_utils"):
                send_savings_goal_complete_email("user@example.com", "Holiday Fund", 1000.0)

        assert any("savings" in r.message.lower() or "goal" in r.message.lower() for r in caplog.records)

    def test_debt_payoff_email_noop_without_sendgrid_key(self, caplog):
        import logging
        from email_utils import send_debt_payoff_email

        with patch("email_utils.SENDGRID_API_KEY", None):
            with caplog.at_level(logging.INFO, logger="email_utils"):
                send_debt_payoff_email("user@example.com")

        assert any("debt" in r.message.lower() for r in caplog.records)
