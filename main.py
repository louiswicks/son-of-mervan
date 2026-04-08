import json
import logging
import os
import re
import uvicorn
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import Path
from fastapi import Body
from fastapi import Query
import hashlib
import secrets
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from core.logging_config import setup_logging
from core.config import settings
from core.limiter import limiter
from core.cache import invalidate_annual_cache
from middleware.security import SecurityHeadersMiddleware
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from database import get_db, User, MonthlyData, MonthlyExpense, RefreshToken, AuditLog
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
from security import create_access_token, verify_token, verify_password
from models import ExpenseUpdateRequest
from routers import tracker, overview, signup, users as users_router, recurring as recurring_router, savings as savings_router, alerts as alerts_router, insights as insights_router, export as export_router, audit as audit_router, currency as currency_router, investments as investments_router, household as household_router, categories as categories_router, import_csv as import_csv_router, forecast as forecast_router, debts as debts_router, net_worth as net_worth_router
import email_utils
from collections import defaultdict

setup_logging()
logger = logging.getLogger(__name__)

# Sentry — only active when SENTRY_DSN is configured (no-op in local dev)
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        environment=settings.ENVIRONMENT,
        release="son-of-mervan@1.0.0",
        # Capture 100% of transactions in production for now; tune down later
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "production" else 0.0,
        # Attach the authenticated user's id to every error event
        send_default_pii=False,
    )
    logger.info("Sentry initialised (environment=%s)", settings.ENVIRONMENT)

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
from sqlalchemy import inspect
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
    currency: Optional[str] = None  # ISO 4217 code; defaults to user's base_currency

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

@app.get("/health")
async def health():
    """Health check endpoint used by Docker and Railway."""
    return {"status": "ok", "version": "1.0.0"}

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

    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This account has been deleted.")

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
            expense.currency = user.base_currency or "GBP"
            db.add(expense)
            db.flush()  # populate expense.id before audit log
            _write_audit(db, user.id, expense.id, "create", None, {
                "name": e.name,
                "category": e.category,
                "planned_amount": float(e.amount),
                "actual_amount": 0.0,
                "currency": user.base_currency or "GBP",
            })
            existing_expenses.append(expense)

    db.commit()
    logger.debug("calculate_budget committed all expenses")
    invalidate_annual_cache(user.id, int(month_norm[:4]))

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
        
        item_currency = (item.currency or "").upper() or (user.base_currency or "GBP")
        if exp:
            # Update ONLY actual_amount (and currency if provided), preserve planned_amount
            exp.actual_amount = float(item.amount or 0.0)
            if item.currency:
                exp.currency = item_currency
        else:
            # Create new expense with actual only
            new_expense = MonthlyExpense(monthly_data_id=month_row.id)
            new_expense.name = item.name
            new_expense.category = item.category
            new_expense.planned_amount = 0.0  # No planned data for this new line
            new_expense.actual_amount = float(item.amount or 0.0)
            new_expense.currency = item_currency
            db.add(new_expense)
            db.flush()  # populate new_expense.id before audit log
            _write_audit(db, user.id, new_expense.id, "create", None, {
                "name": item.name,
                "category": item.category,
                "planned_amount": 0.0,
                "actual_amount": float(item.amount or 0.0),
                "currency": item_currency,
            })
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
    invalidate_annual_cache(user.id, int(month_norm[:4]))

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
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    month_norm = normalize_month(month)

    user = get_user_by_email(db, current_user)
    if not user:
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "salary_actual": 0.0,
            "rows": [],
            "expenses": {"items": [], "total": 0, "page": page, "pages": 0, "page_size": page_size},
        }

    # Use encrypted column for query
    month_row = find_month_by_value(db, user, month_norm)
    if not month_row:
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "salary_actual": 0.0,
            "rows": [],
            "expenses": {"items": [], "total": 0, "page": page, "pages": 0, "page_size": page_size},
        }

    all_expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,
        )
        .all()
    )

    # Decrypt and optionally filter by category (in Python — fields are Fernet-encrypted)
    expense_dicts = [
        {
            "id": e.id,
            "name": e.name or "",
            "category": e.category or "",
            "planned_amount": float(e.planned_amount or 0.0),
            "actual_amount": float(e.actual_amount or 0.0),
            "currency": e.currency or user.base_currency or "GBP",
        }
        for e in all_expenses
    ]

    if category:
        expense_dicts = [e for e in expense_dicts if e["category"] == category]

    # Group by category for backward-compatible `rows` field (unfiltered)
    sums = defaultdict(lambda: {"projected": 0.0, "actual": 0.0})
    for e in expense_dicts:
        sums[e["category"]]["projected"] += e["planned_amount"]
        sums[e["category"]]["actual"]    += e["actual_amount"]

    rows = [
        {"category": cat, "projected": v["projected"], "actual": v["actual"]}
        for cat, v in sums.items()
    ]

    # Paginate
    total = len(expense_dicts)
    pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    page_items = expense_dicts[offset: offset + page_size]

    return {
        "month": month_norm,
        "salary_planned": float(month_row.salary_planned or 0.0),
        "salary_actual": float(month_row.salary_actual or 0.0),
        "base_currency": user.base_currency or "GBP",
        "rows": rows,
        "expenses": {
            "items": page_items,
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
        },
    }

@app.get("/expenses/search")
async def search_expenses(
    q: Optional[str] = Query(None, max_length=200, description="Partial match on expense name (case-insensitive)"),
    category: Optional[str] = Query(None, max_length=100, description="Exact category filter"),
    from_month: Optional[str] = Query(None, alias="from", description="Start month YYYY-MM (inclusive)"),
    to_month: Optional[str] = Query(None, alias="to", description="End month YYYY-MM (inclusive)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Search expenses across all months with optional name, category, and date-range filters."""
    _month_re = re.compile(r"^\d{4}-\d{2}$")
    if from_month and not _month_re.match(from_month):
        raise HTTPException(status_code=422, detail="'from' must be in YYYY-MM format")
    if to_month and not _month_re.match(to_month):
        raise HTTPException(status_code=422, detail="'to' must be in YYYY-MM format")

    user = get_user_by_email(db, current_user)
    if not user:
        return {"items": [], "total": 0, "page": page, "per_page": per_page, "pages": 0}

    # Fetch all month records for this user (decrypt month in Python — Fernet non-deterministic)
    all_months = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()

    # Filter months by date range
    matching_months = []
    for md in all_months:
        m = md.month
        if not m:
            continue
        if from_month and m < from_month:
            continue
        if to_month and m > to_month:
            continue
        matching_months.append((md, m))

    # Collect matching expenses from those months
    results = []
    q_lower = q.lower() if q else None
    for md, month_str in matching_months:
        expenses = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == md.id,
                MonthlyExpense.deleted_at == None,
            )
            .all()
        )
        for e in expenses:
            name_dec = e.name or ""
            cat_dec = e.category or ""
            if q_lower and q_lower not in name_dec.lower():
                continue
            if category and cat_dec != category:
                continue
            results.append({
                "id": e.id,
                "name": name_dec,
                "category": cat_dec,
                "planned_amount": float(e.planned_amount or 0.0),
                "actual_amount": float(e.actual_amount or 0.0),
                "currency": e.currency or user.base_currency or "GBP",
                "month": month_str,
            })

    # Sort most-recent month first, then by name
    results.sort(key=lambda x: (-ord(x["month"][0]) * 1000000 + sum(ord(c) for c in x["month"]), x["name"]))
    results.sort(key=lambda x: x["month"], reverse=True)

    # Paginate
    total = len(results)
    pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 0
    offset = (page - 1) * per_page
    items = results[offset: offset + per_page]

    return JSONResponse(
        content={"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages},
        headers={"X-Total-Count": str(total), "X-Page": str(page)},
    )


def _invalidate_expense_year_cache(db: Session, user_id: int, monthly_data_id: int) -> None:
    """Look up the month for an expense and invalidate its annual cache entry."""
    md = db.query(MonthlyData).filter(MonthlyData.id == monthly_data_id).first()
    if md and md.month:
        invalidate_annual_cache(user_id, int(md.month[:4]))


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


def _expense_snapshot(expense: MonthlyExpense) -> dict:
    """Return a plaintext dict of an expense's auditable fields."""
    return {
        "name": expense.name,
        "category": expense.category,
        "planned_amount": float(expense.planned_amount or 0.0),
        "actual_amount": float(expense.actual_amount or 0.0),
        "currency": expense.currency or "GBP",
    }


def _write_audit(
    db: Session,
    user_id: int,
    expense_id: int,
    action: str,
    before: dict | None,
    after: dict | None,
) -> None:
    """Append one immutable audit row. Caller must commit."""
    log = AuditLog(
        user_id=user_id,
        expense_id=expense_id,
        action=action,
        changed_fields=json.dumps({"before": before, "after": after}),
    )
    db.add(log)


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

    before = _expense_snapshot(expense)
    user = get_user_by_email(db, current_user)

    if data.name is not None:
        expense.name = data.name
    if data.category is not None:
        expense.category = data.category
    if data.planned_amount is not None:
        expense.planned_amount = data.planned_amount
    if data.actual_amount is not None:
        expense.actual_amount = data.actual_amount
    if data.currency is not None:
        from routers.currency import VALID_CURRENCY_CODES
        code = data.currency.upper()
        if code not in VALID_CURRENCY_CODES:
            raise HTTPException(status_code=400, detail=f"Unsupported currency code: {code}")
        expense.currency = code

    after = _expense_snapshot(expense)
    _write_audit(db, user.id, expense.id, "update", before, after)
    db.commit()
    db.refresh(expense)
    _invalidate_expense_year_cache(db, user.id, expense.monthly_data_id)

    return {
        "id": expense.id,
        "name": expense.name,
        "category": expense.category,
        "planned_amount": float(expense.planned_amount or 0.0),
        "actual_amount": float(expense.actual_amount or 0.0),
        "currency": expense.currency or "GBP",
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

    before = _expense_snapshot(expense)
    user = get_user_by_email(db, current_user)
    monthly_data_id = expense.monthly_data_id
    expense.deleted_at = datetime.utcnow()
    _write_audit(db, user.id, expense.id, "delete", before, None)
    db.commit()
    _invalidate_expense_year_cache(db, user.id, monthly_data_id)
    # 204 No Content — no response body


@app.get("/verify-token")
async def verify_user_token(current_user: str = Depends(verify_token)):
    return {"user": current_user, "authenticated": True, "expires_in_hours": 24}

# -------------------- Routers --------------------
# Ensure your routers import:  from security import verify_token
app.include_router(tracker.router)
app.include_router(overview.router)
app.include_router(signup.router)
app.include_router(users_router.router)
app.include_router(recurring_router.router)
app.include_router(savings_router.router)
app.include_router(alerts_router.router)
app.include_router(insights_router.router)
app.include_router(export_router.router)
app.include_router(audit_router.router)
app.include_router(currency_router.router)
app.include_router(investments_router.router)
app.include_router(household_router.router)
app.include_router(categories_router.router)
app.include_router(import_csv_router.router)
app.include_router(forecast_router.router)
app.include_router(debts_router.router)
app.include_router(net_worth_router.router)

# -------------------- Scheduler --------------------
_scheduler = BackgroundScheduler(daemon=True)


def send_monthly_digests(session_factory):
    """
    APScheduler job: runs on the 1st of each month at 08:00 UTC.
    Sends a budget digest email for the previous month to all opted-in users
    who have spending data for that month.
    """
    from datetime import date

    today = date.today()
    # Previous month — handle January → December of prior year
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1
    month_str = f"{prev_year:04d}-{prev_month:02d}"

    db = session_factory()
    try:
        users = (
            db.query(User)
            .filter(User.digest_enabled == True, User.deleted_at == None)  # noqa: E711
            .all()
        )
        sent = 0
        for user in users:
            # Find this user's MonthlyData for the previous month
            month_rec = find_month_by_value(db, user, month_str)
            if not month_rec:
                continue  # no data → skip

            # Collect non-deleted expenses for the month
            expenses = (
                db.query(MonthlyExpense)
                .filter(
                    MonthlyExpense.monthly_data_id == month_rec.id,
                    MonthlyExpense.deleted_at == None,  # noqa: E711
                )
                .all()
            )

            # Aggregate actual spend per category
            category_totals: dict[str, float] = {}
            for exp in expenses:
                cat = exp.category or "Other"
                amt = exp.actual_amount or 0.0
                category_totals[cat] = category_totals.get(cat, 0.0) + amt

            total_spent = sum(category_totals.values())
            income = month_rec.salary_actual or month_rec.salary_planned or 0.0
            savings_rate = ((income - total_spent) / income * 100) if income > 0 else 0.0

            top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:3]

            # Find over-budget categories
            planned_by_cat: dict[str, float] = {}
            for exp in expenses:
                cat = exp.category or "Other"
                planned = exp.planned_amount or 0.0
                planned_by_cat[cat] = planned_by_cat.get(cat, 0.0) + planned

            over_budget = [
                cat for cat, actual in category_totals.items()
                if actual > planned_by_cat.get(cat, float("inf"))
            ]

            currency = user.base_currency or "GBP"
            try:
                email_utils.send_monthly_digest_email(
                    to_email=user.email,
                    month=month_str,
                    income=income,
                    total_spent=total_spent,
                    savings_rate=savings_rate,
                    top_categories=top_categories,
                    over_budget=over_budget,
                    currency=currency,
                )
                sent += 1
            except Exception:
                logger.exception("Failed to send digest to user %s", user.id)
        logger.info("Monthly digest job complete — sent=%d month=%s", sent, month_str)
    finally:
        db.close()


def sync_all_investment_prices(session_factory):
    """Daily job: sync latest prices for all active investment holdings with a ticker."""
    db = session_factory()
    try:
        from database import Investment, InvestmentPrice, User
        from routers.investments import fetch_price_for_ticker

        users = db.query(User).filter(User.deleted_at == None).all()
        total = 0
        for user in users:
            holdings = (
                db.query(Investment)
                .filter(Investment.user_id == user.id, Investment.deleted_at == None)
                .all()
            )
            for holding in holdings:
                if not holding.ticker:
                    continue
                price = fetch_price_for_ticker(holding.ticker)
                if price is None:
                    continue
                snap = InvestmentPrice(investment_id=holding.id, price=price)
                db.add(snap)
                total += 1
        if total:
            db.commit()
        logger.info("Investment price sync complete — %d price(s) updated", total)
    except Exception:
        logger.exception("Investment price sync job failed")
    finally:
        db.close()


@app.on_event("startup")
def _start_scheduler():
    from routers.recurring import generate_all_recurring
    from routers.alerts import check_budget_alerts
    from routers.currency import sync_exchange_rates
    _scheduler.add_job(
        sync_exchange_rates,
        "cron",
        hour=0,
        minute=15,
        id="sync_exchange_rates",
        replace_existing=True,
        args=[SessionLocal],
    )
    _scheduler.add_job(
        generate_all_recurring,
        "cron",
        hour=0,
        minute=5,
        id="generate_recurring",
        replace_existing=True,
        args=[SessionLocal],
    )
    _scheduler.add_job(
        check_budget_alerts,
        "cron",
        hour=0,
        minute=10,
        id="check_budget_alerts",
        replace_existing=True,
        args=[SessionLocal],
    )
    _scheduler.add_job(
        send_monthly_digests,
        "cron",
        day=1,
        hour=8,
        minute=0,
        id="send_monthly_digests",
        replace_existing=True,
        args=[SessionLocal],
    )
    _scheduler.add_job(
        sync_all_investment_prices,
        "cron",
        hour=16,
        minute=30,
        id="sync_investment_prices",
        replace_existing=True,
        args=[SessionLocal],
    )
    from routers.milestones import check_milestones
    _scheduler.add_job(
        check_milestones,
        "cron",
        day=1,
        hour=9,
        minute=0,
        id="check_milestones",
        replace_existing=True,
        args=[SessionLocal],
    )
    _scheduler.start()
    logger.info(
        "APScheduler started — recurring-expense generation at 00:05 UTC, "
        "budget alert checks at 00:10 UTC, exchange rate sync at 00:15 UTC, "
        "monthly digest on 1st of month at 08:00 UTC, "
        "investment price sync at 16:30 UTC, "
        "milestone email checks on 1st of month at 09:00 UTC"
    )


@app.on_event("shutdown")
def _stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")

# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))  # nosec B104
