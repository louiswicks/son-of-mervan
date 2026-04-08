"""
Tests for data export endpoints.

Coverage targets:
  routers/export.py — GET /export/csv, GET /export/pdf
"""
import pytest

from tests.conftest import make_month, make_expense


class TestCSVExport:
    def test_csv_empty_range_returns_200(self, auth_client):
        r = auth_client.get("/export/csv?from=2026-01&to=2026-03")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_csv_with_data(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-02")
        make_expense(db, month, name="Netflix", category="Entertainment", planned=15.0, actual=15.0)

        r = auth_client.get("/export/csv?from=2026-02&to=2026-02")
        assert r.status_code == 200
        content = r.content.decode("utf-8")
        # Header row must be present
        assert "Category" in content or "category" in content.lower()
        # Expense should appear in output
        assert "Netflix" in content

    def test_csv_invalid_from_format(self, auth_client):
        r = auth_client.get("/export/csv?from=Jan-2026&to=2026-03")
        assert r.status_code == 422

    def test_csv_invalid_to_format(self, auth_client):
        r = auth_client.get("/export/csv?from=2026-01&to=March")
        assert r.status_code == 422

    def test_csv_missing_params_uses_defaults_or_422(self, auth_client):
        # Missing required params — either defaults apply (200) or validation fails (422)
        r = auth_client.get("/export/csv")
        assert r.status_code in (200, 422)

    def test_csv_unauthenticated(self, client):
        r = client.get("/export/csv?from=2026-01&to=2026-03")
        assert r.status_code in (401, 403)

    def test_csv_only_own_data(self, auth_client, db, second_user):
        # Expense owned by second_user must not appear in authenticated user's export
        month = make_month(db, second_user, month="2026-01")
        make_expense(db, month, name="SecretExpense", category="Other")

        r = auth_client.get("/export/csv?from=2026-01&to=2026-01")
        assert r.status_code == 200
        assert "SecretExpense" not in r.content.decode("utf-8")


class TestPDFExport:
    def test_pdf_returns_200_or_503(self, auth_client, db, verified_user):
        # 200 when fpdf2 is installed; 503 when it is not (optional dependency)
        make_month(db, verified_user, month="2026-01")
        r = auth_client.get("/export/pdf?month=2026-01")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert "application/pdf" in r.headers.get("content-type", "")

    def test_pdf_no_data_returns_404_or_503(self, auth_client):
        # No MonthlyData → 404. fpdf2 absent → 503 (503 checked before 404 in handler).
        r = auth_client.get("/export/pdf?month=2025-06")
        assert r.status_code in (404, 503)

    def test_pdf_invalid_month_format(self, auth_client):
        # When fpdf2 is absent the handler returns 503 before format validation
        r = auth_client.get("/export/pdf?month=June-2026")
        assert r.status_code in (422, 503)

    def test_pdf_unauthenticated(self, client):
        r = client.get("/export/pdf?month=2026-01")
        assert r.status_code in (401, 403)


class TestTaxSummary:
    """Tests for GET /export/tax-summary (JSON) and GET /export/tax-pdf."""

    def test_tax_summary_empty_year_returns_200(self, auth_client):
        # No data — should still return a valid JSON summary with zeros
        r = auth_client.get("/export/tax-summary?tax_year=2022")
        assert r.status_code == 200
        body = r.json()
        assert body["tax_year"] == 2022
        assert body["total_income"] == 0.0
        assert body["total_expenses"] == 0.0
        assert body["months_with_data"] == 0
        assert body["category_breakdown"] == []

    def test_tax_summary_with_data(self, auth_client, db, verified_user):
        # Create months that fall inside tax year 2025 (Apr 2025 – Mar 2026)
        m1 = make_month(db, verified_user, month="2025-04", salary_actual=3000.0, total_actual=1060.0)
        make_expense(db, m1, name="Rent", category="Housing", planned=1000.0, actual=1000.0)
        make_expense(db, m1, name="Uber", category="Transportation", planned=50.0, actual=60.0)
        m2 = make_month(db, verified_user, month="2026-01", salary_actual=3000.0, total_actual=15.0)
        make_expense(db, m2, name="Netflix", category="Entertainment", planned=15.0, actual=15.0)

        r = auth_client.get("/export/tax-summary?tax_year=2025")
        assert r.status_code == 200
        body = r.json()
        assert body["tax_year"] == 2025
        assert body["period_start"] == "2025-04-06"
        assert body["period_end"] == "2026-04-05"
        assert body["months_with_data"] == 2
        assert body["total_income"] == 6000.0

        # All three expenses should be reflected in category_breakdown
        cats = {c["category"] for c in body["category_breakdown"]}
        assert "Housing" in cats
        assert "Transportation" in cats
        assert "Entertainment" in cats

        # Housing and Transportation are potentially deductible; Entertainment is not
        for c in body["category_breakdown"]:
            if c["category"] in ("Housing", "Transportation"):
                assert c["potentially_deductible"] is True
            elif c["category"] == "Entertainment":
                assert c["potentially_deductible"] is False

        assert body["potentially_deductible_total"] > 0

    def test_tax_summary_only_own_data(self, auth_client, db, second_user):
        # Expenses from second_user must not appear in authenticated user's summary
        m = make_month(db, second_user, month="2025-05", salary_actual=5000.0)
        make_expense(db, m, name="OtherRent", category="Housing", planned=1200.0, actual=1200.0)

        r = auth_client.get("/export/tax-summary?tax_year=2025")
        assert r.status_code == 200
        body = r.json()
        assert body["total_income"] == 0.0
        assert body["category_breakdown"] == []

    def test_tax_summary_months_outside_year_excluded(self, auth_client, db, verified_user):
        # Month 2025-03 is in tax year 2024 (Apr 2024 – Mar 2025), not 2025
        m = make_month(db, verified_user, month="2025-03", salary_actual=3000.0)
        make_expense(db, m, name="OldRent", category="Housing", planned=800.0, actual=800.0)

        r = auth_client.get("/export/tax-summary?tax_year=2025")
        assert r.status_code == 200
        body = r.json()
        # 2025-03 should NOT appear in tax year 2025
        assert body["months_with_data"] == 0

    def test_tax_summary_invalid_year_too_old(self, auth_client):
        r = auth_client.get("/export/tax-summary?tax_year=1999")
        assert r.status_code == 422

    def test_tax_summary_invalid_year_too_future(self, auth_client):
        r = auth_client.get("/export/tax-summary?tax_year=2099")
        assert r.status_code == 422

    def test_tax_summary_unauthenticated(self, client):
        r = client.get("/export/tax-summary?tax_year=2024")
        assert r.status_code in (401, 403)

    def test_tax_pdf_returns_200_or_503(self, auth_client, db, verified_user):
        # Create data so 404 is not triggered
        make_month(db, verified_user, month="2025-06")
        r = auth_client.get("/export/tax-pdf?tax_year=2025")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert "application/pdf" in r.headers.get("content-type", "")
            assert "tax_summary_2025_2026.pdf" in r.headers.get("content-disposition", "")

    def test_tax_pdf_unauthenticated(self, client):
        r = client.get("/export/tax-pdf?tax_year=2024")
        assert r.status_code in (401, 403)

    def test_tax_pdf_invalid_year(self, auth_client):
        r = auth_client.get("/export/tax-pdf?tax_year=1990")
        assert r.status_code in (422, 503)


class TestFullBackupExport:
    """Tests for GET /export/full-backup."""

    def test_full_backup_returns_200_with_json(self, auth_client):
        r = auth_client.get("/export/full-backup")
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", "")
        body = r.json()
        assert "profile" in body
        assert "months" in body
        assert "recurring_expenses" in body
        assert "savings_goals" in body
        assert "debts" in body
        assert "categories" in body
        assert "net_worth_snapshots" in body

    def test_full_backup_unauthenticated(self, client):
        r = client.get("/export/full-backup")
        assert r.status_code in (401, 403)

    def test_full_backup_content_disposition_header(self, auth_client):
        r = auth_client.get("/export/full-backup")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "backup-" in cd
        assert ".json" in cd

    def test_full_backup_includes_expense_data(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-03", salary_planned=4000.0)
        make_expense(db, month, name="Groceries", category="Food", planned=300.0, actual=280.0)

        r = auth_client.get("/export/full-backup")
        assert r.status_code == 200
        body = r.json()
        months = body["months"]
        assert any(m["month"] == "2026-03" for m in months)
        march = next(m for m in months if m["month"] == "2026-03")
        expense_names = [e["name"] for e in march["expenses"]]
        assert "Groceries" in expense_names

    def test_full_backup_only_own_data(self, auth_client, db, second_user):
        # Expense owned by second_user must not appear in authenticated user's backup
        month = make_month(db, second_user, month="2026-04")
        make_expense(db, month, name="OtherSecret", category="Other")

        r = auth_client.get("/export/full-backup")
        assert r.status_code == 200
        body = r.json()
        all_expense_names = [
            e["name"]
            for m in body["months"]
            for e in m["expenses"]
        ]
        assert "OtherSecret" not in all_expense_names
