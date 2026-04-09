"""
Tests for GET /reports/quarterly
"""
import pytest
from tests.conftest import make_month, make_expense


class TestQuarterlyReport:
    # ── auth ──────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/reports/quarterly?year=2026&quarter=1")
        assert r.status_code in (401, 403)

    # ── validation ────────────────────────────────────────────────────────────

    def test_quarter_below_range_returns_422(self, auth_client):
        r = auth_client.get("/reports/quarterly?year=2026&quarter=0")
        assert r.status_code == 422

    def test_quarter_above_range_returns_422(self, auth_client):
        r = auth_client.get("/reports/quarterly?year=2026&quarter=5")
        assert r.status_code == 422

    def test_missing_year_returns_422(self, auth_client):
        r = auth_client.get("/reports/quarterly?quarter=1")
        assert r.status_code == 422

    def test_missing_quarter_returns_422(self, auth_client):
        r = auth_client.get("/reports/quarterly?year=2026")
        assert r.status_code == 422

    # ── no data ───────────────────────────────────────────────────────────────

    def test_no_data_returns_zeroed_totals(self, auth_client):
        r = auth_client.get("/reports/quarterly?year=2025&quarter=2")
        assert r.status_code == 200
        body = r.json()
        assert body["quarter"] == 2
        assert body["year"] == 2025
        assert body["totals"]["salary_total"] == 0.0
        assert body["totals"]["expense_total"] == 0.0
        assert body["totals"]["savings_total"] == 0.0
        assert body["totals"]["savings_rate_pct"] is None
        # all 3 months should be placeholders
        assert len(body["months"]) == 3
        for m in body["months"]:
            assert m["has_data"] is False

    # ── happy path ────────────────────────────────────────────────────────────

    def test_returns_3_months_for_each_quarter(self, auth_client):
        for q in range(1, 5):
            r = auth_client.get(f"/reports/quarterly?year=2026&quarter={q}")
            assert r.status_code == 200
            assert len(r.json()["months"]) == 3

    def test_correct_month_labels_per_quarter(self, auth_client):
        expected = {
            1: ["2026-01", "2026-02", "2026-03"],
            2: ["2026-04", "2026-05", "2026-06"],
            3: ["2026-07", "2026-08", "2026-09"],
            4: ["2026-10", "2026-11", "2026-12"],
        }
        for q, months in expected.items():
            body = auth_client.get(f"/reports/quarterly?year=2026&quarter={q}").json()
            assert [m["month"] for m in body["months"]] == months

    def test_full_quarter_calculates_totals(self, auth_client, db, verified_user):
        for month_str in ("2026-01", "2026-02", "2026-03"):
            make_month(
                db, verified_user,
                month=month_str,
                salary_actual=3000.0,
                total_actual=1200.0,
            )
        r = auth_client.get("/reports/quarterly?year=2026&quarter=1")
        assert r.status_code == 200
        body = r.json()
        totals = body["totals"]
        assert totals["salary_total"] == pytest.approx(9000.0)
        assert totals["expense_total"] == pytest.approx(3600.0)
        assert totals["savings_total"] == pytest.approx(5400.0)
        assert totals["savings_rate_pct"] == pytest.approx(60.0)

    def test_partial_quarter_includes_zeroed_missing_months(self, auth_client, db, verified_user):
        # Only January has data; February and March are missing
        make_month(
            db, verified_user,
            month="2026-01",
            salary_actual=4000.0,
            total_actual=1000.0,
        )
        r = auth_client.get("/reports/quarterly?year=2026&quarter=1")
        assert r.status_code == 200
        body = r.json()
        months = {m["month"]: m for m in body["months"]}
        assert months["2026-01"]["has_data"] is True
        assert months["2026-02"]["has_data"] is False
        assert months["2026-03"]["has_data"] is False
        # Totals only reflect the one month with data
        assert body["totals"]["salary_total"] == pytest.approx(4000.0)
        assert body["totals"]["expense_total"] == pytest.approx(1000.0)

    def test_savings_rate_null_when_salary_zero(self, auth_client, db, verified_user):
        make_month(
            db, verified_user,
            month="2026-04",
            salary_actual=0.0,
            total_actual=200.0,
        )
        r = auth_client.get("/reports/quarterly?year=2026&quarter=2")
        assert r.status_code == 200
        body = r.json()
        months = {m["month"]: m for m in body["months"]}
        assert months["2026-04"]["savings_rate_pct"] is None
        assert body["totals"]["savings_rate_pct"] is None

    def test_data_isolation(self, auth_client, db, second_user):
        # Data owned by second_user should not appear in auth_client's response
        make_month(
            db, second_user,
            month="2026-01",
            salary_actual=9999.0,
            total_actual=5000.0,
        )
        r = auth_client.get("/reports/quarterly?year=2026&quarter=1")
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["salary_total"] == 0.0
