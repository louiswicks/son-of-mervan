"""Tests for X-Request-ID tracing middleware (PRD 21.4)."""
import uuid

import pytest


HEADER = "x-request-id"  # HTTP headers are lowercased by starlette TestClient


class TestRequestIDMiddleware:
    def test_response_always_contains_header(self, client):
        """Every response must include X-Request-ID."""
        r = client.get("/health")
        assert HEADER in r.headers

    def test_valid_uuid4_is_echoed(self, client):
        """Client-supplied UUID4 is echoed back unchanged."""
        req_id = str(uuid.uuid4())
        r = client.get("/health", headers={"X-Request-ID": req_id})
        assert r.headers[HEADER] == req_id

    def test_non_uuid4_header_is_replaced(self, client):
        """A non-UUID4 X-Request-ID is replaced with a fresh server-generated UUID4."""
        bad_value = "not-a-uuid"
        r = client.get("/health", headers={"X-Request-ID": bad_value})
        response_id = r.headers[HEADER]
        assert response_id != bad_value
        # The replacement must itself be a valid UUID4
        parsed = uuid.UUID(response_id, version=4)
        assert str(parsed) == response_id

    def test_missing_header_generates_uuid4(self, client):
        """When no X-Request-ID is sent the server generates a valid UUID4."""
        r = client.get("/health")
        response_id = r.headers[HEADER]
        parsed = uuid.UUID(response_id, version=4)
        assert str(parsed) == response_id

    def test_each_request_gets_unique_id(self, client):
        """Two requests without an X-Request-ID header receive different IDs."""
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers[HEADER] != r2.headers[HEADER]

    def test_uuid1_header_is_replaced(self, client):
        """UUID1 (not UUID4) is not a valid value and should be replaced."""
        uuid1_value = str(uuid.uuid1())
        r = client.get("/health", headers={"X-Request-ID": uuid1_value})
        response_id = r.headers[HEADER]
        # Must differ from the submitted UUID1
        assert response_id != uuid1_value
        # Replacement must be a valid UUID4
        parsed = uuid.UUID(response_id, version=4)
        assert str(parsed) == response_id

    def test_header_present_on_authenticated_endpoint(self, auth_client):
        """X-Request-ID is present even on protected endpoints."""
        r = auth_client.get("/verify-token")
        assert HEADER in r.headers

    def test_client_id_propagated_on_post(self, client):
        """Client-supplied UUID4 is echoed on POST requests too."""
        req_id = str(uuid.uuid4())
        r = client.post(
            "/login",
            json={"email": "nobody@example.com", "password": "wrong"},
            headers={"X-Request-ID": req_id},
        )
        # Login will fail (401/403) but the header must still be echoed
        assert r.headers[HEADER] == req_id
