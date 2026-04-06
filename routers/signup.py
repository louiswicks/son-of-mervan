# routers/signup.py
import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Response
from pydantic import BaseModel, EmailStr, constr, validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

from database import get_db, User, PasswordResetToken, RefreshToken
from security import get_password_hash, verify_password, create_access_token, create_email_verify_token, decode_email_verify_token
from email_utils import send_verification_email, send_password_reset_email
from core.limiter import limiter
from core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip('/')

class SignupRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=128)

    @validator("password")
    def password_policy(cls, v: str):
        if not re.search(r"[A-Z]", v): raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", v): raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"\d", v):    raise ValueError("Password must include a digit.")
        if not re.search(r"[^\w\s]", v): raise ValueError("Password must include a special character.")
        return v

class SignupResponse(BaseModel):
    message: str
    dev_verify_url: str | None = None

@router.post("/signup", response_model=SignupResponse)
@limiter.limit("5/minute")
async def signup(request: Request, payload: SignupRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 1) check duplicate
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    # 2) create user
    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        email_verified=False,
        verification_sent_at=datetime.utcnow(),
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered.")

    # 3) generate token + URL
    token = create_email_verify_token(user.id, user.email)
    verify_url = f"{FRONTEND_BASE_URL}#/verify-email?token={token}"

    # 4) Send email (or print dev link)
    smtp_ready = all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
    if smtp_ready:
        background_tasks.add_task(send_verification_email, user.email, verify_url)
        dev_link = None
    else:
        logger.info("[DEV] Verification link for %s: %s", user.email, verify_url)
        dev_link = verify_url

    return {
        "message": "Account created. Please check your email to verify.",
        "dev_verify_url": dev_link,
    }

class PasswordResetRequestPayload(BaseModel):
    email: EmailStr

class PasswordResetConfirmPayload(BaseModel):
    token: str
    new_password: constr(min_length=8, max_length=128)

    @validator("new_password")
    def password_policy(cls, v: str):
        if not re.search(r"[A-Z]", v): raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", v): raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"\d", v):    raise ValueError("Password must include a digit.")
        if not re.search(r"[^\w\s]", v): raise ValueError("Password must include a special character.")
        return v

@router.post("/password-reset-request", response_model=SignupResponse)
@limiter.limit("5/minute")
async def password_reset_request(
    request: Request,
    payload: PasswordResetRequestPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return success to prevent user enumeration
    if not user or not user.email_verified:
        return {"message": "If that email is registered, a reset link has been sent."}

    # Invalidate any existing unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at == None,  # noqa: E711
    ).update({"used_at": datetime.utcnow()})

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TTL_MIN)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    db.commit()

    reset_url = f"{FRONTEND_BASE_URL}#/reset-password?token={raw_token}"

    sendgrid_ready = bool(settings.SENDGRID_API_KEY)
    if sendgrid_ready:
        background_tasks.add_task(send_password_reset_email, user.email, reset_url)
        dev_link = None
    else:
        logger.info("[DEV] Password reset link for %s: %s", user.email, reset_url)
        dev_link = reset_url

    return {
        "message": "If that email is registered, a reset link has been sent.",
        "dev_verify_url": dev_link,
    }


@router.post("/password-reset-confirm", response_model=SignupResponse)
async def password_reset_confirm(
    payload: PasswordResetConfirmPayload,
    db: Session = Depends(get_db),
):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
    ).first()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    if reset_token.used_at is not None:
        raise HTTPException(status_code=400, detail="This reset link has already been used.")
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link has expired.")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user.password_hash = get_password_hash(payload.new_password)
    reset_token.used_at = datetime.utcnow()
    db.commit()

    return {"message": "Password updated successfully. You can now log in."}


class VerifyResponse(BaseModel):
    message: str

@router.get("/verify-email", response_model=VerifyResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    data = decode_email_verify_token(token)
    user_id = int(data["sub"])
    email = data["email"]

    user = db.query(User).filter(User.id == user_id, User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found for token.")

    if user.email_verified:
        return {"message": "Email already verified."}

    user.email_verified = True
    db.add(user)
    db.commit()
    return {"message": "Email verified successfully."}


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_access_token(request: Request, db: Session = Depends(get_db)):
    """Issue a new 15-min access token from a valid httpOnly refresh token cookie."""
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token provided.")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rt = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at == None,  # noqa: E711
    ).first()

    if not rt:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token.")
    if rt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token has expired.")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    access_token = create_access_token({"sub": user.email}, expires_delta=timedelta(minutes=15))
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", response_model=VerifyResponse)
async def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revoke the refresh token cookie and clear the cookie."""
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at == None,  # noqa: E711
        ).update({"revoked_at": datetime.utcnow()})
        db.commit()

    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully."}
