"""
POST /budget/copy-forward — copy planned expenses from one month to another.

Addresses the most common user friction: re-entering the same planned budget
every month.  The endpoint does a server-side clone of non-deleted planned
expenses from *from_month* into *to_month*, skipping any expense whose
name+category already exists in the destination.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.cache import invalidate_annual_cache
from database import MonthlyData, MonthlyExpense, User, get_db
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget", tags=["budget"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CopyForwardRequest(BaseModel):
    from_month: str  # "YYYY-MM"
    to_month: str    # "YYYY-MM"


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


def _find_month(db: Session, user_id: int, month_str: str) -> MonthlyData | None:
    """Linear scan with decryption — required because month is Fernet-encrypted."""
    rows = db.query(MonthlyData).filter(MonthlyData.user_id == user_id).all()
    for row in rows:
        if row.month == month_str:
            return row
    return None


def _get_or_create_month(db: Session, user: User, month_str: str) -> MonthlyData:
    existing = _find_month(db, user.id, month_str)
    if existing:
        return existing
    new_m = MonthlyData(user_id=user.id)
    new_m.month = month_str
    new_m.salary_planned = 0.0
    new_m.salary_actual = 0.0
    new_m.total_planned = 0.0
    new_m.total_actual = 0.0
    new_m.remaining_planned = 0.0
    new_m.remaining_actual = 0.0
    db.add(new_m)
    db.commit()
    db.refresh(new_m)
    return new_m


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/copy-forward")
def copy_budget_forward(
    payload: CopyForwardRequest,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """
    Copy all planned expenses (and salary_planned) from *from_month* to
    *to_month*.  Expenses whose name+category already exist in the destination
    are skipped so existing data is never overwritten.
    """
    from_month = _normalize_month(payload.from_month)
    to_month = _normalize_month(payload.to_month)

    if from_month == to_month:
        raise HTTPException(
            status_code=400, detail="from_month and to_month must be different"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Source month must exist
    source = _find_month(db, user.id, from_month)
    if not source:
        raise HTTPException(
            status_code=404, detail=f"No budget found for {from_month}"
        )

    source_expenses = [e for e in source.expenses if e.deleted_at is None]
    if not source_expenses:
        raise HTTPException(
            status_code=404,
            detail=f"No expenses found in {from_month}",
        )

    # Destination: get or create
    dest = _get_or_create_month(db, user, to_month)

    # Build a set of (name, category) keys already in the destination
    dest_existing = [e for e in dest.expenses if e.deleted_at is None]
    existing_keys = {(e.name, e.category) for e in dest_existing}

    # Copy salary_planned only when destination has none yet
    if (dest.salary_planned or 0.0) == 0.0 and (source.salary_planned or 0.0) > 0.0:
        dest.salary_planned = source.salary_planned

    # Copy expenses
    copied = 0
    skipped = 0
    for src in source_expenses:
        key = (src.name, src.category)
        if key in existing_keys:
            skipped += 1
            continue
        new_exp = MonthlyExpense(monthly_data_id=dest.id)
        new_exp.name = src.name
        new_exp.category = src.category
        new_exp.planned_amount = src.planned_amount
        new_exp.actual_amount = 0.0
        new_exp.currency = src.currency or getattr(user, "base_currency", None) or "GBP"
        db.add(new_exp)
        existing_keys.add(key)
        copied += 1

    db.commit()
    db.refresh(dest)

    # Recalculate totals for destination month
    all_dest = [e for e in dest.expenses if e.deleted_at is None]
    dest.total_planned = sum(e.planned_amount for e in all_dest)
    dest.remaining_planned = (dest.salary_planned or 0.0) - dest.total_planned
    db.commit()

    # Bust annual cache for affected years
    from_year = int(from_month.split("-")[0])
    to_year = int(to_month.split("-")[0])
    invalidate_annual_cache(user.id, from_year)
    if to_year != from_year:
        invalidate_annual_cache(user.id, to_year)

    logger.info(
        "budget_copy_forward user=%s from=%s to=%s copied=%d skipped=%d",
        email, from_month, to_month, copied, skipped,
    )

    return {
        "from_month": from_month,
        "to_month": to_month,
        "copied": copied,
        "skipped": skipped,
    }
