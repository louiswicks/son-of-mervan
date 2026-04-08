"""Tests for POST /import/csv and POST /import/csv/confirm."""
import io
import pytest

from tests.conftest import make_month, make_expense


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _csv_bytes(*rows: str, header: str = "Date,Description,Amount") -> bytes:
    """Build a minimal CSV file as bytes."""
    lines = [header] + list(rows)
    return "\n".join(lines).encode()


def _upload(client, content: bytes, month: str | None = None, filename: str = "test.csv"):
    """POST /import/csv multipart upload."""
    files = {"file": (filename, io.BytesIO(content), "text/csv")}
    data = {}
    if month:
        data["month"] = month
    return client.post("/import/csv", files=files, data=data)


# ---------------------------------------------------------------------------
# Test: unauthenticated access
# ---------------------------------------------------------------------------

class TestCSVPreviewAuth:
    def test_preview_requires_auth(self, client):
        content = _csv_bytes("2026-01-05,Netflix,12.99")
        resp = _upload(client, content)
        assert resp.status_code in (401, 403)

    def test_confirm_requires_auth(self, client):
        resp = client.post("/import/csv/confirm", json={"rows": []})
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test: CSV parsing
# ---------------------------------------------------------------------------

class TestCSVPreview:
    def test_single_row_parsed_correctly(self, auth_client):
        content = _csv_bytes("2026-01-05,Netflix,12.99")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["parse_errors"] == 0
        row = data["rows"][0]
        assert row["description"] == "Netflix"
        assert row["amount"] == 12.99
        assert row["month"] == "2026-01"
        assert row["is_duplicate"] is False

    def test_auto_categorisation_entertainment(self, auth_client):
        content = _csv_bytes("2026-01-05,Spotify Premium,9.99")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["suggested_category"] == "Entertainment"

    def test_auto_categorisation_food(self, auth_client):
        content = _csv_bytes("2026-01-10,Tesco Grocery,45.00")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["suggested_category"] == "Food"

    def test_unknown_description_defaults_to_other(self, auth_client):
        content = _csv_bytes("2026-01-15,ACME Corp Unknown,50.00")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["suggested_category"] == "Other"

    def test_month_inferred_from_date_column(self, auth_client):
        content = _csv_bytes("2026-03-15,Rent Payment,900.00")
        # No month override — should infer 2026-03 from the date
        resp = _upload(auth_client, content)
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["month"] == "2026-03"

    def test_multiple_rows_parsed(self, auth_client):
        content = _csv_bytes(
            "2026-01-01,Rent,1000.00",
            "2026-01-05,Netflix,12.99",
            "2026-01-10,Tesco,55.00",
        )
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    def test_blank_lines_ignored(self, auth_client):
        content = b"Date,Description,Amount\n2026-01-01,Rent,1000.00\n\n\n2026-01-05,Netflix,12.99\n"
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_zero_amounts_skipped_negative_converted(self, auth_client):
        content = _csv_bytes(
            "2026-01-01,Refund,-20.00",   # negative → abs → 20.00, kept
            "2026-01-02,Zero,0.00",        # zero → skipped (parse error)
            "2026-01-03,Valid,10.00",
        )
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        data = resp.json()
        # Zero is a parse error; negatives are converted via abs() and kept
        assert data["total"] == 2
        assert data["parse_errors"] == 1
        descriptions = [r["description"] for r in data["rows"]]
        assert "Valid" in descriptions
        assert "Refund" in descriptions

    def test_empty_file_returns_422(self, auth_client):
        resp = _upload(auth_client, b"")
        assert resp.status_code == 422

    def test_missing_columns_returns_422(self, auth_client):
        content = b"Foo,Bar\n1,2\n"
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 422
        assert "Could not detect" in resp.json()["detail"]

    def test_invalid_month_override_returns_422(self, auth_client):
        content = _csv_bytes("2026-01-01,Rent,1000.00")
        resp = _upload(auth_client, content, month="not-a-month")
        assert resp.status_code == 422

    def test_duplicate_flagged_when_expense_exists(self, auth_client, db, verified_user):
        m = make_month(db, verified_user, month="2026-01")
        make_expense(db, m, name="Netflix", category="Entertainment", actual=12.99)

        content = _csv_bytes("2026-01-10,Netflix,12.99")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["duplicates_count"] == 1
        assert data["rows"][0]["is_duplicate"] is True

    def test_non_duplicate_not_flagged(self, auth_client, db, verified_user):
        m = make_month(db, verified_user, month="2026-01")
        make_expense(db, m, name="Rent", category="Housing", actual=1000.00)

        content = _csv_bytes("2026-01-10,Netflix,12.99")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        assert resp.json()["rows"][0]["is_duplicate"] is False

    def test_cross_user_expenses_not_considered_duplicates(
        self, auth_client, db, verified_user, second_user
    ):
        m2 = make_month(db, second_user, month="2026-01")
        make_expense(db, m2, name="Netflix", category="Entertainment", actual=12.99)

        content = _csv_bytes("2026-01-10,Netflix,12.99")
        resp = _upload(auth_client, content, month="2026-01")
        assert resp.status_code == 200
        # Other user's expense should NOT cause a duplicate flag
        assert resp.json()["rows"][0]["is_duplicate"] is False


# ---------------------------------------------------------------------------
# Test: confirm import
# ---------------------------------------------------------------------------

class TestCSVConfirm:
    def _confirm(self, auth_client, rows):
        return auth_client.post("/import/csv/confirm", json={"rows": rows})

    def test_confirm_creates_new_expense(self, auth_client, db, verified_user):
        make_month(db, verified_user, month="2026-01")

        resp = self._confirm(auth_client, [
            {
                "row_id": "abc",
                "description": "Netflix",
                "amount": 12.99,
                "month": "2026-01",
                "category": "Entertainment",
                "include": True,
            }
        ])
        assert resp.status_code == 200
        assert resp.json()["imported"] == 1
        assert resp.json()["skipped"] == 0

    def test_confirm_skips_excluded_rows(self, auth_client):
        resp = self._confirm(auth_client, [
            {
                "row_id": "xyz",
                "description": "Ignored",
                "amount": 5.00,
                "month": "2026-01",
                "category": "Other",
                "include": False,
            }
        ])
        assert resp.status_code == 200
        assert resp.json()["imported"] == 0
        assert resp.json()["skipped"] == 1

    def test_confirm_updates_existing_actual_amount(self, auth_client, db, verified_user):
        m = make_month(db, verified_user, month="2026-01")
        exp = make_expense(db, m, name="Netflix", category="Entertainment", actual=9.99)

        resp = self._confirm(auth_client, [
            {
                "row_id": "abc",
                "description": "Netflix",
                "amount": 12.99,
                "month": "2026-01",
                "category": "Entertainment",
                "include": True,
            }
        ])
        assert resp.status_code == 200
        assert resp.json()["imported"] == 1
        db.refresh(exp)
        assert float(exp.actual_amount) == 12.99

    def test_confirm_creates_monthly_data_when_missing(self, auth_client, db, verified_user):
        """No MonthlyData exists for 2026-05 — confirm should create it automatically."""
        resp = self._confirm(auth_client, [
            {
                "row_id": "new-month",
                "description": "Phone Bill",
                "amount": 30.00,
                "month": "2026-05",
                "category": "Utilities",
                "include": True,
            }
        ])
        assert resp.status_code == 200
        assert resp.json()["imported"] == 1

    def test_confirm_empty_rows_returns_zero(self, auth_client):
        resp = self._confirm(auth_client, [])
        assert resp.status_code == 200
        assert resp.json()["imported"] == 0
        assert resp.json()["skipped"] == 0

    def test_confirm_invalid_month_skips_row(self, auth_client):
        resp = self._confirm(auth_client, [
            {
                "row_id": "bad",
                "description": "Rent",
                "amount": 1000.00,
                "month": "not-valid",
                "category": "Housing",
                "include": True,
            }
        ])
        assert resp.status_code == 200
        # Invalid month → skipped
        assert resp.json()["skipped"] == 1
        assert resp.json()["imported"] == 0
