from pydantic import BaseModel, Field
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
    currency: Optional[str] = None

class ExpenseResponse(BaseModel):
    id: int
    name: str
    category: str
    planned_amount: float
    actual_amount: float
    currency: str = "GBP"

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


# ---------- Budget Alerts ----------

VALID_CATEGORIES = {"Housing", "Transportation", "Food", "Utilities", "Insurance", "Healthcare", "Entertainment", "Other"}


class BudgetAlertCreate(BaseModel):
    category: str
    threshold_pct: int = 80   # 1–100


class BudgetAlertUpdate(BaseModel):
    category: Optional[str] = None
    threshold_pct: Optional[int] = None
    active: Optional[bool] = None


class BudgetAlertResponse(BaseModel):
    id: int
    category: str
    threshold_pct: int
    active: bool
    created_at: datetime


# ---------- Notifications ----------

class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    read_at: Optional[datetime]
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    unread_count: int


class AuditLogResponse(BaseModel):
    id: int
    expense_id: int
    action: str  # "create" | "update" | "delete"
    # {"before": null|{...}, "after": null|{...}}
    changed_fields: Optional[Dict] = None
    timestamp: datetime


# ---------- Investments ----------

VALID_ASSET_TYPES = {"stock", "etf", "fund", "crypto", "other"}


class InvestmentCreate(BaseModel):
    name: str
    ticker: Optional[str] = None
    asset_type: str = "stock"   # stock | etf | fund | crypto | other
    units: float
    purchase_price: float        # price per unit at time of purchase
    currency: str = "GBP"
    notes: Optional[str] = None


class InvestmentUpdate(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    asset_type: Optional[str] = None
    units: Optional[float] = None
    purchase_price: Optional[float] = None
    currency: Optional[str] = None
    notes: Optional[str] = None


class InvestmentResponse(BaseModel):
    id: int
    name: str
    ticker: Optional[str]
    asset_type: str
    units: float
    purchase_price: float
    currency: str
    notes: Optional[str]
    current_price: Optional[float]   # latest synced price (None if never synced)
    current_value: Optional[float]   # units × current_price
    cost_basis: float                # units × purchase_price
    gain_loss: Optional[float]       # current_value − cost_basis
    gain_loss_pct: Optional[float]   # (gain_loss / cost_basis) × 100
    last_price_at: Optional[datetime]
    created_at: datetime


class InvestmentPortfolioSummary(BaseModel):
    total_cost: float
    total_value: Optional[float]
    total_gain_loss: Optional[float]
    total_gain_loss_pct: Optional[float]
    holdings_count: int


# ---------- Tax Filing ----------

class TaxCategoryBreakdown(BaseModel):
    category: str
    hmrc_category: str           # mapped HMRC expense heading
    total_actual: float          # total actual spend across tax year
    months_with_data: int        # how many months had expenses in this category
    potentially_deductible: bool # advisory flag (user should verify with accountant)


class TaxSummaryResponse(BaseModel):
    tax_year: int                # e.g. 2024 means April 2024 – April 2025
    period_start: str            # "2024-04-06"
    period_end: str              # "2025-04-05"
    months_with_data: int
    total_income: float
    total_expenses: float
    net_savings: float
    savings_rate: float          # percentage
    category_breakdown: List[TaxCategoryBreakdown]
    potentially_deductible_total: float


# ---------- Household ----------

class HouseholdCreate(BaseModel):
    name: str


class HouseholdInviteRequest(BaseModel):
    email: str


class HouseholdJoinRequest(BaseModel):
    token: str


class MemberResponse(BaseModel):
    user_id: int
    email: str
    username: Optional[str]
    role: str
    joined_at: datetime


class HouseholdResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    members: List[MemberResponse]
    pending_invites: List[str]   # list of invitee emails awaiting acceptance
    created_at: datetime


class HouseholdBudgetMemberSummary(BaseModel):
    user_id: int
    email: str
    username: Optional[str]
    salary_planned: float
    salary_actual: float
    total_expenses_planned: float
    total_expenses_actual: float
    remaining_planned: float
    remaining_actual: float


class HouseholdBudgetResponse(BaseModel):
    month: str
    members: List[HouseholdBudgetMemberSummary]
    combined_salary_planned: float
    combined_salary_actual: float
    combined_expenses_planned: float
    combined_expenses_actual: float
    combined_remaining_planned: float
    combined_remaining_actual: float


# ---------- User Categories ----------

class UserCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#6b7280", max_length=7)


class UserCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, max_length=7)


class UserCategoryResponse(BaseModel):
    id: int
    name: str
    color: str
    is_default: bool

    class Config:
        from_attributes = True


# ---------- CSV Import ----------

class CSVPreviewRow(BaseModel):
    row_id: str
    date: str
    description: str
    amount: float
    month: str  # YYYY-MM
    suggested_category: str
    is_duplicate: bool


class CSVPreviewResponse(BaseModel):
    rows: List[CSVPreviewRow]
    total: int
    duplicates_count: int
    parse_errors: int


class CSVConfirmRow(BaseModel):
    row_id: str
    description: str
    amount: float
    month: str  # YYYY-MM
    category: str
    include: bool = True


class CSVConfirmRequest(BaseModel):
    rows: List[CSVConfirmRow]


class CSVImportResult(BaseModel):
    imported: int
    skipped: int
