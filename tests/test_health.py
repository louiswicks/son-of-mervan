"""
Tests for enhanced health probe endpoints (PRD 22.1).

Coverage targets:
  main.py — GET /health/live, GET /health/ready, GET /health
"""
from unittest.mock import patch, MagicMock

import pytest


class TestHealthLive:
    def test_always_returns_200(self, client):
        """/health/live must return HTTP 200 unconditionally."""
        r = client.get("/health/live")
        assert r.status_code == 200

    def test_response_body(self, client):
        """Response must contain status=alive."""
        r = client.get("/health/live")
        assert r.json() == {"status": "alive"}

    def test_no_auth_required(self, client):
        """/health/live is public — no token needed."""
        r = client.get("/health/live")
        assert r.status_code == 200

    def test_returns_alive_even_when_db_down(self, client):
        """Liveness probe must succeed regardless of DB state."""
        with patch("sqlalchemy.engine.base.Engine.connect", side_effect=Exception("db down")):
            r = client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"


class TestHealthReady:
    def test_returns_200_when_healthy(self, client):
        """/health/ready returns 200 when DB is reachable."""
        r = client.get("/health/ready")
        assert r.status_code == 200

    def test_response_has_status_and_checks(self, client):
        """Response must include 'status' and 'checks' list."""
        r = client.get("/health/ready")
        body = r.json()
        assert "status" in body
        assert "checks" in body
        assert isinstance(body["checks"], list)

    def test_db_check_present(self, client):
        """Database check must appear in checks list."""
        r = client.get("/health/ready")
        check_names = [c["name"] for c in r.json()["checks"]]
        assert "database" in check_names

    def test_db_check_ok_true_when_healthy(self, client):
        """Database check ok must be True when DB is reachable."""
        r = client.get("/health/ready")
        db_check = next(c for c in r.json()["checks"] if c["name"] == "database")
        assert db_check["ok"] is True

    def test_status_ready_when_all_healthy(self, client):
        """Status must be 'ready' when all checks pass."""
        r = client.get("/health/ready")
        assert r.json()["status"] == "ready"

    def test_returns_503_when_db_unreachable(self, client):
        """/health/ready returns 503 when DB is unreachable."""
        with patch("database.engine.connect", side_effect=Exception("connection refused")):
            r = client.get("/health/ready")
        assert r.status_code == 503

    def test_db_check_ok_false_when_db_down(self, client):
        """Database check ok must be False when DB is unreachable."""
        with patch("database.engine.connect", side_effect=Exception("connection refused")):
            r = client.get("/health/ready")
        body = r.json()
        db_check = next(c for c in body["checks"] if c["name"] == "database")
        assert db_check["ok"] is False

    def test_status_degraded_when_db_down(self, client):
        """Status must be 'degraded' when a check fails."""
        with patch("database.engine.connect", side_effect=Exception("connection refused")):
            r = client.get("/health/ready")
        assert r.json()["status"] == "degraded"

    def test_no_redis_check_when_redis_url_not_set(self, client):
        """Redis check must not appear when REDIS_URL is not configured."""
        with patch("core.config.settings") as mock_settings:
            mock_settings.REDIS_URL = ""
            mock_settings.REDIS_URL = ""
            r = client.get("/health/ready")
        check_names = [c["name"] for c in r.json()["checks"]]
        assert "redis" not in check_names

    def test_no_auth_required(self, client):
        """/health/ready is public."""
        r = client.get("/health/ready")
        assert r.status_code in (200, 503)  # either way, no 401/403


class TestHealthDetailed:
    def test_returns_200(self, client):
        """/health returns 200."""
        r = client.get("/health")
        assert r.status_code == 200

    def test_includes_version(self, client):
        """Response must include 'version' string."""
        r = client.get("/health")
        assert "version" in r.json()
        assert isinstance(r.json()["version"], str)

    def test_includes_uptime(self, client):
        """Response must include 'uptime_seconds' float ≥ 0."""
        r = client.get("/health")
        body = r.json()
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], (int, float))
        assert body["uptime_seconds"] >= 0

    def test_includes_db_ok(self, client):
        """Response must include 'db_ok' boolean."""
        r = client.get("/health")
        body = r.json()
        assert "db_ok" in body
        assert isinstance(body["db_ok"], bool)

    def test_db_ok_true_when_healthy(self, client):
        """db_ok must be True in a healthy test environment."""
        r = client.get("/health")
        assert r.json()["db_ok"] is True

    def test_includes_scheduler_running(self, client):
        """Response must include 'scheduler_running' boolean."""
        r = client.get("/health")
        body = r.json()
        assert "scheduler_running" in body
        assert isinstance(body["scheduler_running"], bool)

    def test_includes_memory_mb_field(self, client):
        """Response must include 'memory_mb' field (may be None on some platforms)."""
        r = client.get("/health")
        body = r.json()
        assert "memory_mb" in body

    def test_status_ok_when_db_healthy(self, client):
        """Status must be 'ok' when DB is reachable."""
        r = client.get("/health")
        assert r.json()["status"] == "ok"

    def test_no_auth_required(self, client):
        """/health is public."""
        r = client.get("/health")
        assert r.status_code == 200
