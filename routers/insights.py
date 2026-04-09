# routers/insights.py
import calendar
import json
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from database import get_db, User, MonthlyData, MonthlyExpense, Notification, SavingsGoal, SavingsContribution
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])

MAX_AI_REVIEWS_PER_DAY = 3
# In-memory fallback for rate limiting when Redis is unavailable (resets on restart)
_ai_review_counts: Dict[str, int] = {}


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
    try:
        return f"{int(y):04d}-{int(mo):02d}"
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")


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


@router.get("/month-close-summary")
def month_close_summary(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Per-category unspent budget for the given month (planned - actual where positive).
    Intended to surface surplus at month-end so the user can move it to savings.
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_row = _find_month(all_rows, month_norm)

    if not month_row:
        return {"month": month_norm, "total_unspent": 0.0, "categories": []}

    cat_data = _category_totals(db, month_row)

    categories = []
    for cat, v in cat_data.items():
        planned = round(float(v["planned"]), 2)
        actual = round(float(v["actual"]), 2)
        unspent = round(max(0.0, planned - actual), 2)
        categories.append({"category": cat, "planned": planned, "actual": actual, "unspent": unspent})

    # Sort by unspent descending
    categories.sort(key=lambda x: x["unspent"], reverse=True)
    total_unspent = round(sum(c["unspent"] for c in categories), 2)

    return {"month": month_norm, "total_unspent": total_unspent, "categories": categories}


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

    # Use selectinload to fetch all expenses in one query, avoiding N+1.
    all_rows = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id)
        .options(selectinload(MonthlyData.expenses))
        .all()
    )
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

        # Expenses already loaded via selectinload — no extra DB query.
        expenses = [e for e in row.expenses if e.deleted_at is None]
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


@router.get("/health-score")
def financial_health_score(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Monthly Financial Health Score (0–100).

    Three weighted components:
      - Savings rate    (40%): how much of income was saved this month
      - Budget adherence (30%): how many expense categories stayed within plan
      - Emergency fund   (30%): months of expenses covered by savings goals

    Score bands: red 0–39, amber 40–69, green 70–100.
    Returns score=0 with no data (not an error).
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    # ── 1. Savings rate ──────────────────────────────────────────────────────
    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_row = _find_month(all_rows, month_norm)

    salary_actual = float(month_row.salary_actual or 0.0) if month_row else 0.0
    total_actual = float(month_row.total_actual or 0.0) if month_row else 0.0

    if salary_actual > 0:
        savings_rate_pct = max(0.0, (salary_actual - total_actual) / salary_actual * 100.0)
        # 20%+ savings = full marks; linear below
        savings_component = min(100.0, savings_rate_pct / 20.0 * 100.0)
        savings_detail = f"Saved {savings_rate_pct:.1f}% of income this month"
    else:
        savings_rate_pct = 0.0
        savings_component = 0.0
        savings_detail = "No income data for this month"

    # ── 2. Budget adherence ──────────────────────────────────────────────────
    cat_data = _category_totals(db, month_row)
    cats_with_budget = [(cat, v) for cat, v in cat_data.items() if v["planned"] > 0]
    if cats_with_budget:
        within_budget = sum(1 for _, v in cats_with_budget if v["actual"] <= v["planned"])
        total_with_budget = len(cats_with_budget)
        adherence_pct = within_budget / total_with_budget * 100.0
        adherence_component = adherence_pct
        adherence_detail = f"{within_budget} of {total_with_budget} categories within budget"
    else:
        within_budget = 0
        total_with_budget = 0
        adherence_component = 0.0  # no data → 0 points
        adherence_detail = "No planned budget amounts set"

    # ── 3. Emergency fund coverage ───────────────────────────────────────────
    # Total saved across all active goals
    goals = (
        db.query(SavingsGoal)
        .filter(SavingsGoal.user_id == user.id, SavingsGoal.deleted_at == None)  # noqa: E711
        .all()
    )
    total_savings = 0.0
    for goal in goals:
        contribs = db.query(SavingsContribution).filter(
            SavingsContribution.goal_id == goal.id
        ).all()
        total_savings += sum(c.amount for c in contribs)

    # Average monthly actual spend over the last 3 months (including requested month)
    year, mo = map(int, month_norm.split("-"))
    last_3_months = []
    for i in range(3):
        m_mo = mo - i
        m_yr = year
        while m_mo <= 0:
            m_mo += 12
            m_yr -= 1
        last_3_months.append(f"{m_yr:04d}-{m_mo:02d}")

    monthly_expenses = []
    for ms in last_3_months:
        row = _find_month(all_rows, ms)
        if row:
            monthly_expenses.append(float(row.total_actual or 0.0))

    avg_monthly_expenses = sum(monthly_expenses) / len(monthly_expenses) if monthly_expenses else 0.0

    if avg_monthly_expenses > 0:
        coverage_months = total_savings / avg_monthly_expenses
        # 3 months coverage = full marks; linear below
        emergency_component = min(100.0, coverage_months / 3.0 * 100.0)
        emergency_detail = f"{coverage_months:.1f} months of expenses covered by savings goals"
    else:
        coverage_months = 0.0
        emergency_component = 0.0
        emergency_detail = "No expense data to calculate coverage"

    # ── Final score ──────────────────────────────────────────────────────────
    score = round(savings_component * 0.4 + adherence_component * 0.3 + emergency_component * 0.3)
    if score >= 70:
        band = "green"
    elif score >= 40:
        band = "amber"
    else:
        band = "red"

    # Contribution of each component to the final score
    savings_pts = round(savings_component * 0.4)
    adherence_pts = round(adherence_component * 0.3)
    emergency_pts = round(emergency_component * 0.3)

    explanations = [
        f"Savings rate ({savings_rate_pct:.1f}%): contributes {savings_pts} of {score} points.",
        f"Budget adherence: {adherence_detail.lower()}, contributing {adherence_pts} points.",
        f"Emergency fund: {emergency_detail.lower()}, contributing {emergency_pts} points.",
    ]

    return {
        "month": month_norm,
        "score": score,
        "band": band,
        "components": {
            "savings_rate": {
                "score": round(savings_component),
                "weight": 0.4,
                "detail": savings_detail,
                "raw_value": round(savings_rate_pct, 2),
            },
            "budget_adherence": {
                "score": round(adherence_component),
                "weight": 0.3,
                "detail": adherence_detail,
                "raw_value": round(adherence_pct if cats_with_budget else 0.0, 2),
            },
            "emergency_fund": {
                "score": round(emergency_component),
                "weight": 0.3,
                "detail": emergency_detail,
                "raw_value": round(coverage_months, 2),
            },
        },
        "explanations": explanations,
    }


@router.get("/suggest-category")
def suggest_category(
    name: str = Query(..., min_length=2, description="Expense name (min 2 chars)"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return the most frequently used category for the given expense name,
    based solely on the authenticated user's own history.

    Matching is case-insensitive substring: "tesco" matches "Tesco Express".
    Returns null suggestion when there are fewer than 2 history matches.
    """
    user = _require_user(db, current_user)

    all_monthly = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    if not all_monthly:
        return {"suggestion": None, "count": 0, "total_matches": 0}

    monthly_ids = [m.id for m in all_monthly]
    expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id.in_(monthly_ids),
            MonthlyExpense.deleted_at == None,  # noqa: E711
        )
        .all()
    )

    name_lower = name.strip().lower()
    category_counts: Dict[str, int] = {}
    for expense in expenses:
        exp_name = (expense.name or "").lower()
        if name_lower in exp_name:
            cat = expense.category or "Other"
            category_counts[cat] = category_counts.get(cat, 0) + 1

    if not category_counts:
        return {"suggestion": None, "count": 0, "total_matches": 0}

    best_category = max(category_counts, key=lambda c: category_counts[c])
    total = sum(category_counts.values())
    return {
        "suggestion": best_category,
        "count": category_counts[best_category],
        "total_matches": total,
    }


@router.get("/pace")
def spending_pace(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Weekly spending pace indicator.

    Computes a linear projection of month-end spend per category:
        projected = (actual_so_far / days_elapsed) × days_in_month

    Returns per-category projections and flags any category projected to
    overspend its planned budget by more than 10%.
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    year, mo = map(int, month_norm.split("-"))
    days_in_month = calendar.monthrange(year, mo)[1]

    today = datetime.utcnow().date()
    month_start = today.replace(year=year, month=mo, day=1)
    month_end = month_start.replace(day=days_in_month)

    if today < month_start:
        # Future month — no actuals yet
        return {
            "month": month_norm,
            "days_elapsed": 0,
            "days_in_month": days_in_month,
            "categories": {},
            "overall": None,
            "warnings": [],
        }

    if today >= month_end:
        days_elapsed = days_in_month
    else:
        days_elapsed = today.day

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_row = _find_month(all_rows, month_norm)
    cat_data = _category_totals(db, month_row)

    categories: Dict[str, Any] = {}
    warnings: List[Dict[str, Any]] = []

    for cat, totals in cat_data.items():
        actual = totals["actual"]
        planned = totals["planned"]

        if days_elapsed > 0:
            projected = round((actual / days_elapsed) * days_in_month, 2)
        else:
            projected = 0.0

        overspend_amount = round(projected - planned, 2) if planned > 0 else None
        is_warning = (
            planned > 0
            and projected > planned * 1.10
        )

        categories[cat] = {
            "actual_so_far": round(actual, 2),
            "planned": round(planned, 2),
            "projected_month_end": projected,
            "overspend_amount": overspend_amount,
            "is_on_pace_to_overspend": is_warning,
        }

        if is_warning:
            warnings.append({
                "category": cat,
                "projected": projected,
                "planned": round(planned, 2),
                "overspend_amount": overspend_amount,
                "message": (
                    f"At this pace you'll overspend {cat} by "
                    f"£{overspend_amount:.2f} by month end."
                ),
            })

    # Overall projection
    total_actual = sum(v["actual"] for v in cat_data.values())
    total_planned = sum(v["planned"] for v in cat_data.values())
    if days_elapsed > 0:
        total_projected = round((total_actual / days_elapsed) * days_in_month, 2)
    else:
        total_projected = 0.0

    overall = {
        "actual_so_far": round(total_actual, 2),
        "planned": round(total_planned, 2),
        "projected_month_end": total_projected,
    }

    return {
        "month": month_norm,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "categories": categories,
        "overall": overall,
        "warnings": warnings,
    }


# -------------------- AI review helpers --------------------

def _check_and_increment_ai_rate_limit(user_id: int) -> tuple[bool, int]:
    """
    Check and increment the AI review rate limit for today.
    Returns (allowed, remaining_after_this_call).
    Uses Redis if available, falls back to in-memory dict.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"ai_review:{user_id}:{today}"

    # Try Redis atomic increment first
    try:
        from core.cache import _get_client  # noqa: PLC0415
        redis_client = _get_client()
        if redis_client is not None:
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, 86400)
            remaining = max(0, MAX_AI_REVIEWS_PER_DAY - count)
            return count <= MAX_AI_REVIEWS_PER_DAY, remaining
    except Exception:
        logger.warning("Redis rate limit check failed, falling back to in-memory")

    # In-memory fallback
    current = _ai_review_counts.get(key, 0) + 1
    _ai_review_counts[key] = current
    remaining = max(0, MAX_AI_REVIEWS_PER_DAY - current)
    return current <= MAX_AI_REVIEWS_PER_DAY, remaining


def _build_ai_prompt(context: Dict[str, Any]) -> str:
    """Build the anonymised prompt sent to Claude. No raw expense names are included."""
    month = context["month"]
    currency = context["currency"]
    salary_planned = context["salary_planned"]
    salary_actual = context["salary_actual"]
    total_planned = context["total_planned"]
    total_actual = context["total_actual"]
    savings_rate = context["savings_rate"]
    categories = context["categories"]
    health_score = context.get("health_score")

    lines = [
        f"You are a friendly, encouraging personal finance coach reviewing a user's budget for {month}.",
        "Provide a concise financial summary (3–5 sentences) followed by 2–3 specific, actionable recommendations.",
        "Be warm but honest. Do not mention any merchant names or specific transaction details.",
        "Keep your entire response under 220 words.",
        "",
        f"Monthly Overview ({currency}):",
        f"  Income:   planned {salary_planned:.2f}, actual {salary_actual:.2f}",
        f"  Spending: planned {total_planned:.2f}, actual {total_actual:.2f}",
        f"  Savings rate this month: {savings_rate:.1f}%",
    ]

    if health_score is not None:
        lines.append(f"  Financial health score: {health_score}/100")

    lines.append("")
    lines.append("Category Breakdown:")
    for cat, data in categories.items():
        variance_pct = data.get("variance_pct")
        pct_str = f" ({variance_pct:+.1f}% vs plan)" if variance_pct is not None else ""
        over = " [OVER BUDGET]" if data.get("over_budget") else ""
        lines.append(
            f"  {cat}: planned {data['planned']:.2f}, actual {data['actual']:.2f}{pct_str}{over}"
        )

    return "\n".join(lines)


async def _stream_ai_review(context: Dict[str, Any]):
    """Async generator that yields SSE-formatted chunks from Claude."""
    from core.config import settings  # noqa: PLC0415

    if not settings.ANTHROPIC_API_KEY:
        yield f"data: {json.dumps({'error': 'AI review is not configured on this server.'})}\n\n"
        return

    prompt = _build_ai_prompt(context)

    try:
        import anthropic  # noqa: PLC0415
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        async with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'chunk': text})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    except Exception as exc:
        logger.error("AI review streaming failed: %s", exc)
        yield f"data: {json.dumps({'error': 'AI review failed. Please try again later.'})}\n\n"


# -------------------- anomaly detection --------------------

@router.get("/anomalies")
def spending_anomalies(
    month: str = Query(..., description="Month to analyse, YYYY-MM"),
    lookback: int = Query(3, ge=2, le=12, description="Prior months to use as baseline (2–12)"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Detect spending anomalies by comparing each category's actual spend in *month*
    against the distribution of the prior *lookback* months.

    Severity thresholds:
      high   — z-score ≥ 2.0, or >100% above mean when std dev is 0
      medium — z-score ≥ 1.5, or >50% above mean when std dev is 0
      low    — z-score ≥ 1.0 and spend >30% above mean

    Categories with no prior history are excluded (no baseline to compare against).
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    current_row = _find_month(all_rows, month_norm)

    if not current_row:
        return {
            "month": month_norm,
            "anomalies": [],
            "lookback_months": lookback,
            "categories_analysed": 0,
        }

    # Build list of prior month strings (oldest → newest, excluding current month)
    year, mo = map(int, month_norm.split("-"))
    prior_months: list[str] = []
    for i in range(lookback, 0, -1):
        pmo = mo - i
        pyr = year
        while pmo <= 0:
            pmo += 12
            pyr -= 1
        prior_months.append(f"{pyr:04d}-{pmo:02d}")

    # Collect per-category actual spend for each prior month that has data
    history: Dict[str, List[float]] = {}
    for pm in prior_months:
        pm_row = _find_month(all_rows, pm)
        if pm_row is None:
            continue
        for cat, vals in _category_totals(db, pm_row).items():
            history.setdefault(cat, []).append(vals["actual"])

    current_cats = _category_totals(db, current_row)

    _severity_order = {"high": 0, "medium": 1, "low": 2}
    anomalies: List[Dict[str, Any]] = []

    for cat, vals in current_cats.items():
        current_actual = vals["actual"]
        if current_actual <= 0:
            continue

        hist_values = history.get(cat)
        if not hist_values:
            continue  # No historical baseline — cannot determine anomaly

        n = len(hist_values)
        mean = sum(hist_values) / n
        if mean <= 0:
            continue  # Historical average is zero — skip to avoid division issues

        pct_change = round(((current_actual - mean) / mean) * 100, 1)

        std_dev = (sum((x - mean) ** 2 for x in hist_values) / n) ** 0.5

        if std_dev == 0:
            # All prior months identical — classify by pct_change only
            if pct_change > 100:
                severity = "high"
            elif pct_change > 50:
                severity = "medium"
            else:
                continue
            anomalies.append({
                "category": cat,
                "current_amount": round(current_actual, 2),
                "historical_avg": round(mean, 2),
                "pct_change": pct_change,
                "z_score": None,
                "severity": severity,
                "message": f"{cat} spending is {pct_change:.0f}% above your usual amount.",
            })
            continue

        z_score = round((current_actual - mean) / std_dev, 2)

        if z_score >= 2.0:
            severity = "high"
        elif z_score >= 1.5:
            severity = "medium"
        elif z_score >= 1.0 and pct_change >= 30:
            severity = "low"
        else:
            continue  # Within normal range

        anomalies.append({
            "category": cat,
            "current_amount": round(current_actual, 2),
            "historical_avg": round(mean, 2),
            "pct_change": pct_change,
            "z_score": z_score,
            "severity": severity,
            "message": (
                f"{cat} spending is {pct_change:.0f}% above your "
                f"{lookback}-month average."
            ),
        })

    anomalies.sort(key=lambda x: _severity_order[x["severity"]])

    return {
        "month": month_norm,
        "anomalies": anomalies,
        "lookback_months": lookback,
        "categories_analysed": len(current_cats),
    }


# -------------------- spending streaks --------------------

@router.get("/streaks")
def spending_streaks(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Compute the user's under-budget streak.

    A month is "tracked" when it has non-zero total_actual spend recorded.
    Among tracked months:
      - Under-budget: total_actual <= total_planned (and total_planned > 0)
      - Over-budget: total_actual > total_planned, or no planned amount set

    current_streak  — consecutive under-budget months ending at the most recent tracked month.
    longest_streak  — maximum streak across all history.
    total_tracked   — total number of months with actual data.
    months_under    — total number of months that were under-budget.
    """
    user = _require_user(db, current_user)
    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()

    # Filter to months that have actual spending data and sort chronologically
    tracked: list[tuple[str, bool]] = []  # (month_str, is_under_budget)
    for row in all_rows:
        month_str = row.month
        if not month_str:
            continue
        total_actual = float(row.total_actual or 0.0)
        if total_actual <= 0:
            continue  # No actual data recorded — skip
        total_planned = float(row.total_planned or 0.0)
        is_under = total_planned > 0 and total_actual <= total_planned
        tracked.append((month_str, is_under))

    # Sort oldest → newest
    tracked.sort(key=lambda x: x[0])

    if not tracked:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "total_tracked": 0,
            "months_under": 0,
        }

    # Compute longest streak and current streak
    longest = 0
    run = 0
    for _, is_under in tracked:
        if is_under:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    # Current streak = run at end of sorted list (already computed as `run`)
    current = run

    months_under = sum(1 for _, is_under in tracked if is_under)

    return {
        "current_streak": current,
        "longest_streak": longest,
        "total_tracked": len(tracked),
        "months_under": months_under,
    }


# -------------------- AI review endpoint --------------------

@router.post("/ai-review")
async def ai_financial_review(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Generate an AI-powered monthly financial review using Claude.

    Opt-in endpoint — rate-limited to 3 requests per user per day.
    Anonymised category-level data is sent to Claude; no raw expense names are included.
    Response streams as Server-Sent Events (SSE).
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    allowed, remaining = _check_and_increment_ai_rate_limit(user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"AI review limit reached. You have {MAX_AI_REVIEWS_PER_DAY} reviews per day.",
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "86400"},
        )

    # Gather anonymised context — no raw expense names
    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_row = _find_month(all_rows, month_norm)
    cat_data = _category_totals(db, month_row)

    salary_planned = float(month_row.salary_planned or 0.0) if month_row else 0.0
    salary_actual = float(month_row.salary_actual or 0.0) if month_row else 0.0
    total_planned = float(month_row.total_planned or 0.0) if month_row else 0.0
    total_actual = float(month_row.total_actual or 0.0) if month_row else 0.0
    savings_rate = (
        max(0.0, (salary_actual - total_actual) / salary_actual * 100.0)
        if salary_actual > 0 else 0.0
    )

    categories: Dict[str, Any] = {}
    for cat, v in cat_data.items():
        planned = v["planned"]
        actual = v["actual"]
        variance_pct = ((actual - planned) / planned * 100.0) if planned > 0 else None
        categories[cat] = {
            "planned": round(planned, 2),
            "actual": round(actual, 2),
            "variance_pct": round(variance_pct, 1) if variance_pct is not None else None,
            "over_budget": actual > planned and planned > 0,
        }

    context: Dict[str, Any] = {
        "month": month_norm,
        "currency": user.base_currency or "GBP",
        "salary_planned": round(salary_planned, 2),
        "salary_actual": round(salary_actual, 2),
        "total_planned": round(total_planned, 2),
        "total_actual": round(total_actual, 2),
        "savings_rate": round(savings_rate, 1),
        "categories": categories,
    }

    return StreamingResponse(
        _stream_ai_review(context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-RateLimit-Remaining": str(remaining),
        },
    )


# -------------------- expense search --------------------

@router.get("/search")
def expense_search(
    q: Optional[str] = Query(None, description="Keyword substring match on expense name"),
    category: Optional[str] = Query(None, description="Exact category match (case-insensitive)"),
    from_month: Optional[str] = Query(None, alias="from", description="Start month YYYY-MM (inclusive)"),
    to_month: Optional[str] = Query(None, alias="to", description="End month YYYY-MM (inclusive)"),
    sort: str = Query("date", description="Sort order: 'date' (default, month desc) or 'amount' (planned_amount desc)"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Full-text search across all expenses for the authenticated user.

    Because all financial fields are Fernet-encrypted (non-deterministic), all
    filtering happens in Python after fetching from the DB — O(n) by design.
    """
    user = _require_user(db, current_user)

    # Normalize optional month bounds
    from_norm = _normalize_month(from_month) if from_month else None
    to_norm = _normalize_month(to_month) if to_month else None

    # Load all MonthlyData for this user, build a month→row map
    all_rows: List[MonthlyData] = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    # Build dict of month_str → row so we can attach month to each expense
    month_map: Dict[int, str] = {row.id: (row.month or "") for row in all_rows}

    if not all_rows:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    monthly_ids = [row.id for row in all_rows]

    # Fetch all non-deleted expenses across all months
    all_expenses: List[MonthlyExpense] = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id.in_(monthly_ids),
            MonthlyExpense.deleted_at == None,  # noqa: E711
        )
        .all()
    )

    # Python-side filtering (encryption prevents SQL predicates)
    q_lower = q.strip().lower() if q else None
    cat_lower = category.strip().lower() if category else None

    results = []
    for exp in all_expenses:
        month_str = month_map.get(exp.monthly_data_id, "")

        # Month range filter
        if from_norm and month_str < from_norm:
            continue
        if to_norm and month_str > to_norm:
            continue

        # Keyword filter (case-insensitive substring)
        if q_lower:
            exp_name = (exp.name or "").lower()
            if q_lower not in exp_name:
                continue

        # Category filter (case-insensitive exact match)
        if cat_lower:
            exp_cat = (exp.category or "").lower()
            if exp_cat != cat_lower:
                continue

        results.append({
            "id": exp.id,
            "month": month_str,
            "name": exp.name,
            "category": exp.category,
            "planned_amount": round(float(exp.planned_amount or 0), 2),
            "actual_amount": round(float(exp.actual_amount or 0), 2),
            "currency": exp.currency,
            "note": exp.note,
            "tags": exp.tags,
        })

    # Sorting
    if sort == "amount":
        results.sort(key=lambda x: x["planned_amount"], reverse=True)
    else:
        # Default: newest month first, then by name within the same month
        results.sort(key=lambda x: (x["month"], x["name"] or ""), reverse=True)

    total = len(results)
    offset = (page - 1) * page_size
    page_items = results[offset: offset + page_size]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# -------------------- spending velocity --------------------

@router.get("/spending-velocity")
def spending_velocity(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return the user's spending velocity projection for the given month.

    Projects month-end spend as:
        projected_total = (actual_ytd / days_elapsed) * days_in_month

    on_track is True when projected_total <= planned_total * 1.10.
    Returns zeroed structure when no data exists for the month.
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    year, mo = map(int, month_norm.split("-"))
    days_in_month = calendar.monthrange(year, mo)[1]

    today = datetime.utcnow().date()
    month_start = date(year, mo, 1)
    month_end = date(year, mo, days_in_month)

    if today < month_start:
        days_elapsed = 0
    elif today >= month_end:
        days_elapsed = days_in_month
    else:
        days_elapsed = today.day

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_row = _find_month(all_rows, month_norm)

    if not month_row:
        return {
            "month": month_norm,
            "actual_ytd": 0.0,
            "planned_total": 0.0,
            "projected_total": 0.0,
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "on_track": True,
        }

    actual_ytd = float(month_row.total_actual or 0.0)
    planned_total = float(month_row.total_planned or 0.0)

    if days_elapsed > 0:
        projected_total = round((actual_ytd / days_elapsed) * days_in_month, 2)
    else:
        projected_total = 0.0

    on_track = planned_total <= 0 or projected_total <= planned_total * 1.10

    return {
        "month": month_norm,
        "actual_ytd": round(actual_ytd, 2),
        "planned_total": round(planned_total, 2),
        "projected_total": projected_total,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "on_track": on_track,
    }


@router.get("/month-performance")
def month_performance(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    KPI summary for a given month powering the "This Month" dashboard card.

    Returns salary, actual vs planned totals, remaining budget, savings rate,
    per-day actual spending array for sparkline rendering, and a traffic-light status.

    Status logic:
        on_track   — actual_ytd <= planned_ytd
        warning    — actual_ytd is 101–110% of planned_ytd
        over_budget — actual_ytd > 110% of planned_ytd
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    month_row = _find_month(all_rows, month_norm)

    year, mo = map(int, month_norm.split("-"))

    if not month_row:
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "actual_ytd": 0.0,
            "planned_ytd": 0.0,
            "remaining": 0.0,
            "savings_rate_pct": 0.0,
            "daily_actuals": [],
            "status": "on_track",
        }

    salary_planned = float(month_row.salary_planned or 0.0)
    actual_ytd = float(month_row.total_actual or 0.0)
    planned_ytd = float(month_row.total_planned or 0.0)
    remaining = round(salary_planned - actual_ytd, 2)

    if salary_planned > 0:
        raw_rate = (salary_planned - actual_ytd) / salary_planned * 100
        savings_rate_pct = round(max(0.0, min(100.0, raw_rate)), 2)
    else:
        savings_rate_pct = 0.0

    # MonthlyExpense tracks monthly totals, not per-day records.
    # Return a single data point for sparkline rendering.
    daily_actuals = [{"date": f"{year:04d}-{mo:02d}-01", "amount": round(actual_ytd, 2)}] if actual_ytd > 0 else []

    # Traffic-light status
    if planned_ytd <= 0:
        status = "on_track"
    else:
        ratio = actual_ytd / planned_ytd
        if ratio <= 1.0:
            status = "on_track"
        elif ratio <= 1.10:
            status = "warning"
        else:
            status = "over_budget"

    return {
        "month": month_norm,
        "salary_planned": round(salary_planned, 2),
        "actual_ytd": round(actual_ytd, 2),
        "planned_ytd": round(planned_ytd, 2),
        "remaining": remaining,
        "savings_rate_pct": savings_rate_pct,
        "daily_actuals": daily_actuals,
        "status": status,
    }


# -------------------- spending forecast --------------------

@router.get("/spending-forecast")
def spending_forecast(
    month: str = Query(..., description="Month to forecast for, YYYY-MM"),
    lookback: int = Query(3, ge=2, le=6, description="Prior months to average (2–6)"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Predict per-category spending for *month* by averaging actual spend across
    the previous *lookback* months.

    Only categories that appear in at least one prior month are returned.
    Categories with no prior data are omitted (not returned as zero).
    Returns an empty list when no historical data exists at all.
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()

    # Build list of prior month strings (oldest → newest, excluding the target month)
    year, mo = map(int, month_norm.split("-"))
    prior_months: list[str] = []
    for i in range(lookback, 0, -1):
        pmo = mo - i
        pyr = year
        while pmo <= 0:
            pmo += 12
            pyr -= 1
        prior_months.append(f"{pyr:04d}-{pmo:02d}")

    # Collect per-category actual spend across prior months that have data
    history: Dict[str, List[float]] = {}
    for pm in prior_months:
        pm_row = _find_month(all_rows, pm)
        if pm_row is None:
            continue
        for cat, vals in _category_totals(db, pm_row).items():
            history.setdefault(cat, []).append(vals["actual"])

    if not history:
        return {
            "month": month_norm,
            "lookback": lookback,
            "categories": [],
            "total": 0.0,
        }

    categories: List[Dict[str, Any]] = []
    for cat in sorted(history.keys()):
        values = history[cat]
        avg = round(sum(values) / len(values), 2)
        categories.append({
            "category": cat,
            "predicted_amount": avg,
            "months_of_data": len(values),
        })

    total = round(sum(c["predicted_amount"] for c in categories), 2)

    return {
        "month": month_norm,
        "lookback": lookback,
        "categories": categories,
        "total": total,
    }


# -------------------- subscription tracker --------------------

@router.get("/subscriptions")
def subscription_tracker(
    year: int = Query(..., description="Year to analyse, e.g. 2026"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Detect likely subscriptions: expenses whose (name, category) pair appears
    in 3 or more distinct months within *year*.

    Returns a list of:
      { name, category, monthly_cost, annual_cost, months_seen, first_seen, last_seen }

    monthly_cost  = average actual_amount across the months seen
    annual_cost   = monthly_cost × months_seen
    first_seen    = earliest YYYY-MM in which the expense appeared
    last_seen     = latest YYYY-MM in which the expense appeared
    """
    user = _require_user(db, current_user)

    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()

    # Build month strings for the requested year
    year_months = [f"{year:04d}-{mo:02d}" for mo in range(1, 13)]

    # key: (name_lower, category_lower) → {months: set[str], amounts: list[float]}
    tracker: Dict[tuple, Dict] = {}

    for month_str in year_months:
        month_row = _find_month(all_rows, month_str)
        if month_row is None:
            continue

        expenses = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense.deleted_at == None,  # noqa: E711
            )
            .all()
        )

        for exp in expenses:
            name = (exp.name or "").strip()
            category = (exp.category or "Other").strip()
            if not name:
                continue

            key = (name.lower(), category.lower())
            if key not in tracker:
                tracker[key] = {
                    "name": name,
                    "category": category,
                    "months": set(),
                    "amounts": [],
                }
            tracker[key]["months"].add(month_str)
            tracker[key]["amounts"].append(float(exp.actual_amount or exp.planned_amount or 0.0))

    subscriptions = []
    for entry in tracker.values():
        months_seen = len(entry["months"])
        if months_seen < 3:
            continue

        monthly_cost = round(sum(entry["amounts"]) / len(entry["amounts"]), 2)
        annual_cost = round(monthly_cost * months_seen, 2)
        sorted_months = sorted(entry["months"])

        subscriptions.append({
            "name": entry["name"],
            "category": entry["category"],
            "monthly_cost": monthly_cost,
            "annual_cost": annual_cost,
            "months_seen": months_seen,
            "first_seen": sorted_months[0],
            "last_seen": sorted_months[-1],
        })

    subscriptions.sort(key=lambda s: (-s["annual_cost"], s["name"]))

    return {
        "year": year,
        "subscriptions": subscriptions,
    }


# -------------------- background job --------------------

def check_spending_velocity(session_factory):
    """
    Evaluate spending velocity for all active users and fire in-app notifications
    (plus email if opted in) when projected month-end spend exceeds planned_total * 1.10.

    Called every 6 hours by APScheduler.
    Dedup key: velocity_{user_id}_{YYYY-MM}_{YYYY-MM-DD} — prevents re-firing within 24 h.
    """
    from email_utils import send_velocity_warning_email  # local import avoids circular dependency

    db = session_factory()
    try:
        now = datetime.utcnow()
        current_month = now.strftime("%Y-%m")
        today_str = now.strftime("%Y-%m-%d")

        year, mo = map(int, current_month.split("-"))
        days_in_month = calendar.monthrange(year, mo)[1]
        today_day = now.day
        # Cap at days_in_month to handle end-of-month gracefully
        days_elapsed = min(today_day, days_in_month)

        if days_elapsed == 0:
            return  # First moment of month — no data yet

        users = (
            db.query(User)
            .filter(User.deleted_at == None)  # noqa: E711
            .all()
        )

        for user in users:
            all_months = (
                db.query(MonthlyData)
                .filter(MonthlyData.user_id == user.id)
                .all()
            )
            month_row = next((m for m in all_months if m.month == current_month), None)
            if not month_row:
                continue

            actual_ytd = float(month_row.total_actual or 0.0)
            planned_total = float(month_row.total_planned or 0.0)

            if planned_total <= 0 or actual_ytd <= 0:
                continue

            projected_total = (actual_ytd / days_elapsed) * days_in_month

            if projected_total <= planned_total * 1.10:
                continue

            # Dedup: one notification per user per day per month
            dedup_key = f"velocity:{user.id}:{current_month}:{today_str}"
            already_sent = (
                db.query(Notification)
                .filter(Notification.dedup_key == dedup_key)
                .first()
            )
            if already_sent:
                continue

            overage_pct = round((projected_total / planned_total - 1) * 100, 1)
            currency = user.base_currency or "GBP"

            notif = Notification(
                user_id=user.id,
                type="velocity_warning",
                dedup_key=dedup_key,
            )
            notif.title = "Spending pace warning"
            notif.message = (
                f"At your current pace you are projected to overspend your {current_month} "
                f"budget by {overage_pct}% ({currency} {projected_total:.2f} vs "
                f"{currency} {planned_total:.2f} planned)."
            )
            db.add(notif)
            db.commit()

            if getattr(user, "notif_budget_alerts", True):
                try:
                    send_velocity_warning_email(
                        to_email=user.email,
                        month=current_month,
                        actual_ytd=actual_ytd,
                        planned_total=planned_total,
                        projected_total=round(projected_total, 2),
                        currency=currency,
                    )
                except Exception:
                    logger.exception(
                        "Failed to send velocity warning email to %s", user.email
                    )

    except Exception:
        logger.exception("check_spending_velocity background job failed")
    finally:
        db.close()
