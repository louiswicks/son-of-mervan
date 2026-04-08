"""Tests for Phase 13.5: Active Session Manager."""
import hashlib
import secrets
from datetime import datetime, timedelta

import pytest

from conftest import TEST_EMAIL
from database import RefreshToken


def _make_refresh_token(db, user, user_agent="Mozilla/5.0 Test Browser", days_old=0):
    """Helper: create a live RefreshToken for a user."""
    raw = secrets.token_urlsafe(32)
    token = RefreshToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        user_agent=user_agent,
        last_used_at=datetime.utcnow() - timedelta(days=days_old),
        created_at=datetime.utcnow() - timedelta(days=days_old),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, raw


class TestGetSessions:
    def test_returns_active_sessions(self, auth_client, db, verified_user):
        _make_refresh_token(db, verified_user, "Chrome/120")
        _make_refresh_token(db, verified_user, "Firefox/119")

        resp = auth_client.get("/auth/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        agents = {s["user_agent"] for s in data}
        assert "Chrome/120" in agents
        assert "Firefox/119" in agents

    def test_excludes_revoked_sessions(self, auth_client, db, verified_user):
        token, _ = _make_refresh_token(db, verified_user, "Chrome/120")
        token.revoked_at = datetime.utcnow()
        db.commit()

        resp = auth_client.get("/auth/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_excludes_expired_sessions(self, auth_client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        expired = RefreshToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
        db.add(expired)
        db.commit()

        resp = auth_client.get("/auth/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/auth/sessions")
        assert resp.status_code in (401, 403)


class TestRevokeSession:
    def test_revoke_own_session(self, auth_client, db, verified_user):
        token, _ = _make_refresh_token(db, verified_user, "Safari/17")
        resp = auth_client.delete(f"/auth/sessions/{token.id}")
        assert resp.status_code == 200
        db.expire(token)
        assert token.revoked_at is not None

    def test_cannot_revoke_other_users_session(self, auth_client, db, second_user):
        token, _ = _make_refresh_token(db, second_user, "Opera/100")
        resp = auth_client.delete(f"/auth/sessions/{token.id}")
        assert resp.status_code == 404

    def test_revoke_nonexistent_session_returns_404(self, auth_client):
        resp = auth_client.delete("/auth/sessions/99999")
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, client):
        resp = client.delete("/auth/sessions/1")
        assert resp.status_code in (401, 403)


class TestRevokeAllOtherSessions:
    def test_revokes_other_sessions(self, auth_client, db, verified_user):
        t1, _ = _make_refresh_token(db, verified_user, "Chrome/120")
        t2, _ = _make_refresh_token(db, verified_user, "Firefox/119")

        resp = auth_client.delete("/auth/sessions")
        assert resp.status_code == 200
        assert "Revoked" in resp.json()["message"]

        db.expire_all()
        # Both tokens revoked (no current cookie in test client)
        assert t1.revoked_at is not None
        assert t2.revoked_at is not None

    def test_unauthenticated_returns_401(self, client):
        resp = client.delete("/auth/sessions")
        assert resp.status_code in (401, 403)
