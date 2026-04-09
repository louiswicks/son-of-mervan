"""
POST /monthly-tracker/{month}/rollover

Carries unspent planned budget from *month* into the following month,
supporting envelope-style budgeting. For each non-deleted expense in the
source month where actual_amount < planned_amount, the surplus
(planned - actual) is added to the matching expense (by name) in the next
month, creating a new planned expense row when no match exists.

The operation is idempotent: the destination MonthlyData stores
`rolled_over_from = source_month`; a second call with the same source month
returns the already-computed totals without double-applying.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.cache import invalidate_annual_cache
from database import MonthlyData, MonthlyExpense, User, get_db
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["budget"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    y, mo = parts
    try:
        return f"{int(y):04d}-{int(mo):02d}"
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")


def _next_month(month_str: str) -> str:
    """Return the YYYY-MM string for the month after *month_str*."""
    year, mo = int(month_str[:4]), int(month_str[5:7])
    if mo == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{mo + 1:02d}"


def _find_month(db: Session, user_id: int, month_str: str) -> MonthlyData | None:
    """Linear scan with decryption — required because month is Fernet-encrypted."""
    rows = db.query(MonthlyData).filter(MonthlyData.user_id == user_id).all()
    for row in rows:
        if row.month == month_str:
            return row
    return None


def _get_or_create_month(
    db: Session, user: User, month_str: str, salary_planned: float = 0.0
) -> MonthlyData:
    existing = _find_month(db, user.id, month_str)
    if existing:
        return existing
    new_m = MonthlyData(user_id=user.id)
    new_m.month = month_str
    new_m.salary_planned = salary_planned
    new_m.salary_actual = 0.0
    new_m.total_planned = 0.0
    new_m.total_actual = 0.0
    new_m.remaining_planned = salary_planned
    new_m.remaining_actual = 0.0
    db.add(new_m)
    db.commit()
    db.refresh(new_m)
    return new_m


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/monthly-tracker/{month}/rollover")
def rollover_budget(
    month: str,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """
    Roll unspent planned budget from *month* into the following month.

    - For each non-deleted expense where actual_amount < planned_amount,
      surplus = planned_amount - actual_amount is added to the matching
      expense (by name, case-insensitive) in the next month.
    - If no matching expense exists in the next month, a new planned expense
      is created with planned_amount = surplus.
    - The next month's MonthlyData is created if it does not exist, inheriting
      salary_planned from the source month.
    - Idempotent: calling this endpoint a second time for the same source month
      returns the totals already applied without modifying any rows.
    - Categories where actual_amount >= planned_amount are silently skipped.
    """
    source_month = _normalize_month(month)
    dest_month = _next_month(source_month)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    source = _find_month(db, user.id, source_month)
    if not source:
        raise HTTPException(
            status_code=404, detail=f"No budget found for {source_month}"
        )

    # Expenses eligible for rollover: non-deleted, actual < planned
    rollover_expenses = [
        e for e in source.expenses
        if e.deleted_at is None
        and (e.planned_amount or 0.0) > (e.actual_amount or 0.0)
    ]

    if not rollover_expenses:
        return {
            "source_month": source_month,
            "dest_month": dest_month,
            "rolled_over_categories": [],
            "total_rolled_over": 0.0,
        }

    # Get or create destination month (copy salary_planned when creating fresh)
    dest = _get_or_create_month(
        db, user, dest_month, salary_planned=source.salary_planned or 0.0
    )

    # ── Idempotency check ────────────────────────────────────────────────────
    # If dest already has rolled_over_from == source_month, compute and return
    # the current rollover totals without re-applying.
    if dest.rolled_over_from == source_month:
        logger.info(
            "rollover already applied user=%s source=%s dest=%s — returning current state",
            email, source_month, dest_month,
        )
        # Reconstruct the response from current dest expenses
        rolled = []
        total = 0.0
        for src_exp in rollover_expenses:
            surplus = round((src_exp.planned_amount or 0.0) - (src_exp.actual_amount or 0.0), 2)
            rolled.append({"category": src_exp.category, "amount": surplus})
            total += surplus
        return {
            "source_month": source_month,
            "dest_month": dest_month,
            "rolled_over_categories": rolled,
            "total_rolled_over": round(total, 2),
        }

    # ── Apply rollover ───────────────────────────────────────────────────────
    # Build lookup of dest expenses by lower-cased name
    dest_expenses = [e for e in dest.expenses if e.deleted_at is None]
    dest_by_name = {e.name.lower(): e for e in dest_expenses if e.name}

    rolled = []
    total = 0.0

    for src_exp in rollover_expenses:
        surplus = round((src_exp.planned_amount or 0.0) - (src_exp.actual_amount or 0.0), 2)
        if surplus <= 0:
            continue

        name_key = (src_exp.name or "").lower()
        existing = dest_by_name.get(name_key)

        if existing:
            existing.planned_amount = round((existing.planned_amount or 0.0) + surplus, 2)
        else:
            new_exp = MonthlyExpense(monthly_data_id=dest.id)
            new_exp.name = src_exp.name
            new_exp.category = src_exp.category
            new_exp.planned_amount = surplus
            new_exp.actual_amount = 0.0
            new_exp.currency = src_exp.currency or getattr(user, "base_currency", None) or "GBP"
            db.add(new_exp)
            dest_by_name[name_key] = new_exp

        rolled.append({"category": src_exp.category, "amount": surplus})
        total += surplus

    # Mark destination as having received a rollover from source_month
    dest.rolled_over_from = source_month

    db.commit()
    db.refresh(dest)

    # Recalculate totals for destination month
    all_dest = [e for e in dest.expenses if e.deleted_at is None]
    dest.total_planned = round(sum(e.planned_amount or 0.0 for e in all_dest), 2)
    dest.remaining_planned = round((dest.salary_planned or 0.0) - dest.total_planned, 2)
    db.commit()

    # Bust annual cache for both affected years
    src_year = int(source_month[:4])
    dst_year = int(dest_month[:4])
    invalidate_annual_cache(user.id, src_year)
    if dst_year != src_year:
        invalidate_annual_cache(user.id, dst_year)

    logger.info(
        "rollover user=%s source=%s dest=%s categories=%d total=%.2f",
        email, source_month, dest_month, len(rolled), total,
    )

    return {
        "source_month": source_month,
        "dest_month": dest_month,
        "rolled_over_categories": rolled,
        "total_rolled_over": round(total, 2),
    }
