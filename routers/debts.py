# routers/debts.py
"""
Debt Payoff Calculator — CRUD + payoff plan simulation.

Routes:
  GET    /debts                              list active debts
  POST   /debts                              create debt
  PUT    /debts/{id}                         update debt
  DELETE /debts/{id}                         soft-delete debt
  GET    /debts/payoff-plan?strategy=...     snowball or avalanche payoff plan
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from database import get_db, Debt, User
from security import verify_token
from models import (
    DebtCreate,
    DebtUpdate,
    DebtResponse,
    PayoffPlanResponse,
    PayoffMonth,
    PayoffDebtMonth,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/debts", tags=["debts"])

VALID_STRATEGIES = {"snowball", "avalanche"}
MAX_PAYOFF_MONTHS = 360  # cap simulation to avoid infinite loops


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_debt(debt_id: int, user: User, db: Session) -> Debt:
    debt = (
        db.query(Debt)
        .filter(
            Debt.id == debt_id,
            Debt.user_id == user.id,
            Debt.deleted_at == None,
        )
        .first()
    )
    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")
    return debt


def _debt_to_response(d: Debt) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "balance": round(d.balance, 2),
        "interest_rate": d.interest_rate,
        "minimum_payment": d.minimum_payment,
        "created_at": d.created_at,
    }


def _compute_payoff_plan(debts: List[Debt], strategy: str) -> dict:
    """
    Simulate month-by-month payoff using snowball or avalanche strategy.

    Snowball: order by ascending balance (smallest first).
    Avalanche: order by descending interest rate (highest APR first).

    Each month:
      1. Apply monthly interest to all balances.
      2. Pay the minimum on each debt; any debt cleared frees its minimum
         payment to roll into the next priority debt.
      3. Record remaining balances for that month.
    """
    # Build mutable state list: [name, balance, interest_rate, minimum_payment]
    state = [
        {
            "name": d.name,
            "balance": d.balance,
            "rate": d.interest_rate / 12,        # monthly rate
            "min_pay": d.minimum_payment,
            "freed": 0.0,
        }
        for d in debts
    ]

    total_interest = 0.0
    months_data: List[PayoffMonth] = []
    month_idx = 0

    while any(s["balance"] > 0.01 for s in state) and month_idx < MAX_PAYOFF_MONTHS:
        month_idx += 1

        # Step 1: accrue monthly interest on all live debts
        for s in state:
            if s["balance"] > 0.01:
                interest = s["balance"] * s["rate"]
                s["balance"] += interest
                total_interest += interest

        # Step 2: determine priority order for this month
        live = [s for s in state if s["balance"] > 0.01]
        if strategy == "snowball":
            live.sort(key=lambda x: x["balance"])
        else:  # avalanche
            live.sort(key=lambda x: -x["rate"])

        # Collect freed payments from debts paid off this month
        extra_pool = sum(s["freed"] for s in state)
        for s in state:
            s["freed"] = 0.0

        # Pay minimum on each live debt; roll any overpayment into pool
        for s in live:
            payment = min(s["min_pay"], s["balance"])
            s["balance"] = max(0.0, s["balance"] - payment)
            if s["balance"] < 0.01:
                s["balance"] = 0.0
                # Freed minimum goes to pool next round
                extra_pool += s["min_pay"] - payment

        # Apply extra pool to the top-priority live debt (first non-zero)
        for s in live:
            if s["balance"] > 0.01:
                applied = min(extra_pool, s["balance"])
                s["balance"] = max(0.0, s["balance"] - applied)
                if s["balance"] < 0.01:
                    s["balance"] = 0.0
                    extra_pool -= applied
                    extra_pool += s["min_pay"]  # its min payment freed for next month
                else:
                    break

        # Record snapshot
        months_data.append(
            PayoffMonth(
                month=month_idx,
                debts=[
                    PayoffDebtMonth(
                        name=s["name"],
                        remaining_balance=round(s["balance"], 2),
                    )
                    for s in state
                ],
            )
        )

    return {
        "strategy": strategy,
        "months": months_data,
        "total_interest_paid": round(total_interest, 2),
        "payoff_months": month_idx,
    }


# ---------- endpoints ----------

@router.get("/payoff-plan", response_model=PayoffPlanResponse)
def get_payoff_plan(
    strategy: str = Query(default="avalanche", description="snowball or avalanche"),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(status_code=422, detail="strategy must be 'snowball' or 'avalanche'")

    user = _get_user(db, email)
    debts = (
        db.query(Debt)
        .filter(Debt.user_id == user.id, Debt.deleted_at == None)
        .all()
    )
    if not debts:
        return PayoffPlanResponse(
            strategy=strategy,
            months=[],
            total_interest_paid=0.0,
            payoff_months=0,
        )

    plan = _compute_payoff_plan(debts, strategy)
    return PayoffPlanResponse(**plan)


@router.get("", response_model=List[DebtResponse])
def list_debts(
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    debts = (
        db.query(Debt)
        .filter(Debt.user_id == user.id, Debt.deleted_at == None)
        .order_by(Debt.created_at.desc())
        .all()
    )
    return [_debt_to_response(d) for d in debts]


@router.post("", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
def create_debt(
    body: DebtCreate,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    if body.balance <= 0:
        raise HTTPException(status_code=422, detail="balance must be positive")
    if body.interest_rate < 0 or body.interest_rate > 2:
        raise HTTPException(status_code=422, detail="interest_rate must be between 0 and 2 (200% APR max)")
    if body.minimum_payment <= 0:
        raise HTTPException(status_code=422, detail="minimum_payment must be positive")

    debt = Debt(
        user_id=user.id,
        interest_rate=body.interest_rate,
        minimum_payment=body.minimum_payment,
    )
    debt.name = body.name
    debt.balance = body.balance
    db.add(debt)
    db.commit()
    db.refresh(debt)
    log.info("Created debt id=%s for user=%s", debt.id, user.id)
    return _debt_to_response(debt)


@router.put("/{debt_id}", response_model=DebtResponse)
def update_debt(
    body: DebtUpdate,
    debt_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    debt = _get_debt(debt_id, user, db)

    if "name" in body.model_fields_set and body.name is not None:
        debt.name = body.name
    if "balance" in body.model_fields_set and body.balance is not None:
        if body.balance <= 0:
            raise HTTPException(status_code=422, detail="balance must be positive")
        debt.balance = body.balance
    if "interest_rate" in body.model_fields_set and body.interest_rate is not None:
        if body.interest_rate < 0 or body.interest_rate > 2:
            raise HTTPException(status_code=422, detail="interest_rate must be between 0 and 2")
        debt.interest_rate = body.interest_rate
    if "minimum_payment" in body.model_fields_set and body.minimum_payment is not None:
        if body.minimum_payment <= 0:
            raise HTTPException(status_code=422, detail="minimum_payment must be positive")
        debt.minimum_payment = body.minimum_payment

    db.commit()
    db.refresh(debt)
    return _debt_to_response(debt)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debt(
    debt_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    debt = _get_debt(debt_id, user, db)
    debt.deleted_at = datetime.utcnow()
    db.commit()
