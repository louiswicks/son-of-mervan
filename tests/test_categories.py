"""
Tests for the custom expense categories endpoints.

Coverage targets:
  routers/categories.py — GET /categories
                           POST /categories
                           PUT /categories/{id}
                           DELETE /categories/{id}
"""
import pytest

from database import UserCategory, DEFAULT_CATEGORIES
from tests.conftest import TEST_EMAIL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_custom_category(db, user, name="Pets", color="#ff00ff"):
    cat = UserCategory(user_id=user.id, name=name, color=color, is_default=False)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# GET /categories
# ---------------------------------------------------------------------------

class TestListCategories:
    def test_seeds_defaults_on_first_call(self, auth_client, db, verified_user):
        """First GET seeds the 8 default categories and returns them."""
        r = auth_client.get("/categories")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 8
        names = {c["name"] for c in data}
        assert "Housing" in names
        assert "Food" in names
        assert "Other" in names

    def test_defaults_flagged_is_default_true(self, auth_client):
        r = auth_client.get("/categories")
        assert r.status_code == 200
        assert all(c["is_default"] for c in r.json())

    def test_second_call_does_not_duplicate(self, auth_client):
        """Two consecutive GETs must return the same 8 rows, not 16."""
        auth_client.get("/categories")
        r = auth_client.get("/categories")
        assert r.status_code == 200
        assert len(r.json()) == 8

    def test_returns_custom_categories_too(self, auth_client, db, verified_user):
        auth_client.get("/categories")  # seed defaults
        _make_custom_category(db, verified_user, name="Pets")
        r = auth_client.get("/categories")
        assert r.status_code == 200
        assert any(c["name"] == "Pets" for c in r.json())

    def test_unauthenticated_returns_4xx(self, client):
        r = client.get("/categories")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /categories
# ---------------------------------------------------------------------------

class TestCreateCategory:
    def test_create_custom_category(self, auth_client):
        r = auth_client.post("/categories", json={"name": "Pets", "color": "#ff0000"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Pets"
        assert body["color"] == "#ff0000"
        assert body["is_default"] is False

    def test_create_appears_in_list(self, auth_client):
        auth_client.post("/categories", json={"name": "Gym", "color": "#00ff00"})
        r = auth_client.get("/categories")
        names = [c["name"] for c in r.json()]
        assert "Gym" in names

    def test_duplicate_name_returns_409(self, auth_client):
        auth_client.post("/categories", json={"name": "Gym", "color": "#00ff00"})
        r = auth_client.post("/categories", json={"name": "Gym", "color": "#0000ff"})
        assert r.status_code == 409

    def test_duplicate_existing_default_returns_409(self, auth_client):
        r = auth_client.post("/categories", json={"name": "Housing", "color": "#aabbcc"})
        assert r.status_code == 409

    def test_unauthenticated_returns_4xx(self, client):
        r = client.post("/categories", json={"name": "Pets", "color": "#ff0000"})
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /categories/{id}
# ---------------------------------------------------------------------------

class TestUpdateCategory:
    def test_rename_custom_category(self, auth_client, db, verified_user):
        auth_client.get("/categories")  # seed
        cat = _make_custom_category(db, verified_user, name="Pets")
        r = auth_client.put(f"/categories/{cat.id}", json={"name": "Animals"})
        assert r.status_code == 200
        assert r.json()["name"] == "Animals"

    def test_recolour_default_category(self, auth_client, db, verified_user):
        """Default categories can be recoloured."""
        auth_client.get("/categories")  # seed
        cats = db.query(UserCategory).filter(
            UserCategory.user_id == verified_user.id,
            UserCategory.is_default == True,
        ).all()
        housing = next(c for c in cats if c.name == "Housing")
        r = auth_client.put(f"/categories/{housing.id}", json={"color": "#123456"})
        assert r.status_code == 200
        assert r.json()["color"] == "#123456"

    def test_rename_to_existing_returns_409(self, auth_client, db, verified_user):
        auth_client.get("/categories")  # seed
        cat = _make_custom_category(db, verified_user, name="Pets")
        r = auth_client.put(f"/categories/{cat.id}", json={"name": "Housing"})
        assert r.status_code == 409

    def test_not_found_returns_404(self, auth_client):
        r = auth_client.put("/categories/99999", json={"name": "X"})
        assert r.status_code == 404

    def test_cannot_update_other_users_category(self, auth_client, db, second_user):
        cat = _make_custom_category(db, second_user, name="OtherUserCat")
        r = auth_client.put(f"/categories/{cat.id}", json={"name": "Stolen"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /categories/{id}
# ---------------------------------------------------------------------------

class TestDeleteCategory:
    def test_delete_custom_category(self, auth_client, db, verified_user):
        auth_client.get("/categories")  # seed
        cat = _make_custom_category(db, verified_user, name="Pets")
        r = auth_client.delete(f"/categories/{cat.id}")
        assert r.status_code == 204
        assert db.query(UserCategory).filter(UserCategory.id == cat.id).first() is None

    def test_delete_default_returns_400(self, auth_client, db, verified_user):
        auth_client.get("/categories")  # seed
        cats = db.query(UserCategory).filter(
            UserCategory.user_id == verified_user.id,
            UserCategory.is_default == True,
        ).all()
        r = auth_client.delete(f"/categories/{cats[0].id}")
        assert r.status_code == 400

    def test_delete_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/categories/99999")
        assert r.status_code == 404

    def test_cannot_delete_other_users_category(self, auth_client, db, second_user):
        cat = _make_custom_category(db, second_user, name="OtherUserCat")
        r = auth_client.delete(f"/categories/{cat.id}")
        assert r.status_code == 404
