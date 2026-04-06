# routers/signup.py
import logging
import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr, constr, validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

from database import get_db, User
from security import get_password_hash, create_email_verify_token, decode_email_verify_token
from email_utils import send_verification_email

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
async def signup(payload: SignupRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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
