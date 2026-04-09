"""
Tests for data export endpoints.

Coverage targets:
  routers/export.py — GET /export/csv, GET /export/pdf, GET /export/calendar.ics
"""
import pytest
from datetime import datetime

from tests.conftest import make_month, make_expense
from database import RecurringExpense


def make_recurring(db, user, name="Rent", category="Housing", amount=1000.0,
                   frequency="monthly", start_date=None, end_date=None):
    """Create a RecurringExpense row owned by *user*."""
    r = RecurringExpense(
        user_id=user.id,
        frequency=frequency,
        start_date=start_date or datetime(2024, 1, 1),
        end_date=end_date,
    )
    r.name = name
    r.category = category
    r.planned_amount = amount
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


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


class TestCalendarExport:
    """Tests for GET /export/calendar.ics."""

    def test_calendar_empty_returns_valid_ical(self, auth_client):
        """No recurring expenses → valid empty VCALENDAR (no VEVENTs)."""
        r = auth_client.get("/export/calendar.ics")
        assert r.status_code == 200
        assert "text/calendar" in r.headers.get("content-type", "")
        body = r.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body
        assert "END:VCALENDAR" in body
        assert "BEGIN:VEVENT" not in body

    def test_calendar_content_disposition(self, auth_client):
        r = auth_client.get("/export/calendar.ics")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "recurring-expenses.ics" in cd

    def test_calendar_with_expense_has_vevent(self, auth_client, db, verified_user):
        make_recurring(db, verified_user, name="Rent", amount=1200.0, frequency="monthly")
        r = auth_client.get("/export/calendar.ics")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "BEGIN:VEVENT" in body
        assert "END:VEVENT" in body
        assert "Rent" in body
        assert "1200.00" in body

    def test_calendar_rrule_frequencies(self, auth_client, db, verified_user):
        """Each frequency maps to the correct RRULE FREQ value."""
        for freq, expected in [
            ("monthly", "FREQ=MONTHLY"),
            ("weekly", "FREQ=WEEKLY"),
            ("daily", "FREQ=DAILY"),
            ("yearly", "FREQ=YEARLY"),
        ]:
            # Clean DB between sub-tests via a fresh recurring each time, but since
            # clean_db runs per test we accumulate all four in one test — that's fine.
            make_recurring(db, verified_user, name=f"Exp-{freq}", frequency=freq)

        r = auth_client.get("/export/calendar.ics")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        for expected in ["FREQ=MONTHLY", "FREQ=WEEKLY", "FREQ=DAILY", "FREQ=YEARLY"]:
            assert expected in body

    def test_calendar_unauthenticated(self, client):
        r = client.get("/export/calendar.ics")
        assert r.status_code in (401, 403)

    def test_calendar_excludes_deleted_expenses(self, auth_client, db, verified_user):
        """Soft-deleted recurring expenses must not appear in the calendar."""
        exp = make_recurring(db, verified_user, name="DeletedRecurring", frequency="monthly")
        exp.deleted_at = datetime.utcnow()
        db.commit()

        r = auth_client.get("/export/calendar.ics")
        assert r.status_code == 200
        assert "DeletedRecurring" not in r.content.decode("utf-8")


class TestGdprExport:
    """Tests for GET /export/gdpr."""

    def test_gdpr_returns_200_with_json(self, auth_client):
        r = auth_client.get("/export/gdpr")
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", "")

    def test_gdpr_unauthenticated(self, client):
        r = client.get("/export/gdpr")
        assert r.status_code in (401, 403)

    def test_gdpr_top_level_keys_present(self, auth_client):
        r = auth_client.get("/export/gdpr")
        assert r.status_code == 200
        body = r.json()
        for key in ("exported_at", "app_version", "profile",
                    "monthly_budgets", "expenses", "savings_goals",
                    "recurring_expenses"):
            assert key in body, f"Missing key: {key}"

    def test_gdpr_content_disposition_header(self, auth_client, verified_user):
        r = auth_client.get("/export/gdpr")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert f"gdpr-export-{verified_user.id}-" in cd
        assert ".json" in cd

    def test_gdpr_includes_expense_data_decrypted(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-05", salary_planned=5000.0)
        make_expense(db, month, name="GDPRGroceries", category="Food",
                     planned=200.0, actual=180.0)

        r = auth_client.get("/export/gdpr")
        assert r.status_code == 200
        body = r.json()
        expense_names = [e["name"] for e in body["expenses"]]
        assert "GDPRGroceries" in expense_names

    def test_gdpr_includes_soft_deleted_expenses(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-06", salary_planned=3000.0)
        exp = make_expense(db, month, name="DeletedItem", category="Other",
                           planned=50.0, actual=50.0)
        exp.deleted_at = datetime.utcnow()
        db.commit()

        r = auth_client.get("/export/gdpr")
        assert r.status_code == 200
        body = r.json()
        expense_names = [e["name"] for e in body["expenses"]]
        assert "DeletedItem" in expense_names

    def test_gdpr_data_isolation(self, auth_client, db, second_user):
        month = make_month(db, second_user, month="2026-07")
        make_expense(db, month, name="OtherUserSecret", category="Other")

        r = auth_client.get("/export/gdpr")
        assert r.status_code == 200
        body = r.json()
        expense_names = [e["name"] for e in body["expenses"]]
        assert "OtherUserSecret" not in expense_names

    def test_gdpr_app_version_is_string(self, auth_client):
        r = auth_client.get("/export/gdpr")
        body = r.json()
        assert isinstance(body["app_version"], str)
        assert len(body["app_version"]) > 0

    def test_gdpr_exported_at_is_iso_string(self, auth_client):
        r = auth_client.get("/export/gdpr")
        body = r.json()
        exported_at = body["exported_at"]
        assert isinstance(exported_at, str)
        # Should parse as a datetime without error
        from datetime import datetime as dt
        dt.fromisoformat(exported_at.replace("Z", "+00:00"))
