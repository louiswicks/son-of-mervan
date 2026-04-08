"""
Tests for the expense search endpoint.

Coverage targets:
  routers/insights.py — GET /insights/search
"""
import pytest

from tests.conftest import make_month, make_expense


class TestExpenseSearch:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/insights/search")
        assert r.status_code in (401, 403)

    def test_empty_db_returns_empty_list(self, auth_client):
        r = auth_client.get("/insights/search")
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    def test_returns_all_expenses_when_no_filters(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Rent", category="Housing", planned=800.0)
        make_expense(db, month, name="Groceries", category="Food", planned=300.0)

        r = auth_client.get("/insights/search")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_keyword_filter_q(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Tesco Express", category="Food")
        make_expense(db, month, name="Amazon Prime", category="Subscriptions")

        r = auth_client.get("/insights/search?q=tesco")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Tesco Express"

    def test_keyword_filter_case_insensitive(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Netflix", category="Subscriptions")

        r = auth_client.get("/insights/search?q=NETFLIX")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_category_filter_exact_match(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Rent", category="Housing")
        make_expense(db, month, name="Groceries", category="Food")
        make_expense(db, month, name="Farmer's Market", category="Food")

        r = auth_client.get("/insights/search?category=Food")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        for item in body["items"]:
            assert item["category"] == "Food"

    def test_category_filter_case_insensitive(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Rent", category="Housing")

        r = auth_client.get("/insights/search?category=housing")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_from_month_filter(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2025-11")
        m2 = make_month(db, verified_user, month="2026-01")
        make_expense(db, m1, name="Old Rent", category="Housing")
        make_expense(db, m2, name="New Rent", category="Housing")

        r = auth_client.get("/insights/search?from=2026-01")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "New Rent"

    def test_to_month_filter(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2025-11")
        m2 = make_month(db, verified_user, month="2026-01")
        make_expense(db, m1, name="Old Rent", category="Housing")
        make_expense(db, m2, name="New Rent", category="Housing")

        r = auth_client.get("/insights/search?to=2025-11")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Old Rent"

    def test_from_and_to_month_range(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2025-10")
        m2 = make_month(db, verified_user, month="2025-12")
        m3 = make_month(db, verified_user, month="2026-02")
        make_expense(db, m1, name="Oct", category="Food")
        make_expense(db, m2, name="Dec", category="Food")
        make_expense(db, m3, name="Feb", category="Food")

        r = auth_client.get("/insights/search?from=2025-11&to=2026-01")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Dec"

    def test_sort_by_amount(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Small", category="Food", planned=50.0)
        make_expense(db, month, name="Big", category="Housing", planned=1500.0)
        make_expense(db, month, name="Medium", category="Food", planned=300.0)

        r = auth_client.get("/insights/search?sort=amount")
        assert r.status_code == 200
        items = r.json()["items"]
        amounts = [i["planned_amount"] for i in items]
        assert amounts == sorted(amounts, reverse=True)

    def test_sort_by_date_default(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2025-06")
        m2 = make_month(db, verified_user, month="2026-03")
        make_expense(db, m1, name="June Rent", category="Housing")
        make_expense(db, m2, name="March Rent", category="Housing")

        r = auth_client.get("/insights/search")
        assert r.status_code == 200
        items = r.json()["items"]
        months = [i["month"] for i in items]
        assert months == sorted(months, reverse=True)

    def test_pagination(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        for i in range(5):
            make_expense(db, month, name=f"Expense {i}", category="Food", planned=float(i * 10))

        r = auth_client.get("/insights/search?page=1&page_size=3")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 5
        assert len(body["items"]) == 3
        assert body["page"] == 1
        assert body["page_size"] == 3

    def test_pagination_page_2(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        for i in range(5):
            make_expense(db, month, name=f"Expense {i}", category="Food", planned=float(i * 10))

        r = auth_client.get("/insights/search?page=2&page_size=3")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2  # remaining 2 on page 2

    def test_deleted_expenses_excluded(self, auth_client, db, verified_user):
        from datetime import datetime
        from database import MonthlyExpense
        month = make_month(db, verified_user, month="2026-01")
        e = make_expense(db, month, name="Deleted Expense", category="Food")
        e.deleted_at = datetime.utcnow()
        db.commit()

        r = auth_client.get("/insights/search")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_response_item_shape(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=810.0)

        r = auth_client.get("/insights/search")
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert "id" in item
        assert "month" in item
        assert "name" in item
        assert "category" in item
        assert "planned_amount" in item
        assert "actual_amount" in item
        assert "currency" in item

    def test_expenses_from_other_users_not_returned(self, auth_client, db, verified_user, second_user):
        other_month = make_month(db, second_user, month="2026-01")
        make_expense(db, other_month, name="Other User Rent", category="Housing")

        r = auth_client.get("/insights/search")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_combined_filters(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2026-01")
        m2 = make_month(db, verified_user, month="2026-03")
        make_expense(db, m1, name="Tesco", category="Food")
        make_expense(db, m1, name="Tesco", category="Housing")
        make_expense(db, m2, name="Tesco", category="Food")

        r = auth_client.get("/insights/search?q=tesco&category=Food&from=2026-01&to=2026-02")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["month"] == "2026-01"
        assert body["items"][0]["category"] == "Food"
