from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import uvicorn

app = FastAPI(title="Son of Louman - Budget API", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class Expense(BaseModel):
    name: str
    amount: float
    category: str = "general"

class BudgetInput(BaseModel):
    monthly_salary: float
    expenses: List[Expense]

class SavingsProjection(BaseModel):
    period_months: int
    period_name: str
    total_saved: float
    monthly_breakdown: List[Dict[str, float]]

class BudgetResponse(BaseModel):
    monthly_salary: float
    total_expenses: float
    monthly_savings: float
    savings_projections: List[SavingsProjection]

@app.get("/")
async def root():
    return {"message": "Welcome to Son of Louman Budget API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/calculate-budget", response_model=BudgetResponse)
async def calculate_budget(budget_data: BudgetInput):
    """
    Calculate budget breakdown and savings projections
    """
    # Calculate total monthly expenses
    total_expenses = sum(expense.amount for expense in budget_data.expenses)
    
    # Calculate monthly savings
    monthly_savings = budget_data.monthly_salary - total_expenses
    
    # Generate savings projections
    projection_periods = [
        {"months": 6, "name": "6 months"},
        {"months": 12, "name": "1 year"},
        {"months": 24, "name": "2 years"}
    ]
    
    savings_projections = []
    
    for period in projection_periods:
        months = period["months"]
        total_saved = monthly_savings * months
        
        # Generate monthly breakdown for line graph
        monthly_breakdown = []
        cumulative_savings = 0
        
        for month in range(1, months + 1):
            cumulative_savings += monthly_savings
            monthly_breakdown.append({
                "month": month,
                "cumulative_savings": round(cumulative_savings, 2)
            })
        
        savings_projections.append(SavingsProjection(
            period_months=months,
            period_name=period["name"],
            total_saved=round(total_saved, 2),
            monthly_breakdown=monthly_breakdown
        ))
    
    return BudgetResponse(
        monthly_salary=budget_data.monthly_salary,
        total_expenses=round(total_expenses, 2),
        monthly_savings=round(monthly_savings, 2),
        savings_projections=savings_projections
    )

@app.get("/expense-categories")
async def get_expense_categories():
    """
    Get predefined expense categories
    """
    categories = [
        "rent",
        "utilities",
        "groceries",
        "transportation",
        "insurance",
        "entertainment",
        "dining_out",
        "healthcare",
        "subscriptions",
        "clothing",
        "savings_goals",
        "miscellaneous"
    ]
    return {"categories": categories}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)