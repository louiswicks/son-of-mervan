# routers/reports.py
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, User, MonthlyData
from security import verify_token

router = APIRouter(prefix="/reports", tags=["reports"])

_QUARTER_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12],
}


def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _find_month(all_rows: List[MonthlyData], month_str: str) -> Optional[MonthlyData]:
    for row in all_rows:
        if row.month == month_str:
            return row
    return None


@router.get("/quarterly")
def quarterly_report(
    year: int = Query(..., description="Year e.g. 2026"),
    quarter: int = Query(..., ge=1, le=4, description="Quarter 1–4"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Aggregates 3 months of income and expense data into a quarterly summary.
    Returns partial data for months that exist; zeroed placeholders for months
    with no data.
    """
    user = _require_user(db, current_user)

    all_rows: List[MonthlyData] = (
        db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    )

    month_nums = _QUARTER_MONTHS[quarter]
    months_out: List[Dict[str, Any]] = []

    salary_total = 0.0
    expense_total = 0.0

    for mo in month_nums:
        month_str = f"{year:04d}-{mo:02d}"
        row = _find_month(all_rows, month_str)

        if row is None:
            months_out.append(
                {
                    "month": month_str,
                    "salary": 0.0,
                    "expense_total": 0.0,
                    "savings": 0.0,
                    "savings_rate_pct": None,
                    "has_data": False,
                }
            )
            continue

        salary_actual = row.salary_actual
        salary = float(
            salary_actual if salary_actual is not None else (row.salary_planned or 0.0)
        )
        total_actual = row.total_actual
        expenses = float(
            total_actual if total_actual is not None else (row.total_planned or 0.0)
        )
        savings = salary - expenses
        savings_rate = round(savings / salary * 100, 2) if salary else None

        months_out.append(
            {
                "month": month_str,
                "salary": salary,
                "expense_total": expenses,
                "savings": savings,
                "savings_rate_pct": savings_rate,
                "has_data": True,
            }
        )

        salary_total += salary
        expense_total += expenses

    savings_total = salary_total - expense_total
    savings_rate_pct = (
        round(savings_total / salary_total * 100, 2) if salary_total else None
    )

    return {
        "year": year,
        "quarter": quarter,
        "months": months_out,
        "totals": {
            "salary_total": salary_total,
            "expense_total": expense_total,
            "savings_total": savings_total,
            "savings_rate_pct": savings_rate_pct,
        },
    }
