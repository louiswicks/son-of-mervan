"""
Critical-path E2E tests for Son-of-Mervan.

These tests run against a real local uvicorn server (no mocking) and cover
the four most important user journeys:

1. Signup → email verification → login
2. Calculate budget (commit=false, read-only planning)
3. POST monthly tracker actuals
4. GET annual overview
"""
import pytest
from playwright.sync_api import APIRequestContext

from e2e.conftest import E2E_EMAIL


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Signup → email verify → login
# ─────────────────────────────────────────────────────────────────────────────

class TestSignupVerifyLogin:
    """Full registration + email-verification + login journey."""

    def test_signup_then_verify_then_login(self, api_context: APIRequestContext, server: str):
        """
        Register a brand-new one-off user (distinct email from the session user),
        verify via the dev_verify_url returned in the response, then log in and
        confirm the access token is a non-empty string.
        """
        email = "e2e_onetime@example.com"
        password = "OnceOnly1!"

        # Step 1 — signup
        signup_resp = api_context.post("/auth/signup", data={"email": email, "password": password})
        assert signup_resp.status == 200, f"Signup failed: {signup_resp.text()}"
        body = signup_resp.json()
        assert "message" in body

        # Step 2 — extract dev verification URL and verify email
        dev_url: str = body.get("dev_verify_url", "")
        assert dev_url, "Expected dev_verify_url — SMTP must be disabled in E2E env"
        jwt_token = dev_url.split("token=", 1)[1]

        verify_resp = api_context.get(f"/auth/verify-email?token={jwt_token}")
        assert verify_resp.status == 200, f"Verification failed: {verify_resp.text()}"
        assert "verified" in verify_resp.json().get("message", "").lower()

        # Step 3 — login using "identifier" field (accepts email or username)
        login_resp = api_context.post("/login", data={"identifier": email, "password": password})
        assert login_resp.status == 200, f"Login failed: {login_resp.text()}"
        access_token = login_resp.json().get("access_token", "")
        assert access_token, "Expected non-empty access_token in login response"

    def test_unverified_user_cannot_login(self, api_context: APIRequestContext):
        """A user who never verified their email must be rejected at login."""
        email = "e2e_noverify@example.com"
        password = "NoVerify1!"

        signup_resp = api_context.post("/auth/signup", data={"email": email, "password": password})
        assert signup_resp.status == 200

        login_resp = api_context.post("/login", data={"identifier": email, "password": password})
        assert login_resp.status == 403, (
            f"Expected 403 for unverified user, got {login_resp.status}"
        )

    def test_wrong_password_returns_401(self, api_context: APIRequestContext, auth_token: str):
        """Correct email, wrong password → 401."""
        resp = api_context.post("/login", data={"identifier": E2E_EMAIL, "password": "WrongPass9!"})
        assert resp.status == 401


# ─────────────────────────────────────────────────────────────────────────────
# 2. Calculate budget (commit=false)
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateBudget:
    """POST /calculate-budget (read-only planning mode)."""

    def test_calculate_budget_returns_totals(self, api_context: APIRequestContext, auth_token: str):
        """
        Send a salary + two expense line items with commit=false.
        The response must include a non-zero total and correct remaining budget.
        """
        payload = {
            "month": "2026-05",
            "monthly_salary": 3000,
            "expenses": [
                {"name": "Rent", "amount": 900, "category": "Housing"},
                {"name": "Groceries", "amount": 300, "category": "Food"},
            ],
        }
        resp = api_context.post(
            "/calculate-budget?commit=false",
            data=payload,
            headers=_auth_headers(auth_token),
        )
        assert resp.status == 200, f"calculate-budget failed: {resp.text()}"
        body = resp.json()
        assert body["total_expenses"] == pytest.approx(1200.0)
        assert body["remaining_budget"] == pytest.approx(1800.0)
        assert "savings_rate" in body

    def test_calculate_budget_commit_false_does_not_persist(
        self, api_context: APIRequestContext, auth_token: str
    ):
        """With commit=false, a subsequent GET /monthly-tracker for the same month returns no rows."""
        month = "2026-11"
        api_context.post(
            "/calculate-budget?commit=false",
            data={
                "month": month,
                "monthly_salary": 2000,
                "expenses": [
                    {"name": "Phantom", "amount": 100, "category": "Test"},
                ],
            },
            headers=_auth_headers(auth_token),
        )
        get_resp = api_context.get(
            f"/monthly-tracker/{month}",
            headers=_auth_headers(auth_token),
        )
        # Either 404 (no data) or 200 with empty items
        if get_resp.status == 200:
            items = get_resp.json().get("expenses", {}).get("items", [])
            names = [e.get("name", "") for e in items]
            assert "Phantom" not in names


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST monthly tracker actuals
# ─────────────────────────────────────────────────────────────────────────────

class TestMonthlyTracker:
    """POST /monthly-tracker/{month} → save actuals, then GET to verify."""

    def test_post_actuals_and_retrieve(self, api_context: APIRequestContext, auth_token: str):
        """
        Commit a budget plan then post actual spending; verify the actual amounts
        appear in a subsequent GET for the same month.
        """
        month = "2026-06"
        headers = _auth_headers(auth_token)

        # First commit a plan so the month row exists
        api_context.post(
            "/calculate-budget?commit=true",
            data={
                "month": month,
                "monthly_salary": 2500,
                "expenses": [
                    {"name": "Bus pass", "amount": 80, "category": "Transport"},
                ],
            },
            headers=headers,
        )

        # Post actuals — salary is optional; expenses use "amount" field
        tracker_resp = api_context.post(
            f"/monthly-tracker/{month}",
            data={
                "salary": 2500,
                "expenses": [
                    {"name": "Bus pass", "amount": 75, "category": "Transport"},
                ],
            },
            headers=headers,
        )
        assert tracker_resp.status == 200, f"monthly-tracker POST failed: {tracker_resp.text()}"

        # Retrieve and verify
        get_resp = api_context.get(f"/monthly-tracker/{month}", headers=headers)
        assert get_resp.status == 200, f"monthly-tracker GET failed: {get_resp.text()}"
        body = get_resp.json()
        items = body.get("expenses", {}).get("items", [])
        transport = [e for e in items if e.get("category") == "Transport"]
        assert transport, "Expected at least one Transport expense"
        assert transport[0]["actual_amount"] == pytest.approx(75.0)

    def test_post_tracker_requires_auth(self, api_context: APIRequestContext):
        """Unauthenticated request must be rejected with 401 or 403."""
        resp = api_context.post(
            "/monthly-tracker/2026-06",
            data={"salary": 2000, "expenses": []},
        )
        assert resp.status in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET annual overview
# ─────────────────────────────────────────────────────────────────────────────

class TestAnnualOverview:
    """GET /overview/annual?year=YYYY — aggregate all months in a year."""

    def test_annual_overview_returns_12_months(self, api_context: APIRequestContext, auth_token: str):
        """
        Commit budget data for two months in 2026, then fetch the annual overview.
        The response must contain exactly 12 month entries, with non-zero totals
        for the months we committed.
        """
        headers = _auth_headers(auth_token)
        year = "2026"

        # Commit data for a couple of months
        for month, salary, amount in [("2026-07", 3000, 500), ("2026-08", 3000, 700)]:
            api_context.post(
                "/calculate-budget?commit=true",
                data={
                    "month": month,
                    "monthly_salary": salary,
                    "expenses": [
                        {"name": "Rent", "amount": amount, "category": "Housing"},
                    ],
                },
                headers=headers,
            )

        overview_resp = api_context.get(
            f"/overview/annual?year={year}",
            headers=headers,
        )
        assert overview_resp.status == 200, f"annual overview failed: {overview_resp.text()}"
        body = overview_resp.json()

        months = body.get("months", [])
        assert len(months) == 12, f"Expected 12 months, got {len(months)}"

        # July and August should have non-zero totals
        by_month = {m["month"]: m for m in months}
        assert by_month.get("2026-07", {}).get("total_planned", 0) > 0
        assert by_month.get("2026-08", {}).get("total_planned", 0) > 0

    def test_annual_overview_requires_auth(self, api_context: APIRequestContext):
        """Unauthenticated request must be rejected."""
        resp = api_context.get("/overview/annual?year=2026")
        assert resp.status in (401, 403)

    def test_annual_overview_invalid_year_rejected(
        self, api_context: APIRequestContext, auth_token: str
    ):
        """Non-numeric year should return a 4xx error."""
        resp = api_context.get(
            "/overview/annual?year=notayear",
            headers=_auth_headers(auth_token),
        )
        assert 400 <= resp.status < 500
