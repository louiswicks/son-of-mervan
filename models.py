from pydantic import BaseModel
from typing import Dict, List, Optional

class ExpenseItem(BaseModel):
    name: str
    amount: float
    category: str

class MonthlyTrackerRequest(BaseModel):
    month: str   # e.g. "2025-08"
    salary: float
    expenses: List[ExpenseItem]

class MonthlyTrackerResponse(BaseModel):
    id: int
    month: str
    salary: float
    total_expenses: float
    remaining_budget: float
    expenses_by_category: Dict[str, float]
    savings_rate: float

class AnnualOverviewResponse(BaseModel):
    year: str
    months: List[MonthlyTrackerResponse]
    total_income: float
    total_expenses: float
    average_savings_rate: float
