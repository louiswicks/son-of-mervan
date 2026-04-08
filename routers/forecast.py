"""
routers/forecast.py — Cashflow Forecasting

Endpoint:
  GET /forecast?months=3&salary_override=<float>

Projects the user's monthly cashflow over N months based on:
- The most recent planned salary (or an explicit salary_override)
- All active recurring expenses scaled to their monthly cost

Response is a list of monthly projections:
  { month, projected_income, projected_expenses, projected_balance, running_balance, deficit }
"""
import calendar
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, MonthlyData, RecurringExpense, User
from security import verify_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecast", tags=["forecast"])


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _monthly_cost(rec: RecurringExpense, year: int, month: int) -> float:
    """Scale a recurring expense's planned_amount to its effective monthly cost."""
    if rec.frequency == "daily":
        return rec.planned_amount * calendar.monthrange(year, month)[1]
    if rec.frequency == "weekly":
        return rec.planned_amount * 4
    if rec.frequency == "yearly":
        return rec.planned_amount / 12  # amortise over 12 months for forecasting
    return rec.planned_amount  # monthly


def _latest_salary(db: Session, user_id: int) -> float:
    """
    Return the salary_planned from the user's most recently-saved MonthlyData row.
    Decrypts all rows in Python (Fernet is non-deterministic so we can't ORDER
    BY the encrypted column).  Returns 0.0 when no data exists yet.
    """
    rows = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user_id)
        .all()
    )
    if not rows:
        return 0.0

    # Sort by decrypted month string descending to find the latest
    def _month_key(row):
        try:
            return row.month  # hybrid property; returns "YYYY-MM"
        except Exception:
            return ""

    latest = max(rows, key=_month_key)
    try:
        return float(latest.salary_planned or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _active_recurring_expenses(db: Session, user_id: int, as_of: datetime) -> list[RecurringExpense]:
    """Return all non-deleted recurring expenses that are active as of *as_of*."""
    rows = (
        db.query(RecurringExpense)
        .filter(
            RecurringExpense.user_id == user_id,
            RecurringExpense.deleted_at == None,
            RecurringExpense.start_date <= as_of,
        )
        .all()
    )
    return [r for r in rows if r.end_date is None or r.end_date >= as_of]


# ---------- endpoint ----------

@router.get("")
def get_forecast(
    months: int = Query(default=3, ge=1, le=12, description="Number of months to project (1–12)"),
    salary_override: float = Query(default=None, ge=0, description="Override monthly salary for projection"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Return a cashflow forecast for the next N months.

    - Uses the most recent planned salary unless *salary_override* is supplied.
    - Recurring expenses are scaled to their effective monthly cost.
    - running_balance accumulates month over month.
    - deficit=true when the month's projected_balance is negative.
    """
    user = _get_user(db, current_user)

    income = salary_override if salary_override is not None else _latest_salary(db, user.id)

    # Start from the first day of *next* month
    today = datetime.utcnow()
    if today.month == 12:
        start_year, start_month = today.year + 1, 1
    else:
        start_year, start_month = today.year, today.month + 1

    # Fetch active recurring expenses once; reuse for all projected months
    active_recurring = _active_recurring_expenses(db, user.id, today)

    projection = []
    running_balance = 0.0

    for i in range(months):
        year = start_year + (start_month + i - 1) // 12
        month = (start_month + i - 1) % 12 + 1
        month_label = f"{year}-{month:02d}"

        # Sum the monthly cost of all active recurring expenses for this month
        monthly_expenses = sum(_monthly_cost(r, year, month) for r in active_recurring)

        projected_balance = income - monthly_expenses
        running_balance += projected_balance

        projection.append({
            "month": month_label,
            "projected_income": round(income, 2),
            "projected_expenses": round(monthly_expenses, 2),
            "projected_balance": round(projected_balance, 2),
            "running_balance": round(running_balance, 2),
            "deficit": projected_balance < 0,
        })

    logger.info(
        "Cashflow forecast: user=%s months=%d income=%.2f",
        current_user, months, income,
    )
    return {"months": months, "monthly_income": round(income, 2), "projection": projection}
