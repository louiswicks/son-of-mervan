# routers/templates.py
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, User, MonthlyData, MonthlyExpense
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget-templates", tags=["budget-templates"])

# ---------------------------------------------------------------------------
# Static template definitions — no DB required
# ---------------------------------------------------------------------------

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "student",
        "name": "Student",
        "description": "Lean budget for students or recent graduates managing tight finances.",
        "allocations": [
            {"category": "Housing", "pct_of_salary": 35},
            {"category": "Food & Groceries", "pct_of_salary": 20},
            {"category": "Transport", "pct_of_salary": 10},
            {"category": "Utilities", "pct_of_salary": 7},
            {"category": "Education", "pct_of_salary": 8},
            {"category": "Entertainment", "pct_of_salary": 8},
            {"category": "Personal Care", "pct_of_salary": 5},
            {"category": "Miscellaneous", "pct_of_salary": 7},
        ],
    },
    {
        "id": "single-professional",
        "name": "Single Professional",
        "description": "Balanced budget for a single working adult with moderate savings.",
        "allocations": [
            {"category": "Housing", "pct_of_salary": 30},
            {"category": "Food & Groceries", "pct_of_salary": 12},
            {"category": "Transport", "pct_of_salary": 10},
            {"category": "Utilities", "pct_of_salary": 5},
            {"category": "Savings", "pct_of_salary": 15},
            {"category": "Entertainment", "pct_of_salary": 8},
            {"category": "Dining Out", "pct_of_salary": 7},
            {"category": "Subscriptions", "pct_of_salary": 3},
            {"category": "Clothing", "pct_of_salary": 5},
            {"category": "Miscellaneous", "pct_of_salary": 5},
        ],
    },
    {
        "id": "family",
        "name": "Family",
        "description": "Household budget for a family with dependents and childcare costs.",
        "allocations": [
            {"category": "Housing", "pct_of_salary": 32},
            {"category": "Food & Groceries", "pct_of_salary": 18},
            {"category": "Transport", "pct_of_salary": 12},
            {"category": "Childcare & Education", "pct_of_salary": 15},
            {"category": "Utilities", "pct_of_salary": 8},
            {"category": "Healthcare", "pct_of_salary": 5},
            {"category": "Entertainment", "pct_of_salary": 5},
            {"category": "Clothing", "pct_of_salary": 3},
            {"category": "Miscellaneous", "pct_of_salary": 2},
        ],
    },
    {
        "id": "frugal",
        "name": "Frugal Saver",
        "description": "Aggressive savings-first budget — ideal for those building an emergency fund or saving for a big goal.",
        "allocations": [
            {"category": "Housing", "pct_of_salary": 28},
            {"category": "Food & Groceries", "pct_of_salary": 12},
            {"category": "Transport", "pct_of_salary": 8},
            {"category": "Utilities", "pct_of_salary": 5},
            {"category": "Savings", "pct_of_salary": 30},
            {"category": "Entertainment", "pct_of_salary": 5},
            {"category": "Personal Care", "pct_of_salary": 4},
            {"category": "Subscriptions", "pct_of_salary": 3},
            {"category": "Miscellaneous", "pct_of_salary": 5},
        ],
    },
    {
        "id": "high-earner",
        "name": "High Earner",
        "description": "Budget for high-income individuals prioritising investments and lifestyle spending.",
        "allocations": [
            {"category": "Housing", "pct_of_salary": 25},
            {"category": "Food & Groceries", "pct_of_salary": 8},
            {"category": "Transport", "pct_of_salary": 8},
            {"category": "Utilities", "pct_of_salary": 4},
            {"category": "Savings", "pct_of_salary": 15},
            {"category": "Investments", "pct_of_salary": 15},
            {"category": "Dining Out", "pct_of_salary": 6},
            {"category": "Entertainment", "pct_of_salary": 6},
            {"category": "Travel", "pct_of_salary": 8},
            {"category": "Miscellaneous", "pct_of_salary": 5},
        ],
    },
]

_TEMPLATE_BY_ID: Dict[str, Dict[str, Any]] = {t["id"]: t for t in TEMPLATES}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _normalize_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    try:
        y, mo = int(parts[0]), int(parts[1])
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    if not (1 <= mo <= 12):
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    return f"{y:04d}-{mo:02d}"


def _find_month(rows: list, month_str: str) -> Optional[MonthlyData]:
    for row in rows:
        if row.month == month_str:
            return row
    return None


def _get_or_create_month(db: Session, user: User, month: str) -> MonthlyData:
    all_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    row = _find_month(all_rows, month)
    if not row:
        row = MonthlyData(user_id=user.id)
        row.month = month
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_templates() -> Dict[str, Any]:
    """Return all available budget templates. No authentication required."""
    return {"templates": TEMPLATES}


@router.post("/{template_id}/apply")
def apply_template(
    template_id: str,
    month: str = Query(..., description="Target month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Apply a budget template to a month by creating planned expense rows.
    Additive — existing rows are left untouched. Only new rows are created.
    Requires the month to have a salary_planned set; returns 400 if salary is 0.
    """
    template = _TEMPLATE_BY_ID.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    month_row = _get_or_create_month(db, user, month_norm)

    salary = float(month_row.salary_planned or 0.0)
    if salary <= 0:
        raise HTTPException(
            status_code=400,
            detail="Month has no planned salary. Set a salary first via POST /calculate-budget.",
        )

    # Fetch existing non-deleted expenses for dedup
    existing = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at.is_(None),
        )
        .all()
    )
    existing_names = {(e.name, e.category) for e in existing}

    created = []
    for alloc in template["allocations"]:
        category = alloc["category"]
        amount = round(salary * alloc["pct_of_salary"] / 100, 2)
        name = category  # use category as default expense name

        if (name, category) in existing_names:
            logger.debug("apply_template: skipping existing expense name=%r category=%r", name, category)
            continue

        expense = MonthlyExpense(monthly_data_id=month_row.id)
        expense.name = name
        expense.category = category
        expense.planned_amount = amount
        expense.actual_amount = 0.0
        expense.currency = user.base_currency or "GBP"
        db.add(expense)
        db.flush()

        created.append({
            "id": expense.id,
            "name": name,
            "category": category,
            "planned_amount": amount,
            "currency": expense.currency,
        })
        logger.debug("apply_template: created expense name=%r category=%r amount=%.2f", name, category, amount)

    db.commit()

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "month": month_norm,
        "created_count": len(created),
        "expenses": created,
    }
