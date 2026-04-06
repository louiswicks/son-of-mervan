# routers/users.py — Account management endpoints
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr, constr, validator
from sqlalchemy.orm import Session

from database import get_db, User, RefreshToken
from security import get_password_hash, verify_password, verify_token
from email_utils import send_account_deletion_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ---------- Schemas ----------

class UserProfileResponse(BaseModel):
    email: str
    username: str | None

class UpdateProfileRequest(BaseModel):
    username: str | None = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: constr(min_length=8, max_length=128)

    @validator("new_password")
    def password_policy(cls, v: str):
        if not re.search(r"[A-Z]", v): raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", v): raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"\d", v):    raise ValueError("Password must include a digit.")
        if not re.search(r"[^\w\s]", v): raise ValueError("Password must include a special character.")
        return v

class MessageResponse(BaseModel):
    message: str


# ---------- Helpers ----------

def _get_current_user(email: str = Depends(verify_token), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------- Endpoints ----------

@router.get("/me", response_model=UserProfileResponse)
def get_profile(user: User = Depends(_get_current_user)):
    """Return the authenticated user's profile."""
    return {"email": user.email, "username": user.username}


@router.put("/me", response_model=UserProfileResponse)
def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    """Update the authenticated user's profile (username only for now)."""
    if payload.username is not None:
        user.username = payload.username if payload.username.strip() else None
    db.commit()
    db.refresh(user)
    return {"email": user.email, "username": user.username}


@router.put("/me/password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    """Change the authenticated user's password. Requires correct current password."""
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password.")

    user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    logger.info("Password changed for user %s", user.email)
    return {"message": "Password updated successfully."}


@router.delete("/me", response_model=MessageResponse)
def delete_account(
    background_tasks: BackgroundTasks,
    user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    """
    Soft-delete the account. Sets deleted_at to now; data is permanently removed after 30 days.
    All active refresh tokens are revoked immediately.
    """
    user.deleted_at = datetime.utcnow()

    # Revoke all active refresh tokens so the user is logged out everywhere
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at == None,  # noqa: E711
    ).update({"revoked_at": datetime.utcnow()})

    db.commit()
    logger.info("Account soft-deleted for user %s", user.email)

    background_tasks.add_task(send_account_deletion_email, user.email)

    return {"message": "Account scheduled for deletion. Your data will be removed within 30 days."}
