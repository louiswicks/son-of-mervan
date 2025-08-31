# routers/overview.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any, List

from database import get_db, User, MonthlyData, MonthlyExpense
from security import verify_token

router = APIRouter(prefix="/overview", tags=["overview"])

def month_key(year: int, m: int) -> str:
    return f"{year:04d}-{m:02d}"

@router.get("/annual")
def annual_overview(
    year: int = Query(None, description="Year like 2025. Default = current year."),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Aggregates planned vs actual per month for the given user/year
    from MonthlyData/MonthlyExpense.
    """
    if year is None:
        year = datetime.utcnow().year

    # user
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        # create empty user overview rather than 404
        months: List[Dict[str, Any]] = [
            {
                "month": month_key(year, m),
                "planned_salary": 0.0,
                "actual_salary": 0.0,
                "total_planned": 0.0,
                "total_actual": 0.0,
                "remaining_actual": 0.0,
            }
            for m in range(1, 13)
        ]
        return {
            "year": year,
            "months": months,
            "totals": {
                "planned_salary": 0.0,
                "actual_salary": 0.0,
                "total_planned": 0.0,
                "total_actual": 0.0,
                "remaining_actual": 0.0,
            },
        }

    # fetch all month rows for that year
    like_prefix = f"{year:04d}-"
    month_rows: List[MonthlyData] = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id, MonthlyData.month.like(f"{like_prefix}%"))
        .all()
    )

    # index by month string
    by_month: Dict[str, MonthlyData] = {row.month: row for row in month_rows}

    months_out: List[Dict[str, Any]] = []
    totals = {
        "planned_salary": 0.0,
        "actual_salary": 0.0,
        "total_planned": 0.0,
        "total_actual": 0.0,
        "remaining_actual": 0.0,
    }

    for m in range(1, 12 + 1):
        key = month_key(year, m)
        row = by_month.get(key)

        if row:
            planned_salary = float(row.salary_planned or 0.0)
            actual_salary = float(row.salary_actual or 0.0)
            total_planned = float(row.total_planned or 0.0)
            total_actual = float(row.total_actual or 0.0)
            remaining_actual = (
                float(row.remaining_actual)
                if row.remaining_actual is not None
                else actual_salary - total_actual
            )
        else:
            planned_salary = actual_salary = total_planned = total_actual = remaining_actual = 0.0


        months_out.append(
            {
                "month": key,
                "planned_salary": planned_salary,
                "actual_salary": actual_salary,
                "total_planned": total_planned,
                "total_actual": total_actual,
                "remaining_actual": remaining_actual,
            }
        )

        totals["planned_salary"] += planned_salary
        totals["actual_salary"] += actual_salary
        totals["total_planned"] += total_planned
        totals["total_actual"] += total_actual
        totals["remaining_actual"] += remaining_actual

    return {"year": year, "months": months_out, "totals": totals}
