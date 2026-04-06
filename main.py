import logging
import os
import uvicorn
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import Path
from fastapi import Body
from fastapi import Query
import hashlib
import secrets
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from starlette import status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.logging_config import setup_logging
from core.config import settings
from core.limiter import limiter
from middleware.security import SecurityHeadersMiddleware
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from database import get_db, User, MonthlyData, MonthlyExpense, RefreshToken, encrypt_value
from security import authenticate_user, create_access_token, verify_token, verify_password
from models import ExpenseUpdateRequest
from routers import tracker, overview, signup
from collections import defaultdict

setup_logging()
logger = logging.getLogger(__name__)

# -------------------- App Setup --------------------
app = FastAPI(title="Son of Mervan - Budget API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

CORS_ORIGINS = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(SecurityHeadersMiddleware, environment=settings.ENVIRONMENT)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Cache-Control"],
)

_alembic_cfg = AlembicConfig("alembic.ini")

# If the DB already has tables but no alembic_version tracking (pre-Alembic deploy),
# stamp it at the initial revision so the migration history starts from the correct
# baseline. Without this, `upgrade head` crashes on existing production DBs.
from sqlalchemy import inspect, text
from database import engine as _engine
with _engine.connect() as _conn:
    _inspector = inspect(_engine)
    _has_users = _inspector.has_table("users")
    _has_alembic = _inspector.has_table("alembic_version")
    if _has_users and not _has_alembic:
        logger.info("Existing DB detected with no Alembic version — stamping at initial revision")
        alembic_command.stamp(_alembic_cfg, "a047a3ff3bf1")

alembic_command.upgrade(_alembic_cfg, "head")

# -------------------- Schemas --------------------
class LoginRequest(BaseModel):
    identifier: str  # email or username
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str

class ExpenseItem(BaseModel):
    name: str
    amount: float
    category: str

class BudgetRequest(BaseModel):
    month: str                 # "YYYY-MM"
    monthly_salary: float      # planned salary
    expenses: List[ExpenseItem]  # planned expense lines

class ActualExpenseItem(BaseModel):
    name: str
    amount: float
    category: str

class ActualBudgetRequest(BaseModel):
    salary: Optional[float] = None
    expenses: List[ActualExpenseItem]  # actual amounts submitted for the month

# -------------------- Small DB helpers --------------------
# DELETE this old helper:
# def get_or_create_user(db: Session, username: str) -> User: ...

# ADD these helpers instead:
def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

def require_user_by_email(db: Session, email: str) -> User:
    user = get_user_by_email(db, email)
    if not user:
        # Signup always creates the user, so treat this as a hard error
        raise HTTPException(status_code=404, detail="User not found")
    return user

# --- add to main.py near the top ---
def normalize_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    y, mo = parts
    return f"{int(y):04d}-{int(mo):02d}"

def find_month_by_value(db: Session, user: User, month: str) -> MonthlyData | None:
    """Find a month row by decrypting values since encryption is non-deterministic."""
    all_months = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id)
        .all()
    )
    for row in all_months:
        if row.month == month:
            return row
    return None

def get_or_create_month(db: Session, user: User, month: str) -> MonthlyData:
    """Get or create a month record by comparing decrypted month values."""
    rec = find_month_by_value(db, user, month)
    if not rec:
        rec = MonthlyData(user_id=user.id)  # Create without month
        rec.month = month  # Set month via property (encrypts automatically)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec

def find_expense_by_values(expenses: list[MonthlyExpense], name: str, category: str) -> MonthlyExpense | None:
    for expense in expenses:
        if expense.name == name and expense.category == category:
            return expense
    return None

# -------------------- Routes --------------------
@app.get("/")
async def root():
    return {"message": "Son of Mervan Budget API is running", "status": "healthy"}

@app.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    ident = payload.identifier.strip()

    # Try email first (exact match); then username fallback
    user = db.query(User).filter(User.email == ident).first()
    if not user:
        user = db.query(User).filter(User.username == ident).first()

    if not user or not verify_password(payload.password, user.password_hash):
        # small delay helps reduce timing attacks
        import time; time.sleep(0.4)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect credentials")

    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Please verify your email before logging in.")

    # 15-min access token (short-lived; refresh token handles long-term sessions)
    access_token = create_access_token({"sub": user.email}, expires_delta=timedelta(minutes=15))

    # 30-day refresh token — stored as httpOnly cookie, only hash persisted in DB
    raw_refresh = secrets.token_urlsafe(32)
    refresh_hash = hashlib.sha256(raw_refresh.encode()).hexdigest()
    refresh_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_expires))
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )

    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/calculate-budget")
async def calculate_budget(
    budget_data: BudgetRequest,
    commit: bool = Query(False),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    month_norm = normalize_month(budget_data.month)

    logger.debug(
        "calculate_budget month=%s commit=%s user=%s salary=%s expenses=%d",
        month_norm, commit, current_user,
        budget_data.monthly_salary, len(budget_data.expenses),
    )

    # compute planned totals
    total_planned = sum(e.amount for e in budget_data.expenses)
    remaining_planned = budget_data.monthly_salary - total_planned

    # build category breakdown (for both branches)
    expenses_by_category = {}
    for e in budget_data.expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0.0) + e.amount

    expense_percentages = (
        {cat: round((amt / budget_data.monthly_salary) * 100, 2) for cat, amt in expenses_by_category.items()}
        if budget_data.monthly_salary > 0 else {}
    )

    recs = []
    if remaining_planned < 0:
        recs.append(f"You're overspending by £{abs(remaining_planned):.2f}! Consider trimming the largest categories.")
    elif remaining_planned < budget_data.monthly_salary * 0.1:
        recs.append("Try to save at least 10% of your income for emergencies.")
    elif remaining_planned < budget_data.monthly_salary * 0.2:
        recs.append("Good job! Consider increasing your savings rate.")
    else:
        recs.append("Excellent! You have a healthy planned surplus.")

    # ---------- READ-ONLY PATH ----------
    if not commit:
        logger.debug("calculate_budget read-only response (not saving)")
        return {
            "id": None,
            "month": month_norm,
            "monthly_salary": budget_data.monthly_salary,
            "total_expenses": total_planned,
            "remaining_budget": remaining_planned,
            "expenses_by_category": expenses_by_category,
            "expense_percentages": expense_percentages,
            "recommendations": recs,
            "savings_rate": round((remaining_planned / budget_data.monthly_salary) * 100, 2)
                if budget_data.monthly_salary else 0,
            "user": current_user,
            "committed": False,
        }

    # ---------- COMMIT (WRITE) PATH ----------
    logger.debug("calculate_budget starting commit path")

    user = require_user_by_email(db, current_user)
    logger.debug("calculate_budget user_id=%d", user.id)

    month_row = get_or_create_month(db, user, month_norm)
    logger.debug("calculate_budget month_row_id=%d", month_row.id)

    month_row.salary_planned = budget_data.monthly_salary
    month_row.total_planned = total_planned
    month_row.remaining_planned = remaining_planned

    db.add(month_row)
    db.commit()
    db.refresh(month_row)

    # UPSERT expenses instead of deleting and recreating
    logger.debug("calculate_budget processing %d expenses", len(budget_data.expenses))

    existing_expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,
        )
        .all()
    )

    for e in budget_data.expenses:
        existing = find_expense_by_values(existing_expenses, e.name, e.category)

        if existing:
            logger.debug(
                "calculate_budget updating expense id=%d name=%r planned=%s->%s",
                existing.id, e.name, existing.planned_amount, e.amount,
            )
            existing.planned_amount = e.amount
        else:
            logger.debug("calculate_budget creating expense name=%r category=%r", e.name, e.category)
            expense = MonthlyExpense(monthly_data_id=month_row.id)
            expense.name = e.name
            expense.category = e.category
            expense.planned_amount = e.amount
            expense.actual_amount = 0.0
            db.add(expense)
            existing_expenses.append(expense)

    db.commit()
    logger.debug("calculate_budget committed all expenses")

    return {
        "id": month_row.id,
        "month": month_row.month,
        "monthly_salary": month_row.salary_planned,
        "total_expenses": total_planned,
        "remaining_budget": remaining_planned,
        "expenses_by_category": expenses_by_category,
        "expense_percentages": expense_percentages,
        "recommendations": recs,
        "savings_rate": round((remaining_planned / budget_data.monthly_salary) * 100, 2)
            if budget_data.monthly_salary else 0,
        "user": current_user,
        "committed": True,
    }

@app.post("/monthly-tracker/{month}")
async def save_actuals(
    month: str = Path(..., description="Month in YYYY-MM format"),
    data: ActualBudgetRequest = Body(None),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    month_norm = normalize_month(month)
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # IMPORTANT: Use get_or_create_month instead of manual query
    # This ensures we use the same record that calculate-budget created
    month_row = get_or_create_month(db, user, month_norm)

    # Update salary_actual (preserve salary_planned)
    if data and data.salary is not None:
        month_row.salary_actual = float(data.salary)

    items = (data.expenses if data and data.expenses else [])
    existing_expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,
        )
        .all()
    )
    for item in items:
        exp = find_expense_by_values(existing_expenses, item.name, item.category)
        
        if exp:
            # Update ONLY actual_amount, preserve planned_amount
            exp.actual_amount = float(item.amount or 0.0)
        else:
            # Create new expense with actual only
            new_expense = MonthlyExpense(monthly_data_id=month_row.id)
            new_expense.name = item.name
            new_expense.category = item.category
            new_expense.planned_amount = 0.0  # No planned data for this new line
            new_expense.actual_amount = float(item.amount or 0.0)
            db.add(new_expense)
            existing_expenses.append(new_expense)


    db.commit()

    # Recalculate totals (exclude soft-deleted)
    refreshed_expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,
        )
        .all()
    )

    total_actual = sum((e.actual_amount or 0.0) for e in refreshed_expenses)

    salary_actual = month_row.salary_actual if month_row.salary_actual is not None else 0.0

    # Only update actual totals — planned totals are owned by calculate_budget
    month_row.total_actual = total_actual
    month_row.remaining_actual = float(salary_actual) - total_actual
    
    db.add(month_row)
    db.commit()
    db.refresh(month_row)

    expenses_by_category = {}
    for e in refreshed_expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0.0) + (e.actual_amount or 0.0)

    return {
        "month": month_row.month,
        "salary": salary_actual,
        "total_actual": month_row.total_actual,
        "total_planned": month_row.total_planned,
        "remaining_actual": month_row.remaining_actual,
        "remaining_planned": month_row.remaining_planned,
        "expenses_by_category": expenses_by_category,
        "user": current_user,
    }

@app.get("/monthly-tracker/{month}")
async def get_monthly_tracker(
    month: str = Path(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    month_norm = normalize_month(month)
    encrypted_month = encrypt_value(month_norm)  # ADD THIS

    user = get_user_by_email(db, current_user)
    if not user:
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "salary_actual": 0.0,
            "rows": [],
        }

    # Use encrypted column for query
    month_row = find_month_by_value(db, user, month_norm)
    if not month_row:
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "salary_actual": 0.0,
            "rows": [],
        }

    expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,
        )
        .all()
    )

    # Group by category (for backward-compatible `rows` field)
    sums = defaultdict(lambda: {"projected": 0.0, "actual": 0.0})
    for e in expenses:
        sums[e.category]["projected"] += float(e.planned_amount or 0.0)
        sums[e.category]["actual"]   += float(e.actual_amount or 0.0)

    rows = [
        {"category": cat, "projected": v["projected"], "actual": v["actual"]}
        for cat, v in sums.items()
    ]

    # Individual expense rows with IDs (for CRUD)
    expense_list = [
        {
            "id": e.id,
            "name": e.name or "",
            "category": e.category or "",
            "planned_amount": float(e.planned_amount or 0.0),
            "actual_amount": float(e.actual_amount or 0.0),
        }
        for e in expenses
    ]

    return {
        "month": month_norm,
        "salary_planned": float(month_row.salary_planned or 0.0),
        "salary_actual": float(month_row.salary_actual or 0.0),
        "rows": rows,
        "expenses": expense_list,
    }

def _get_owned_expense(expense_id: int, current_user_email: str, db: Session) -> MonthlyExpense:
    """Fetch an expense and verify the current user owns it. Raises 404/403 as appropriate."""
    expense = db.query(MonthlyExpense).filter(MonthlyExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    # Walk up to MonthlyData to verify ownership
    month_data = db.query(MonthlyData).filter(MonthlyData.id == expense.monthly_data_id).first()
    if not month_data:
        raise HTTPException(status_code=404, detail="Expense not found")
    user = get_user_by_email(db, current_user_email)
    if not user or month_data.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised to modify this expense")
    return expense


@app.put("/expenses/{expense_id}")
async def update_expense(
    expense_id: int = Path(...),
    data: ExpenseUpdateRequest = Body(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    expense = _get_owned_expense(expense_id, current_user, db)
    if expense.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Expense not found")

    if data.name is not None:
        expense.name = data.name
    if data.category is not None:
        expense.category = data.category
    if data.planned_amount is not None:
        expense.planned_amount = data.planned_amount
    if data.actual_amount is not None:
        expense.actual_amount = data.actual_amount

    db.commit()
    db.refresh(expense)

    return {
        "id": expense.id,
        "name": expense.name,
        "category": expense.category,
        "planned_amount": float(expense.planned_amount or 0.0),
        "actual_amount": float(expense.actual_amount or 0.0),
    }


@app.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: int = Path(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    expense = _get_owned_expense(expense_id, current_user, db)
    if expense.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense.deleted_at = datetime.utcnow()
    db.commit()
    # 204 No Content — no response body


@app.get("/verify-token")
async def verify_user_token(current_user: str = Depends(verify_token)):
    return {"user": current_user, "authenticated": True, "expires_in_hours": 24}

# -------------------- Routers --------------------
# Ensure your routers import:  from security import verify_token
app.include_router(tracker.router)
app.include_router(overview.router)
app.include_router(signup.router)

# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
