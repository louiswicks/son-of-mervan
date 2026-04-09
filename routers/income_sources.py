"""
Multiple Income Sources — CRUD.

Routes:
  GET    /income-sources?month=YYYY-MM   list income sources for a month
  POST   /income-sources                 add an income source
  PUT    /income-sources/{id}            update an income source
  DELETE /income-sources/{id}            soft-delete an income source
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import (
    IncomeSource,
    MonthlyData,
    User,
    VALID_INCOME_SOURCE_TYPES,
    get_db,
)
from security import verify_token

router = APIRouter(prefix="/income-sources", tags=["income-sources"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class IncomeSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., gt=0)
    source_type: str = Field("salary", max_length=50)
    month: str = Field(..., description="YYYY-MM")


class IncomeSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    amount: Optional[float] = Field(None, gt=0)
    source_type: Optional[str] = Field(None, max_length=50)


class IncomeSourceOut(BaseModel):
    id: int
    name: str
    amount: float
    source_type: str
    month: str

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _find_month(db: Session, user: User, month: str) -> MonthlyData | None:
    """Return MonthlyData for *user* matching *month* (YYYY-MM), or None."""
    rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    for row in rows:
        if row.month == month:
            return row
    return None


def _normalize_month(month: str) -> str:
    """Accept YYYY-MM or YYYY-M and return YYYY-MM."""
    parts = month.split("-")
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1].zfill(2)}"
    return month


def _get_source(source_id: int, user: User, db: Session) -> IncomeSource:
    src = (
        db.query(IncomeSource)
        .filter(
            IncomeSource.id == source_id,
            IncomeSource.user_id == user.id,
            IncomeSource.deleted_at == None,
        )
        .first()
    )
    if not src:
        raise HTTPException(status_code=404, detail="Income source not found")
    return src


def _to_out(src: IncomeSource, month_row: MonthlyData) -> dict:
    return {
        "id": src.id,
        "name": src.name or "",
        "amount": src.amount,
        "source_type": src.source_type,
        "month": month_row.month or "",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[IncomeSourceOut])
def list_income_sources(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _require_user(db, current_user)
    month_norm = _normalize_month(month)
    month_row = _find_month(db, user, month_norm)
    if not month_row:
        return []

    sources = (
        db.query(IncomeSource)
        .filter(
            IncomeSource.monthly_data_id == month_row.id,
            IncomeSource.deleted_at == None,
        )
        .all()
    )
    return [_to_out(s, month_row) for s in sources]


@router.post("", response_model=IncomeSourceOut, status_code=status.HTTP_201_CREATED)
def create_income_source(
    body: IncomeSourceCreate,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    if body.source_type not in VALID_INCOME_SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"source_type must be one of: {sorted(VALID_INCOME_SOURCE_TYPES)}",
        )

    user = _require_user(db, current_user)
    month_norm = _normalize_month(body.month)
    month_row = _find_month(db, user, month_norm)
    if not month_row:
        raise HTTPException(status_code=404, detail="Month not found — POST to /monthly-tracker first")

    src = IncomeSource(user_id=user.id, monthly_data_id=month_row.id, source_type=body.source_type)
    src.name = body.name
    src.amount = body.amount
    db.add(src)
    db.commit()
    db.refresh(src)
    return _to_out(src, month_row)


@router.put("/{source_id}", response_model=IncomeSourceOut)
def update_income_source(
    source_id: int,
    body: IncomeSourceUpdate,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    if body.source_type is not None and body.source_type not in VALID_INCOME_SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"source_type must be one of: {sorted(VALID_INCOME_SOURCE_TYPES)}",
        )

    user = _require_user(db, current_user)
    src = _get_source(source_id, user, db)
    month_row = db.query(MonthlyData).filter(MonthlyData.id == src.monthly_data_id).first()

    if body.name is not None:
        src.name = body.name
    if body.amount is not None:
        src.amount = body.amount
    if body.source_type is not None:
        src.source_type = body.source_type

    db.commit()
    db.refresh(src)
    return _to_out(src, month_row)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income_source(
    source_id: int,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _require_user(db, current_user)
    src = _get_source(source_id, user, db)
    src.deleted_at = datetime.utcnow()
    db.commit()
