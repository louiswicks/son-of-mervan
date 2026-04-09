# routers/onboarding.py
"""
Onboarding status and dismissal endpoints.

Routes:
  GET  /onboarding/status   Return wizard step completion state for the authenticated user
  POST /onboarding/dismiss  Permanently dismiss the onboarding wizard
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, MonthlyData, MonthlyExpense, RecurringExpense, SavingsGoal, User
from security import verify_token

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _compute_steps(user: User, db: Session) -> list[dict]:
    """Derive each wizard step's completion from real DB state."""
    # Step 1: Has set a salary (any month with salary_planned > 0)
    has_salary = False
    months = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    for m in months:
        try:
            if float(m.salary_planned) > 0:
                has_salary = True
                break
        except (ValueError, TypeError):
            pass

    # Step 2: Has added at least one planned expense (not soft-deleted)
    has_expense = False
    for m in months:
        expense = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == m.id,
                MonthlyExpense.deleted_at.is_(None),
            )
            .first()
        )
        if expense:
            has_expense = True
            break

    # Step 3: Has at least one savings goal (not soft-deleted)
    has_savings_goal = (
        db.query(SavingsGoal)
        .filter(SavingsGoal.user_id == user.id, SavingsGoal.deleted_at.is_(None))
        .first()
        is not None
    )

    # Step 4: Has at least one recurring expense (not soft-deleted)
    has_recurring = (
        db.query(RecurringExpense)
        .filter(RecurringExpense.user_id == user.id, RecurringExpense.deleted_at.is_(None))
        .first()
        is not None
    )

    return [
        {"id": "set_salary", "label": "Set your monthly salary", "done": has_salary},
        {"id": "add_expense", "label": "Add your first planned expense", "done": has_expense},
        {"id": "add_savings_goal", "label": "Create a savings goal", "done": has_savings_goal},
        {"id": "add_recurring", "label": "Set up a recurring expense", "done": has_recurring},
    ]


@router.get("/status")
def get_onboarding_status(
    current_user_email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return the wizard step completion state and whether onboarding is complete."""
    current_user = _get_user(db, current_user_email)
    steps = _compute_steps(current_user, db)
    completed = all(s["done"] for s in steps) or current_user.onboarding_dismissed_at is not None
    return {
        "completed": completed,
        "dismissed": current_user.onboarding_dismissed_at is not None,
        "steps": steps,
    }


@router.post("/dismiss", status_code=200)
def dismiss_onboarding(
    current_user_email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Permanently dismiss the onboarding wizard for the authenticated user."""
    current_user = _get_user(db, current_user_email)
    if current_user.onboarding_dismissed_at is None:
        current_user.onboarding_dismissed_at = datetime.utcnow()
        db.commit()
    return {"dismissed": True}
