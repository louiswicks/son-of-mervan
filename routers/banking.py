"""
routers/banking.py — TrueLayer open banking OAuth integration.

Endpoints:
  GET  /banking/connect                 Generate TrueLayer authorisation URL (auth required)
  GET  /banking/callback?code=&state=   OAuth callback — exchanges code, stores BankConnection
  POST /banking/refresh/{id}            Refresh access token for a connection (auth required)
  GET  /banking/connections             List the current user's active bank connections (auth required)
  POST /banking/sync                    Fetch transactions from TrueLayer and create draft rows (auth required)
  GET  /banking/drafts                  List pending draft transactions (auth required)
  PATCH /banking/drafts/{id}            Confirm or reject a draft transaction (auth required)
  POST /banking/drafts/confirm-all      Bulk confirm all drafts for the authenticated user (auth required)
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
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except httpx.HTTPStatusError as exc:
        logger.error("TrueLayer transactions fetch failed %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail="Failed to fetch transactions from TrueLayer")
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
@limiter.limit("1/5 minute")
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

    # Determine fetch window
    from_dt = conn.last_synced_at or (datetime.utcnow() - timedelta(days=90))

    # Fetch transactions — auto-refresh token on 401
    try:
        raw_txns = _fetch_transactions(conn.access_token, conn.account_id, from_dt)
    except HTTPException as exc:
        if exc.status_code == 502:
            # Try refreshing the token and retrying once
            logger.info("Refreshing token for connection %s and retrying sync", conn.id)
            _do_refresh_connection(db, conn)
            raw_txns = _fetch_transactions(conn.access_token, conn.account_id, from_dt)
        else:
            raise

    # Collect existing external IDs for deduplication (decrypt all rows for this connection)
    existing_txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.bank_connection_id == conn.id)
        .all()
    )
    existing_external_ids = {t.external_id for t in existing_txns}

    synced = 0
    skipped = 0
    for raw in raw_txns:
        ext_id = raw.get("transaction_id") or raw.get("id", "")
        if not ext_id or ext_id in existing_external_ids:
            skipped += 1
            continue

        description = raw.get("description") or raw.get("merchant_name") or ""
        amount = raw.get("amount")
        currency = raw.get("currency", "GBP")
        txn_date_str = raw.get("timestamp") or raw.get("date") or ""
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
