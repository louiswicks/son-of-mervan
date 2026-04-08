"""
Tests for net worth snapshot endpoints.

Coverage targets:
  routers/net_worth.py — GET/POST/PUT/DELETE /net-worth/snapshots
"""
from datetime import date, datetime

import pytest

from database import NetWorthSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(db, user, snapshot_date=None, assets=None, liabilities=None):
    assets = assets or [{"name": "Savings", "value": 10000.0}]
    liabilities = liabilities or [{"name": "Credit Card", "value": 2000.0}]
    snap = NetWorthSnapshot(
        user_id=user.id,
        snapshot_date=snapshot_date or date(2026, 1, 1),
        total_assets=sum(a["value"] for a in assets),
        total_liabilities=sum(lib["value"] for lib in liabilities),
    )
    snap.assets_json = assets
    snap.liabilities_json = liabilities
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


_VALID_BODY = {
    "snapshot_date": "2026-03-01",
    "assets": [{"name": "ISA", "value": 5000.0}, {"name": "House", "value": 200000.0}],
    "liabilities": [{"name": "Mortgage", "value": 150000.0}],
}


# ---------------------------------------------------------------------------
# GET /net-worth/snapshots
# ---------------------------------------------------------------------------

class TestListSnapshots:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/net-worth/snapshots")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_own_snapshots(self, auth_client, db, verified_user):
        _make_snapshot(db, verified_user)
        r = auth_client.get("/net-worth/snapshots")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_list_excludes_deleted(self, auth_client, db, verified_user):
        snap = _make_snapshot(db, verified_user)
        snap.deleted_at = datetime.utcnow()
        db.commit()
        r = auth_client.get("/net-worth/snapshots")
        assert r.json() == []

    def test_list_excludes_other_user(self, auth_client, db, second_user):
        _make_snapshot(db, second_user)
        r = auth_client.get("/net-worth/snapshots")
        assert r.json() == []

    def test_list_returns_net_worth_field(self, auth_client, db, verified_user):
        _make_snapshot(
            db, verified_user,
            assets=[{"name": "Cash", "value": 10000.0}],
            liabilities=[{"name": "Loan", "value": 3000.0}],
        )
        r = auth_client.get("/net-worth/snapshots")
        body = r.json()
        assert body[0]["net_worth"] == pytest.approx(7000.0)

    def test_list_ordered_chronologically(self, auth_client, db, verified_user):
        _make_snapshot(db, verified_user, snapshot_date=date(2026, 3, 1))
        _make_snapshot(db, verified_user, snapshot_date=date(2026, 1, 1))
        r = auth_client.get("/net-worth/snapshots")
        dates = [row["snapshot_date"] for row in r.json()]
        assert dates == sorted(dates)

    def test_unauthenticated(self, client):
        r = client.get("/net-worth/snapshots")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /net-worth/snapshots
# ---------------------------------------------------------------------------

class TestCreateSnapshot:
    def test_create_returns_201(self, auth_client):
        r = auth_client.post("/net-worth/snapshots", json=_VALID_BODY)
        assert r.status_code == 201

    def test_create_response_shape(self, auth_client):
        r = auth_client.post("/net-worth/snapshots", json=_VALID_BODY)
        body = r.json()
        assert "id" in body
        assert body["total_assets"] == pytest.approx(205000.0)
        assert body["total_liabilities"] == pytest.approx(150000.0)
        assert body["net_worth"] == pytest.approx(55000.0)
        assert body["snapshot_date"] == "2026-03-01"
        assert len(body["assets"]) == 2
        assert len(body["liabilities"]) == 1

    def test_create_assets_only(self, auth_client):
        body = {"snapshot_date": "2026-04-01", "assets": [{"name": "Cash", "value": 500.0}], "liabilities": []}
        r = auth_client.post("/net-worth/snapshots", json=body)
        assert r.status_code == 201
        assert r.json()["total_liabilities"] == 0.0

    def test_create_liabilities_only(self, auth_client):
        body = {"snapshot_date": "2026-04-01", "assets": [], "liabilities": [{"name": "Loan", "value": 1000.0}]}
        r = auth_client.post("/net-worth/snapshots", json=body)
        assert r.status_code == 201
        assert r.json()["total_assets"] == 0.0

    def test_create_requires_at_least_one_item(self, auth_client):
        body = {"snapshot_date": "2026-04-01", "assets": [], "liabilities": []}
        r = auth_client.post("/net-worth/snapshots", json=body)
        assert r.status_code == 422

    def test_create_missing_date(self, auth_client):
        body = {"assets": [{"name": "Cash", "value": 100.0}]}
        r = auth_client.post("/net-worth/snapshots", json=body)
        assert r.status_code == 422

    def test_unauthenticated(self, client):
        r = client.post("/net-worth/snapshots", json=_VALID_BODY)
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /net-worth/snapshots/{id}
# ---------------------------------------------------------------------------

class TestUpdateSnapshot:
    def test_update_assets(self, auth_client, db, verified_user):
        snap = _make_snapshot(db, verified_user)
        r = auth_client.put(
            f"/net-worth/snapshots/{snap.id}",
            json={"assets": [{"name": "New ISA", "value": 20000.0}]},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_assets"] == pytest.approx(20000.0)
        assert body["assets"][0]["name"] == "New ISA"

    def test_update_date(self, auth_client, db, verified_user):
        snap = _make_snapshot(db, verified_user)
        r = auth_client.put(
            f"/net-worth/snapshots/{snap.id}",
            json={"snapshot_date": "2026-06-01"},
        )
        assert r.status_code == 200
        assert r.json()["snapshot_date"] == "2026-06-01"

    def test_update_not_found(self, auth_client):
        r = auth_client.put("/net-worth/snapshots/9999", json={"snapshot_date": "2026-06-01"})
        assert r.status_code == 404

    def test_update_other_user_snapshot(self, auth_client, db, second_user):
        snap = _make_snapshot(db, second_user)
        r = auth_client.put(
            f"/net-worth/snapshots/{snap.id}",
            json={"snapshot_date": "2026-06-01"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /net-worth/snapshots/{id}
# ---------------------------------------------------------------------------

class TestDeleteSnapshot:
    def test_delete_returns_204(self, auth_client, db, verified_user):
        snap = _make_snapshot(db, verified_user)
        r = auth_client.delete(f"/net-worth/snapshots/{snap.id}")
        assert r.status_code == 204

    def test_delete_soft_deletes(self, auth_client, db, verified_user):
        snap = _make_snapshot(db, verified_user)
        auth_client.delete(f"/net-worth/snapshots/{snap.id}")
        db.refresh(snap)
        assert snap.deleted_at is not None

    def test_delete_not_found(self, auth_client):
        r = auth_client.delete("/net-worth/snapshots/9999")
        assert r.status_code == 404

    def test_delete_other_user_snapshot(self, auth_client, db, second_user):
        snap = _make_snapshot(db, second_user)
        r = auth_client.delete(f"/net-worth/snapshots/{snap.id}")
        assert r.status_code == 404
