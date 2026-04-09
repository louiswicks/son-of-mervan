"""Tests for idempotency key support on POST /calculate-budget and POST /monthly-tracker/{month}."""
import json
import uuid
from datetime import datetime, timedelta

import pytest

from conftest import TEST_EMAIL, TEST_EMAIL_2, make_expense, make_month
from core.idempotency import compute_key_hash
from database import IdempotencyRecord


BUDGET_PAYLOAD = {
    "month": "2026-03",
    "monthly_salary": 3000.0,
    "expenses": [
        {"name": "Rent", "category": "Housing", "amount": 800.0},
    ],
}

TRACKER_PAYLOAD = {
    "salary": 3000.0,
    "expenses": [
        {"name": "Groceries", "category": "Food", "amount": 150.0},
    ],
}


class TestIdempotencyCalculateBudget:
    def test_no_key_processes_normally(self, auth_client):
        r = auth_client.post("/calculate-budget?commit=true", json=BUDGET_PAYLOAD)
        assert r.status_code == 200
        assert r.json()["committed"] is True

    def test_unauthenticated_returns_403(self, client):
        r = client.post(
            "/calculate-budget?commit=true",
            json=BUDGET_PAYLOAD,
            headers={"X-Idempotency-Key": "key-abc"},
        )
        assert r.status_code == 403

    def test_key_too_long_returns_422(self, auth_client):
        long_key = "x" * 257
        r = auth_client.post(
            "/calculate-budget?commit=true",
            json=BUDGET_PAYLOAD,
            headers={"X-Idempotency-Key": long_key},
        )
        assert r.status_code == 422

    def test_key_max_length_accepted(self, auth_client):
        max_key = "k" * 256
        r = auth_client.post(
            "/calculate-budget?commit=true",
            json=BUDGET_PAYLOAD,
            headers={"X-Idempotency-Key": max_key},
        )
        assert r.status_code == 200

    def test_first_request_saves_record(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        r = auth_client.post(
            "/calculate-budget?commit=true",
            json=BUDGET_PAYLOAD,
            headers={"X-Idempotency-Key": key},
        )
        assert r.status_code == 200
        key_hash = compute_key_hash(verified_user.id, key)
        record = db.query(IdempotencyRecord).filter_by(key_hash=key_hash).first()
        assert record is not None
        assert record.request_path == "/calculate-budget"
        body = json.loads(record.response_body)
        assert body["committed"] is True

    def test_second_request_returns_cached_response(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        headers = {"X-Idempotency-Key": key}

        r1 = auth_client.post("/calculate-budget?commit=true", json=BUDGET_PAYLOAD, headers=headers)
        assert r1.status_code == 200
        first_id = r1.json()["id"]

        # Second call with identical key should return the same cached response
        r2 = auth_client.post("/calculate-budget?commit=true", json=BUDGET_PAYLOAD, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["id"] == first_id

    def test_second_request_does_not_create_new_idempotency_record(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        headers = {"X-Idempotency-Key": key}

        auth_client.post("/calculate-budget?commit=true", json=BUDGET_PAYLOAD, headers=headers)
        auth_client.post("/calculate-budget?commit=true", json=BUDGET_PAYLOAD, headers=headers)

        key_hash = compute_key_hash(verified_user.id, key)
        count = db.query(IdempotencyRecord).filter_by(key_hash=key_hash).count()
        assert count == 1  # only one record, not two

    def test_read_only_path_does_not_save_idempotency_record(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        # commit=False — idempotency should not be applied (no DB writes anyway)
        r = auth_client.post(
            "/calculate-budget",  # no ?commit=true
            json=BUDGET_PAYLOAD,
            headers={"X-Idempotency-Key": key},
        )
        assert r.status_code == 200
        assert r.json()["committed"] is False
        key_hash = compute_key_hash(verified_user.id, key)
        record = db.query(IdempotencyRecord).filter_by(key_hash=key_hash).first()
        assert record is None

    def test_expired_key_treated_as_new_request(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        key_hash = compute_key_hash(verified_user.id, key)
        # Insert an expired record manually
        expired_record = IdempotencyRecord(
            key_hash=key_hash,
            user_id=verified_user.id,
            request_path="/calculate-budget",
            response_body=json.dumps({"old": True}),
            created_at=datetime.utcnow() - timedelta(hours=25),
        )
        db.add(expired_record)
        db.commit()

        r = auth_client.post(
            "/calculate-budget?commit=true",
            json=BUDGET_PAYLOAD,
            headers={"X-Idempotency-Key": key},
        )
        assert r.status_code == 200
        data = r.json()
        # Should have processed a fresh request (not returned the old stub)
        assert "old" not in data
        assert data["committed"] is True

    def test_same_key_different_users_have_different_hashes(
        self, db, verified_user, second_user
    ):
        """Key hashes are user-scoped: same client key → different DB records for different users."""
        key = "shared-key-between-users"
        h1 = compute_key_hash(verified_user.id, key)
        h2 = compute_key_hash(second_user.id, key)
        assert h1 != h2

    def test_cached_response_is_not_visible_to_another_user(
        self, auth_client, db, verified_user, second_user
    ):
        """Seeding user1's idempotency record should not serve user2 a cached response."""
        key = "shared-key-across-users"
        user1_hash = compute_key_hash(verified_user.id, key)

        # Seed a record attributed to user1
        record = IdempotencyRecord(
            key_hash=user1_hash,
            user_id=verified_user.id,
            request_path="/calculate-budget",
            response_body=json.dumps({"user1_data": True}),
            created_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()

        # user2's hash is different, so get_cached_response will miss
        user2_hash = compute_key_hash(second_user.id, key)
        from core.idempotency import get_cached_response
        session = db  # same session for simplicity
        result = get_cached_response(session, user2_hash)
        assert result is None


class TestIdempotencyMonthlyTracker:
    def test_no_key_processes_normally(self, auth_client):
        r = auth_client.post("/monthly-tracker/2026-03", json=TRACKER_PAYLOAD)
        assert r.status_code == 200
        assert r.json()["month"] == "2026-03"

    def test_unauthenticated_returns_403(self, client):
        r = client.post(
            "/monthly-tracker/2026-03",
            json=TRACKER_PAYLOAD,
            headers={"X-Idempotency-Key": "some-key"},
        )
        assert r.status_code == 403

    def test_key_too_long_returns_422(self, auth_client):
        long_key = "y" * 257
        r = auth_client.post(
            "/monthly-tracker/2026-03",
            json=TRACKER_PAYLOAD,
            headers={"X-Idempotency-Key": long_key},
        )
        assert r.status_code == 422

    def test_first_request_saves_record(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        r = auth_client.post(
            "/monthly-tracker/2026-03",
            json=TRACKER_PAYLOAD,
            headers={"X-Idempotency-Key": key},
        )
        assert r.status_code == 200
        key_hash = compute_key_hash(verified_user.id, key)
        record = db.query(IdempotencyRecord).filter_by(key_hash=key_hash).first()
        assert record is not None
        assert "/monthly-tracker/" in record.request_path

    def test_second_request_returns_cached_response(self, auth_client, db, verified_user):
        key = str(uuid.uuid4())
        headers = {"X-Idempotency-Key": key}

        r1 = auth_client.post("/monthly-tracker/2026-03", json=TRACKER_PAYLOAD, headers=headers)
        assert r1.status_code == 200

        r2 = auth_client.post("/monthly-tracker/2026-03", json=TRACKER_PAYLOAD, headers=headers)
        assert r2.status_code == 200
        # Both responses should be identical
        assert r1.json() == r2.json()

    def test_different_keys_create_independent_records(self, auth_client, db, verified_user):
        key1 = "tracker-key-001"
        key2 = "tracker-key-002"

        auth_client.post("/monthly-tracker/2026-03", json=TRACKER_PAYLOAD,
                         headers={"X-Idempotency-Key": key1})
        auth_client.post("/monthly-tracker/2026-03", json=TRACKER_PAYLOAD,
                         headers={"X-Idempotency-Key": key2})

        h1 = compute_key_hash(verified_user.id, key1)
        h2 = compute_key_hash(verified_user.id, key2)
        assert db.query(IdempotencyRecord).filter_by(key_hash=h1).count() == 1
        assert db.query(IdempotencyRecord).filter_by(key_hash=h2).count() == 1
