import os
import uvicorn
from datetime import timedelta
from typing import List, Optional
from fastapi import Path
from fastapi import Body
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db, User, MonthlyData, MonthlyExpense
from security import authenticate_user, create_access_token, verify_token
from routers import tracker, overview
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
    username: str
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
def get_or_create_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# --- add to main.py near the top ---
def normalize_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    y, mo = parts
    return f"{int(y):04d}-{int(mo):02d}"

def get_or_create_month(db: Session, user: User, month: str) -> MonthlyData:
    rec = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id, MonthlyData.month == month)
        .first()
    )
    if not rec:
        rec = MonthlyData(month=month, user_id=user.id)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec

# -------------------- Routes --------------------
@app.get("/")
async def root():
    return {"message": "Son of Mervan Budget API is running", "status": "healthy"}

@app.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    if not authenticate_user(login_data.username, login_data.password):
        # small delay helps reduce timing attacks
        import time
        time.sleep(0.4)
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": login_data.username}, expires_delta=timedelta(hours=24))
    return {"access_token": token, "token_type": "bearer"}

@app.post("/calculate-budget")
async def calculate_budget(
    budget_data: BudgetRequest,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
     # normalize month
    month_norm = normalize_month(budget_data.month)

    total_planned = sum(e.amount for e in budget_data.expenses)
    remaining_planned = budget_data.monthly_salary - total_planned

    user = get_or_create_user(db, current_user)
    month_row = get_or_create_month(db, user, month_norm)

    month_row.salary_planned = budget_data.monthly_salary
    month_row.total_planned = total_planned
    month_row.remaining_planned = remaining_planned
    db.add(month_row)
    db.commit()
    db.refresh(month_row)

    db.query(MonthlyExpense).filter(
        MonthlyExpense.monthly_data_id == month_row.id
    ).delete()
    db.commit()

    db.add_all([
        MonthlyExpense(
            monthly_data_id=month_row.id,
            name=e.name,
            category=e.category,
            planned_amount=e.amount,
            actual_amount=0.0
        )
        for e in budget_data.expenses
    ])
    db.commit()

    # 5) category breakdown (planned)
    expenses_by_category = {}
    for e in budget_data.expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0.0) + e.amount

    expense_percentages = (
        {cat: round((amt / budget_data.monthly_salary) * 100, 2) for cat, amt in expenses_by_category.items()}
        if budget_data.monthly_salary > 0 else {}
    )

    # 6) simple recommendations (planned)
    recs = []
    if remaining_planned < 0:
        recs.append(f"You're overspending by £{abs(remaining_planned):.2f}! Consider trimming the largest categories.")
    elif remaining_planned < budget_data.monthly_salary * 0.1:
        recs.append("Try to save at least 10% of your income for emergencies.")
    elif remaining_planned < budget_data.monthly_salary * 0.2:
        recs.append("Good job! Consider increasing your savings rate.")
    else:
        recs.append("Excellent! You have a healthy planned surplus.")

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
    }

@app.post("/monthly-tracker/{month}")
async def save_actuals(
    month: str = Path(..., description="Month in YYYY-MM format"),
    data: ActualBudgetRequest = Body(None),  # accept missing/empty body gracefully
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Save **actual** expenses for a given month.
    If the month row does not exist, it will be created automatically.
    Updates MonthlyExpense.actual_amount and recalculates totals.
    """
    month_norm = normalize_month(month)

    # 1) user + month (always upsert)
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        user = User(username=current_user)
        db.add(user)
        db.commit()
        db.refresh(user)

    month_row = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id, MonthlyData.month == month_norm)
        .first()
    )
    if not month_row:
        month_row = MonthlyData(month=month_norm, user_id=user.id)
        db.add(month_row)
        db.commit()
        db.refresh(month_row)

    if data and data.salary is not None:
        month_row.salary_actual = float(data.salary)

    # 2) apply actuals (if any)
    items = (data.expenses if data and data.expenses else [])
    for item in items:
        exp = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense.name == item.name,
                MonthlyExpense.category == item.category,
            )
            .first()
        )
        if exp:
            exp.actual_amount = float(item.amount or 0.0)
        else:
            db.add(
                MonthlyExpense(
                    monthly_data_id=month_row.id,
                    name=item.name,
                    category=item.category,
                    planned_amount=0.0,
                    actual_amount=float(item.amount or 0.0),
                )
            )

    db.commit()

    # 3) recompute totals from DB (don’t trust client payload)
    #    total_actual = sum of all actual_amount in this month
    refreshed_expenses = (
        db.query(MonthlyExpense)
        .filter(MonthlyExpense.monthly_data_id == month_row.id)
        .all()
    )

    total_actual = sum((e.actual_amount or 0.0) for e in refreshed_expenses)

    # default salary_actual to salary_planned if that’s how you want it,
    # or leave as 0.0 if not set yet
    salary_actual = month_row.salary_actual if month_row.salary_actual is not None else (
        month_row.salary_planned or 0.0
    )

    month_row.total_actual = total_actual
    month_row.remaining_actual = float(salary_actual) - total_actual
    db.add(month_row)
    db.commit()
    db.refresh(month_row)

    # 4) build per-category summary (actuals)
    expenses_by_category = {}
    for e in refreshed_expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0.0) + (e.actual_amount or 0.0)

    return {
        "month": month_row.month,
        "salary": salary_actual,
        "total_actual": month_row.total_actual,
        "remaining_actual": month_row.remaining_actual,
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

    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        # nothing saved yet
        return {
            "month": month_norm,
            "salary_planned": 0.0,
            "salary_actual": 0.0,
            "rows": [],
        }

    month_row = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id, MonthlyData.month == month_norm)
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

    # sum per category so it fits your one-row-per-category UI
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

# -------------------- Routers --------------------
# Ensure your routers import:  from security import verify_token
app.include_router(tracker.router)
app.include_router(overview.router) 

# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
