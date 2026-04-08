# routers/totp.py
"""
TOTP-based Two-Factor Authentication endpoints.

Flow:
  Setup:
    1. POST /auth/2fa/setup   — generate secret, return provisioning URI + QR PNG (base64)
    2. POST /auth/2fa/confirm — verify first code + enable 2FA on the account

  Login (when totp_enabled=True):
    1. POST /login            — returns {requires_2fa: true, totp_challenge_token: <JWT>}
    2. POST /auth/2fa/verify-login — accepts challenge_token + code, returns full session

  Manage:
    GET  /auth/2fa/status  — {enabled: bool}
    POST /auth/2fa/disable — requires password + current TOTP code; disables 2FA
"""
import base64
import hashlib
import io
import logging
import secrets
from datetime import datetime, timedelta

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status

from core.config import settings
from core.limiter import limiter
from database import get_db, User, RefreshToken
from security import (
    verify_token,
    verify_password,
    create_access_token,
    decode_totp_challenge_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/2fa", tags=["2fa"])

TOTP_ISSUER = "SYITB"


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TOTPSetupResponse(BaseModel):
    provisioning_uri: str
    qr_code_b64: str       # base64-encoded PNG to render as <img src="data:image/png;base64,...">


class TOTPConfirmRequest(BaseModel):
    code: str


class TOTPDisableRequest(BaseModel):
    password: str
    code: str


class TOTPStatusResponse(BaseModel):
    enabled: bool


class TOTPVerifyLoginRequest(BaseModel):
    challenge_token: str
    code: str


class TOTPVerifyLoginResponse(BaseModel):
    access_token: str
    token_type: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def _verify_totp_code(secret: str, code: str) -> bool:
    """Returns True if code is valid within ±1 time-step window (±30s)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def _generate_qr_b64(provisioning_uri: str) -> str:
    """Render a QR code for the provisioning URI and return as base64 PNG."""
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=TOTPStatusResponse)
def totp_status(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return whether 2FA is enabled for the current user."""
    user = _get_user(db, current_user)
    return {"enabled": bool(user.totp_enabled)}


@router.post("/setup", response_model=TOTPSetupResponse)
@limiter.limit("10/minute")
def totp_setup(
    request: Request,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Generate a TOTP secret and return the provisioning URI + QR code.
    The secret is stored (encrypted) but NOT yet activated — call /confirm next.
    """
    user = _get_user(db, current_user)

    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled. Disable it first to reset.",
        )

    # Generate a fresh base32 secret
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.commit()

    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name=TOTP_ISSUER,
    )
    qr_b64 = _generate_qr_b64(provisioning_uri)

    return {"provisioning_uri": provisioning_uri, "qr_code_b64": qr_b64}


@router.post("/confirm")
@limiter.limit("10/minute")
def totp_confirm(
    request: Request,
    payload: TOTPConfirmRequest,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Verify the first TOTP code from the authenticator app and enable 2FA.
    Must be called after /setup.
    """
    user = _get_user(db, current_user)

    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled.")

    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /auth/2fa/setup first.")

    if not _verify_totp_code(user.totp_secret, payload.code.strip()):
        raise HTTPException(status_code=400, detail="Invalid TOTP code.")

    user.totp_enabled = True
    db.commit()

    logger.info("2FA enabled for user %s", user.id)
    return {"message": "Two-factor authentication enabled successfully."}


@router.post("/disable")
@limiter.limit("5/minute")
def totp_disable(
    request: Request,
    payload: TOTPDisableRequest,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Disable 2FA. Requires the account password AND a valid TOTP code.
    """
    user = _get_user(db, current_user)

    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not currently enabled.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
        )

    if not _verify_totp_code(user.totp_secret, payload.code.strip()):
        raise HTTPException(status_code=400, detail="Invalid TOTP code.")

    user.totp_enabled = False
    user.totp_secret = None
    db.commit()

    logger.info("2FA disabled for user %s", user.id)
    return {"message": "Two-factor authentication disabled."}


@router.post("/verify-login", response_model=TOTPVerifyLoginResponse)
@limiter.limit("10/minute")
def totp_verify_login(
    request: Request,
    response: Response,
    payload: TOTPVerifyLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Complete a 2FA-gated login.
    Accepts the short-lived challenge token (from /login) + TOTP code.
    On success: issues access token + sets httpOnly refresh cookie.
    """
    data = decode_totp_challenge_token(payload.challenge_token)
    user_id = int(data["sub"])
    email = data["email"]

    user = db.query(User).filter(User.id == user_id, User.email == email).first()
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Invalid challenge token.")

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA is not configured for this account.")

    if not _verify_totp_code(user.totp_secret, payload.code.strip()):
        raise HTTPException(status_code=401, detail="Invalid or expired TOTP code.")

    # Issue full session
    access_token = create_access_token({"sub": user.email}, expires_delta=timedelta(minutes=15))

    raw_refresh = secrets.token_urlsafe(32)
    refresh_hash = hashlib.sha256(raw_refresh.encode()).hexdigest()
    refresh_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    user_agent = request.headers.get("user-agent", "")[:512]
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_expires, user_agent=user_agent, last_used_at=datetime.utcnow()))
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )

    logger.info("2FA login complete for user %s", user.id)
    return {"access_token": access_token, "token_type": "bearer"}
