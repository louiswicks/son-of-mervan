import json
from sqlalchemy.orm import Session
from database import MonthlyData, User
from models import MonthlyTrackerRequest

def get_or_create_user(db: Session, username: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def save_monthly_data(db: Session, user: User, data: MonthlyTrackerRequest):
    total_expenses = sum(e.amount for e in data.expenses)
    remaining_budget = data.salary - total_expenses

    expenses_by_category = {}
    for e in data.expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0) + e.amount

    db_data = MonthlyData(
        month=data.month,
        salary=data.salary,
        total_expenses=total_expenses,
        remaining_budget=remaining_budget,
        expenses_json=json.dumps(expenses_by_category),
        owner=user,
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data

def get_monthly_data(db: Session, user: User, month: str):
    return db.query(MonthlyData).filter(MonthlyData.owner == user, MonthlyData.month == month).first()

def get_annual_data(db: Session, user: User, year: str):
    return db.query(MonthlyData).filter(MonthlyData.owner == user, MonthlyData.month.like(f"{year}-%")).all()
