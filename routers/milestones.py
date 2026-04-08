# routers/milestones.py — Monthly milestone email notifications (Phase 12.5)
#
# APScheduler job: runs on the 1st of each month at 09:00 UTC.
# Checks every active user for three types of milestones:
#   1. Under-budget spending streak reaching 3 / 6 / 12 months
#   2. A savings goal whose contributions have met or exceeded the target amount
#   3. All tracked debts reaching a zero balance (debt-free)
#
# Duplicate-send prevention: a MilestoneNotificationSent row is inserted per
# (user_id, milestone_type) before sending the email.  The UNIQUE constraint on
# that pair guarantees at-most-once delivery even if the job runs twice.

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from database import (
    Debt,
    MilestoneNotificationSent,
    MonthlyData,
    SavingsContribution,
    SavingsGoal,
    User,
)
from email_utils import (
    send_debt_payoff_email,
    send_savings_goal_complete_email,
    send_streak_milestone_email,
)

logger = logging.getLogger(__name__)

STREAK_THRESHOLDS = (3, 6, 12)


def _compute_current_streak(db: Session, user_id: int) -> int:
    """
    Return the user's current consecutive under-budget streak length.

    Mirrors the logic in GET /insights/streaks.  A month is counted only when
    total_actual > 0.  A month is "under budget" when total_actual <= total_planned
    and total_planned > 0.
    """
    rows = db.query(MonthlyData).filter(MonthlyData.user_id == user_id).all()

    tracked: list[tuple[str, bool]] = []
    for row in rows:
        month_str = row.month
        if not month_str:
            continue
        total_actual = float(row.total_actual or 0.0)
        if total_actual <= 0:
            continue
        total_planned = float(row.total_planned or 0.0)
        is_under = total_planned > 0 and total_actual <= total_planned
        tracked.append((month_str, is_under))

    tracked.sort(key=lambda x: x[0])

    run = 0
    for _, is_under in tracked:
        if is_under:
            run += 1
        else:
            run = 0
    return run


def _already_sent(db: Session, user_id: int, milestone_type: str) -> bool:
    return (
        db.query(MilestoneNotificationSent)
        .filter(
            MilestoneNotificationSent.user_id == user_id,
            MilestoneNotificationSent.milestone_type == milestone_type,
        )
        .first()
        is not None
    )


def _record_sent(db: Session, user_id: int, milestone_type: str) -> None:
    db.add(
        MilestoneNotificationSent(
            user_id=user_id,
            milestone_type=milestone_type,
            sent_at=datetime.utcnow(),
        )
    )
    db.commit()


def _check_streak_milestones(db: Session, user: User) -> None:
    current_streak = _compute_current_streak(db, user.id)
    for threshold in STREAK_THRESHOLDS:
        if current_streak < threshold:
            continue
        milestone_type = f"streak_{threshold}"
        if _already_sent(db, user.id, milestone_type):
            continue
        # Record first so a SendGrid failure doesn't cause a duplicate on retry
        _record_sent(db, user.id, milestone_type)
        try:
            send_streak_milestone_email(user.email, threshold)
        except Exception:
            logger.exception("Failed to send streak milestone email user_id=%d streak=%d", user.id, threshold)


def _check_savings_goal_milestones(db: Session, user: User) -> None:
    goals = (
        db.query(SavingsGoal)
        .filter(SavingsGoal.user_id == user.id, SavingsGoal.deleted_at.is_(None))
        .all()
    )
    for goal in goals:
        milestone_type = f"savings_goal_{goal.id}"
        if _already_sent(db, user.id, milestone_type):
            continue

        total_contributed = sum(
            float(c.amount or 0.0)
            for c in db.query(SavingsContribution)
            .filter(SavingsContribution.goal_id == goal.id)
            .all()
        )
        if total_contributed < goal.target_amount:
            continue

        _record_sent(db, user.id, milestone_type)
        try:
            send_savings_goal_complete_email(
                user.email,
                goal.name or "Your goal",
                goal.target_amount,
                getattr(user, "base_currency", "GBP") or "GBP",
            )
        except Exception:
            logger.exception("Failed to send savings goal email user_id=%d goal_id=%d", user.id, goal.id)


def _check_debt_free_milestone(db: Session, user: User) -> None:
    milestone_type = "debt_free"
    if _already_sent(db, user.id, milestone_type):
        return

    debts = (
        db.query(Debt)
        .filter(Debt.user_id == user.id, Debt.deleted_at.is_(None))
        .all()
    )
    if not debts:
        return  # No debts tracked — not a milestone

    all_zero = all(float(d.balance or 0.0) <= 0.01 for d in debts)
    if not all_zero:
        return

    _record_sent(db, user.id, milestone_type)
    try:
        send_debt_payoff_email(user.email)
    except Exception:
        logger.exception("Failed to send debt payoff email user_id=%d", user.id)


def check_milestones(session_factory) -> None:
    """
    APScheduler entry point.  Runs on the 1st of each month at 09:00 UTC.

    Iterates over all active, verified users and dispatches milestone emails
    where applicable, with full duplicate-send prevention.
    """
    db: Session = session_factory()
    try:
        users = (
            db.query(User)
            .filter(User.deleted_at.is_(None), User.email_verified.is_(True))
            .all()
        )
        logger.info("check_milestones: checking %d users", len(users))
        for user in users:
            if not getattr(user, "notif_milestones", True):
                logger.debug("check_milestones: skipping emails for user_id=%d (opted out)", user.id)
                continue
            try:
                _check_streak_milestones(db, user)
                _check_savings_goal_milestones(db, user)
                _check_debt_free_milestone(db, user)
            except Exception:
                logger.exception("check_milestones: error processing user_id=%d", user.id)
    finally:
        db.close()
