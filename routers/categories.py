"""
routers/categories.py — User-defined expense categories.

Endpoints:
  GET    /categories          List the current user's categories (seeds defaults on first call)
  POST   /categories          Create a custom category
  PUT    /categories/{id}     Rename or recolour a category
  DELETE /categories/{id}     Delete a custom category (defaults cannot be deleted)
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from database import DEFAULT_CATEGORIES, UserCategory, User, get_db
from models import UserCategoryCreate, UserCategoryUpdate, UserCategoryResponse
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/categories", tags=["categories"])


# -------------------- Helpers --------------------

def _get_user(email: str, db: Session) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _seed_defaults(db: Session, user_id: int) -> None:
    """Insert the 8 built-in categories for a user who has none yet."""
    for name, color in DEFAULT_CATEGORIES:
        cat = UserCategory(
            user_id=user_id,
            name=name,
            color=color,
            is_default=True,
        )
        db.add(cat)
    db.commit()


def _get_or_seed(db: Session, user_id: int) -> List[UserCategory]:
    """Return all categories for a user, seeding defaults if the list is empty."""
    cats = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    if not cats:
        _seed_defaults(db, user_id)
        cats = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    return cats


# -------------------- Endpoints --------------------

@router.get("", response_model=List[UserCategoryResponse])
def list_categories(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    return _get_or_seed(db, user.id)


@router.post("", response_model=UserCategoryResponse, status_code=201)
def create_category(
    payload: UserCategoryCreate,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    _get_or_seed(db, user.id)  # ensure defaults exist before adding a custom one

    existing = (
        db.query(UserCategory)
        .filter(UserCategory.user_id == user.id, UserCategory.name == payload.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Category name already exists")

    cat = UserCategory(user_id=user.id, name=payload.name, color=payload.color)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    logger.info("User %s created category '%s'", user.id, cat.name)
    return cat


@router.put("/{category_id}", response_model=UserCategoryResponse)
def update_category(
    category_id: int = Path(...),
    payload: UserCategoryUpdate = None,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    cat = (
        db.query(UserCategory)
        .filter(UserCategory.id == category_id, UserCategory.user_id == user.id)
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.name is not None:
        dup = (
            db.query(UserCategory)
            .filter(
                UserCategory.user_id == user.id,
                UserCategory.name == payload.name,
                UserCategory.id != category_id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="Category name already exists")
        cat.name = payload.name

    if payload.color is not None:
        cat.color = payload.color

    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int = Path(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    cat = (
        db.query(UserCategory)
        .filter(UserCategory.id == category_id, UserCategory.user_id == user.id)
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete a default category")
    db.delete(cat)
    db.commit()
