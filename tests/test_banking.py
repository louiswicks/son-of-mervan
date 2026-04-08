"""
Tests for the open banking OAuth flow (Phase 15.2) and transaction sync (Phase 15.3).

Coverage targets:
  routers/banking.py — GET /banking/connect
                        GET /banking/callback
                        POST /banking/refresh/{id}
                        GET /banking/connections
                        POST /banking/sync
                        GET /banking/drafts
                        PATCH /banking/drafts/{id}
                        POST /banking/drafts/confirm-all
"""
import hashlib
import hmac
import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from database import BankConnection, BankTransaction, MonthlyExpense
from tests.conftest import TEST_EMAIL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(user_id: int, secret: str = "test-jwt-secret-for-pytest-not-for-production") -> str:
    """Mirror _make_state from routers/banking.py with a fixed nonce for tests."""
    nonce = "deadbeef" * 4  # 32 hex chars
    payload = f"{user_id}.{nonce}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _make_connection(db, user, access_token="tok_access", refresh_token="tok_refresh",
                     account_id="acc_123", provider="truelayer-sandbox"):
    conn = BankConnection(user_id=user.id)
    conn.provider = provider
    conn.access_token = access_token
    conn.refresh_token = refresh_token
    conn.account_id = account_id
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


# ---------------------------------------------------------------------------
# GET /banking/connect
# ---------------------------------------------------------------------------

class TestConnect:
    def test_returns_503_when_not_configured(self, auth_client):
        """Returns 503 when TrueLayer credentials are absent."""
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = ""
            mock_settings.TRUELAYER_CLIENT_SECRET = ""
            mock_settings.TRUELAYER_SANDBOX = True
            r = auth_client.get("/banking/connect")
        assert r.status_code == 503

    def test_returns_auth_url_when_configured(self, auth_client):
        """Returns a TrueLayer auth URL when credentials are configured."""
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.TRUELAYER_REDIRECT_URI = "http://localhost:8000/banking/callback"
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            r = auth_client.get("/banking/connect")
        assert r.status_code == 200
        body = r.json()
        assert "auth_url" in body
        assert "truelayer-sandbox.com" in body["auth_url"]
        assert "sandbox-client-id" in body["auth_url"]
        assert "state=" in body["auth_url"]

    def test_auth_url_contains_required_scopes(self, auth_client):
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.TRUELAYER_REDIRECT_URI = "http://localhost:8000/banking/callback"
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            r = auth_client.get("/banking/connect")
        assert r.status_code == 200
        url = r.json()["auth_url"]
        assert "accounts" in url
        assert "transactions" in url
        assert "balance" in url

    def test_unauthenticated_returns_4xx(self, client):
        r = client.get("/banking/connect")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /banking/callback
# ---------------------------------------------------------------------------

class TestCallback:
    def _mock_token_response(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
        }
        return mock_resp

    def _mock_accounts_response(self, account_id="acc_abc123"):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"account_id": account_id}]
        }
        return mock_resp

    def test_creates_bank_connection_on_valid_callback(self, client, db, verified_user):
        state = _make_state(verified_user.id)
        token_resp = self._mock_token_response()
        accounts_resp = self._mock_accounts_response()

        with patch("routers.banking.settings") as mock_settings, \
             patch("httpx.post", return_value=token_resp), \
             patch("httpx.get", return_value=accounts_resp):
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.TRUELAYER_REDIRECT_URI = "http://localhost:8000/banking/callback"
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            mock_settings.FRONTEND_BASE_URL = "http://localhost:3000"
            r = client.get(
                f"/banking/callback?code=authcode&state={state}",
                follow_redirects=False,
            )

        # Should redirect to frontend
        assert r.status_code in (302, 307)
        assert "connected=true" in r.headers.get("location", "")

        # BankConnection row must be created
        conn = db.query(BankConnection).filter(BankConnection.user_id == verified_user.id).first()
        assert conn is not None
        assert conn.account_id == "acc_abc123"
        # Token fields are stored encrypted — decrypting via hybrid property
        assert conn.access_token == "new_access_token"
        assert conn.refresh_token == "new_refresh_token"

    def test_invalid_state_returns_400(self, client, db, verified_user):
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            r = client.get(
                "/banking/callback?code=authcode&state=invalid.state.token",
                follow_redirects=False,
            )
        assert r.status_code in (400, 422)

    def test_missing_state_returns_422(self, client):
        r = client.get("/banking/callback?code=authcode", follow_redirects=False)
        assert r.status_code == 422

    def test_missing_code_returns_422(self, client):
        r = client.get("/banking/callback?state=somestate", follow_redirects=False)
        assert r.status_code == 422

    def test_token_exchange_failure_returns_502(self, client, db, verified_user):
        import httpx as _httpx

        state = _make_state(verified_user.id)
        with patch("routers.banking.settings") as mock_settings, \
             patch("httpx.post", side_effect=_httpx.RequestError("timeout")):
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.TRUELAYER_REDIRECT_URI = "http://localhost:8000/banking/callback"
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            r = client.get(
                f"/banking/callback?code=authcode&state={state}",
                follow_redirects=False,
            )
        assert r.status_code == 502

    def test_503_when_not_configured(self, client, db, verified_user):
        state = _make_state(verified_user.id)
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = ""
            mock_settings.TRUELAYER_CLIENT_SECRET = ""
            r = client.get(
                f"/banking/callback?code=authcode&state={state}",
                follow_redirects=False,
            )
        assert r.status_code == 503

    def test_second_callback_updates_existing_connection(self, client, db, verified_user):
        """A second callback upserts instead of creating a duplicate connection."""
        _make_connection(db, verified_user, access_token="old_token")
        state = _make_state(verified_user.id)
        token_resp = self._mock_token_response()
        accounts_resp = self._mock_accounts_response(account_id="acc_new")

        with patch("routers.banking.settings") as mock_settings, \
             patch("httpx.post", return_value=token_resp), \
             patch("httpx.get", return_value=accounts_resp):
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.TRUELAYER_REDIRECT_URI = "http://localhost:8000/banking/callback"
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            mock_settings.FRONTEND_BASE_URL = "http://localhost:3000"
            client.get(
                f"/banking/callback?code=authcode&state={state}",
                follow_redirects=False,
            )

        connections = db.query(BankConnection).filter(BankConnection.user_id == verified_user.id).all()
        assert len(connections) == 1  # upserted, not duplicated
        assert connections[0].access_token == "new_access_token"


# ---------------------------------------------------------------------------
# POST /banking/refresh/{id}
# ---------------------------------------------------------------------------

class TestRefreshConnection:
    def test_refreshes_token_successfully(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user, refresh_token="old_refresh")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "refreshed_access",
            "refresh_token": "refreshed_refresh",
        }

        with patch("routers.banking.settings") as mock_settings, \
             patch("httpx.post", return_value=mock_resp):
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            mock_settings.JWT_SECRET_KEY = "test-jwt-secret-for-pytest-not-for-production"
            r = auth_client.post(f"/banking/refresh/{conn.id}")

        assert r.status_code == 200
        db.refresh(conn)
        assert conn.access_token == "refreshed_access"
        assert conn.refresh_token == "refreshed_refresh"

    def test_refresh_not_found_returns_404(self, auth_client):
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            r = auth_client.post("/banking/refresh/99999")
        assert r.status_code == 404

    def test_refresh_other_users_connection_returns_404(
        self, auth_client, db, second_user
    ):
        conn = _make_connection(db, second_user)
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = "sandbox-client-id"
            mock_settings.TRUELAYER_CLIENT_SECRET = "sandbox-secret"
            mock_settings.TRUELAYER_SANDBOX = True
            r = auth_client.post(f"/banking/refresh/{conn.id}")
        assert r.status_code == 404

    def test_refresh_503_when_not_configured(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        with patch("routers.banking.settings") as mock_settings:
            mock_settings.TRUELAYER_CLIENT_ID = ""
            mock_settings.TRUELAYER_CLIENT_SECRET = ""
            r = auth_client.post(f"/banking/refresh/{conn.id}")
        assert r.status_code == 503

    def test_unauthenticated_returns_4xx(self, client, db, verified_user):
        conn = _make_connection(db, verified_user)
        r = client.post(f"/banking/refresh/{conn.id}")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /banking/connections
# ---------------------------------------------------------------------------

class TestListConnections:
    def test_returns_empty_list_when_none(self, auth_client):
        r = auth_client.get("/banking/connections")
        assert r.status_code == 200
        assert r.json()["connections"] == []

    def test_returns_active_connection(self, auth_client, db, verified_user):
        _make_connection(db, verified_user, account_id="acc_xyz")
        r = auth_client.get("/banking/connections")
        assert r.status_code == 200
        conns = r.json()["connections"]
        assert len(conns) == 1
        assert conns[0]["account_id"] == "acc_xyz"
        assert conns[0]["provider"] == "truelayer-sandbox"

    def test_excludes_disconnected_connections(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        conn.disconnected_at = datetime.utcnow()
        db.commit()
        r = auth_client.get("/banking/connections")
        assert r.status_code == 200
        assert r.json()["connections"] == []

    def test_does_not_expose_tokens(self, auth_client, db, verified_user):
        _make_connection(db, verified_user)
        r = auth_client.get("/banking/connections")
        body = r.json()
        conn_json = body["connections"][0]
        # No token fields should appear in the response
        assert "access_token" not in conn_json
        assert "refresh_token" not in conn_json

    def test_unauthenticated_returns_4xx(self, client):
        r = client.get("/banking/connections")
        assert r.status_code in (401, 403)

    def test_only_returns_own_connections(self, auth_client, db, second_user):
        _make_connection(db, second_user, account_id="other_acc")
        r = auth_client.get("/banking/connections")
        assert r.status_code == 200
        assert r.json()["connections"] == []


# ---------------------------------------------------------------------------
# Phase 15.3 helpers
# ---------------------------------------------------------------------------

def _make_transaction(db, user, conn, external_id="ext_001", description="Tesco",
                      amount=15.50, currency="GBP", txn_date=None, status="draft",
                      suggested_category=None):
    txn = BankTransaction(
        user_id=user.id,
        bank_connection_id=conn.id,
        transaction_date=txn_date or date(2026, 4, 1),
        suggested_category=suggested_category,
        status=status,
    )
    txn.external_id = external_id
    txn.description = description
    txn.amount = amount
    txn.currency = currency
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def _mock_truelayer_transactions(txns: list[dict]):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"results": txns}
    return mock_resp


_SAMPLE_TXN = {
    "transaction_id": "txn_abc123",
    "description": "TESCO STORES",
    "amount": -12.50,
    "currency": "GBP",
    "timestamp": "2026-04-01T10:00:00Z",
}


# ---------------------------------------------------------------------------
# POST /banking/sync
# ---------------------------------------------------------------------------

class TestSync:
    def test_sync_creates_draft_transactions(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        mock_resp = _mock_truelayer_transactions([_SAMPLE_TXN])

        with patch("routers.banking.settings") as ms, \
             patch("httpx.get", return_value=mock_resp):
            ms.TRUELAYER_CLIENT_ID = "cid"
            ms.TRUELAYER_CLIENT_SECRET = "secret"
            ms.TRUELAYER_SANDBOX = True
            r = auth_client.post("/banking/sync")

        assert r.status_code == 200
        body = r.json()
        assert body["synced"] == 1
        assert body["skipped"] == 0
        assert body["connection_id"] == conn.id

        txns = db.query(BankTransaction).filter(BankTransaction.user_id == verified_user.id).all()
        assert len(txns) == 1
        assert txns[0].status == "draft"
        assert txns[0].description == "TESCO STORES"

    def test_sync_deduplicates_existing_external_id(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        _make_transaction(db, verified_user, conn, external_id="txn_abc123")
        mock_resp = _mock_truelayer_transactions([_SAMPLE_TXN])

        with patch("routers.banking.settings") as ms, \
             patch("httpx.get", return_value=mock_resp):
            ms.TRUELAYER_CLIENT_ID = "cid"
            ms.TRUELAYER_CLIENT_SECRET = "secret"
            ms.TRUELAYER_SANDBOX = True
            r = auth_client.post("/banking/sync")

        assert r.status_code == 200
        body = r.json()
        assert body["synced"] == 0
        assert body["skipped"] == 1

    def test_sync_updates_last_synced_at(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        assert conn.last_synced_at is None
        mock_resp = _mock_truelayer_transactions([])

        with patch("routers.banking.settings") as ms, \
             patch("httpx.get", return_value=mock_resp):
            ms.TRUELAYER_CLIENT_ID = "cid"
            ms.TRUELAYER_CLIENT_SECRET = "secret"
            ms.TRUELAYER_SANDBOX = True
            r = auth_client.post("/banking/sync")

        assert r.status_code == 200
        db.refresh(conn)
        assert conn.last_synced_at is not None

    def test_sync_503_when_not_configured(self, auth_client):
        with patch("routers.banking.settings") as ms:
            ms.TRUELAYER_CLIENT_ID = ""
            ms.TRUELAYER_CLIENT_SECRET = ""
            r = auth_client.post("/banking/sync")
        assert r.status_code == 503

    def test_sync_404_when_no_active_connection(self, auth_client):
        with patch("routers.banking.settings") as ms:
            ms.TRUELAYER_CLIENT_ID = "cid"
            ms.TRUELAYER_CLIENT_SECRET = "secret"
            ms.TRUELAYER_SANDBOX = True
            r = auth_client.post("/banking/sync")
        assert r.status_code == 404

    def test_sync_unauthenticated_returns_4xx(self, client):
        r = client.post("/banking/sync")
        assert r.status_code in (401, 403)

    def test_sync_handles_date_without_timestamp(self, auth_client, db, verified_user):
        _make_connection(db, verified_user)
        txn_with_date = {**_SAMPLE_TXN, "transaction_id": "txn_date_only",
                         "timestamp": None, "date": "2026-04-02"}
        mock_resp = _mock_truelayer_transactions([txn_with_date])

        with patch("routers.banking.settings") as ms, \
             patch("httpx.get", return_value=mock_resp):
            ms.TRUELAYER_CLIENT_ID = "cid"
            ms.TRUELAYER_CLIENT_SECRET = "secret"
            ms.TRUELAYER_SANDBOX = True
            r = auth_client.post("/banking/sync")

        assert r.status_code == 200
        txns = db.query(BankTransaction).filter(BankTransaction.user_id == verified_user.id).all()
        assert len(txns) == 1
        assert txns[0].transaction_date == date(2026, 4, 2)


# ---------------------------------------------------------------------------
# GET /banking/drafts
# ---------------------------------------------------------------------------

class TestListDrafts:
    def test_returns_empty_when_no_drafts(self, auth_client):
        r = auth_client.get("/banking/drafts")
        assert r.status_code == 200
        body = r.json()
        assert body["drafts"] == []
        assert body["total"] == 0

    def test_returns_draft_transactions(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        _make_transaction(db, verified_user, conn, external_id="e1", description="Sainsbury's")
        _make_transaction(db, verified_user, conn, external_id="e2", description="Costa Coffee")
        r = auth_client.get("/banking/drafts")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["drafts"]) == 2

    def test_excludes_confirmed_and_rejected(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        _make_transaction(db, verified_user, conn, external_id="e_draft", status="draft")
        _make_transaction(db, verified_user, conn, external_id="e_conf", status="confirmed")
        _make_transaction(db, verified_user, conn, external_id="e_rej", status="rejected")
        r = auth_client.get("/banking/drafts")
        body = r.json()
        assert body["total"] == 1
        assert body["drafts"][0]["status"] == "draft"

    def test_pagination(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        for i in range(5):
            _make_transaction(db, verified_user, conn, external_id=f"e_{i}")
        r = auth_client.get("/banking/drafts?page=1&page_size=3")
        body = r.json()
        assert body["total"] == 5
        assert len(body["drafts"]) == 3
        r2 = auth_client.get("/banking/drafts?page=2&page_size=3")
        body2 = r2.json()
        assert len(body2["drafts"]) == 2

    def test_does_not_return_other_users_drafts(self, auth_client, db, second_user):
        conn2 = _make_connection(db, second_user)
        _make_transaction(db, second_user, conn2, external_id="other_txn")
        r = auth_client.get("/banking/drafts")
        body = r.json()
        assert body["total"] == 0

    def test_unauthenticated_returns_4xx(self, client):
        r = client.get("/banking/drafts")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /banking/drafts/{id}
# ---------------------------------------------------------------------------

class TestActionDraft:
    def test_reject_sets_status_to_rejected(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1")
        r = auth_client.patch(f"/banking/drafts/{txn.id}", json={"action": "reject"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "rejected"
        db.refresh(txn)
        assert txn.status == "rejected"

    def test_confirm_creates_monthly_expense(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1",
                                 description="Tesco", amount=12.50, currency="GBP",
                                 suggested_category="Groceries")
        r = auth_client.patch(f"/banking/drafts/{txn.id}", json={"action": "confirm"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "confirmed"
        assert body["monthly_expense_id"] is not None

        expense = db.query(MonthlyExpense).filter(
            MonthlyExpense.id == body["monthly_expense_id"]
        ).first()
        assert expense is not None
        assert expense.name == "Tesco"
        assert expense.category == "Groceries"
        assert expense.actual_amount == 12.50
        assert expense.currency == "GBP"

    def test_confirm_uses_custom_category(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1",
                                 suggested_category="Groceries")
        r = auth_client.patch(f"/banking/drafts/{txn.id}",
                               json={"action": "confirm", "category": "Transport"})
        assert r.status_code == 200
        expense = db.query(MonthlyExpense).filter(
            MonthlyExpense.id == r.json()["monthly_expense_id"]
        ).first()
        assert expense.category == "Transport"

    def test_confirm_falls_back_to_other_when_no_category(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1",
                                 suggested_category=None)
        r = auth_client.patch(f"/banking/drafts/{txn.id}", json={"action": "confirm"})
        assert r.status_code == 200
        expense = db.query(MonthlyExpense).filter(
            MonthlyExpense.id == r.json()["monthly_expense_id"]
        ).first()
        assert expense.category == "Other"

    def test_action_on_confirmed_returns_409(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1", status="confirmed")
        r = auth_client.patch(f"/banking/drafts/{txn.id}", json={"action": "reject"})
        assert r.status_code == 409

    def test_action_on_other_users_draft_returns_403(self, auth_client, db, second_user):
        conn2 = _make_connection(db, second_user)
        txn = _make_transaction(db, second_user, conn2, external_id="e1")
        r = auth_client.patch(f"/banking/drafts/{txn.id}", json={"action": "reject"})
        assert r.status_code == 403

    def test_action_on_missing_draft_returns_404(self, auth_client):
        r = auth_client.patch("/banking/drafts/99999", json={"action": "reject"})
        assert r.status_code == 404

    def test_invalid_action_returns_422(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1")
        r = auth_client.patch(f"/banking/drafts/{txn.id}", json={"action": "delete"})
        assert r.status_code == 422

    def test_unauthenticated_returns_4xx(self, client, db, verified_user):
        conn = _make_connection(db, verified_user)
        txn = _make_transaction(db, verified_user, conn, external_id="e1")
        r = client.patch(f"/banking/drafts/{txn.id}", json={"action": "reject"})
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /banking/drafts/confirm-all
# ---------------------------------------------------------------------------

class TestConfirmAll:
    def test_confirms_all_drafts(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        _make_transaction(db, verified_user, conn, external_id="e1",
                          description="Tesco", suggested_category="Groceries")
        _make_transaction(db, verified_user, conn, external_id="e2",
                          description="Netflix", suggested_category="Entertainment")
        r = auth_client.post("/banking/drafts/confirm-all")
        assert r.status_code == 200
        assert r.json()["confirmed"] == 2

        remaining = db.query(BankTransaction).filter(
            BankTransaction.user_id == verified_user.id,
            BankTransaction.status == "draft",
        ).count()
        assert remaining == 0

    def test_confirm_all_returns_zero_when_no_drafts(self, auth_client):
        r = auth_client.post("/banking/drafts/confirm-all")
        assert r.status_code == 200
        assert r.json()["confirmed"] == 0

    def test_confirm_all_only_affects_own_drafts(self, auth_client, db, second_user):
        conn2 = _make_connection(db, second_user)
        _make_transaction(db, second_user, conn2, external_id="e_other")
        r = auth_client.post("/banking/drafts/confirm-all")
        assert r.status_code == 200
        assert r.json()["confirmed"] == 0

        # Other user's draft untouched
        other_txns = db.query(BankTransaction).filter(
            BankTransaction.user_id == second_user.id,
            BankTransaction.status == "draft",
        ).count()
        assert other_txns == 1

    def test_confirm_all_skips_non_draft_statuses(self, auth_client, db, verified_user):
        conn = _make_connection(db, verified_user)
        _make_transaction(db, verified_user, conn, external_id="e_draft", status="draft")
        _make_transaction(db, verified_user, conn, external_id="e_rej", status="rejected")
        r = auth_client.post("/banking/drafts/confirm-all")
        assert r.json()["confirmed"] == 1

    def test_unauthenticated_returns_4xx(self, client):
        r = client.post("/banking/drafts/confirm-all")
        assert r.status_code in (401, 403)
