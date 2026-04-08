"""
Tests for the public /version endpoint.

Coverage targets:
  main.py — GET /version
"""
from core.config import VERSION, CHANGELOG


class TestVersionEndpoint:
    def test_returns_200_no_auth(self, client):
        """Endpoint is public — no token required."""
        r = client.get("/version")
        assert r.status_code == 200

    def test_response_shape(self, client):
        """Response must include 'version' string and 'changelog' list."""
        r = client.get("/version")
        body = r.json()
        assert "version" in body
        assert "changelog" in body
        assert isinstance(body["version"], str)
        assert isinstance(body["changelog"], list)

    def test_version_matches_constant(self, client):
        """Reported version must match the VERSION constant in core/config.py."""
        r = client.get("/version")
        assert r.json()["version"] == VERSION

    def test_changelog_has_current_version_entry(self, client):
        """Changelog must contain at least one entry for the current version."""
        r = client.get("/version")
        versions = [entry["version"] for entry in r.json()["changelog"]]
        assert VERSION in versions

    def test_changelog_entries_have_required_fields(self, client):
        """Every changelog entry must have version, date, and summary fields."""
        r = client.get("/version")
        for entry in r.json()["changelog"]:
            assert "version" in entry
            assert "date" in entry
            assert "summary" in entry

    def test_changelog_is_non_empty(self, client):
        """Changelog must contain at least one entry."""
        r = client.get("/version")
        assert len(r.json()["changelog"]) >= 1

    def test_changelog_constant_matches_endpoint(self, client):
        """CHANGELOG constant must equal the list returned by the endpoint."""
        r = client.get("/version")
        assert r.json()["changelog"] == CHANGELOG
