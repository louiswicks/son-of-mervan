"""
Category-rule CRUD + bulk-apply endpoint.

Rules let users define keyword patterns that auto-assign categories to expenses.
Pattern matching is case-insensitive substring.  Rules evaluated in ascending
priority order; first match wins.

Endpoints
---------
GET    /category-rules              list active rules for the current user
POST   /category-rules              create a rule
PUT    /category-rules/{id}         update pattern / category / priority
DELETE /category-rules/{id}         soft-delete
POST   /category-rules/apply        re-categorize all expenses in a month
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import CategoryRule, MonthlyData, MonthlyExpense, User, get_db
from security import verify_token

router = APIRouter(prefix="/category-rules", tags=["category-rules"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CategoryRuleCreate(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=256)
    category: str = Field(..., min_length=1, max_length=128)
    priority: int = Field(0, ge=0)


class CategoryRuleUpdate(BaseModel):
    pattern: Optional[str] = Field(None, min_length=1, max_length=256)
    category: Optional[str] = Field(None, min_length=1, max_length=128)
    priority: Optional[int] = Field(None, ge=0)


class CategoryRuleOut(BaseModel):
    id: int
    pattern: str
    category: str
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _get_rule(db: Session, rule_id: int, user_id: int) -> CategoryRule:
    rule = (
        db.query(CategoryRule)
        .filter(
            CategoryRule.id == rule_id,
            CategoryRule.user_id == user_id,
            CategoryRule.deleted_at == None,  # noqa: E711
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


def _normalize_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    y, mo = parts
    try:
        return f"{int(y):04d}-{int(mo):02d}"
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")


def apply_rules_to_name(rules: List[CategoryRule], name: str) -> Optional[str]:
    """
    Return the category of the first rule (sorted by priority asc) whose
    pattern is a case-insensitive substring of *name*, or None if no match.
    """
    lower_name = name.lower()
    for rule in sorted(rules, key=lambda r: r.priority):
        if rule.pattern.lower() in lower_name:
            return rule.category
    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[CategoryRuleOut])
def list_rules(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return active rules for the current user, ordered by priority then id."""
    user = _require_user(db, current_user)
    rules = (
        db.query(CategoryRule)
        .filter(
            CategoryRule.user_id == user.id,
            CategoryRule.deleted_at == None,  # noqa: E711
        )
        .order_by(CategoryRule.priority, CategoryRule.id)
        .all()
    )
    return [
        CategoryRuleOut(
            id=r.id,
            pattern=r.pattern,
            category=r.category,
            priority=r.priority,
            created_at=r.created_at,
        )
        for r in rules
    ]


@router.post("", response_model=CategoryRuleOut, status_code=201)
def create_rule(
    body: CategoryRuleCreate,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> CategoryRuleOut:
    user = _require_user(db, current_user)
    rule = CategoryRule(user_id=user.id, pattern=body.pattern, priority=body.priority)
    rule.category = body.category
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return CategoryRuleOut(
        id=rule.id,
        pattern=rule.pattern,
        category=rule.category,
        priority=rule.priority,
        created_at=rule.created_at,
    )


@router.put("/{rule_id}", response_model=CategoryRuleOut)
def update_rule(
    rule_id: int,
    body: CategoryRuleUpdate,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> CategoryRuleOut:
    user = _require_user(db, current_user)
    rule = _get_rule(db, rule_id, user.id)
    if body.pattern is not None:
        rule.pattern = body.pattern
    if body.category is not None:
        rule.category = body.category
    if body.priority is not None:
        rule.priority = body.priority
    db.commit()
    db.refresh(rule)
    return CategoryRuleOut(
        id=rule.id,
        pattern=rule.pattern,
        category=rule.category,
        priority=rule.priority,
        created_at=rule.created_at,
    )


@router.delete("/{rule_id}", status_code=204, response_model=None)
def delete_rule(
    rule_id: int,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _require_user(db, current_user)
    rule = _get_rule(db, rule_id, user.id)
    rule.deleted_at = datetime.utcnow()
    db.commit()


@router.post("/apply")
def apply_rules(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Re-categorize every non-deleted expense in the given month against the
    user's active rules.  Returns the count of updated expenses.
    """
    month_norm = _normalize_month(month)
    user = _require_user(db, current_user)

    rules = (
        db.query(CategoryRule)
        .filter(
            CategoryRule.user_id == user.id,
            CategoryRule.deleted_at == None,  # noqa: E711
        )
        .order_by(CategoryRule.priority, CategoryRule.id)
        .all()
    )

    # Find the month row first (O(n) decrypt — consistent with the rest of the app)
    all_months = (
        db.query(MonthlyData)
        .filter(MonthlyData.user_id == user.id)
        .all()
    )
    month_row = next((m for m in all_months if m.month == month_norm), None)
    if not month_row:
        raise HTTPException(status_code=404, detail="No data found for that month")

    if not rules:
        return {"month": month_norm, "updated": 0}

    expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,  # noqa: E711
        )
        .all()
    )

    updated = 0
    for exp in expenses:
        new_cat = apply_rules_to_name(rules, exp.name or "")
        if new_cat and new_cat != exp.category:
            exp.category = new_cat
            updated += 1

    if updated:
        db.commit()

    return {"month": month_norm, "updated": updated}
