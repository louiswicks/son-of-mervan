"""
Tests for savings goals and contributions endpoints.

Coverage targets:
  routers/savings.py — GET/POST/PUT/DELETE /savings-goals
                        GET/POST /savings-goals/{id}/contributions
                        DELETE /savings-goals/{id}/contributions/{contrib_id}
"""
from datetime import datetime

import pytest

from database import SavingsGoal, SavingsContribution


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_goal(db, user, name="House Deposit", target_amount=10000.0, target_date=None):
    g = SavingsGoal(user_id=user.id, target_date=target_date)
    g.name = name
    g.target_amount = target_amount
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def _make_contribution(db, goal, amount=500.0, note=None):
    c = SavingsContribution(goal_id=goal.id, contributed_at=datetime.utcnow())
    c.amount = amount
    c.note = note
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


_VALID_GOAL = {"name": "Emergency Fund", "target_amount": 5000.0}


# ---------------------------------------------------------------------------
# Goals CRUD
# ---------------------------------------------------------------------------

class TestSavingsGoalsList:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/savings-goals")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_own_goals(self, auth_client, db, verified_user):
        _make_goal(db, verified_user)
        r = auth_client.get("/savings-goals")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_list_excludes_deleted(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        g.deleted_at = datetime.utcnow()
        db.commit()
        r = auth_client.get("/savings-goals")
        assert r.json() == []

    def test_list_excludes_other_user(self, auth_client, db, second_user):
        _make_goal(db, second_user)
        r = auth_client.get("/savings-goals")
        assert r.json() == []

    def test_unauthenticated(self, client):
        r = client.get("/savings-goals")
        assert r.status_code in (401, 403)


class TestSavingsGoalsCreate:
    def test_create_returns_201(self, auth_client):
        r = auth_client.post("/savings-goals", json=_VALID_GOAL)
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Emergency Fund"
        assert body["target_amount"] == 5000.0
        assert body["current_amount"] == 0.0

    def test_create_with_target_date(self, auth_client):
        payload = {**_VALID_GOAL, "target_date": "2027-01-01T00:00:00"}
        r = auth_client.post("/savings-goals", json=payload)
        assert r.status_code == 201
        assert r.json()["target_date"] is not None

    def test_create_status_no_deadline(self, auth_client):
        r = auth_client.post("/savings-goals", json=_VALID_GOAL)
        assert r.status_code == 201
        assert r.json()["status"] == "no_deadline"

    def test_create_unauthenticated(self, client):
        r = client.post("/savings-goals", json=_VALID_GOAL)
        assert r.status_code in (401, 403)


class TestSavingsGoalsUpdate:
    def test_update_name(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        r = auth_client.put(f"/savings-goals/{g.id}", json={"name": "Vacation Fund"})
        assert r.status_code == 200
        assert r.json()["name"] == "Vacation Fund"

    def test_update_target_amount(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        r = auth_client.put(f"/savings-goals/{g.id}", json={"target_amount": 20000.0})
        assert r.status_code == 200
        assert r.json()["target_amount"] == 20000.0

    def test_update_wrong_user_returns_404(self, auth_client, db, second_user):
        g = _make_goal(db, second_user)
        r = auth_client.put(f"/savings-goals/{g.id}", json={"name": "Hijacked"})
        assert r.status_code == 404

    def test_update_nonexistent_returns_404(self, auth_client):
        r = auth_client.put("/savings-goals/99999", json={"name": "Ghost"})
        assert r.status_code == 404


class TestSavingsGoalsDelete:
    def test_delete_returns_204(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        r = auth_client.delete(f"/savings-goals/{g.id}")
        assert r.status_code == 204

    def test_delete_soft_deletes(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        auth_client.delete(f"/savings-goals/{g.id}")
        db.refresh(g)
        assert g.deleted_at is not None

    def test_deleted_goal_not_listed(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        auth_client.delete(f"/savings-goals/{g.id}")
        r = auth_client.get("/savings-goals")
        assert r.json() == []

    def test_delete_wrong_user_returns_404(self, auth_client, db, second_user):
        g = _make_goal(db, second_user)
        r = auth_client.delete(f"/savings-goals/{g.id}")
        assert r.status_code == 404

    def test_delete_nonexistent_returns_404(self, auth_client):
        r = auth_client.delete("/savings-goals/99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------

class TestSavingsContributions:
    def test_list_contributions_empty(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        r = auth_client.get(f"/savings-goals/{g.id}/contributions")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_contributions_returns_own(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        _make_contribution(db, g, amount=200.0)
        r = auth_client.get(f"/savings-goals/{g.id}/contributions")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["amount"] == 200.0

    def test_list_contributions_wrong_goal_returns_404(self, auth_client, db, second_user):
        g = _make_goal(db, second_user)
        r = auth_client.get(f"/savings-goals/{g.id}/contributions")
        assert r.status_code == 404

    def test_add_contribution(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        r = auth_client.post(f"/savings-goals/{g.id}/contributions", json={"amount": 500.0})
        assert r.status_code == 201
        assert r.json()["amount"] == 500.0

    def test_add_contribution_updates_current_amount(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        auth_client.post(f"/savings-goals/{g.id}/contributions", json={"amount": 100.0})
        auth_client.post(f"/savings-goals/{g.id}/contributions", json={"amount": 200.0})
        r = auth_client.get("/savings-goals")
        goal_data = next(item for item in r.json() if item["id"] == g.id)
        assert goal_data["current_amount"] == 300.0

    def test_add_contribution_with_note(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        r = auth_client.post(
            f"/savings-goals/{g.id}/contributions",
            json={"amount": 50.0, "note": "Birthday money"}
        )
        assert r.status_code == 201
        assert r.json()["note"] == "Birthday money"

    def test_add_contribution_wrong_goal_returns_404(self, auth_client, db, second_user):
        g = _make_goal(db, second_user)
        r = auth_client.post(f"/savings-goals/{g.id}/contributions", json={"amount": 100.0})
        assert r.status_code == 404

    def test_delete_contribution(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        c = _make_contribution(db, g)
        r = auth_client.delete(f"/savings-goals/{g.id}/contributions/{c.id}")
        assert r.status_code == 204

    def test_delete_contribution_updates_current_amount(self, auth_client, db, verified_user):
        g = _make_goal(db, verified_user)
        c1 = _make_contribution(db, g, amount=400.0)
        _make_contribution(db, g, amount=100.0)
        auth_client.delete(f"/savings-goals/{g.id}/contributions/{c1.id}")
        r = auth_client.get("/savings-goals")
        goal_data = next(item for item in r.json() if item["id"] == g.id)
        assert goal_data["current_amount"] == 100.0

    def test_delete_contribution_wrong_goal_returns_404(self, auth_client, db, second_user):
        g = _make_goal(db, second_user)
        c = _make_contribution(db, g)
        r = auth_client.delete(f"/savings-goals/{g.id}/contributions/{c.id}")
        assert r.status_code == 404
