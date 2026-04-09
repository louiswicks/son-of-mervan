"""
E2E test configuration for Son-of-Mervan.

Starts a real uvicorn server on a free port, wired to an isolated SQLite DB,
so every test exercises the real HTTP stack without any mocking.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from playwright.sync_api import Playwright

# ── Deterministic secrets so the test process and server share the same keys ──
E2E_JWT_SECRET = "e2e-test-jwt-secret-not-for-production-use"
E2E_ENCRYPTION_KEY = Fernet.generate_key().decode()
E2E_DB_PATH = Path(__file__).parent / "e2e_test.db"
E2E_DB_URL = f"sqlite:///{E2E_DB_PATH}"
SERVER_PORT = 8799
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"

# Test user credentials — a fresh account is registered per test session
E2E_EMAIL = "e2e_test_user@example.com"
E2E_PASSWORD = "E2eTestPass1!"


def _wait_for_server(url: str, timeout: float = 30.0) -> None:
    """Poll GET /health until the server responds or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


@pytest.fixture(scope="session")
def server():
    """Start a real uvicorn server for the session and tear it down after."""
    env = {
        **os.environ,
        "JWT_SECRET_KEY": E2E_JWT_SECRET,
        "ENCRYPTION_KEY": E2E_ENCRYPTION_KEY,
        "DATABASE_URL": E2E_DB_URL,
        "ENVIRONMENT": "testing",
        "CORS_ORIGINS": "http://localhost:3000",
        "FRONTEND_BASE_URL": "http://localhost:3000",
        # Disable APScheduler background jobs to avoid SQLite write-lock contention
        "DISABLE_SCHEDULER": "1",
    }
    # Remove keys that would trigger external services in tests
    env.pop("SENDGRID_API_KEY", None)
    env.pop("SMTP_HOST", None)
    env.pop("SMTP_USER", None)
    env.pop("SMTP_PASS", None)
    env.pop("REDIS_URL", None)
    env.pop("SENTRY_DSN", None)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(SERVER_PORT), "--log-level", "warning"],
        env=env,
        cwd=Path(__file__).parent.parent,
    )
    try:
        _wait_for_server(BASE_URL)
        yield BASE_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        E2E_DB_PATH.unlink(missing_ok=True)
        Path(str(E2E_DB_PATH) + "-shm").unlink(missing_ok=True)
        Path(str(E2E_DB_PATH) + "-wal").unlink(missing_ok=True)


@pytest.fixture(scope="session")
def base_url(server):
    return server


@pytest.fixture(scope="session")
def api_context(playwright: Playwright, server):
    """Session-scoped Playwright API request context pointed at the live server."""
    ctx = playwright.request.new_context(base_url=server)
    yield ctx
    ctx.dispose()


@pytest.fixture(scope="session")
def auth_token(api_context, server):
    """Register, verify, and login the E2E test user once per session.

    Returns the Bearer token string so individual tests can attach it.
    """
    # 1. Sign up
    resp = api_context.post("/auth/signup", data={"email": E2E_EMAIL, "password": E2E_PASSWORD})
    # May already exist if a previous run left the DB — treat 400 as OK here
    body = resp.json()

    if resp.status == 200:
        # Extract the dev verification URL returned when SMTP is not configured
        dev_url: str = body.get("dev_verify_url", "")
        assert dev_url, "Expected dev_verify_url in signup response (SMTP not configured)"
        # The URL has the form:  …#/verify-email?token=<jwt>
        token_str = dev_url.split("token=", 1)[1]
        verify_resp = api_context.get(f"/auth/verify-email?token={token_str}")
        assert verify_resp.status == 200, f"Email verification failed: {verify_resp.text()}"

    # 2. Login — endpoint expects {"identifier": "...", "password": "..."}
    login_resp = api_context.post("/login", data={"identifier": E2E_EMAIL, "password": E2E_PASSWORD})
    assert login_resp.status == 200, f"Login failed: {login_resp.text()}"
    return login_resp.json()["access_token"]
