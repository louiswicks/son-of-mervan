# routers/insights.py
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, User, MonthlyData, MonthlyExpense
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


# -------------------- helpers --------------------

def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _normalize_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    y, mo = parts
    return f"{int(y):04d}-{int(mo):02d}"


def _prev_month_str(month_norm: str) -> str:
    year, mo = map(int, month_norm.split("-"))
    mo -= 1
    if mo == 0:
        mo = 12
        year -= 1
    return f"{year:04d}-{mo:02d}"


def _month_list(n: int) -> list[str]:
    """Return list of n month strings ending with the current month, oldest first."""
    now = datetime.utcnow()
    months = []
    for i in range(n - 1, -1, -1):
        year = now.year
        mo = now.month - i
        while mo <= 0:
            mo += 12
            year -= 1
        months.append(f"{year:04d}-{mo:02d}")
    return months


def _find_month(all_rows: list[MonthlyData], month_str: str) -> Optional[MonthlyData]:
    for row in all_rows:
        if row.month == month_str:
            return row
    return None


def _category_totals(db: Session, month_row: Optional[MonthlyData]) -> Dict[str, Dict[str, float]]:
    """Return {category: {planned, actual}} for the given MonthlyData row."""
    if not month_row:
        return {}
    expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,  # noqa: E711
        )
        .all()
    )
    totals: Dict[str, Dict[str, float]] = {}
    for e in expenses:
        cat = e.category or "Other"
        if cat not in totals:
            totals[cat] = {"planned": 0.0, "actual": 0.0}
        totals[cat]["planned"] += float(e.planned_amount or 0.0)
        totals[cat]["actual"] += float(e.actual_amount or 0.0)
    return totals


# -------------------- endpoints --------------------

@router.get("/monthly-summary")
def monthly_summary(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Month-over-month spending summary: per-category % change vs previous month,
    biggest overspend, net income, and plain-English insight cards.
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    current_row = _find_month(all_rows, month_norm)
    prev_row = _find_month(all_rows, _prev_month_str(month_norm))

    current_cats = _category_totals(db, current_row)
    prev_cats = _category_totals(db, prev_row)

    all_categories = set(current_cats.keys()) | set(prev_cats.keys())
    categories: Dict[str, Any] = {}
    for cat in sorted(all_categories):
        curr = current_cats.get(cat, {"planned": 0.0, "actual": 0.0})
        prev_actual = prev_cats.get(cat, {}).get("actual", 0.0)

        pct_change: Optional[float] = None
        if prev_actual > 0:
            pct_change = round(((curr["actual"] - prev_actual) / prev_actual) * 100, 1)

        variance = curr["actual"] - curr["planned"]
        categories[cat] = {
            "planned": round(curr["planned"], 2),
            "actual": round(curr["actual"], 2),
            "prev_month_actual": round(prev_actual, 2),
            "pct_change": pct_change,
            "over_budget": curr["actual"] > curr["planned"] and curr["planned"] > 0,
            "variance": round(variance, 2),
        }

    salary_actual = float(current_row.salary_actual or 0.0) if current_row else 0.0
    total_actual = sum(v["actual"] for v in categories.values())
    net_income = salary_actual - total_actual

    # Biggest overspend (most negative variance)
    overspenders = {c: v for c, v in categories.items() if v["over_budget"]}
    biggest_overspend = (
        min(overspenders, key=lambda c: overspenders[c]["variance"])
        if overspenders else None
    )

    # Plain-English insight cards (limit to top 5 most impactful)
    raw_insights = []
    for cat, data in categories.items():
        if data["pct_change"] is not None and abs(data["pct_change"]) >= 10:
            direction = "up" if data["pct_change"] > 0 else "down"
            raw_insights.append({
                "type": "trend",
                "category": cat,
                "text": (
                    f"Your {cat} spending is {direction} "
                    f"{abs(data['pct_change']):.0f}% vs last month."
                ),
                "positive": data["pct_change"] < 0,
                "impact": abs(data["actual"] - data["prev_month_actual"]),
            })
        if data["over_budget"] and data["planned"] > 0:
            raw_insights.append({
                "type": "overspend",
                "category": cat,
                "text": (
                    f"You've exceeded your {cat} budget by "
                    f"£{abs(data['variance']):.2f}."
                ),
                "positive": False,
                "impact": abs(data["variance"]),
            })

    # Sort by impact (highest first) and cap at 5
    raw_insights.sort(key=lambda x: x["impact"], reverse=True)
    insights = [{k: v for k, v in i.items() if k != "impact"} for i in raw_insights[:5]]

    # Net income card always first
    if salary_actual > 0:
        if net_income >= 0:
            net_card = {
                "type": "net_income",
                "category": None,
                "text": f"You have £{net_income:.2f} remaining this month.",
                "positive": True,
            }
        else:
            net_card = {
                "type": "net_income",
                "category": None,
                "text": f"You're over budget by £{abs(net_income):.2f} this month.",
                "positive": False,
            }
        insights.insert(0, net_card)

    return {
        "month": month_norm,
        "net_income": round(net_income, 2),
        "salary_actual": round(salary_actual, 2),
        "total_actual": round(total_actual, 2),
        "categories": categories,
        "biggest_overspend": biggest_overspend,
        "insights": insights,
    }


@router.get("/trends")
def spending_trends(
    months: int = Query(6, ge=2, le=24, description="Number of months to include"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Monthly spending totals and per-category breakdown for the last N months,
    plus 3-month rolling averages for use in trend charts.
    """
    user = _require_user(db, current_user)
    month_strs = _month_list(months)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_map = {row.month: row for row in all_rows}

    monthly: list[Dict[str, Any]] = []
    for ms in month_strs:
        row = month_map.get(ms)
        if not row:
            monthly.append({
                "month": ms,
                "total_actual": 0.0,
                "salary_actual": 0.0,
                "categories": {},
            })
            continue

        expenses = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == row.id,
                MonthlyExpense.deleted_at == None,  # noqa: E711
            )
            .all()
        )
        cat_totals: Dict[str, float] = {}
        for e in expenses:
            cat = e.category or "Other"
            cat_totals[cat] = cat_totals.get(cat, 0.0) + float(e.actual_amount or 0.0)

        monthly.append({
            "month": ms,
            "total_actual": float(row.total_actual or 0.0),
            "salary_actual": float(row.salary_actual or 0.0),
            "categories": cat_totals,
        })

    all_cats = sorted({cat for m in monthly for cat in m["categories"]})

    category_trends: Dict[str, list] = {}
    rolling_averages: Dict[str, list] = {}
    for cat in all_cats:
        amounts = [m["categories"].get(cat, 0.0) for m in monthly]
        category_trends[cat] = [
            {"month": month_strs[i], "amount": round(amounts[i], 2)}
            for i in range(len(month_strs))
        ]
        # 3-month rolling average
        rolling = []
        for i in range(len(amounts)):
            window = amounts[max(0, i - 2) : i + 1]
            rolling.append(round(sum(window) / len(window), 2))
        rolling_averages[cat] = [
            {"month": month_strs[i], "amount": rolling[i]}
            for i in range(len(month_strs))
        ]

    overall_trend = [
        {
            "month": m["month"],
            "total_actual": round(m["total_actual"], 2),
            "salary_actual": round(m["salary_actual"], 2),
            "net": round(m["salary_actual"] - m["total_actual"], 2),
        }
        for m in monthly
    ]

    return {
        "months": month_strs,
        "overall_trend": overall_trend,
        "category_trends": category_trends,
        "rolling_averages": rolling_averages,
    }


@router.get("/heatmap")
def spending_heatmap(
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Monthly spending totals for each month of the year, with quartile-based
    intensity levels (0=no data, 1=low, 2=medium, 3=high, 4=very high).
    """
    y = year or datetime.utcnow().year
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()

    heatmap: list[Dict[str, Any]] = []
    max_spending = 0.0
    for mo in range(1, 13):
        month_str = f"{y:04d}-{mo:02d}"
        row = _find_month(all_rows, month_str)
        total = float(row.total_actual or 0.0) if row else 0.0
        max_spending = max(max_spending, total)
        heatmap.append({"month": month_str, "total_actual": round(total, 2)})

    # Assign quartile levels
    non_zero = sorted(m["total_actual"] for m in heatmap if m["total_actual"] > 0)
    if non_zero:
        def quartile(lst, q):
            idx = max(0, int(len(lst) * q) - 1)
            return lst[idx]
        q1 = quartile(non_zero, 0.25)
        q2 = quartile(non_zero, 0.50)
        q3 = quartile(non_zero, 0.75)
    else:
        q1, q2, q3 = 0.0, 0.0, 0.0

    for m in heatmap:
        amt = m["total_actual"]
        if amt == 0:
            m["level"] = 0
        elif amt <= q1:
            m["level"] = 1
        elif amt <= q2:
            m["level"] = 2
        elif amt <= q3:
            m["level"] = 3
        else:
            m["level"] = 4

    return {
        "year": str(y),
        "months": heatmap,
        "max_spending": round(max_spending, 2),
    }
