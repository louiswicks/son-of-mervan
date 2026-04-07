# routers/investments.py
"""
Investment Portfolio Tracking — Phase 8.3.

Routes:
  GET    /investments               list all active holdings (with latest price + P&L)
  POST   /investments               add a holding
  PUT    /investments/{id}          update a holding
  DELETE /investments/{id}          soft-delete a holding
  GET    /investments/summary       portfolio totals
  POST   /investments/sync-prices   manual price sync trigger (uses yfinance)
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from database import get_db, Investment, InvestmentPrice, User
from security import verify_token
from models import (
    InvestmentCreate,
    InvestmentUpdate,
    InvestmentResponse,
    InvestmentPortfolioSummary,
    VALID_ASSET_TYPES,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/investments", tags=["investments"])


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_holding(holding_id: int, user: User, db: Session) -> Investment:
    holding = (
        db.query(Investment)
        .filter(
            Investment.id == holding_id,
            Investment.user_id == user.id,
            Investment.deleted_at == None,
        )
        .first()
    )
    if not holding:
        raise HTTPException(status_code=404, detail="Investment not found")
    return holding


def _latest_price(holding: Investment) -> Optional[InvestmentPrice]:
    """Return the most recent InvestmentPrice row, or None."""
    if not holding.prices:
        return None
    return max(holding.prices, key=lambda p: p.fetched_at)


def _holding_to_response(holding: Investment) -> dict:
    cost_basis = round(holding.units * holding.purchase_price, 2)
    latest = _latest_price(holding)
    current_price = latest.price if latest else None
    current_value = round(holding.units * current_price, 2) if current_price is not None else None
    if current_value is not None:
        gain_loss = round(current_value - cost_basis, 2)
        gain_loss_pct = round((gain_loss / cost_basis) * 100, 2) if cost_basis else 0.0
    else:
        gain_loss = None
        gain_loss_pct = None

    return {
        "id": holding.id,
        "name": holding.name,
        "ticker": holding.ticker,
        "asset_type": holding.asset_type,
        "units": holding.units,
        "purchase_price": holding.purchase_price,
        "currency": holding.currency,
        "notes": holding.notes,
        "current_price": current_price,
        "current_value": current_value,
        "cost_basis": cost_basis,
        "gain_loss": gain_loss,
        "gain_loss_pct": gain_loss_pct,
        "last_price_at": latest.fetched_at if latest else None,
        "created_at": holding.created_at,
    }


def fetch_price_for_ticker(ticker: str) -> Optional[float]:
    """
    Fetch the latest price for a ticker via yfinance.
    Returns None on any error — callers should handle gracefully.
    """
    try:
        import yfinance as yf  # noqa: PLC0415
        info = yf.Ticker(ticker).fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            price = getattr(info, "regular_market_price", None)
        if price and price > 0:
            return float(price)
    except Exception as exc:  # noqa: BLE001
        log.warning("yfinance price fetch failed for %s: %s", ticker, exc)
    return None


def sync_prices_for_user(user: User, db: Session) -> int:
    """Sync latest prices for all active holdings with a ticker. Returns count updated."""
    holdings = (
        db.query(Investment)
        .filter(Investment.user_id == user.id, Investment.deleted_at == None)
        .all()
    )
    updated = 0
    for holding in holdings:
        if not holding.ticker:
            continue
        price = fetch_price_for_ticker(holding.ticker)
        if price is None:
            continue
        snap = InvestmentPrice(investment_id=holding.id, price=price)
        db.add(snap)
        updated += 1
        log.info(
            "Synced price for investment %s (%s): %.4f",
            holding.id,
            holding.ticker,
            price,
        )
    if updated:
        db.commit()
    return updated


# ---------- routes ----------

@router.get("", response_model=List[InvestmentResponse])
def list_investments(
    email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """List all active investment holdings with latest price and P&L."""
    user = _get_user(db, email)
    holdings = (
        db.query(Investment)
        .filter(Investment.user_id == user.id, Investment.deleted_at == None)
        .order_by(Investment.created_at)
        .all()
    )
    return [_holding_to_response(h) for h in holdings]


@router.get("/summary", response_model=InvestmentPortfolioSummary)
def portfolio_summary(
    email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return aggregate portfolio totals: total cost, total value, total gain/loss."""
    user = _get_user(db, email)
    holdings = (
        db.query(Investment)
        .filter(Investment.user_id == user.id, Investment.deleted_at == None)
        .all()
    )
    total_cost = sum(h.units * h.purchase_price for h in holdings)
    values = []
    for h in holdings:
        latest = _latest_price(h)
        if latest:
            values.append(h.units * latest.price)

    if values:
        total_value = round(sum(values), 2)
        total_gain_loss = round(total_value - total_cost, 2)
        total_gain_loss_pct = round((total_gain_loss / total_cost) * 100, 2) if total_cost else 0.0
    else:
        total_value = None
        total_gain_loss = None
        total_gain_loss_pct = None

    return {
        "total_cost": round(total_cost, 2),
        "total_value": total_value,
        "total_gain_loss": total_gain_loss,
        "total_gain_loss_pct": total_gain_loss_pct,
        "holdings_count": len(holdings),
    }


@router.post("", response_model=InvestmentResponse, status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: InvestmentCreate,
    email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Add a new investment holding."""
    user = _get_user(db, email)

    if payload.asset_type not in VALID_ASSET_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"asset_type must be one of: {', '.join(sorted(VALID_ASSET_TYPES))}",
        )
    if payload.units <= 0:
        raise HTTPException(status_code=422, detail="units must be > 0")
    if payload.purchase_price < 0:
        raise HTTPException(status_code=422, detail="purchase_price must be >= 0")

    holding = Investment(
        user_id=user.id,
        ticker=payload.ticker.upper().strip() if payload.ticker else None,
        asset_type=payload.asset_type,
        currency=payload.currency.upper(),
    )
    holding.name = payload.name
    holding.units = payload.units
    holding.purchase_price = payload.purchase_price
    holding.notes = payload.notes
    db.add(holding)
    db.commit()
    db.refresh(holding)

    # Attempt an immediate price fetch if ticker provided
    if holding.ticker:
        price = fetch_price_for_ticker(holding.ticker)
        if price:
            snap = InvestmentPrice(investment_id=holding.id, price=price)
            db.add(snap)
            db.commit()
            db.refresh(holding)

    log.info("Investment %s created for user %s", holding.id, user.id)
    return _holding_to_response(holding)


@router.put("/{holding_id}", response_model=InvestmentResponse)
def update_investment(
    holding_id: int = Path(..., gt=0),
    payload: InvestmentUpdate = ...,
    email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Update an existing investment holding."""
    user = _get_user(db, email)
    holding = _get_holding(holding_id, user, db)

    if payload.asset_type is not None and payload.asset_type not in VALID_ASSET_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"asset_type must be one of: {', '.join(sorted(VALID_ASSET_TYPES))}",
        )
    if payload.units is not None and payload.units <= 0:
        raise HTTPException(status_code=422, detail="units must be > 0")
    if payload.purchase_price is not None and payload.purchase_price < 0:
        raise HTTPException(status_code=422, detail="purchase_price must be >= 0")

    if payload.name is not None:
        holding.name = payload.name
    if payload.ticker is not None:
        holding.ticker = payload.ticker.upper().strip() if payload.ticker else None
    if payload.asset_type is not None:
        holding.asset_type = payload.asset_type
    if payload.units is not None:
        holding.units = payload.units
    if payload.purchase_price is not None:
        holding.purchase_price = payload.purchase_price
    if payload.currency is not None:
        holding.currency = payload.currency.upper()
    if payload.notes is not None:
        holding.notes = payload.notes

    db.commit()
    db.refresh(holding)
    log.info("Investment %s updated for user %s", holding.id, user.id)
    return _holding_to_response(holding)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment(
    holding_id: int = Path(..., gt=0),
    email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Soft-delete an investment holding."""
    user = _get_user(db, email)
    holding = _get_holding(holding_id, user, db)
    holding.deleted_at = datetime.utcnow()
    db.commit()
    log.info("Investment %s soft-deleted for user %s", holding.id, user.id)


@router.post("/sync-prices", status_code=status.HTTP_200_OK)
def manual_sync_prices(
    email: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Manually trigger a price sync for all holdings with a ticker symbol."""
    user = _get_user(db, email)
    updated = sync_prices_for_user(user, db)
    return {"updated": updated, "message": f"Synced prices for {updated} holding(s)"}
