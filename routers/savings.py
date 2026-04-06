# routers/savings.py
"""
Savings Goals — CRUD + contributions management.

Routes:
  GET    /savings-goals                      list all active goals (with current_amount + status)
  POST   /savings-goals                      create goal
  PUT    /savings-goals/{id}                 update goal
  DELETE /savings-goals/{id}                 soft-delete goal

  GET    /savings-goals/{id}/contributions   list contributions for a goal
  POST   /savings-goals/{id}/contributions   add contribution
  DELETE /savings-goals/{id}/contributions/{contrib_id}   delete contribution
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from database import get_db, SavingsGoal, SavingsContribution, User
from security import verify_token
from models import (
    SavingsGoalCreate,
    SavingsGoalUpdate,
    SavingsGoalResponse,
    SavingsContributionCreate,
    SavingsContributionResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/savings-goals", tags=["savings"])


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_goal(goal_id: int, user: User, db: Session) -> SavingsGoal:
    goal = (
        db.query(SavingsGoal)
        .filter(
            SavingsGoal.id == goal_id,
            SavingsGoal.user_id == user.id,
            SavingsGoal.deleted_at == None,
        )
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")
    return goal


def _get_contribution(contrib_id: int, goal: SavingsGoal, db: Session) -> SavingsContribution:
    contrib = (
        db.query(SavingsContribution)
        .filter(
            SavingsContribution.id == contrib_id,
            SavingsContribution.goal_id == goal.id,
        )
        .first()
    )
    if not contrib:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contrib


def _compute_status(goal: SavingsGoal, current_amount: float):
    """
    Returns (status, required_monthly).
    status: on_track | behind | ahead | achieved | no_deadline
    required_monthly: None if no deadline or already achieved
    """
    if current_amount >= goal.target_amount:
        return "achieved", None

    if not goal.target_date:
        return "no_deadline", None

    now = datetime.utcnow()
    if goal.target_date <= now:
        return "behind", None

    # Months remaining (fractional)
    months_remaining = (
        (goal.target_date.year - now.year) * 12
        + (goal.target_date.month - now.month)
        + (goal.target_date.day - now.day) / 30.0
    )
    if months_remaining <= 0:
        return "behind", None

    amount_still_needed = goal.target_amount - current_amount
    required_monthly = round(amount_still_needed / months_remaining, 2)

    # Work out average actual monthly contribution pace
    # Use goal age in months as denominator
    goal_age_months = (
        (now.year - goal.created_at.year) * 12
        + (now.month - goal.created_at.month)
        + (now.day - goal.created_at.day) / 30.0
    )
    if goal_age_months < 0.5:
        # Goal is brand new — treat as on_track (no pace data)
        return "on_track", required_monthly

    actual_monthly = current_amount / goal_age_months

    if actual_monthly >= required_monthly * 1.05:
        return "ahead", required_monthly
    elif actual_monthly >= required_monthly * 0.95:
        return "on_track", required_monthly
    else:
        return "behind", required_monthly


def _goal_to_response(goal: SavingsGoal) -> dict:
    current_amount = sum(c.amount for c in goal.contributions)
    status, required_monthly = _compute_status(goal, current_amount)
    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "current_amount": round(current_amount, 2),
        "target_date": goal.target_date,
        "status": status,
        "required_monthly": required_monthly,
        "created_at": goal.created_at,
    }


def _contrib_to_response(c: SavingsContribution) -> dict:
    return {
        "id": c.id,
        "goal_id": c.goal_id,
        "amount": c.amount,
        "note": c.note,
        "contributed_at": c.contributed_at,
        "created_at": c.created_at,
    }


# ---------- goal endpoints ----------

@router.get("", response_model=List[SavingsGoalResponse])
def list_goals(
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    goals = (
        db.query(SavingsGoal)
        .filter(SavingsGoal.user_id == user.id, SavingsGoal.deleted_at == None)
        .order_by(SavingsGoal.created_at.desc())
        .all()
    )
    return [_goal_to_response(g) for g in goals]


@router.post("", response_model=SavingsGoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    body: SavingsGoalCreate,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    if body.target_amount <= 0:
        raise HTTPException(status_code=422, detail="target_amount must be positive")

    goal = SavingsGoal(user_id=user.id, target_date=body.target_date)
    goal.name = body.name
    goal.target_amount = body.target_amount
    db.add(goal)
    db.commit()
    db.refresh(goal)
    log.info("Created savings goal id=%s for user=%s", goal.id, user.id)
    return _goal_to_response(goal)


@router.put("/{goal_id}", response_model=SavingsGoalResponse)
def update_goal(
    body: SavingsGoalUpdate,
    goal_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    goal = _get_goal(goal_id, user, db)

    if "name" in body.model_fields_set and body.name is not None:
        goal.name = body.name
    if "target_amount" in body.model_fields_set and body.target_amount is not None:
        if body.target_amount <= 0:
            raise HTTPException(status_code=422, detail="target_amount must be positive")
        goal.target_amount = body.target_amount
    if "target_date" in body.model_fields_set:
        goal.target_date = body.target_date   # allow clearing (None)

    db.commit()
    db.refresh(goal)
    return _goal_to_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    goal = _get_goal(goal_id, user, db)
    goal.deleted_at = datetime.utcnow()
    db.commit()


# ---------- contribution endpoints ----------

@router.get("/{goal_id}/contributions", response_model=List[SavingsContributionResponse])
def list_contributions(
    goal_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    goal = _get_goal(goal_id, user, db)
    contribs = (
        db.query(SavingsContribution)
        .filter(SavingsContribution.goal_id == goal.id)
        .order_by(SavingsContribution.contributed_at.desc())
        .all()
    )
    return [_contrib_to_response(c) for c in contribs]


@router.post(
    "/{goal_id}/contributions",
    response_model=SavingsContributionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_contribution(
    body: SavingsContributionCreate,
    goal_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    goal = _get_goal(goal_id, user, db)
    if body.amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be positive")

    contrib = SavingsContribution(
        goal_id=goal.id,
        contributed_at=body.contributed_at or datetime.utcnow(),
    )
    contrib.amount = body.amount
    contrib.note = body.note
    db.add(contrib)
    db.commit()
    db.refresh(contrib)
    log.info("Added contribution id=%s to goal id=%s", contrib.id, goal.id)
    return _contrib_to_response(contrib)


@router.delete(
    "/{goal_id}/contributions/{contrib_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_contribution(
    goal_id: int = Path(...),
    contrib_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    goal = _get_goal(goal_id, user, db)
    contrib = _get_contribution(contrib_id, goal, db)
    db.delete(contrib)
    db.commit()
