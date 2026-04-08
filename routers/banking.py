"""
routers/banking.py — TrueLayer open banking OAuth integration.

Endpoints:
  GET  /banking/connect                 Generate TrueLayer authorisation URL (auth required)
  GET  /banking/callback?code=&state=   OAuth callback — exchanges code, stores BankConnection
  POST /banking/refresh/{id}            Refresh access token for a connection (auth required)
  GET  /banking/connections             List the current user's active bank connections (auth required)
"""
import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.config import settings
from database import BankConnection, User, get_db
from models import BankConnectResponse, BankConnectionListResponse, BankConnectionResponse
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/banking", tags=["banking"])

# ---------------------------------------------------------------------------
# TrueLayer URL helpers
# ---------------------------------------------------------------------------

def _auth_base() -> str:
    return "https://auth.truelayer-sandbox.com" if settings.TRUELAYER_SANDBOX else "https://auth.truelayer.com"


def _api_base() -> str:
    return "https://api.truelayer-sandbox.com" if settings.TRUELAYER_SANDBOX else "https://api.truelayer.com"


def _truelayer_configured() -> bool:
    return bool(settings.TRUELAYER_CLIENT_ID and settings.TRUELAYER_CLIENT_SECRET)


# ---------------------------------------------------------------------------
# CSRF state helpers (HMAC-signed, stateless)
# ---------------------------------------------------------------------------

def _make_state(user_id: int) -> str:
    """Return a tamper-evident state token: '{user_id}.{nonce}.{hmac}'."""
    nonce = secrets.token_hex(16)
    payload = f"{user_id}.{nonce}"
    sig = hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{sig}"


def _verify_state(state: str) -> int:
    """Decode and verify state; raise 400 on tampering. Returns user_id."""
    parts = state.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    user_id_str, nonce, sig = parts
    payload = f"{user_id_str}.{nonce}"
    expected = hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="State signature mismatch — possible CSRF")
    try:
        return int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _connection_response(conn: BankConnection) -> BankConnectionResponse:
    return BankConnectionResponse(
        id=conn.id,
        provider=conn.provider,
        account_id=conn.account_id,
        last_synced_at=conn.last_synced_at,
        created_at=conn.created_at,
        is_sandbox=settings.TRUELAYER_SANDBOX,
    )


# ---------------------------------------------------------------------------
# GET /banking/connect
# ---------------------------------------------------------------------------

@router.get("/connect", response_model=BankConnectResponse)
def connect_bank(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Return a TrueLayer authorisation URL that the frontend should redirect the
    user to.  Includes an HMAC-signed state token to prevent CSRF on callback.
    """
    if not _truelayer_configured():
        raise HTTPException(
            status_code=503,
            detail="Open banking is not configured on this server",
        )

    user = _require_user(db, current_user)
    state = _make_state(user.id)

    params = {
        "response_type": "code",
        "client_id": settings.TRUELAYER_CLIENT_ID,
        "scope": "accounts transactions balance",
        "redirect_uri": settings.TRUELAYER_REDIRECT_URI,
        "state": state,
        "providers": "uk-ob-all uk-oauth-all",
    }
    auth_url = f"{_auth_base()}/?{urlencode(params)}"
    logger.info("Generated TrueLayer auth URL for user %s", user.id)
    return BankConnectResponse(auth_url=auth_url)


# ---------------------------------------------------------------------------
# GET /banking/callback
# ---------------------------------------------------------------------------

@router.get("/callback")
def banking_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    OAuth callback — called by TrueLayer (browser redirect) after the user
    grants access.  Exchanges the code for tokens, fetches the first account,
    and stores an encrypted BankConnection row.  Redirects the browser to the
    frontend /banking page.
    """
    if not _truelayer_configured():
        raise HTTPException(status_code=503, detail="Open banking is not configured")

    user_id = _verify_state(state)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Exchange authorisation code for tokens
    token_url = f"{_auth_base()}/connect/token"
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.TRUELAYER_CLIENT_ID,
                "client_secret": settings.TRUELAYER_CLIENT_SECRET,
                "redirect_uri": settings.TRUELAYER_REDIRECT_URI,
                "code": code,
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("TrueLayer token exchange failed: %s", exc.response.text)
        raise HTTPException(status_code=502, detail="Token exchange with TrueLayer failed")
    except httpx.RequestError as exc:
        logger.error("TrueLayer token exchange network error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach TrueLayer")

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    # Fetch the first account to store as the linked account_id
    account_id = _fetch_first_account_id(access_token)

    # Upsert: if the user already has an active connection, update it
    existing = (
        db.query(BankConnection)
        .filter(
            BankConnection.user_id == user_id,
            BankConnection.disconnected_at.is_(None),
        )
        .first()
    )
    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.account_id = account_id
        conn = existing
    else:
        conn = BankConnection(user_id=user_id)
        conn.provider = "truelayer-sandbox" if settings.TRUELAYER_SANDBOX else "truelayer"
        conn.access_token = access_token
        conn.refresh_token = refresh_token
        conn.account_id = account_id
        db.add(conn)

    db.commit()
    db.refresh(conn)
    logger.info("BankConnection %s created/updated for user %s", conn.id, user_id)

    frontend_url = f"{settings.FRONTEND_BASE_URL}/#/banking?connected=true"
    return RedirectResponse(url=frontend_url, status_code=302)


def _fetch_first_account_id(access_token: str) -> str:
    """Call TrueLayer /data/v1/accounts and return the first account_id."""
    try:
        resp = httpx.get(
            f"{_api_base()}/data/v1/accounts",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0].get("account_id", "")
    except Exception as exc:
        logger.warning("Could not fetch TrueLayer accounts: %s", exc)
    return ""


# ---------------------------------------------------------------------------
# POST /banking/refresh/{connection_id}
# ---------------------------------------------------------------------------

@router.post("/refresh/{connection_id}", response_model=BankConnectionResponse)
def refresh_connection(
    connection_id: int,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Refresh the access token for a bank connection using the stored refresh
    token.  Called automatically by the sync endpoint when a 401 is received.
    """
    if not _truelayer_configured():
        raise HTTPException(status_code=503, detail="Open banking is not configured")

    user = _require_user(db, current_user)
    conn = (
        db.query(BankConnection)
        .filter(
            BankConnection.id == connection_id,
            BankConnection.user_id == user.id,
            BankConnection.disconnected_at.is_(None),
        )
        .first()
    )
    if not conn:
        raise HTTPException(status_code=404, detail="Bank connection not found")

    if not conn.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token stored for this connection")

    token_url = f"{_auth_base()}/connect/token"
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.TRUELAYER_CLIENT_ID,
                "client_secret": settings.TRUELAYER_CLIENT_SECRET,
                "refresh_token": conn.refresh_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("TrueLayer token refresh failed: %s", exc.response.text)
        raise HTTPException(status_code=502, detail="Token refresh with TrueLayer failed")
    except httpx.RequestError as exc:
        logger.error("TrueLayer refresh network error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach TrueLayer")

    conn.access_token = tokens.get("access_token", conn.access_token)
    if "refresh_token" in tokens:
        conn.refresh_token = tokens["refresh_token"]
    db.commit()
    db.refresh(conn)
    logger.info("Refreshed access token for BankConnection %s", conn.id)
    return _connection_response(conn)


# ---------------------------------------------------------------------------
# GET /banking/connections
# ---------------------------------------------------------------------------

@router.get("/connections", response_model=BankConnectionListResponse)
def list_connections(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return the current user's active (non-disconnected) bank connections."""
    user = _require_user(db, current_user)
    connections = (
        db.query(BankConnection)
        .filter(
            BankConnection.user_id == user.id,
            BankConnection.disconnected_at.is_(None),
        )
        .order_by(BankConnection.created_at.desc())
        .all()
    )
    return BankConnectionListResponse(
        connections=[_connection_response(c) for c in connections]
    )
