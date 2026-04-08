"""
Tests for the budget templates endpoints.

Coverage targets:
  routers/templates.py — GET /budget-templates
                          POST /budget-templates/{id}/apply
"""
import pytest

from tests.conftest import make_month


class TestListTemplates:
    def test_returns_200_no_auth(self, client):
        r = client.get("/budget-templates")
        assert r.status_code == 200

    def test_returns_five_or_more_templates(self, client):
        r = client.get("/budget-templates")
        templates = r.json()["templates"]
        assert len(templates) >= 5

    def test_each_template_has_required_fields(self, client):
        r = client.get("/budget-templates")
        for t in r.json()["templates"]:
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "allocations" in t
            assert len(t["allocations"]) > 0
            for alloc in t["allocations"]:
                assert "category" in alloc
                assert "pct_of_salary" in alloc

    def test_template_ids_are_unique(self, client):
        r = client.get("/budget-templates")
        ids = [t["id"] for t in r.json()["templates"]]
        assert len(ids) == len(set(ids))


class TestApplyTemplate:
    def test_unauthenticated_returns_401(self, client):
        r = client.post("/budget-templates/student/apply?month=2026-01")
        assert r.status_code in (401, 403)

    def test_unknown_template_returns_404(self, auth_client, db, verified_user):
        make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        r = auth_client.post("/budget-templates/nonexistent/apply?month=2026-01")
        assert r.status_code == 404

    def test_no_salary_returns_400(self, auth_client, db, verified_user):
        # Month exists but salary_planned=0 (default)
        make_month(db, verified_user, month="2026-02", salary_planned=0.0)
        r = auth_client.post("/budget-templates/student/apply?month=2026-02")
        assert r.status_code == 400

    def test_no_month_row_and_no_salary_returns_400(self, auth_client):
        # Month doesn't exist yet — will be created but salary=0 → 400
        r = auth_client.post("/budget-templates/student/apply?month=2026-03")
        assert r.status_code == 400

    def test_apply_creates_expense_rows(self, auth_client, db, verified_user):
        make_month(db, verified_user, month="2026-01", salary_planned=4000.0)
        r = auth_client.post("/budget-templates/student/apply?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        assert body["template_id"] == "student"
        assert body["month"] == "2026-01"
        assert body["created_count"] > 0
        assert len(body["expenses"]) == body["created_count"]

    def test_apply_amounts_match_salary_percentages(self, auth_client, db, verified_user):
        salary = 4000.0
        make_month(db, verified_user, month="2026-01", salary_planned=salary)
        r = auth_client.post("/budget-templates/single-professional/apply?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        # Find Housing (30%) — expected = 4000 * 0.30 = 1200.0
        housing = next((e for e in body["expenses"] if e["category"] == "Housing"), None)
        assert housing is not None
        assert abs(housing["planned_amount"] - salary * 0.30) < 0.01

    def test_apply_is_additive_no_duplicate_rows(self, auth_client, db, verified_user):
        make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        # Apply twice — second call should create 0 new rows
        r1 = auth_client.post("/budget-templates/frugal/apply?month=2026-01")
        assert r1.status_code == 200
        created_first = r1.json()["created_count"]
        assert created_first > 0

        r2 = auth_client.post("/budget-templates/frugal/apply?month=2026-01")
        assert r2.status_code == 200
        assert r2.json()["created_count"] == 0

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.post("/budget-templates/student/apply?month=not-a-month")
        assert r.status_code == 422

    def test_all_known_template_ids_apply_successfully(self, auth_client, db, verified_user):
        known_ids = ["student", "single-professional", "family", "frugal", "high-earner"]
        for i, tid in enumerate(known_ids):
            month = f"2026-{i + 1:02d}"
            make_month(db, verified_user, month=month, salary_planned=5000.0)
            r = auth_client.post(f"/budget-templates/{tid}/apply?month={month}")
            assert r.status_code == 200, f"Template {tid} failed: {r.json()}"
            assert r.json()["created_count"] > 0
