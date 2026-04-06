"""
routers/recurring.py — CRUD for RecurringExpense.

Endpoints:
  GET    /recurring-expenses          list active recurring expenses
  POST   /recurring-expenses          create a new recurring expense
  PUT    /recurring-expenses/{id}     update fields on an existing entry
  DELETE /recurring-expenses/{id}     soft-delete an entry
  POST   /recurring-expenses/generate manually trigger generation for current month
"""
import logging
import calendar
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from database import get_db, RecurringExpense, User, MonthlyExpense
from security import verify_token
from models import (
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
    RecurringExpenseResponse,
    VALID_FREQUENCIES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recurring-expenses", tags=["recurring"])


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _get_owned(rec_id: int, user: User, db: Session) -> RecurringExpense:
    rec = db.query(RecurringExpense).filter(RecurringExpense.id == rec_id).first()
    if not rec or rec.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    if rec.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    return rec


def _to_response(rec: RecurringExpense) -> dict:
    return {
        "id": rec.id,
        "name": rec.name,
        "category": rec.category,
        "planned_amount": rec.planned_amount,
        "frequency": rec.frequency,
        "start_date": rec.start_date,
        "end_date": rec.end_date,
        "last_generated_at": rec.last_generated_at,
        "created_at": rec.created_at,
    }


# ---------- endpoints ----------

@router.get("", response_model=list[RecurringExpenseResponse])
def list_recurring(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(db, current_user)
    rows = (
        db.query(RecurringExpense)
        .filter(RecurringExpense.user_id == user.id, RecurringExpense.deleted_at == None)
        .order_by(RecurringExpense.created_at.desc())
        .all()
    )
    return [_to_response(r) for r in rows]


@router.post("", response_model=RecurringExpenseResponse, status_code=201)
def create_recurring(
    data: RecurringExpenseCreate = Body(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    if data.frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=422, detail=f"frequency must be one of {sorted(VALID_FREQUENCIES)}")

    user = _get_user(db, current_user)
    rec = RecurringExpense(
        user_id=user.id,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    rec.name = data.name
    rec.category = data.category
    rec.planned_amount = data.planned_amount
    db.add(rec)
    db.commit()
    db.refresh(rec)
    logger.info("Created recurring expense id=%d user=%s", rec.id, current_user)
    return _to_response(rec)


@router.put("/{rec_id}", response_model=RecurringExpenseResponse)
def update_recurring(
    rec_id: int = Path(...),
    data: RecurringExpenseUpdate = Body(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(db, current_user)
    rec = _get_owned(rec_id, user, db)

    if data.frequency is not None:
        if data.frequency not in VALID_FREQUENCIES:
            raise HTTPException(status_code=422, detail=f"frequency must be one of {sorted(VALID_FREQUENCIES)}")
        rec.frequency = data.frequency
    if data.name is not None:
        rec.name = data.name
    if data.category is not None:
        rec.category = data.category
    if data.planned_amount is not None:
        rec.planned_amount = data.planned_amount
    if data.start_date is not None:
        rec.start_date = data.start_date
    if "end_date" in data.model_fields_set:
        rec.end_date = data.end_date

    db.commit()
    db.refresh(rec)
    return _to_response(rec)


@router.delete("/{rec_id}", status_code=204)
def delete_recurring(
    rec_id: int = Path(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(db, current_user)
    rec = _get_owned(rec_id, user, db)
    rec.deleted_at = datetime.utcnow()
    db.commit()


@router.post("/generate", status_code=200)
def trigger_generate(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Manually trigger generation of planned rows for the current month."""
    user = _get_user(db, current_user)
    count = _generate_for_user(db, user)
    return {"generated": count, "month": datetime.utcnow().strftime("%Y-%m")}


# ---------- generation logic (also called by the scheduler) ----------

def _monthly_amount(rec: RecurringExpense, year: int, month: int) -> float:
    """Return the planned_amount scaled to a full month based on frequency."""
    if rec.frequency == "daily":
        return rec.planned_amount * calendar.monthrange(year, month)[1]
    if rec.frequency == "weekly":
        return rec.planned_amount * 4  # approximate; 4 weeks / month
    # monthly or yearly: store the per-period amount as-is
    return rec.planned_amount


def _generate_for_user(db: Session, user: User) -> int:
    """
    Ensure planned MonthlyExpense rows exist for every active recurring expense
    for the current month.  Returns the number of new rows created.
    """
    # Deferred import to avoid circular dependency with main.py helpers
    from main import get_or_create_month, find_expense_by_values

    today = datetime.utcnow()
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_str = today.strftime("%Y-%m")

    active = (
        db.query(RecurringExpense)
        .filter(
            RecurringExpense.user_id == user.id,
            RecurringExpense.deleted_at == None,
            RecurringExpense.start_date <= today,
        )
        .all()
    )

    created = 0
    for rec in active:
        # Skip if past end_date
        if rec.end_date and rec.end_date < today:
            continue

        # Skip if already generated this month
        if rec.last_generated_at and rec.last_generated_at >= current_month_start:
            continue

        # Yearly: only generate in the same calendar month as start_date
        if rec.frequency == "yearly" and today.month != rec.start_date.month:
            continue

        amount = _monthly_amount(rec, today.year, today.month)
        month_row = get_or_create_month(db, user, current_month_str)

        existing = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense.deleted_at == None,
            )
            .all()
        )

        if not find_expense_by_values(existing, rec.name, rec.category):
            expense = MonthlyExpense(monthly_data_id=month_row.id)
            expense.name = rec.name
            expense.category = rec.category
            expense.planned_amount = amount
            expense.actual_amount = 0.0
            db.add(expense)
            created += 1

        rec.last_generated_at = today

    if created:
        db.commit()
        logger.info(
            "_generate_for_user: created %d planned rows for user_id=%d month=%s",
            created, user.id, current_month_str,
        )
    return created


def generate_all_recurring(db_factory) -> None:
    """
    Called by the APScheduler daily job.
    Iterates all users with active recurring expenses and generates planned rows.
    """
    from main import get_or_create_month, find_expense_by_values  # noqa: F401 – imported inside to avoid circular import at module load

    db = db_factory()
    try:
        today = datetime.utcnow()
        current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_str = today.strftime("%Y-%m")

        active = (
            db.query(RecurringExpense)
            .filter(
                RecurringExpense.deleted_at == None,
                RecurringExpense.start_date <= today,
            )
            .all()
        )

        user_cache: dict[int, User] = {}
        total = 0

        for rec in active:
            if rec.end_date and rec.end_date < today:
                continue
            if rec.last_generated_at and rec.last_generated_at >= current_month_start:
                continue
            if rec.frequency == "yearly" and today.month != rec.start_date.month:
                continue

            if rec.user_id not in user_cache:
                u = db.query(User).filter(User.id == rec.user_id).first()
                if not u or u.deleted_at is not None:
                    continue
                user_cache[rec.user_id] = u
            user = user_cache[rec.user_id]

            amount = _monthly_amount(rec, today.year, today.month)
            month_row = get_or_create_month(db, user, current_month_str)

            existing = (
                db.query(MonthlyExpense)
                .filter(
                    MonthlyExpense.monthly_data_id == month_row.id,
                    MonthlyExpense.deleted_at == None,
                )
                .all()
            )

            if not find_expense_by_values(existing, rec.name, rec.category):
                expense = MonthlyExpense(monthly_data_id=month_row.id)
                expense.name = rec.name
                expense.category = rec.category
                expense.planned_amount = amount
                expense.actual_amount = 0.0
                db.add(expense)
                total += 1

            rec.last_generated_at = today

        if total:
            db.commit()
        logger.info("generate_all_recurring: created %d rows for %s", total, current_month_str)
    except Exception:
        logger.exception("generate_all_recurring: failed")
        db.rollback()
    finally:
        db.close()
