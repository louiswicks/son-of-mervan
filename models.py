from pydantic import BaseModel
from typing import Dict, List, Optional

class ExpenseItem(BaseModel):
    name: str
    amount: float
    category: str

class ExpenseUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    planned_amount: Optional[float] = None
    actual_amount: Optional[float] = None

class ExpenseResponse(BaseModel):
    id: int
    name: str
    category: str
    planned_amount: float
    actual_amount: float

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
