"""
Tests for Phase 8.3 — Investment Portfolio Tracking.

Covers:
- CRUD: create, list, update, delete
- Ownership enforcement (user cannot access another user's holdings)
- Portfolio summary totals
- Manual price sync (mocked yfinance)
- P&L calculation in responses
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from database import Investment, InvestmentPrice, User
from security import get_password_hash
from tests.conftest import TEST_EMAIL, TEST_EMAIL_2


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_holding(db, user, name="Vanguard S&P 500", ticker="VUSA.L",
                  asset_type="etf", units=10.0, purchase_price=50.0,
                  currency="GBP"):
    h = Investment(user_id=user.id, ticker=ticker, asset_type=asset_type, currency=currency)
    h.name = name
    h.units = units
    h.purchase_price = purchase_price
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def _make_price(db, holding, price=55.0):
    snap = InvestmentPrice(investment_id=holding.id, price=price, fetched_at=datetime.utcnow())
    db.add(snap)
    db.commit()
    return snap


# ── List ─────────────────────────────────────────────────────────────────────

def test_list_empty(auth_client):
    resp = auth_client.get("/investments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_owned_holdings(auth_client, db, verified_user, second_user):
    _make_holding(db, verified_user, name="HSBC Stock")
    _make_holding(db, second_user, name="Other User Stock")

    resp = auth_client.get("/investments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "HSBC Stock"


def test_list_soft_deleted_excluded(auth_client, db, verified_user):
    h = _make_holding(db, verified_user)
    h.deleted_at = datetime.utcnow()
    db.commit()

    resp = auth_client.get("/investments")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_holding_no_ticker(auth_client):
    payload = {
        "name": "Vanguard LifeStrategy",
        "asset_type": "fund",
        "units": 100.0,
        "purchase_price": 2.50,
        "currency": "GBP",
    }
    resp = auth_client.post("/investments", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Vanguard LifeStrategy"
    assert data["ticker"] is None
    assert data["units"] == 100.0
    assert data["purchase_price"] == 2.50
    assert data["cost_basis"] == pytest.approx(250.0)
    assert data["current_price"] is None
    assert data["gain_loss"] is None


def test_create_holding_with_ticker_no_price_fetch(auth_client):
    """When yfinance returns None, current_price stays None."""
    with patch("routers.investments.fetch_price_for_ticker", return_value=None):
        payload = {
            "name": "Apple Inc",
            "ticker": "AAPL",
            "asset_type": "stock",
            "units": 5.0,
            "purchase_price": 180.0,
            "currency": "USD",
        }
        resp = auth_client.post("/investments", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "AAPL"
    assert data["current_price"] is None


def test_create_holding_with_ticker_price_fetched(auth_client, db, verified_user):
    """When yfinance returns a price, current_price and gain_loss are populated."""
    with patch("routers.investments.fetch_price_for_ticker", return_value=200.0):
        payload = {
            "name": "Apple Inc",
            "ticker": "AAPL",
            "asset_type": "stock",
            "units": 5.0,
            "purchase_price": 180.0,
            "currency": "USD",
        }
        resp = auth_client.post("/investments", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["current_price"] == pytest.approx(200.0)
    assert data["current_value"] == pytest.approx(1000.0)
    assert data["cost_basis"] == pytest.approx(900.0)
    assert data["gain_loss"] == pytest.approx(100.0)
    assert data["gain_loss_pct"] == pytest.approx(11.11, abs=0.01)


def test_create_invalid_asset_type(auth_client):
    payload = {
        "name": "Test",
        "asset_type": "derivatives",
        "units": 1.0,
        "purchase_price": 10.0,
    }
    resp = auth_client.post("/investments", json=payload)
    assert resp.status_code == 422


def test_create_zero_units_rejected(auth_client):
    payload = {
        "name": "Test",
        "asset_type": "stock",
        "units": 0.0,
        "purchase_price": 10.0,
    }
    resp = auth_client.post("/investments", json=payload)
    assert resp.status_code == 422


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_holding(auth_client, db, verified_user):
    h = _make_holding(db, verified_user, units=10.0)
    resp = auth_client.put(f"/investments/{h.id}", json={"units": 15.0, "notes": "Added more"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["units"] == 15.0
    assert data["notes"] == "Added more"


def test_update_other_users_holding_returns_404(auth_client, db, second_user):
    h = _make_holding(db, second_user)
    resp = auth_client.put(f"/investments/{h.id}", json={"units": 99.0})
    assert resp.status_code == 404


def test_update_nonexistent_holding_returns_404(auth_client):
    resp = auth_client.put("/investments/99999", json={"units": 1.0})
    assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_holding(auth_client, db, verified_user):
    h = _make_holding(db, verified_user)
    resp = auth_client.delete(f"/investments/{h.id}")
    assert resp.status_code == 204

    # Confirm soft-deleted
    db.refresh(h)
    assert h.deleted_at is not None

    # No longer visible in list
    resp2 = auth_client.get("/investments")
    assert resp2.json() == []


def test_delete_other_users_holding_returns_404(auth_client, db, second_user):
    h = _make_holding(db, second_user)
    resp = auth_client.delete(f"/investments/{h.id}")
    assert resp.status_code == 404


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summary_empty(auth_client):
    resp = auth_client.get("/investments/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["holdings_count"] == 0
    assert data["total_cost"] == 0.0
    assert data["total_value"] is None


def test_summary_with_holdings_no_prices(auth_client, db, verified_user):
    _make_holding(db, verified_user, units=10, purchase_price=50.0)
    _make_holding(db, verified_user, name="Fund B", ticker=None, units=100, purchase_price=2.50)

    resp = auth_client.get("/investments/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["holdings_count"] == 2
    assert data["total_cost"] == pytest.approx(750.0)
    assert data["total_value"] is None  # no prices synced


def test_summary_with_prices(auth_client, db, verified_user):
    h1 = _make_holding(db, verified_user, units=10, purchase_price=50.0)
    _make_price(db, h1, price=60.0)  # value = 600, gain = 100

    h2 = _make_holding(db, verified_user, name="Fund B", ticker=None, units=100, purchase_price=2.50)
    _make_price(db, h2, price=3.00)  # value = 300, gain = 50

    resp = auth_client.get("/investments/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cost"] == pytest.approx(750.0)
    assert data["total_value"] == pytest.approx(900.0)
    assert data["total_gain_loss"] == pytest.approx(150.0)
    assert data["total_gain_loss_pct"] == pytest.approx(20.0)


# ── Sync Prices ───────────────────────────────────────────────────────────────

def test_sync_prices_no_ticker_skipped(auth_client, db, verified_user):
    _make_holding(db, verified_user, ticker=None)
    resp = auth_client.post("/investments/sync-prices")
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0


def test_sync_prices_updates_holding(auth_client, db, verified_user):
    _make_holding(db, verified_user, ticker="VUSA.L")
    with patch("routers.investments.fetch_price_for_ticker", return_value=58.50):
        resp = auth_client.post("/investments/sync-prices")
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1

    # Verify price was saved
    holdings_resp = auth_client.get("/investments")
    assert holdings_resp.json()[0]["current_price"] == pytest.approx(58.50)


def test_sync_prices_yfinance_failure_handled(auth_client, db, verified_user):
    _make_holding(db, verified_user, ticker="INVALID")
    with patch("routers.investments.fetch_price_for_ticker", return_value=None):
        resp = auth_client.post("/investments/sync-prices")
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0


# ── Unauthenticated access ────────────────────────────────────────────────────

def test_unauthenticated_list(client):
    resp = client.get("/investments")
    assert resp.status_code in (401, 403)


def test_unauthenticated_create(client):
    resp = client.post("/investments", json={"name": "X", "units": 1, "purchase_price": 10})
    assert resp.status_code in (401, 403)
