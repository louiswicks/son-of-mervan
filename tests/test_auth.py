"""Tests for auth flows and account management endpoints."""
import hashlib
import secrets
from datetime import datetime, timedelta

import pytest

from conftest import TEST_EMAIL, TEST_EMAIL_2, TEST_PASSWORD
from database import PasswordResetToken, RefreshToken, User
from security import create_email_verify_token, get_password_hash


# ── Health ─────────────────────────────────────────────────────────────────────

class TestRoot:
    def test_root_returns_healthy(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


# ── Signup ─────────────────────────────────────────────────────────────────────

class TestSignup:
    def test_signup_success(self, client):
        r = client.post("/auth/signup", json={
            "email": "brand_new@example.com",
            "password": "NewPass1!",
        })
        assert r.status_code == 200
        assert "message" in r.json()

    def test_signup_duplicate_email(self, client, verified_user):
        r = client.post("/auth/signup", json={
            "email": TEST_EMAIL,
            "password": "NewPass1!",
        })
        assert r.status_code == 400
        assert "already registered" in r.json()["detail"]

    def test_signup_missing_uppercase(self, client):
        r = client.post("/auth/signup", json={
            "email": "x@example.com",
            "password": "weakpass1!",
        })
        assert r.status_code == 422

    def test_signup_missing_digit(self, client):
        r = client.post("/auth/signup", json={
            "email": "x@example.com",
            "password": "WeakPass!!",
        })
        assert r.status_code == 422

    def test_signup_missing_special_char(self, client):
        r = client.post("/auth/signup", json={
            "email": "x@example.com",
            "password": "WeakPass1",
        })
        assert r.status_code == 422

    def test_signup_too_short(self, client):
        r = client.post("/auth/signup", json={
            "email": "x@example.com",
            "password": "S1!",
        })
        assert r.status_code == 422

    def test_signup_invalid_email(self, client):
        r = client.post("/auth/signup", json={
            "email": "not-an-email",
            "password": "TestPass1!",
        })
        assert r.status_code == 422


# ── Email verification ─────────────────────────────────────────────────────────

class TestVerifyEmail:
    def test_verify_email_success(self, client, db):
        user = User(
            email="unverified@example.com",
            password_hash=get_password_hash(TEST_PASSWORD),
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_email_verify_token(user.id, user.email)
        r = client.get(f"/auth/verify-email?token={token}")
        assert r.status_code == 200
        assert "verified" in r.json()["message"].lower()

    def test_verify_email_already_verified(self, client, verified_user):
        token = create_email_verify_token(verified_user.id, verified_user.email)
        r = client.get(f"/auth/verify-email?token={token}")
        assert r.status_code == 200
        assert "already" in r.json()["message"].lower()

    def test_verify_email_invalid_token(self, client):
        r = client.get("/auth/verify-email?token=thisisnotavalidtoken")
        assert r.status_code == 400


# ── Login ──────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success_by_email(self, client, verified_user):
        r = client.post("/login", json={
            "identifier": TEST_EMAIL,
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_stores_refresh_token_in_db(self, client, db, verified_user):
        r = client.post("/login", json={
            "identifier": TEST_EMAIL,
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 200
        rt = db.query(RefreshToken).filter(RefreshToken.user_id == verified_user.id).first()
        assert rt is not None
        assert rt.expires_at > datetime.utcnow()

    def test_login_wrong_password(self, client, verified_user):
        r = client.post("/login", json={
            "identifier": TEST_EMAIL,
            "password": "WrongPass9!",
        })
        assert r.status_code == 401

    def test_login_unverified_user(self, client, db):
        user = User(
            email="unver@example.com",
            password_hash=get_password_hash(TEST_PASSWORD),
            email_verified=False,
        )
        db.add(user)
        db.commit()

        r = client.post("/login", json={
            "identifier": "unver@example.com",
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 403
        assert "verify" in r.json()["detail"].lower()

    def test_login_soft_deleted_account(self, client, db):
        user = User(
            email="deleted@example.com",
            password_hash=get_password_hash(TEST_PASSWORD),
            email_verified=True,
            deleted_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()

        r = client.post("/login", json={
            "identifier": "deleted@example.com",
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 403
        assert "deleted" in r.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        r = client.post("/login", json={
            "identifier": "nobody@example.com",
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 401


# ── Password reset ──────────────────────────────────────────────────────────────

class TestPasswordReset:
    def test_reset_request_unknown_email_returns_200(self, client):
        """Must always return 200 to prevent user enumeration."""
        r = client.post("/auth/password-reset-request", json={
            "email": "nobody@example.com",
        })
        assert r.status_code == 200

    def test_reset_request_verified_user(self, client, verified_user):
        r = client.post("/auth/password-reset-request", json={
            "email": TEST_EMAIL,
        })
        assert r.status_code == 200

    def test_reset_confirm_success(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        rt = PasswordResetToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=60),
        )
        db.add(rt)
        db.commit()

        r = client.post("/auth/password-reset-confirm", json={
            "token": raw,
            "new_password": "UpdatedPass2@",
        })
        assert r.status_code == 200
        assert "updated" in r.json()["message"].lower()

    def test_reset_confirm_invalid_token(self, client):
        r = client.post("/auth/password-reset-confirm", json={
            "token": "totallybadtoken",
            "new_password": "UpdatedPass2@",
        })
        assert r.status_code == 400

    def test_reset_confirm_expired_token(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        rt = PasswordResetToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.add(rt)
        db.commit()

        r = client.post("/auth/password-reset-confirm", json={
            "token": raw,
            "new_password": "UpdatedPass2@",
        })
        assert r.status_code == 400
        assert "expired" in r.json()["detail"]

    def test_reset_confirm_already_used_token(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        rt = PasswordResetToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=60),
            used_at=datetime.utcnow(),
        )
        db.add(rt)
        db.commit()

        r = client.post("/auth/password-reset-confirm", json={
            "token": raw,
            "new_password": "UpdatedPass2@",
        })
        assert r.status_code == 400
        assert "already been used" in r.json()["detail"]

    def test_reset_invalidates_previous_tokens(self, client, db, verified_user):
        """Requesting a second reset should invalidate the first token."""
        raw_old = secrets.token_urlsafe(32)
        old_rt = PasswordResetToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw_old.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=60),
        )
        db.add(old_rt)
        db.commit()

        client.post("/auth/password-reset-request", json={"email": TEST_EMAIL})

        db.refresh(old_rt)
        assert old_rt.used_at is not None


# ── Token refresh & logout ─────────────────────────────────────────────────────

class TestRefreshToken:
    def test_refresh_no_cookie_fails(self, client):
        r = client.post("/auth/refresh")
        assert r.status_code == 401

    def test_refresh_valid_cookie_issues_new_token(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        db.add(RefreshToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        ))
        db.commit()

        client.cookies.set("refresh_token", raw)
        r = client.post("/auth/refresh")
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_refresh_revoked_token_fails(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        db.add(RefreshToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked_at=datetime.utcnow(),
        ))
        db.commit()

        client.cookies.set("refresh_token", raw)
        r = client.post("/auth/refresh")
        assert r.status_code == 401

    def test_refresh_expired_token_fails(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        db.add(RefreshToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() - timedelta(days=1),
        ))
        db.commit()

        client.cookies.set("refresh_token", raw)
        r = client.post("/auth/refresh")
        assert r.status_code == 401


class TestLogout:
    def test_logout_revokes_refresh_token(self, client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        rt = RefreshToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(rt)
        db.commit()
        rt_id = rt.id

        client.cookies.set("refresh_token", raw)
        r = client.post("/auth/logout")
        assert r.status_code == 200

        updated = db.query(RefreshToken).filter(RefreshToken.id == rt_id).first()
        assert updated.revoked_at is not None

    def test_logout_without_cookie_succeeds(self, client):
        r = client.post("/auth/logout")
        assert r.status_code == 200


# ── Account management ─────────────────────────────────────────────────────────

class TestAccountManagement:
    def test_get_profile(self, auth_client, verified_user):
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == TEST_EMAIL

    def test_update_username(self, auth_client):
        r = auth_client.put("/users/me", json={"username": "mynewname"})
        assert r.status_code == 200
        assert r.json()["username"] == "mynewname"

    def test_update_username_empty_clears_it(self, auth_client):
        r = auth_client.put("/users/me", json={"username": "  "})
        assert r.status_code == 200
        assert r.json()["username"] is None

    def test_change_password_success(self, auth_client):
        r = auth_client.put("/users/me/password", json={
            "current_password": TEST_PASSWORD,
            "new_password": "NewPass2@",
        })
        assert r.status_code == 200
        assert "updated" in r.json()["message"].lower()

    def test_change_password_wrong_current(self, auth_client):
        r = auth_client.put("/users/me/password", json={
            "current_password": "WrongOld9!",
            "new_password": "NewPass2@",
        })
        assert r.status_code == 400
        assert "incorrect" in r.json()["detail"].lower()

    def test_change_password_same_as_current(self, auth_client):
        r = auth_client.put("/users/me/password", json={
            "current_password": TEST_PASSWORD,
            "new_password": TEST_PASSWORD,
        })
        assert r.status_code == 400

    def test_delete_account_soft_deletes_user(self, auth_client, db, verified_user):
        r = auth_client.delete("/users/me")
        assert r.status_code == 200
        assert "deletion" in r.json()["message"].lower()

        db.refresh(verified_user)
        assert verified_user.deleted_at is not None

    def test_delete_account_revokes_refresh_tokens(self, auth_client, db, verified_user):
        raw = secrets.token_urlsafe(32)
        rt = RefreshToken(
            user_id=verified_user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(rt)
        db.commit()
        rt_id = rt.id

        auth_client.delete("/users/me")

        updated = db.query(RefreshToken).filter(RefreshToken.id == rt_id).first()
        assert updated.revoked_at is not None
