from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

class ExpenseItem(BaseModel):
    name: str
    amount: float
    category: str

class PaginatedExpenseResponse(BaseModel):
    items: List["ExpenseResponse"]
    total: int
    page: int
    pages: int
    page_size: int

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


VALID_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}


class RecurringExpenseCreate(BaseModel):
    name: str
    category: str
    planned_amount: float
    frequency: str          # daily / weekly / monthly / yearly
    start_date: datetime
    end_date: Optional[datetime] = None


class RecurringExpenseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    planned_amount: Optional[float] = None
    frequency: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class RecurringExpenseResponse(BaseModel):
    id: int
    name: str
    category: str
    planned_amount: float
    frequency: str
    start_date: datetime
    end_date: Optional[datetime]
    last_generated_at: Optional[datetime]
    created_at: datetime


# ---------- Savings Goals ----------

class SavingsGoalCreate(BaseModel):
    name: str
    target_amount: float
    target_date: Optional[datetime] = None


class SavingsGoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    target_date: Optional[datetime] = None


class SavingsContributionCreate(BaseModel):
    amount: float
    note: Optional[str] = None
    contributed_at: Optional[datetime] = None


class SavingsContributionResponse(BaseModel):
    id: int
    goal_id: int
    amount: float
    note: Optional[str]
    contributed_at: datetime
    created_at: datetime


class SavingsGoalResponse(BaseModel):
    id: int
    name: str
    target_amount: float
    current_amount: float
    target_date: Optional[datetime]
    status: str          # on_track | behind | ahead | achieved | no_deadline
    required_monthly: Optional[float]   # amount needed per month to hit target
    created_at: datetime
