# routers/currency.py — Multi-currency support
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, ExchangeRate
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/currency", tags=["currency"])

# Curated list of commonly used ISO 4217 currencies with symbols
SUPPORTED_CURRENCIES: List[Dict] = [
    {"code": "GBP", "name": "British Pound Sterling", "symbol": "£"},
    {"code": "USD", "name": "US Dollar", "symbol": "$"},
    {"code": "EUR", "name": "Euro", "symbol": "€"},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥"},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "CA$"},
    {"code": "AUD", "name": "Australian Dollar", "symbol": "A$"},
    {"code": "CHF", "name": "Swiss Franc", "symbol": "Fr"},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥"},
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹"},
    {"code": "MXN", "name": "Mexican Peso", "symbol": "MX$"},
    {"code": "BRL", "name": "Brazilian Real", "symbol": "R$"},
    {"code": "KRW", "name": "South Korean Won", "symbol": "₩"},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$"},
    {"code": "HKD", "name": "Hong Kong Dollar", "symbol": "HK$"},
    {"code": "SEK", "name": "Swedish Krona", "symbol": "kr"},
    {"code": "NOK", "name": "Norwegian Krone", "symbol": "kr"},
    {"code": "DKK", "name": "Danish Krone", "symbol": "kr"},
    {"code": "NZD", "name": "New Zealand Dollar", "symbol": "NZ$"},
    {"code": "ZAR", "name": "South African Rand", "symbol": "R"},
    {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ"},
    {"code": "PLN", "name": "Polish Zloty", "symbol": "zł"},
    {"code": "TRY", "name": "Turkish Lira", "symbol": "₺"},
    {"code": "THB", "name": "Thai Baht", "symbol": "฿"},
    {"code": "MYR", "name": "Malaysian Ringgit", "symbol": "RM"},
    {"code": "IDR", "name": "Indonesian Rupiah", "symbol": "Rp"},
]

CURRENCY_SYMBOLS: Dict[str, str] = {c["code"]: c["symbol"] for c in SUPPORTED_CURRENCIES}
VALID_CURRENCY_CODES = {c["code"] for c in SUPPORTED_CURRENCIES}


# ---------- Schemas ----------

class CurrencyInfo(BaseModel):
    code: str
    name: str
    symbol: str


class ExchangeRatesResponse(BaseModel):
    base: str
    date: str
    rates: Dict[str, float]


# ---------- Endpoints ----------

@router.get("/list", response_model=List[CurrencyInfo])
def list_currencies(_: str = Depends(verify_token)):
    """Return the list of supported ISO 4217 currencies with symbols."""
    return SUPPORTED_CURRENCIES


@router.get("/rates", response_model=ExchangeRatesResponse)
def get_exchange_rates(
    base: str = "GBP",
    _: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Return the latest exchange rates for the given base currency.
    Rates are computed from EUR-based rows stored in the DB.
    Falls back to a live Frankfurter API fetch if no DB data exists.
    """
    base = base.upper()
    if base not in VALID_CURRENCY_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported currency: {base}")

    today = date.today()

    # Find the most recent date in the DB
    latest_date = (
        db.query(ExchangeRate.date)
        .filter(ExchangeRate.base == "EUR")
        .order_by(ExchangeRate.date.desc())
        .scalar()
    )

    if latest_date is None:
        # No rates in DB yet — trigger a sync inline (cold start)
        logger.info("No exchange rates in DB — fetching from Frankfurter API")
        _fetch_and_store_rates(db)
        latest_date = today

    # Load all EUR-based rates for that date
    eur_rows = (
        db.query(ExchangeRate)
        .filter(ExchangeRate.base == "EUR", ExchangeRate.date == latest_date)
        .all()
    )

    if not eur_rows:
        raise HTTPException(status_code=503, detail="Exchange rates not available")

    eur_rates: Dict[str, float] = {r.target: r.rate for r in eur_rows}
    # EUR itself = 1.0 relative to EUR
    eur_rates["EUR"] = 1.0

    # Convert from EUR-base to requested base
    if base == "EUR":
        rates = {code: round(rate, 6) for code, rate in eur_rates.items() if code in VALID_CURRENCY_CODES}
    elif base not in eur_rates:
        raise HTTPException(status_code=503, detail=f"No rate data for {base}")
    else:
        base_in_eur = eur_rates[base]  # e.g. 1 EUR = 0.86 GBP  →  base_in_eur = 0.86
        rates = {}
        for code in VALID_CURRENCY_CODES:
            if code in eur_rates:
                # rate(base→code) = eur_rates[code] / eur_rates[base]
                rates[code] = round(eur_rates[code] / base_in_eur, 6)

    return {"base": base, "date": str(latest_date), "rates": rates}


# ---------- Background sync ----------

def sync_exchange_rates(db_factory) -> None:
    """
    Fetch the latest EUR-based rates from Frankfurter and upsert into exchange_rates.
    Called by APScheduler at 00:15 UTC daily and on cold-start when no DB data exists.
    """
    db = db_factory()
    try:
        _fetch_and_store_rates(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("Exchange rate sync failed: %s", exc)
    finally:
        db.close()


def _fetch_and_store_rates(db: Session) -> None:
    """Fetch EUR-based rates from Frankfurter and write/update DB rows for today."""
    url = "https://api.frankfurter.app/latest?from=EUR"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.warning("Frankfurter fetch failed (%s), trying fallback open.er-api.com", exc)
        # Fallback: open.er-api.com (no API key required for basic rates)
        resp = httpx.get("https://open.er-api.com/v6/latest/EUR", timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        payload = {"base": "EUR", "date": str(date.today()), "rates": raw.get("rates", {})}

    rate_date_str = payload.get("date", str(date.today()))
    try:
        rate_date = date.fromisoformat(rate_date_str)
    except ValueError:
        rate_date = date.today()

    raw_rates: Dict[str, float] = payload.get("rates", {})

    for target, rate in raw_rates.items():
        if target not in VALID_CURRENCY_CODES:
            continue
        existing = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.base == "EUR",
                ExchangeRate.target == target,
                ExchangeRate.date == rate_date,
            )
            .first()
        )
        if existing:
            existing.rate = float(rate)
        else:
            db.add(ExchangeRate(
                base="EUR",
                target=target,
                rate=float(rate),
                date=rate_date,
                created_at=datetime.utcnow(),
            ))

    db.commit()
    logger.info("Exchange rates synced for %s (%d currencies)", rate_date, len(raw_rates))
