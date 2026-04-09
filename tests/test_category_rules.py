"""
Tests for Phase 19.2 — Auto-categorization Rules.

Covers:
- CRUD (create, read, update, delete)
- Ownership enforcement (user A cannot see/edit/delete user B's rules)
- apply endpoint: re-categorizes matching expenses, returns count
- apply: no match → count=0
- apply: no rules → count=0
- apply: month not found → 404
- Auto-apply on POST /monthly-tracker/{month} for new expenses
- Priority ordering (lowest priority wins first)
- Case-insensitive pattern matching
"""
import pytest

from tests.conftest import make_expense, make_month


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_rule(client, pattern, category, priority=0):
    r = client.post(
        "/category-rules",
        json={"pattern": pattern, "category": category, "priority": priority},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_create_rule_returns_201(auth_client):
    r = auth_client.post(
        "/category-rules",
        json={"pattern": "netflix", "category": "Entertainment", "priority": 1},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["pattern"] == "netflix"
    assert body["category"] == "Entertainment"
    assert body["priority"] == 1
    assert "id" in body


def test_list_rules_empty(auth_client):
    r = auth_client.get("/category-rules")
    assert r.status_code == 200
    assert r.json() == []


def test_list_rules_returns_all_owned(auth_client):
    _create_rule(auth_client, "spotify", "Entertainment", priority=2)
    _create_rule(auth_client, "tesco", "Food", priority=1)
    r = auth_client.get("/category-rules")
    assert r.status_code == 200
    rules = r.json()
    assert len(rules) == 2
    # sorted by priority asc
    assert rules[0]["priority"] <= rules[1]["priority"]


def test_update_rule(auth_client):
    rule = _create_rule(auth_client, "amazon", "Shopping", priority=5)
    r = auth_client.put(
        f"/category-rules/{rule['id']}",
        json={"category": "Entertainment", "priority": 10},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["category"] == "Entertainment"
    assert updated["priority"] == 10
    assert updated["pattern"] == "amazon"


def test_delete_rule_soft(auth_client):
    rule = _create_rule(auth_client, "gym", "Health")
    r = auth_client.delete(f"/category-rules/{rule['id']}")
    assert r.status_code == 204

    # Should no longer appear in list
    rules = auth_client.get("/category-rules").json()
    assert all(x["id"] != rule["id"] for x in rules)


def test_delete_nonexistent_rule_returns_404(auth_client):
    r = auth_client.delete("/category-rules/999999")
    assert r.status_code == 404


def test_update_nonexistent_rule_returns_404(auth_client):
    r = auth_client.put("/category-rules/999999", json={"pattern": "x"})
    assert r.status_code == 404


# ── Ownership enforcement ─────────────────────────────────────────────────────

def test_list_rules_isolation(db, auth_client, second_user):
    """User A's rules must not appear when user B lists rules."""
    from database import CategoryRule

    # Create a rule directly for second_user
    rule = CategoryRule(user_id=second_user.id, pattern="starbucks", priority=0)
    rule.category = "Coffee"
    db.add(rule)
    db.commit()

    # auth_client is user A — should see zero rules
    rules = auth_client.get("/category-rules").json()
    assert rules == []


def test_delete_other_users_rule_returns_404(db, auth_client, second_user):
    from database import CategoryRule

    rule = CategoryRule(user_id=second_user.id, pattern="bp", priority=0)
    rule.category = "Transportation"
    db.add(rule)
    db.commit()

    r = auth_client.delete(f"/category-rules/{rule.id}")
    assert r.status_code == 404


# ── Apply endpoint ────────────────────────────────────────────────────────────

def test_apply_no_rules_returns_zero(auth_client, db, verified_user):
    month_row = make_month(db, verified_user, month="2026-02")
    make_expense(db, month_row, name="Tesco Food Shop", category="Uncategorized")

    r = auth_client.post("/category-rules/apply?month=2026-02")
    assert r.status_code == 200
    assert r.json()["updated"] == 0


def test_apply_updates_matching_expenses(auth_client, db, verified_user):
    _create_rule(auth_client, "tesco", "Food")
    month_row = make_month(db, verified_user, month="2026-03")
    make_expense(db, month_row, name="Tesco Food Shop", category="Uncategorized")

    r = auth_client.post("/category-rules/apply?month=2026-03")
    assert r.status_code == 200
    assert r.json()["updated"] == 1


def test_apply_case_insensitive(auth_client, db, verified_user):
    _create_rule(auth_client, "NETFLIX", "Entertainment")
    month_row = make_month(db, verified_user, month="2026-04")
    make_expense(db, month_row, name="netflix subscription", category="Other")

    r = auth_client.post("/category-rules/apply?month=2026-04")
    assert r.status_code == 200
    assert r.json()["updated"] == 1


def test_apply_no_match_returns_zero(auth_client, db, verified_user):
    _create_rule(auth_client, "netflix", "Entertainment")
    month_row = make_month(db, verified_user, month="2026-05")
    make_expense(db, month_row, name="Amazon Prime", category="Other")

    r = auth_client.post("/category-rules/apply?month=2026-05")
    assert r.status_code == 200
    assert r.json()["updated"] == 0


def test_apply_month_not_found_returns_404(auth_client):
    r = auth_client.post("/category-rules/apply?month=2020-01")
    assert r.status_code == 404


def test_apply_invalid_month_returns_422(auth_client):
    r = auth_client.post("/category-rules/apply?month=bad-month")
    assert r.status_code == 422


def test_apply_priority_ordering(auth_client, db, verified_user):
    """Priority 0 wins over priority 10 — expense gets Food, not Transport."""
    _create_rule(auth_client, "tesco", "Food", priority=0)
    _create_rule(auth_client, "tesco", "Transport", priority=10)

    month_row = make_month(db, verified_user, month="2026-06")
    make_expense(db, month_row, name="Tesco Petrol", category="Other")

    auth_client.post("/category-rules/apply?month=2026-06")

    # Verify the expense now has the highest-priority (lowest int) category
    from database import MonthlyExpense
    from tests.conftest import SessionLocal

    db2 = SessionLocal()
    try:
        exp = db2.query(MonthlyExpense).filter(
            MonthlyExpense.monthly_data_id == month_row.id
        ).first()
        assert exp.category == "Food"
    finally:
        db2.close()


# ── Auto-apply on POST /monthly-tracker ───────────────────────────────────────

def test_auto_apply_on_monthly_tracker_post(auth_client, db, verified_user):
    """Rules should auto-categorize new expenses submitted via monthly-tracker."""
    _create_rule(auth_client, "netflix", "Entertainment")

    r = auth_client.post(
        "/monthly-tracker/2026-07",
        json={
            "salary": 3000,
            "expenses": [
                {"name": "Netflix Monthly", "amount": 15.99, "category": "Other"}
            ],
        },
    )
    assert r.status_code == 200

    # Verify category was overridden to Entertainment
    from database import MonthlyData, MonthlyExpense

    months = db.query(MonthlyData).filter(MonthlyData.user_id == verified_user.id).all()
    month_row = next((m for m in months if m.month == "2026-07"), None)
    assert month_row is not None

    expenses = (
        db.query(MonthlyExpense)
        .filter(MonthlyExpense.monthly_data_id == month_row.id)
        .all()
    )
    netflix_exp = next((e for e in expenses if "netflix" in (e.name or "").lower()), None)
    assert netflix_exp is not None
    assert netflix_exp.category == "Entertainment"


# ── Auth required ─────────────────────────────────────────────────────────────

def test_list_rules_requires_auth(client):
    r = client.get("/category-rules")
    assert r.status_code in (401, 403)


def test_create_rule_requires_auth(client):
    r = client.post(
        "/category-rules",
        json={"pattern": "x", "category": "Food", "priority": 0},
    )
    assert r.status_code in (401, 403)


def test_apply_requires_auth(client):
    r = client.post("/category-rules/apply?month=2026-01")
    assert r.status_code in (401, 403)
