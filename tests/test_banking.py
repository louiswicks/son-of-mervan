"""
Tests for the open banking OAuth flow (Phase 15.2).

Coverage targets:
  routers/banking.py — GET /banking/connect
                        GET /banking/callback
                        POST /banking/refresh/{id}
                        GET /banking/connections
"""
import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from database import BankConnection
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
