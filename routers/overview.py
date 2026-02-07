# routers/overview.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List

from database import get_db, User, MonthlyData, MonthlyExpense
from security import verify_token

router = APIRouter(prefix="/overview", tags=["overview"])

def _require_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/annual")
def annual_overview(
    year: Optional[int] = Query(None),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns per-month aggregates for the given year (or current year if omitted),
    plus year totals. Uses the authenticated user's email to scope data.
    """
    y = year or datetime.utcnow().year
    user = _require_user_by_email(db, current_user)

    # pull all months for that user+year
    all_months: List[MonthlyData] = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id)
        .all()
    )

    # Filter in Python after decryption
    year_str = str(y)
    months = [
        m for m in all_months 
        if m.month and m.month.startswith(f"{year_str}-")
    ]

    # Sort by month (already decrypted)
    months.sort(key=lambda m: m.month)

    # prepare 12 slots
    by_index = {int(m.month[5:7]) - 1: m for m in months if m.month and len(m.month) >= 7}
    months_out = []
    totals = {
        "planned_salary": 0.0,
        "total_planned": 0.0,
        "total_actual": 0.0,
        "remaining_actual": 0.0,
    }

    for i in range(12):
        mrow = by_index.get(i)
        if not mrow:
            months_out.append({
                "month": f"{y}-{i+1:02d}",
                "planned_salary": 0.0,
                "actual_salary": 0.0,
                "total_planned": 0.0,
                "total_actual": 0.0,
                "remaining_actual": 0.0,
            })
            continue

        planned_salary = float(mrow.salary_planned or 0.0)
        actual_salary  = float(mrow.salary_actual or 0.0)
        total_planned  = float(mrow.total_planned or 0.0)
        total_actual   = float(mrow.total_actual or 0.0)

        # prefer backend stored remaining_actual; fallback to actual_salary - total_actual
        remaining_actual = (
            float(mrow.remaining_actual) if mrow.remaining_actual is not None
            else (actual_salary - total_actual)
        )

        months_out.append({
            "month": mrow.month,
            "planned_salary": planned_salary,
            "actual_salary": actual_salary,
            "total_planned": total_planned,
            "total_actual": total_actual,
            "remaining_actual": remaining_actual,
        })

        totals["planned_salary"]   += planned_salary
        totals["total_planned"]    += total_planned
        totals["total_actual"]     += total_actual
        totals["remaining_actual"] += remaining_actual

    return {"months": months_out, "totals": totals}
