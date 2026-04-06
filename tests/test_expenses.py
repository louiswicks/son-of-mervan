"""Tests for individual expense CRUD and monthly tracker endpoints."""
from datetime import datetime

import pytest

from conftest import TEST_EMAIL, make_expense, make_month
from database import MonthlyExpense


class TestUpdateExpense:
    def test_update_name(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month)

        r = auth_client.put(f"/expenses/{expense.id}", json={"name": "New Rent"})
        assert r.status_code == 200
        assert r.json()["name"] == "New Rent"
        assert r.json()["category"] == "Housing"  # unchanged

    def test_update_category(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month, name="Car", category="Transportation")

        r = auth_client.put(f"/expenses/{expense.id}", json={"category": "Other"})
        assert r.status_code == 200
        assert r.json()["category"] == "Other"

    def test_update_planned_amount(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month, planned=800.0, actual=750.0)

        r = auth_client.put(f"/expenses/{expense.id}", json={"planned_amount": 900.0})
        assert r.status_code == 200
        assert r.json()["planned_amount"] == 900.0
        assert r.json()["actual_amount"] == 750.0  # unchanged

    def test_update_actual_amount(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month, planned=800.0, actual=0.0)

        r = auth_client.put(f"/expenses/{expense.id}", json={"actual_amount": 820.0})
        assert r.status_code == 200
        assert r.json()["actual_amount"] == 820.0

    def test_update_wrong_user_returns_403(self, auth_client, db, second_user):
        """auth_client is authenticated as TEST_EMAIL; second_user owns the expense."""
        month = make_month(db, second_user)
        expense = make_expense(db, month)

        r = auth_client.put(f"/expenses/{expense.id}", json={"name": "Hacked"})
        assert r.status_code == 403

    def test_update_nonexistent_returns_404(self, auth_client):
        r = auth_client.put("/expenses/99999", json={"name": "Ghost"})
        assert r.status_code == 404

    def test_update_soft_deleted_returns_404(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month)
        expense.deleted_at = datetime.utcnow()
        db.commit()

        r = auth_client.put(f"/expenses/{expense.id}", json={"name": "Ghost"})
        assert r.status_code == 404


class TestDeleteExpense:
    def test_delete_success_returns_204(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month)

        r = auth_client.delete(f"/expenses/{expense.id}")
        assert r.status_code == 204

    def test_delete_sets_deleted_at_in_db(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month)
        exp_id = expense.id

        auth_client.delete(f"/expenses/{expense.id}")

        db_expense = db.query(MonthlyExpense).filter(MonthlyExpense.id == exp_id).first()
        assert db_expense.deleted_at is not None

    def test_delete_wrong_user_returns_403(self, auth_client, db, second_user):
        month = make_month(db, second_user)
        expense = make_expense(db, month)

        r = auth_client.delete(f"/expenses/{expense.id}")
        assert r.status_code == 403

    def test_delete_already_deleted_returns_404(self, auth_client, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month)
        expense.deleted_at = datetime.utcnow()
        db.commit()

        r = auth_client.delete(f"/expenses/{expense.id}")
        assert r.status_code == 404

    def test_delete_nonexistent_returns_404(self, auth_client):
        r = auth_client.delete("/expenses/99999")
        assert r.status_code == 404


class TestMonthlyTrackerGet:
    def test_empty_month_returns_zero_totals(self, auth_client):
        r = auth_client.get("/monthly-tracker/2026-01")
        assert r.status_code == 200
        data = r.json()
        assert data["month"] == "2026-01"
        assert data["salary_planned"] == 0.0
        assert data["expenses"]["items"] == []
        assert data["expenses"]["total"] == 0

    def test_returns_all_active_expenses(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-02")
        make_expense(db, month, "Rent", "Housing", 800, 800)
        make_expense(db, month, "Groceries", "Food", 200, 250)

        r = auth_client.get("/monthly-tracker/2026-02")
        data = r.json()
        assert data["expenses"]["total"] == 2
        assert len(data["expenses"]["items"]) == 2

    def test_excludes_soft_deleted_expenses(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-03")
        deleted = make_expense(db, month, "Deleted", "Other", 100, 100)
        deleted.deleted_at = datetime.utcnow()
        db.commit()
        make_expense(db, month, "Active", "Food", 50, 50)

        r = auth_client.get("/monthly-tracker/2026-03")
        data = r.json()
        assert data["expenses"]["total"] == 1
        assert data["expenses"]["items"][0]["name"] == "Active"

    def test_category_filter(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-04")
        make_expense(db, month, "Rent", "Housing", 800, 800)
        make_expense(db, month, "Groceries", "Food", 200, 250)
        make_expense(db, month, "Gym", "Health", 50, 50)

        r = auth_client.get("/monthly-tracker/2026-04?category=Housing")
        data = r.json()
        items = data["expenses"]["items"]
        assert len(items) == 1
        assert items[0]["category"] == "Housing"

    def test_pagination_respects_page_size(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-05")
        for i in range(7):
            make_expense(db, month, f"Expense{i}", "Food", 50, 50)

        r = auth_client.get("/monthly-tracker/2026-05?page=1&page_size=3")
        data = r.json()
        assert data["expenses"]["total"] == 7
        assert data["expenses"]["pages"] == 3
        assert len(data["expenses"]["items"]) == 3

    def test_pagination_second_page(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-06")
        for i in range(5):
            make_expense(db, month, f"Expense{i}", "Food", 50, 50)

        r = auth_client.get("/monthly-tracker/2026-06?page=2&page_size=3")
        data = r.json()
        assert len(data["expenses"]["items"]) == 2  # remaining 2 items on page 2

    def test_includes_salary_totals(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-07", salary_planned=3500.0)

        r = auth_client.get("/monthly-tracker/2026-07")
        assert r.json()["salary_planned"] == 3500.0

    def test_expense_item_has_id_field(self, auth_client, db, verified_user):
        """Items must include DB id so the frontend can target CRUD operations."""
        month = make_month(db, verified_user, "2026-08")
        expense = make_expense(db, month)

        r = auth_client.get("/monthly-tracker/2026-08")
        item = r.json()["expenses"]["items"][0]
        assert item["id"] == expense.id

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.get("/monthly-tracker/2026/01")
        assert r.status_code in (404, 422)  # path routing


class TestMonthlyTrackerPost:
    def test_save_new_actuals(self, auth_client):
        r = auth_client.post("/monthly-tracker/2026-09", json={
            "salary": 3000,
            "expenses": [
                {"name": "Groceries", "amount": 280, "category": "Food"},
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["salary"] == 3000.0
        assert data["total_actual"] == 280.0

    def test_save_actuals_updates_existing_expense(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-10")
        make_expense(db, month, "Rent", "Housing", planned=800.0, actual=0.0)

        r = auth_client.post("/monthly-tracker/2026-10", json={
            "salary": 3000,
            "expenses": [{"name": "Rent", "amount": 790, "category": "Housing"}],
        })
        assert r.status_code == 200
        assert r.json()["total_actual"] == 790.0

    def test_save_actuals_preserves_planned_amount(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, "2026-11")
        expense = make_expense(db, month, "Rent", "Housing", planned=800.0, actual=0.0)

        auth_client.post("/monthly-tracker/2026-11", json={
            "salary": 3000,
            "expenses": [{"name": "Rent", "amount": 790, "category": "Housing"}],
        })

        db.refresh(expense)
        assert expense.planned_amount == 800.0  # planned untouched
        assert expense.actual_amount == 790.0

    def test_remaining_actual_calculated_correctly(self, auth_client):
        r = auth_client.post("/monthly-tracker/2026-12", json={
            "salary": 3000,
            "expenses": [{"name": "Rent", "amount": 1000, "category": "Housing"}],
        })
        assert r.json()["remaining_actual"] == 2000.0
