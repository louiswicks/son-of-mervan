"""Tests for Phase 9.2: Onboarding Wizard — has_completed_onboarding flag."""
import pytest


# ---------------------------------------------------------------------------
# GET /users/me — has_completed_onboarding field
# ---------------------------------------------------------------------------

class TestOnboardingFlag:
    def test_profile_includes_onboarding_flag(self, auth_client):
        """GET /users/me includes has_completed_onboarding."""
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert "has_completed_onboarding" in r.json()

    def test_new_user_has_onboarding_incomplete(self, auth_client):
        """New users default to has_completed_onboarding=False."""
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is False

    def test_put_sets_onboarding_complete(self, auth_client):
        """PUT /users/me with has_completed_onboarding=True persists the change."""
        r = auth_client.put("/users/me", json={"has_completed_onboarding": True})
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is True

    def test_get_reflects_persisted_onboarding_flag(self, auth_client):
        """Subsequent GET /users/me returns the persisted value."""
        auth_client.put("/users/me", json={"has_completed_onboarding": True})
        r = auth_client.get("/users/me")
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is True

    def test_can_reset_onboarding_flag_to_false(self, auth_client):
        """has_completed_onboarding can be toggled back to False."""
        auth_client.put("/users/me", json={"has_completed_onboarding": True})
        r = auth_client.put("/users/me", json={"has_completed_onboarding": False})
        assert r.status_code == 200
        assert r.json()["has_completed_onboarding"] is False

    def test_put_preserves_other_profile_fields(self, auth_client):
        """Setting has_completed_onboarding does not clobber other fields."""
        auth_client.put("/users/me", json={"base_currency": "EUR"})
        r = auth_client.put("/users/me", json={"has_completed_onboarding": True})
        assert r.status_code == 200
        data = r.json()
        assert data["has_completed_onboarding"] is True
        assert data["base_currency"] == "EUR"

    def test_omitting_onboarding_flag_does_not_change_it(self, auth_client):
        """PUT without has_completed_onboarding leaves the existing value."""
        auth_client.put("/users/me", json={"has_completed_onboarding": True})
        # Update only base_currency, leaving onboarding flag alone
        r = auth_client.put("/users/me", json={"base_currency": "USD"})
        assert r.status_code == 200
        data = r.json()
        assert data["has_completed_onboarding"] is True
        assert data["base_currency"] == "USD"

    def test_unauthenticated_get_profile_returns_401(self, client):
        """Unauthenticated requests to GET /users/me are rejected."""
        r = client.get("/users/me")
        assert r.status_code in (401, 403)

    def test_unauthenticated_put_profile_returns_401(self, client):
        """Unauthenticated requests to PUT /users/me are rejected."""
        r = client.put("/users/me", json={"has_completed_onboarding": True})
        assert r.status_code in (401, 403)
