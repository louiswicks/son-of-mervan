"""Tests for the purge_expired_tokens APScheduler job (Phase 16.2)."""
import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from database import PasswordResetToken, RefreshToken
from main import purge_expired_tokens


def _make_refresh(db, user, *, expired=False):
    raw = secrets.token_hex(32)
    token = RefreshToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() - timedelta(days=1) if expired else datetime.utcnow() + timedelta(days=30),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token.id  # return ID before the session may expunge it


def _make_reset(db, user, *, expired=False, used=False):
    raw = secrets.token_hex(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() - timedelta(hours=1) if expired else datetime.utcnow() + timedelta(hours=1),
        used_at=datetime.utcnow() if used else None,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token.id


@pytest.fixture
def session_factory(db):
    """Returns a factory that yields the test session; mocks close() so pytest can still use it."""
    factory = MagicMock()
    factory.return_value = db
    db.close = MagicMock()
    return factory


class TestPurgeExpiredTokens:
    """purge_expired_tokens should hard-delete stale tokens only."""

    def test_deletes_expired_refresh_tokens(self, db, session_factory, verified_user):
        stale_id = _make_refresh(db, verified_user, expired=True)
        purge_expired_tokens(session_factory)
        assert db.query(RefreshToken).filter(RefreshToken.id == stale_id).first() is None

    def test_keeps_valid_refresh_tokens(self, db, session_factory, verified_user):
        live_id = _make_refresh(db, verified_user, expired=False)
        purge_expired_tokens(session_factory)
        assert db.query(RefreshToken).filter(RefreshToken.id == live_id).first() is not None

    def test_deletes_expired_reset_tokens(self, db, session_factory, verified_user):
        stale_id = _make_reset(db, verified_user, expired=True)
        purge_expired_tokens(session_factory)
        assert db.query(PasswordResetToken).filter(PasswordResetToken.id == stale_id).first() is None

    def test_deletes_used_reset_tokens(self, db, session_factory, verified_user):
        used_id = _make_reset(db, verified_user, used=True)
        purge_expired_tokens(session_factory)
        assert db.query(PasswordResetToken).filter(PasswordResetToken.id == used_id).first() is None

    def test_keeps_valid_unused_reset_tokens(self, db, session_factory, verified_user):
        live_id = _make_reset(db, verified_user)
        purge_expired_tokens(session_factory)
        assert db.query(PasswordResetToken).filter(PasswordResetToken.id == live_id).first() is not None

    def test_mixed_batch(self, db, session_factory, verified_user):
        """Stale tokens are removed; live tokens survive in the same batch."""
        expired_refresh_id = _make_refresh(db, verified_user, expired=True)
        live_refresh_id = _make_refresh(db, verified_user, expired=False)
        expired_reset_id = _make_reset(db, verified_user, expired=True)
        used_reset_id = _make_reset(db, verified_user, used=True)
        live_reset_id = _make_reset(db, verified_user)

        purge_expired_tokens(session_factory)

        assert db.query(RefreshToken).filter(RefreshToken.id == expired_refresh_id).first() is None
        assert db.query(RefreshToken).filter(RefreshToken.id == live_refresh_id).first() is not None
        assert db.query(PasswordResetToken).filter(PasswordResetToken.id == expired_reset_id).first() is None
        assert db.query(PasswordResetToken).filter(PasswordResetToken.id == used_reset_id).first() is None
        assert db.query(PasswordResetToken).filter(PasswordResetToken.id == live_reset_id).first() is not None

    def test_noop_when_nothing_to_purge(self, db, session_factory, verified_user):
        """Job should complete without error when there is nothing to delete."""
        purge_expired_tokens(session_factory)  # no tokens at all — should not raise
