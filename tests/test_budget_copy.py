"""Tests for POST /budget/copy-forward (Phase 18.1)."""
import pytest
from tests.conftest import make_month, make_expense


class TestBudgetCopyForward:

    # ── Auth ────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_401(self, client):
        r = client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        assert r.status_code in (401, 403)

    # ── Validation ──────────────────────────────────────────────────────────

    def test_same_month_returns_400(self, auth_client):
        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-03", "to_month": "2026-03"},
        )
        assert r.status_code == 400

    def test_invalid_from_month_format_returns_422(self, auth_client):
        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026/03", "to_month": "2026-04"},
        )
        assert r.status_code == 422

    def test_invalid_to_month_format_returns_422(self, auth_client):
        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-03", "to_month": "bad"},
        )
        assert r.status_code == 422

    def test_missing_from_month_no_data_returns_404(self, auth_client):
        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2025-01", "to_month": "2026-04"},
        )
        assert r.status_code == 404

    # ── Happy-path copy ──────────────────────────────────────────────────────

    def test_copies_expenses_to_empty_destination(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, month, name="Rent", category="Housing", planned=900.0)
        make_expense(db, month, name="Groceries", category="Food", planned=300.0)

        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["copied"] == 2
        assert body["skipped"] == 0
        assert body["from_month"] == "2026-01"
        assert body["to_month"] == "2026-02"

    def test_copies_salary_when_destination_has_none(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01", salary_planned=2500.0)
        make_expense(db, month, name="Rent", category="Housing", planned=800.0)

        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        assert r.status_code == 200

        # Verify destination month has salary
        r2 = auth_client.get("/monthly-tracker/2026-02")
        assert r2.status_code == 200
        assert r2.json()["salary_planned"] == 2500.0

    def test_skips_existing_expenses_in_destination(self, auth_client, db, verified_user):
        src = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, src, name="Rent", category="Housing", planned=900.0)
        make_expense(db, src, name="Groceries", category="Food", planned=300.0)

        # Pre-populate destination with one of the same expenses
        dest = make_month(db, verified_user, month="2026-02", salary_planned=3000.0)
        make_expense(db, dest, name="Rent", category="Housing", planned=950.0)

        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["copied"] == 1   # only Groceries
        assert body["skipped"] == 1  # Rent already exists

    def test_does_not_overwrite_existing_salary(self, auth_client, db, verified_user):
        src = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, src, name="Rent", category="Housing", planned=900.0)

        dest = make_month(db, verified_user, month="2026-02", salary_planned=4000.0)

        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        assert r.status_code == 200

        # salary_planned in destination should still be 4000 (not overwritten)
        r2 = auth_client.get("/monthly-tracker/2026-02")
        assert r2.json()["salary_planned"] == 4000.0

    def test_recalculates_totals_after_copy(self, auth_client, db, verified_user):
        src = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, src, name="Rent", category="Housing", planned=900.0)
        make_expense(db, src, name="Groceries", category="Food", planned=300.0)

        auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )

        r = auth_client.get("/monthly-tracker/2026-02")
        assert r.status_code == 200
        body = r.json()
        # total_planned should reflect both copied expenses
        row_totals = sum(row["projected"] for row in body["rows"])
        assert row_totals == pytest.approx(1200.0)

    # ── Data isolation ───────────────────────────────────────────────────────

    def test_cannot_copy_another_users_month(self, auth_client, db, second_user):
        other_month = make_month(db, second_user, month="2026-01", salary_planned=5000.0)
        make_expense(db, other_month, name="Rent", category="Housing", planned=1500.0)

        # auth_client is verified_user; other data belongs to second_user
        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        # Should return 404 (no data found for authenticated user)
        assert r.status_code == 404

    # ── Source with no expenses ──────────────────────────────────────────────

    def test_source_with_no_expenses_returns_404(self, auth_client, db, verified_user):
        make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        # No expenses added

        r = auth_client.post(
            "/budget/copy-forward",
            json={"from_month": "2026-01", "to_month": "2026-02"},
        )
        assert r.status_code == 404
