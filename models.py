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
