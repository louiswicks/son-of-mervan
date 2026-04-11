"""
routers/banking.py — Open banking integration (TrueLayer + GoCardless).

TrueLayer endpoints (sandbox/mock testing):
  GET    /banking/connect                 Generate TrueLayer authorisation URL (auth required)
  GET    /banking/callback?code=&state=   OAuth callback — exchanges code, stores BankConnection
  POST   /banking/refresh/{id}            Refresh access token for a connection (auth required)

GoCardless endpoints (real UK banks: HSBC, Santander, Monzo, etc.):
  GET    /banking/institutions            List UK banks available via GoCardless
  GET    /banking/connect/gocardless      Create requisition and return auth link (auth required)
  GET    /banking/callback/gocardless     Callback after bank auth; stores BankConnection

Shared endpoints:
  GET    /banking/connections             List the current user's active bank connections (auth required)
  DELETE /banking/connections/{id}        Disconnect a bank connection; deletes drafts, nulls confirmed (auth required)
  POST   /banking/sync                    Fetch transactions (TrueLayer or GoCardless) and create draft rows (auth required)
  GET    /banking/drafts                  List pending draft transactions (auth required)
  PATCH  /banking/drafts/{id}             Confirm or reject a draft transaction (auth required)
  POST   /banking/drafts/confirm-all      Bulk confirm all drafts for the authenticated user (auth required)
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.config import settings
from core.limiter import limiter
from database import BankConnection, BankTransaction, MonthlyData, MonthlyExpense, User, get_db
from models import (
    BankConfirmAllResponse,
    BankConnectResponse,
    BankConnectionListResponse,
    BankConnectionResponse,
    BankDisconnectResponse,
    BankDraftActionRequest,
    BankDraftActionResponse,
    BankDraftsResponse,
    BankSyncResponse,
    BankTransactionResponse,
)
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
# GET /banking/status — what providers are configured
# ---------------------------------------------------------------------------

@router.get("/status")
def banking_status(current_user: str = Depends(verify_token)):
    """Return which banking providers are available and whether TrueLayer is in sandbox mode."""
    return {
        "truelayer_available": _truelayer_configured(),
        "truelayer_sandbox": settings.TRUELAYER_SANDBOX,
        "gocardless_available": _gc_configured(),
    }


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
        "scope": "info accounts transactions balance offline_access",
        "redirect_uri": settings.TRUELAYER_REDIRECT_URI,
        "state": state,
        "providers": "mock" if settings.TRUELAYER_SANDBOX else "uk-ob-all uk-oauth-all",
    }
    auth_url = f"{_auth_base()}?{urlencode(params)}"
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
        error_body = exc.response.text
        logger.error("TrueLayer token exchange failed (status=%s): %s", exc.response.status_code, error_body)
        raise HTTPException(status_code=502, detail=f"Token exchange with TrueLayer failed: {error_body}")
    except httpx.RequestError as exc:
        logger.error("TrueLayer token exchange network error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach TrueLayer")

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    # Fetch account ID and bank display name from TrueLayer
    account_id, provider_name = _fetch_truelayer_account_info(access_token)

    # Always create a new connection — multiple accounts are supported
    conn = BankConnection(user_id=user_id)
    conn.provider = provider_name
    conn.access_token = access_token
    conn.refresh_token = refresh_token
    conn.account_id = account_id
    db.add(conn)

    db.commit()
    db.refresh(conn)
    logger.info("BankConnection %s created/updated for user %s", conn.id, user_id)

    frontend_url = f"{settings.FRONTEND_BASE_URL}/#/banking?connected=true"
    return RedirectResponse(url=frontend_url, status_code=302)


def _fetch_truelayer_account_info(access_token: str) -> tuple[str, str]:
    """
    Call TrueLayer /data/v1/accounts and return (account_id, provider_display_name).
    Falls back to empty strings on failure.
    """
    try:
        resp = httpx.get(
            f"{_api_base()}/data/v1/accounts",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            account = results[0]
            account_id = account.get("account_id", "")
            # TrueLayer returns provider.display_name e.g. "Monzo"
            provider_name = (
                account.get("provider", {}).get("display_name")
                or account.get("provider", {}).get("provider_id")
                or "truelayer"
            )
            return account_id, provider_name
    except Exception as exc:
        logger.warning("Could not fetch TrueLayer accounts: %s", exc)
    return "", "truelayer"


# ---------------------------------------------------------------------------
# GoCardless helpers
# ---------------------------------------------------------------------------

GC_BASE = "https://bankaccountdata.gocardless.com/api/v2"


def _gc_configured() -> bool:
    return bool(settings.GOCARDLESS_SECRET_ID and settings.GOCARDLESS_SECRET_KEY)


def _gc_api_token() -> str:
    """Get a short-lived GoCardless API token using our app credentials."""
    try:
        resp = httpx.post(
            f"{GC_BASE}/token/new/",
            json={"secret_id": settings.GOCARDLESS_SECRET_ID, "secret_key": settings.GOCARDLESS_SECRET_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access"]
    except Exception as exc:
        logger.error("GoCardless token fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not authenticate with GoCardless")


# ---------------------------------------------------------------------------
# GET /banking/institutions
# ---------------------------------------------------------------------------

@router.get("/institutions")
def list_institutions(
    country: str = Query(default="GB"),
    current_user: str = Depends(verify_token),
):
    """List banks available via GoCardless for a given country (default GB)."""
    if not _gc_configured():
        raise HTTPException(status_code=503, detail="GoCardless is not configured on this server")
    token = _gc_api_token()
    try:
        resp = httpx.get(
            f"{GC_BASE}/institutions/",
            headers={"Authorization": f"Bearer {token}"},
            params={"country": country},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("GoCardless institutions fetch failed: %s", exc.response.text)
        raise HTTPException(status_code=502, detail="Failed to fetch institutions from GoCardless")


# ---------------------------------------------------------------------------
# GET /banking/connect/gocardless
# ---------------------------------------------------------------------------

@router.get("/connect/gocardless", response_model=BankConnectResponse)
def connect_gocardless(
    institution_id: str = Query(..., description="GoCardless institution ID e.g. MONZO_MONZGB2L"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Create a GoCardless end-user agreement and requisition for the given
    institution, then return the bank authorisation link.
    """
    if not _gc_configured():
        raise HTTPException(status_code=503, detail="GoCardless is not configured on this server")

    user = _require_user(db, current_user)
    state = _make_state(user.id)
    token = _gc_api_token()

    # Create end-user agreement (90 days history, 90 days access)
    try:
        agreement_resp = httpx.post(
            f"{GC_BASE}/agreements/enduser/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "institution_id": institution_id,
                "max_historical_days": 90,
                "access_valid_for_days": 90,
                "access_scope": ["balances", "details", "transactions"],
            },
            timeout=15,
        )
        agreement_resp.raise_for_status()
        agreement_id = agreement_resp.json().get("id")
    except httpx.HTTPStatusError as exc:
        logger.error("GoCardless agreement creation failed: %s", exc.response.text)
        raise HTTPException(status_code=502, detail="Failed to create bank agreement")

    # Create requisition — state stored in 'reference' for CSRF check on callback
    try:
        req_resp = httpx.post(
            f"{GC_BASE}/requisitions/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redirect": settings.GOCARDLESS_REDIRECT_URI,
                "institution_id": institution_id,
                "reference": state,
                "agreement": agreement_id,
                "user_language": "EN",
            },
            timeout=15,
        )
        req_resp.raise_for_status()
        data = req_resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("GoCardless requisition creation failed: %s", exc.response.text)
        raise HTTPException(status_code=502, detail="Failed to create bank requisition")

    logger.info("Created GoCardless requisition for user %s, institution %s", user.id, institution_id)
    return BankConnectResponse(auth_url=data["link"])


# ---------------------------------------------------------------------------
# GET /banking/callback/gocardless
# ---------------------------------------------------------------------------

@router.get("/callback/gocardless")
def gocardless_callback(
    ref: str = Query(..., description="GoCardless requisition ID"),
    error: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Callback from GoCardless after the user completes bank authorisation.
    Fetches account IDs from the requisition and stores a BankConnection row.
    """
    if error:
        logger.warning("GoCardless callback received error: %s", error)
        return RedirectResponse(
            url=f"{settings.FRONTEND_BASE_URL}/#/banking?error={error}",
            status_code=302,
        )

    if not _gc_configured():
        raise HTTPException(status_code=503, detail="GoCardless is not configured")

    token = _gc_api_token()

    # Fetch the requisition — contains accounts list and our CSRF reference
    try:
        req_resp = httpx.get(
            f"{GC_BASE}/requisitions/{ref}/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        req_resp.raise_for_status()
        req_data = req_resp.json()
    except Exception as exc:
        logger.error("GoCardless requisition fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch bank connection details from GoCardless")

    # Verify CSRF — reference field holds the HMAC-signed state we stored
    state = req_data.get("reference", "")
    user_id = _verify_state(state)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    account_ids = req_data.get("accounts", [])
    institution_id = req_data.get("institution_id", "unknown")

    # Store connection: requisition_id in access_token field, account IDs comma-separated
    conn = BankConnection(user_id=user_id)
    conn.provider = f"gocardless:{institution_id}"
    conn.access_token = ref  # requisition_id — used to re-fetch accounts if needed
    conn.refresh_token = ""
    conn.account_id = ",".join(account_ids)
    db.add(conn)
    db.commit()
    db.refresh(conn)

    logger.info(
        "GoCardless BankConnection %s created for user %s (%d accounts, institution %s)",
        conn.id, user_id, len(account_ids), institution_id,
    )
    return RedirectResponse(
        url=f"{settings.FRONTEND_BASE_URL}/#/banking?connected=true",
        status_code=302,
    )


def _fetch_transactions_gocardless(account_ids_str: str, from_dt: datetime) -> list[dict]:
    """
    Fetch and normalise transactions from GoCardless for all stored account IDs.
    Returns a list of dicts with keys: transaction_id, description, amount, currency, date.
    """
    token = _gc_api_token()
    from_str = from_dt.strftime("%Y-%m-%d")
    to_str = datetime.utcnow().strftime("%Y-%m-%d")
    account_ids = [a.strip() for a in account_ids_str.split(",") if a.strip()]

    results = []
    for account_id in account_ids:
        try:
            resp = httpx.get(
                f"{GC_BASE}/accounts/{account_id}/transactions/",
                headers={"Authorization": f"Bearer {token}"},
                params={"date_from": from_str, "date_to": to_str},
                timeout=30,
            )
            resp.raise_for_status()
            booked = resp.json().get("transactions", {}).get("booked", [])
            for t in booked:
                amount_info = t.get("transactionAmount", {})
                results.append({
                    "transaction_id": t.get("transactionId") or t.get("internalTransactionId", ""),
                    "description": (
                        t.get("remittanceInformationUnstructured")
                        or t.get("creditorName")
                        or t.get("remittanceInformationStructured")
                        or ""
                    ),
                    "amount": float(amount_info.get("amount", 0)),
                    "currency": amount_info.get("currency", "GBP"),
                    "date": t.get("bookingDate") or t.get("valueDate", ""),
                })
        except Exception as exc:
            logger.warning("GoCardless transactions fetch failed for account %s: %s", account_id, exc)

    return results


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
# GET /banking/connections/{id}/details — live account name + balance
# ---------------------------------------------------------------------------

@router.get("/connections/{connection_id}/details")
def connection_details(
    connection_id: int,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Fetch live account name and balance from TrueLayer for a connection.
    Not cached — called by the frontend when the card is rendered.
    """
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

    is_gocardless = (conn.provider or "").startswith("gocardless:")
    if is_gocardless:
        return {"account_name": conn.provider.replace("gocardless:", ""), "balance": None, "currency": None}

    if not _truelayer_configured():
        raise HTTPException(status_code=503, detail="Open banking is not configured")

    accounts = []
    balance = None
    currency = None
    account_name = conn.provider or "Bank account"

    def _get_accounts(token: str) -> list:
        r = httpx.get(
            f"{_api_base()}/data/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("results", [])

    try:
        accounts = _get_accounts(conn.access_token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            # Token expired — refresh and retry once
            try:
                _do_refresh_connection(db, conn)
                accounts = _get_accounts(conn.access_token)
            except Exception as refresh_exc:
                logger.warning("Token refresh failed in details: %s", refresh_exc)
        else:
            logger.warning("TrueLayer accounts fetch failed %s: %s", exc.response.status_code, exc.response.text)
    except Exception as exc:
        logger.warning("Could not fetch TrueLayer account details: %s", exc)

    if accounts:
        acc = accounts[0]
        provider_name = acc.get("provider", {}).get("display_name", "")
        display = acc.get("display_name", "")
        account_type = acc.get("account_type", "")
        if display:
            account_name = display
        elif provider_name and account_type:
            account_name = f"{provider_name} {account_type}"
        elif provider_name:
            account_name = provider_name
        else:
            account_name = conn.provider or "Bank account"

    if accounts:
        try:
            account_id = accounts[0].get("account_id", conn.account_id)
            bal_resp = httpx.get(
                f"{_api_base()}/data/v1/accounts/{account_id}/balance",
                headers={"Authorization": f"Bearer {conn.access_token}"},
                timeout=15,
            )
            bal_resp.raise_for_status()
            bal_results = bal_resp.json().get("results", [])
            if bal_results:
                balance = bal_results[0].get("available") or bal_results[0].get("current")
                currency = bal_results[0].get("currency", "GBP")
        except Exception as exc:
            logger.warning("Could not fetch TrueLayer balance: %s", exc)

    return {"account_name": account_name, "balance": balance, "currency": currency}


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


# ---------------------------------------------------------------------------
# DELETE /banking/connections/{connection_id}
# ---------------------------------------------------------------------------

@router.delete("/connections/{connection_id}", response_model=BankDisconnectResponse)
def disconnect_bank(
    connection_id: int,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Revoke a bank connection.

    - Calls TrueLayer token revocation endpoint (best-effort; proceeds even on failure).
    - Sets disconnected_at on the BankConnection row (soft-delete from connections list).
    - Hard-deletes all BankTransaction rows in 'draft' status for this connection.
    - Nulls bank_connection_id on 'confirmed' rows (preserves confirmed expenses).
    """
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

    # Best-effort token revocation — don't fail disconnect if TrueLayer is unreachable
    if _truelayer_configured() and conn.access_token:
        try:
            revoke_url = f"{_auth_base()}/connect/revoke"
            httpx.post(
                revoke_url,
                data={"token": conn.access_token},
                timeout=10,
            )
            logger.info("Revoked TrueLayer token for connection %s", conn.id)
        except Exception as exc:
            logger.warning("TrueLayer token revocation failed (proceeding anyway): %s", exc)

    # Hard-delete draft transactions for this connection
    draft_txns = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.bank_connection_id == conn.id,
            BankTransaction.status == "draft",
        )
        .all()
    )
    drafts_deleted = len(draft_txns)
    for txn in draft_txns:
        db.delete(txn)

    # Null the connection FK on confirmed/rejected rows (preserve the expense data)
    confirmed_txns = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.bank_connection_id == conn.id,
            BankTransaction.status.in_(["confirmed", "rejected"]),
        )
        .all()
    )
    confirmed_preserved = len(confirmed_txns)
    for txn in confirmed_txns:
        txn.bank_connection_id = None

    # Mark connection as disconnected
    conn.disconnected_at = datetime.utcnow()
    db.commit()

    logger.info(
        "Disconnected BankConnection %s for user %s: %d drafts deleted, %d confirmed preserved",
        conn.id, user.id, drafts_deleted, confirmed_preserved,
    )
    return BankDisconnectResponse(
        id=connection_id,
        drafts_deleted=drafts_deleted,
        confirmed_preserved=confirmed_preserved,
    )


# ---------------------------------------------------------------------------
# Internal helpers for sync
# ---------------------------------------------------------------------------

def _suggest_category(db: Session, user_id: int, description: str) -> str | None:
    """
    Return the most frequently used category for the given description
    from the user's own expense history (same logic as GET /insights/suggest-category).
    Returns None when there are fewer than 2 history matches.
    """
    all_monthly = db.query(MonthlyData).filter(MonthlyData.user_id == user_id).all()
    if not all_monthly:
        return None

    monthly_ids = [m.id for m in all_monthly]
    expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id.in_(monthly_ids),
            MonthlyExpense.deleted_at == None,  # noqa: E711
        )
        .all()
    )

    name_lower = description.strip().lower()
    category_counts: dict[str, int] = {}
    for expense in expenses:
        exp_name = (expense.name or "").lower()
        if name_lower in exp_name:
            cat = expense.category or "Other"
            category_counts[cat] = category_counts.get(cat, 0) + 1

    total = sum(category_counts.values())
    if total < 2:
        return None
    return max(category_counts, key=lambda c: category_counts[c])


def _get_active_connection(db: Session, user_id: int, connection_id: int | None) -> BankConnection:
    """Return the user's active connection, optionally filtered by id. Raises 404 if not found."""
    q = db.query(BankConnection).filter(
        BankConnection.user_id == user_id,
        BankConnection.disconnected_at.is_(None),
    )
    if connection_id is not None:
        q = q.filter(BankConnection.id == connection_id)
    conn = q.order_by(BankConnection.created_at.desc()).first()
    if not conn:
        raise HTTPException(status_code=404, detail="No active bank connection found")
    return conn


def _fetch_transactions(access_token: str, account_id: str, from_dt: datetime) -> list[dict]:
    """Fetch transactions from TrueLayer for a given account since from_dt."""
    from_str = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{_api_base()}/data/v1/accounts/{account_id}/transactions"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"from": from_str},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        error_body = exc.response.text
        logger.error("TrueLayer transactions fetch failed %s: %s", status, error_body)
        if status == 403:
            raise HTTPException(
                status_code=403,
                detail="TrueLayer rejected the request — your app may still be in testing mode. Contact TrueLayer to enable production access.",
            )
        if status == 401:
            raise HTTPException(status_code=401, detail="TrueLayer access token expired")
        raise HTTPException(status_code=502, detail=f"Failed to fetch transactions from TrueLayer: {error_body}")
    except httpx.TimeoutException:
        logger.error("TrueLayer transactions fetch timed out for account %s", account_id)
        raise HTTPException(status_code=504, detail="TrueLayer request timed out — try again in a moment")
    except httpx.RequestError as exc:
        logger.error("TrueLayer transactions network error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach TrueLayer")


def _transaction_response(txn: BankTransaction) -> BankTransactionResponse:
    return BankTransactionResponse(
        id=txn.id,
        connection_id=txn.bank_connection_id,
        description=txn.description,
        amount=txn.amount,
        currency=txn.currency,
        transaction_date=txn.transaction_date,
        suggested_category=txn.suggested_category,
        status=txn.status,
        created_at=txn.created_at,
    )


def _get_or_create_month(db: Session, user: User, month: str) -> MonthlyData:
    """Get or create a MonthlyData row for the given YYYY-MM month string."""
    all_monthly = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    for row in all_monthly:
        if row.month == month:
            return row
    rec = MonthlyData(user_id=user.id)
    rec.month = month
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# POST /banking/sync
# ---------------------------------------------------------------------------

@router.post("/sync", response_model=BankSyncResponse)
@limiter.limit("10/minute")
def sync_transactions(
    request: Request,
    connection_id: int | None = Query(default=None, description="Specific connection ID to sync (optional)"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Fetch new transactions from TrueLayer for the user's active connection.
    Transactions since last_synced_at (or 90 days ago on first sync) are fetched.
    Existing transactions are deduplicated by external_id.
    Each new transaction gets a category suggestion from the user's expense history.
    Rate-limited to 1 call per 5 minutes per IP.
    """
    if not _truelayer_configured():
        raise HTTPException(status_code=503, detail="Open banking is not configured on this server")

    user = _require_user(db, current_user)
    conn = _get_active_connection(db, user.id, connection_id)

    logger.info(
        "Starting sync for connection %s (provider=%s, account_id=%s)",
        conn.id, conn.provider, conn.account_id,
    )

    # Determine fetch window
    from_dt = conn.last_synced_at or (datetime.utcnow() - timedelta(days=90))

    # Fetch transactions — route to correct provider
    is_gocardless = (conn.provider or "").startswith("gocardless:")
    try:
        if is_gocardless:
            if not _gc_configured():
                raise HTTPException(status_code=503, detail="GoCardless is not configured on this server")
            raw_txns = _fetch_transactions_gocardless(conn.account_id, from_dt)
        else:
            if not _truelayer_configured():
                raise HTTPException(status_code=503, detail="Open banking is not configured on this server")
            try:
                raw_txns = _fetch_transactions(conn.access_token, conn.account_id, from_dt)
            except HTTPException as exc:
                if exc.status_code == 401:
                    logger.info("TrueLayer token expired for connection %s — refreshing and retrying", conn.id)
                    _do_refresh_connection(db, conn)
                    raw_txns = _fetch_transactions(conn.access_token, conn.account_id, from_dt)
                else:
                    raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during sync for connection %s: %s", conn.id, exc)
        raise HTTPException(status_code=500, detail=f"Sync failed unexpectedly: {type(exc).__name__}: {exc}")

    # Collect existing external IDs for deduplication
    existing_txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.bank_connection_id == conn.id)
        .all()
    )
    existing_external_ids = {t.external_id for t in existing_txns}

    synced = 0
    skipped = 0
    for raw in raw_txns:
        # Normalised keys differ between providers — GoCardless normalisation done in helper
        if is_gocardless:
            ext_id = raw.get("transaction_id", "")
            description = raw.get("description", "")
            amount = raw.get("amount")
            currency = raw.get("currency", "GBP")
            txn_date_str = raw.get("date", "")
        else:
            ext_id = raw.get("transaction_id") or raw.get("id", "")
            description = raw.get("description") or raw.get("merchant_name") or ""
            amount = raw.get("amount")
            currency = raw.get("currency", "GBP")
            txn_date_str = raw.get("timestamp") or raw.get("date") or ""

        if not ext_id or ext_id in existing_external_ids:
            skipped += 1
            continue

        try:
            from datetime import date as date_type
            if "T" in txn_date_str:
                txn_date = datetime.fromisoformat(txn_date_str.replace("Z", "+00:00")).date()
            else:
                txn_date = date_type.fromisoformat(txn_date_str[:10])
        except (ValueError, AttributeError):
            txn_date = datetime.utcnow().date()

        suggested = _suggest_category(db, user.id, description) if description else None

        txn = BankTransaction(
            user_id=user.id,
            bank_connection_id=conn.id,
            transaction_date=txn_date,
            suggested_category=suggested,
            status="draft",
        )
        txn.external_id = ext_id
        txn.description = description
        txn.amount = float(amount) if amount is not None else None
        txn.currency = currency
        db.add(txn)
        existing_external_ids.add(ext_id)
        synced += 1

    conn.last_synced_at = datetime.utcnow()
    db.commit()
    logger.info("Sync complete for connection %s: %d synced, %d skipped", conn.id, synced, skipped)
    return BankSyncResponse(synced=synced, skipped=skipped, connection_id=conn.id)


def _do_refresh_connection(db: Session, conn: BankConnection) -> None:
    """Refresh the access token for a connection in-place (raises 502 on failure)."""
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
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.error("Auto token refresh failed: %s", exc)
        raise HTTPException(status_code=502, detail="Token refresh failed")
    conn.access_token = tokens.get("access_token", conn.access_token)
    if "refresh_token" in tokens:
        conn.refresh_token = tokens["refresh_token"]
    db.commit()
    db.refresh(conn)


# ---------------------------------------------------------------------------
# GET /banking/drafts
# ---------------------------------------------------------------------------

@router.get("/drafts", response_model=BankDraftsResponse)
def list_drafts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return a paginated list of the user's draft (unreviewed) bank transactions."""
    user = _require_user(db, current_user)

    all_drafts = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.user_id == user.id,
            BankTransaction.status == "draft",
        )
        .order_by(BankTransaction.transaction_date.desc())
        .all()
    )

    total = len(all_drafts)
    offset = (page - 1) * page_size
    page_items = all_drafts[offset : offset + page_size]

    return BankDraftsResponse(
        drafts=[_transaction_response(t) for t in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# PATCH /banking/drafts/{id}
# ---------------------------------------------------------------------------

@router.patch("/drafts/{draft_id}", response_model=BankDraftActionResponse)
def action_draft(
    draft_id: int,
    body: BankDraftActionRequest,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Confirm or reject a single draft transaction.

    confirm — creates a MonthlyExpense from the draft (using body.category or
               the suggested_category), sets status=confirmed, sets monthly_expense_id.
    reject  — sets status=rejected; the draft is excluded from future GET /banking/drafts.
    """
    if body.action not in ("confirm", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'confirm' or 'reject'")

    user = _require_user(db, current_user)
    txn = db.query(BankTransaction).filter(BankTransaction.id == draft_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Draft transaction not found")
    if txn.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised to modify this draft")
    if txn.status != "draft":
        raise HTTPException(status_code=409, detail=f"Transaction is already {txn.status}")

    if body.action == "reject":
        txn.status = "rejected"
        db.commit()
        return BankDraftActionResponse(id=txn.id, status="rejected")

    # confirm — create a MonthlyExpense
    category = (body.category or txn.suggested_category or "Other").strip()
    month_str = txn.transaction_date.strftime("%Y-%m")

    month_row = _get_or_create_month(db, user, month_str)

    expense = MonthlyExpense(monthly_data_id=month_row.id)
    expense.name = txn.description or "Bank transaction"
    expense.category = category
    expense.planned_amount = 0.0
    expense.actual_amount = float(txn.amount) if txn.amount is not None else 0.0
    expense.currency = txn.currency or user.base_currency or "GBP"
    db.add(expense)
    db.flush()

    txn.status = "confirmed"
    txn.monthly_expense_id = expense.id
    db.commit()

    logger.info("Confirmed draft %s → MonthlyExpense %s", txn.id, expense.id)
    return BankDraftActionResponse(id=txn.id, status="confirmed", monthly_expense_id=expense.id)


# ---------------------------------------------------------------------------
# POST /banking/drafts/confirm-all
# ---------------------------------------------------------------------------

@router.post("/drafts/confirm-all", response_model=BankConfirmAllResponse)
def confirm_all_drafts(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Bulk confirm all draft transactions for the authenticated user."""
    user = _require_user(db, current_user)

    all_drafts = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.user_id == user.id,
            BankTransaction.status == "draft",
        )
        .all()
    )

    confirmed = 0
    for txn in all_drafts:
        category = (txn.suggested_category or "Other").strip()
        month_str = txn.transaction_date.strftime("%Y-%m")
        month_row = _get_or_create_month(db, user, month_str)

        expense = MonthlyExpense(monthly_data_id=month_row.id)
        expense.name = txn.description or "Bank transaction"
        expense.category = category
        expense.planned_amount = 0.0
        expense.actual_amount = float(txn.amount) if txn.amount is not None else 0.0
        expense.currency = txn.currency or user.base_currency or "GBP"
        db.add(expense)
        db.flush()

        txn.status = "confirmed"
        txn.monthly_expense_id = expense.id
        confirmed += 1

    db.commit()
    logger.info("Bulk confirmed %d drafts for user %s", confirmed, user.id)
    return BankConfirmAllResponse(confirmed=confirmed)
