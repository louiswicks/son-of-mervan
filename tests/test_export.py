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
