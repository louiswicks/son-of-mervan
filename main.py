import os
import uvicorn
from datetime import timedelta
from typing import List, Optional
from fastapi import Path
from fastapi import Body
from fastapi import Query
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from starlette import status

from database import init_db, get_db, User, MonthlyData, MonthlyExpense, encrypt_value
from security import authenticate_user, create_access_token, verify_token, verify_password
from routers import tracker, overview, signup
from collections import defaultdict

# -------------------- App Setup --------------------
app = FastAPI(title="Son of Mervan - Budget API", version="1.0.0")

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://louiswicks.github.io"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

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

def get_or_create_month(db: Session, user: User, month: str) -> MonthlyData:
    """
    Get or create a month record. Since month is encrypted, we must:
    1. Encrypt the search value
    2. Query using the encrypted column directly
    """
    encrypted_month = encrypt_value(month)
    
    rec = (
        db.query(MonthlyData)
        .filter(
            MonthlyData.user_id == user.id, 
            MonthlyData._month_encrypted == encrypted_month  # Use encrypted column
        )
        .first()
    )
    if not rec:
        rec = MonthlyData(user_id=user.id)  # Create without month
        rec.month = month  # Set month via property (encrypts automatically)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec

# -------------------- Routes --------------------
@app.get("/")
async def root():
    return {"message": "Son of Mervan Budget API is running", "status": "healthy"}

@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
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

    # Put the email (or user_id) in the JWT. Be consistent with your frontend.
    token = create_access_token({"sub": user.email}, expires_delta=timedelta(hours=24))
    return {"access_token": token, "token_type": "bearer"}

@app.post("/calculate-budget")
async def calculate_budget(
    budget_data: BudgetRequest,
    commit: bool = Query(False),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    month_norm = normalize_month(budget_data.month)
    
    # DEBUG: Log what we're receiving
    print(f"========== DEBUG calculate_budget ==========")
    print(f"Month: {month_norm}")
    print(f"Commit: {commit}")
    print(f"User: {current_user}")
    print(f"Salary: {budget_data.monthly_salary}")
    print(f"Number of expenses: {len(budget_data.expenses)}")
    print(f"Expenses:")
    for e in budget_data.expenses:
        print(f"  - Name: '{e.name}', Category: '{e.category}', Amount: {e.amount}")
    print(f"===========================================")

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
        print(f"DEBUG: Returning read-only response (not saving)")
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
    print(f"DEBUG: Starting commit path...")
    
    user = require_user_by_email(db, current_user)
    print(f"DEBUG: Found user with ID: {user.id}")
    
    month_row = get_or_create_month(db, user, month_norm)
    print(f"DEBUG: Got month_row with ID: {month_row.id}")

    month_row.salary_planned = budget_data.monthly_salary
    month_row.total_planned = total_planned
    month_row.remaining_planned = remaining_planned
    
    print(f"DEBUG: Set month_row values:")
    print(f"  salary_planned: {month_row.salary_planned}")
    print(f"  total_planned: {month_row.total_planned}")
    print(f"  remaining_planned: {month_row.remaining_planned}")
    
    db.add(month_row)
    db.commit()
    db.refresh(month_row)
    
    print(f"DEBUG: Committed month_row")

    # UPSERT expenses instead of deleting and recreating
    print(f"DEBUG: Processing {len(budget_data.expenses)} expenses...")
    
    for i, e in enumerate(budget_data.expenses):
        print(f"DEBUG: Expense {i+1}:")
        print(f"  Name: '{e.name}'")
        print(f"  Category: '{e.category}'")
        print(f"  Amount: {e.amount}")
        
        encrypted_name = encrypt_value(e.name)
        encrypted_category = encrypt_value(e.category)
        
        # Try to find existing expense
        existing = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense._name_encrypted == encrypted_name,
                MonthlyExpense._category_encrypted == encrypted_category,
            )
            .first()
        )
        
        if existing:
            print(f"  DEBUG: Found existing expense (ID: {existing.id})")
            print(f"  DEBUG: Old planned_amount: {existing.planned_amount}")
            existing.planned_amount = e.amount
            print(f"  DEBUG: New planned_amount: {existing.planned_amount}")
        else:
            print(f"  DEBUG: Creating new expense")
            expense = MonthlyExpense(monthly_data_id=month_row.id)
            expense.name = e.name
            expense.category = e.category
            expense.planned_amount = e.amount
            expense.actual_amount = 0.0
            db.add(expense)
            print(f"  DEBUG: Added new expense to session")
    
    db.commit()
    print(f"DEBUG: Committed all expenses")
    
    # Verify what was saved
    saved_expenses = db.query(MonthlyExpense).filter(
        MonthlyExpense.monthly_data_id == month_row.id
    ).all()
    print(f"DEBUG: Verification - found {len(saved_expenses)} expenses in database:")
    for exp in saved_expenses:
        print(f"  - {exp.name} ({exp.category}): planned={exp.planned_amount}, actual={exp.actual_amount}")

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
    encrypted_month = encrypt_value(month_norm)

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
    for item in items:
        encrypted_name = encrypt_value(item.name)
        encrypted_category = encrypt_value(item.category)
        
        exp = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense._name_encrypted == encrypted_name,
                MonthlyExpense._category_encrypted == encrypted_category,
            )
            .first()
        )
        
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

    db.commit()

    # Recalculate totals
    refreshed_expenses = (
        db.query(MonthlyExpense)
        .filter(MonthlyExpense.monthly_data_id == month_row.id)
        .all()
    )

    total_actual = sum((e.actual_amount or 0.0) for e in refreshed_expenses)
    total_planned = sum((e.planned_amount or 0.0) for e in refreshed_expenses)

    salary_actual = month_row.salary_actual if month_row.salary_actual is not None else 0.0
    salary_planned = month_row.salary_planned if month_row.salary_planned is not None else 0.0

    # Update month row - preserve planned values, only update actual
    month_row.total_actual = total_actual
    month_row.total_planned = total_planned  # Recalculate from expenses
    month_row.remaining_actual = float(salary_actual) - total_actual
    month_row.remaining_planned = float(salary_planned) - total_planned
    
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
    month_row = (
        db.query(MonthlyData)
        .filter(
            MonthlyData.user_id == user.id, 
            MonthlyData._month_encrypted == encrypted_month  # CHANGED
        )
        .first()
    )
    if not month_row:
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "salary_actual": 0.0,
            "rows": [],
        }

    expenses = (
        db.query(MonthlyExpense)
        .filter(MonthlyExpense.monthly_data_id == month_row.id)
        .all()
    )

    # Group by category (decrypt the category for grouping)
    sums = defaultdict(lambda: {"projected": 0.0, "actual": 0.0})
    for e in expenses:
        sums[e.category]["projected"] += float(e.planned_amount or 0.0)
        sums[e.category]["actual"]   += float(e.actual_amount or 0.0)

    rows = [
        {"category": cat, "projected": v["projected"], "actual": v["actual"]}
        for cat, v in sums.items()
    ]

    return {
        "month": month_norm,
        "salary_planned": float(month_row.salary_planned or 0.0),
        "salary_actual": float(month_row.salary_actual or 0.0),
        "rows": rows,
    }

@app.get("/verify-token")
async def verify_user_token(current_user: str = Depends(verify_token)):
    return {"user": current_user, "authenticated": True, "expires_in_hours": 24}

@app.post("/run-migration")
async def run_migration():
    """Temporary endpoint to run migration - REMOVE after use!"""
    import subprocess
    result = subprocess.run(["python", "migrate_to_encrypted.py"], 
                          capture_output=True, text=True)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }

@app.post("/cleanup-old-columns")
async def cleanup_old_columns():
    """Remove old unencrypted columns"""
    from sqlalchemy import text
    from database import engine
    
    with engine.connect() as conn:
        # Drop old columns from users
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS username"))
        
        # Drop old columns from monthly_data
        for col in ["month", "salary_planned", "salary_actual", "total_planned", 
                    "total_actual", "remaining_planned", "remaining_actual"]:
            conn.execute(text(f"ALTER TABLE monthly_data DROP COLUMN IF EXISTS {col}"))
        
        # Drop old columns from monthly_expenses
        for col in ["name", "category", "planned_amount", "actual_amount"]:
            conn.execute(text(f"ALTER TABLE monthly_expenses DROP COLUMN IF EXISTS {col}"))
        
        conn.commit()
    
    return {"status": "Old columns dropped successfully"}

@app.get("/debug/check-month/{month}")
async def debug_month(
    month: str,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Debug endpoint to check what's in the database"""
    from database import encrypt_value
    
    user = db.query(User).filter(User.email == current_user).first()
    if not user:
        return {"error": "User not found"}
    
    encrypted_month = encrypt_value(month)
    month_row = db.query(MonthlyData).filter(
        MonthlyData.user_id == user.id,
        MonthlyData._month_encrypted == encrypted_month
    ).first()
    
    if not month_row:
        return {"error": f"No data for {month}"}
    
    return {
        "month": month_row.month,
        "salary_planned": month_row.salary_planned,
        "salary_actual": month_row.salary_actual,
        "total_planned": month_row.total_planned,
        "total_actual": month_row.total_actual,
        "remaining_planned": month_row.remaining_planned,
        "remaining_actual": month_row.remaining_actual,
    }

# -------------------- Routers --------------------
# Ensure your routers import:  from security import verify_token
app.include_router(tracker.router)
app.include_router(overview.router)
app.include_router(signup.router)

# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
