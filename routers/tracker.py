from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from security import verify_token
from database import get_db
from crud import get_or_create_user, save_monthly_data, get_monthly_data
from models import MonthlyTrackerRequest, MonthlyTrackerResponse
import json

router = APIRouter(prefix="/tracker", tags=["tracker"])

@router.post("/", response_model=MonthlyTrackerResponse)
def save_tracker_data(
    data: MonthlyTrackerRequest,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user = get_or_create_user(db, current_user)
    saved = save_monthly_data(db, user, data)
    return MonthlyTrackerResponse(
        id=saved.id,
        month=saved.month,
        salary=saved.salary,
        total_expenses=saved.total_expenses,
        remaining_budget=saved.remaining_budget,
        expenses_by_category=json.loads(saved.expenses_json),
        savings_rate=round((saved.remaining_budget / saved.salary) * 100, 2) if saved.salary > 0 else 0
    )

@router.get("/{month}", response_model=MonthlyTrackerResponse)
def get_tracker_data(
    month: str,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user = get_or_create_user(db, current_user)
    record = get_monthly_data(db, user, month)
    if not record:
        raise HTTPException(status_code=404, detail="No data for this month")
    return MonthlyTrackerResponse(
        id=record.id,
        month=record.month,
        salary=record.salary,
        total_expenses=record.total_expenses,
        remaining_budget=record.remaining_budget,
        expenses_by_category=json.loads(record.expenses_json),
        savings_rate=round((record.remaining_budget / record.salary) * 100, 2) if record.salary > 0 else 0
    )
