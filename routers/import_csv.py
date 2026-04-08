"""
POST /import/csv        — Parse bank CSV, return preview (nothing saved yet)
POST /import/csv/confirm — Persist confirmed rows as actual expenses
"""
import csv
import io
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from core.limiter import limiter
from database import AuditLog, MonthlyData, MonthlyExpense, User, get_db
from models import CSVConfirmRequest, CSVImportResult, CSVPreviewResponse, CSVPreviewRow
from security import verify_token

router = APIRouter(prefix="/import", tags=["import"])

# ---------------------------------------------------------------------------
# Category keyword map for auto-categorisation (case-insensitive substring)
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Housing": [
        "rent", "mortgage", "lease", "property management", "estate agent",
        "letting", "ground rent", "service charge",
    ],
    "Transportation": [
        "uber", "lyft", "taxi", "cab", "bus", "tube", "tfl", "national rail",
        "petrol", "fuel", "parking", "toll", "ferry", "airline", "ryanair",
        "easyjet", "eurostar", "heathrow", "gatwick", "trainline",
    ],
    "Food": [
        "restaurant", "cafe", "coffee", "grocery", "supermarket", "tesco",
        "sainsbury", "lidl", "aldi", "waitrose", "morrisons", "asda", "co-op",
        "marks & spencer", "m&s food", "pizza", "burger", "chicken", "takeaway",
        "deliveroo", "just eat", "ubereats", "greggs", "pret",
    ],
    "Utilities": [
        "electric", "electricity", "gas bill", "water bill", "internet",
        "broadband", "council tax", "bt ", "virgin media", "sky ", "ee ",
        "o2 ", "vodafone", "three ", "octopus", "bulb", "ovo energy",
        "british gas", "thames water",
    ],
    "Insurance": [
        "insurance", "assurance", "aviva", "axa", "admiral", "direct line",
        "churchill", "hastings",
    ],
    "Healthcare": [
        "pharmacy", "chemist", "doctor", "dentist", "hospital", "prescription",
        "nhs", "clinic", "health", "boots", "lloyds pharmacy", "vision express",
        "optician", "physio",
    ],
    "Entertainment": [
        "netflix", "spotify", "amazon prime", "cinema", "theatre", "gym",
        "disney+", "apple music", "youtube premium", "twitch", "steam",
        "playstation", "xbox", "nintendo", "ticketmaster",
    ],
}


def _suggest_category(description: str) -> str:
    """Return the best-matching category based on keyword matching."""
    desc_lower = description.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                return category
    return "Other"


def _detect_columns(header: list[str]) -> dict[str, int]:
    """
    Map header columns to date/description/amount indices.
    Raises ValueError when required columns cannot be found.
    """
    lower = [h.lower().strip() for h in header]

    date_candidates = [
        "date", "transaction date", "value date", "posting date", "trans date",
        "transaction_date",
    ]
    date_idx = next((lower.index(c) for c in date_candidates if c in lower), None)

    desc_candidates = [
        "description", "merchant name", "narrative", "details", "memo",
        "payee", "transaction description", "reference", "trans description",
        "name", "merchant", "particulars",
    ]
    desc_idx = next((lower.index(c) for c in desc_candidates if c in lower), None)

    amount_candidates = [
        "amount", "debit amount", "credit amount", "debit", "credit",
        "transaction amount", "value", "withdrawal", "deposit",
    ]
    amount_idx = next((lower.index(c) for c in amount_candidates if c in lower), None)

    missing = [
        name
        for name, idx in [("date", date_idx), ("description", desc_idx), ("amount", amount_idx)]
        if idx is None
    ]
    if missing:
        raise ValueError(
            f"Could not detect required column(s) {missing} in header: {header}. "
            "Expected columns named: date, description, amount (or common alternatives)."
        )
    return {"date": date_idx, "description": desc_idx, "amount": amount_idx}


def _parse_amount(raw: str) -> Optional[float]:
    """
    Parse amount strings like '1,234.56', '-£20.00', '(50.00)'.
    Returns a positive float (expense amount), or None on failure.
    """
    s = (
        raw.strip()
        .replace(",", "")
        .replace("£", "")
        .replace("$", "")
        .replace("€", "")
        .strip()
    )
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return abs(float(s))
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[datetime]:
    """Try several common date formats; return None if none match."""
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
        "%Y/%m/%d", "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/csv", response_model=CSVPreviewResponse)
@limiter.limit("20/minute")
async def preview_csv_import(
    request: Request,
    file: UploadFile = File(...),
    month: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
) -> CSVPreviewResponse:
    """
    Parse a bank-exported CSV and return a preview payload.
    Nothing is saved to the database at this stage.

    - `file`: CSV file (multipart/form-data)
    - `month`: Optional YYYY-MM override; if omitted, month is inferred from each row's date.
    """
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Validate explicit month param
    if month:
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=422, detail="month must be in YYYY-MM format"
            )

    # Read and decode file
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # strip UTF-8 BOM if present
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows_iter = iter(reader)

    try:
        header = next(rows_iter)
    except StopIteration:
        raise HTTPException(status_code=422, detail="CSV file is empty")

    try:
        col = _detect_columns(header)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Build a set of existing (name_lower, rounded_amount, month) for duplicate detection
    existing: set[tuple[str, float, str]] = set()
    all_month_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    for md in all_month_rows:
        md_month = md.month  # hybrid property decrypts
        for exp in (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == md.id,
                MonthlyExpense.deleted_at.is_(None),
            )
            .all()
        ):
            existing.add(
                (
                    (exp.name or "").lower(),
                    round(exp.actual_amount or 0.0, 2),
                    md_month,
                )
            )

    preview_rows: list[CSVPreviewRow] = []
    parse_errors = 0

    for raw in rows_iter:
        # Skip blank lines
        if not any(cell.strip() for cell in raw):
            continue

        try:
            date_str = raw[col["date"]].strip()
            desc = raw[col["description"]].strip()
            amt_str = raw[col["amount"]].strip()
        except IndexError:
            parse_errors += 1
            continue

        if not desc or not amt_str:
            parse_errors += 1
            continue

        amount = _parse_amount(amt_str)
        if amount is None or amount <= 0:
            parse_errors += 1
            continue

        # Determine month for this row
        if month:
            row_month = month
        else:
            parsed_date = _parse_date(date_str)
            if parsed_date is None:
                parse_errors += 1
                continue
            row_month = parsed_date.strftime("%Y-%m")

        suggested = _suggest_category(desc)
        is_dup = (desc.lower(), round(amount, 2), row_month) in existing

        preview_rows.append(
            CSVPreviewRow(
                row_id=str(uuid.uuid4()),
                date=date_str,
                description=desc,
                amount=round(amount, 2),
                month=row_month,
                suggested_category=suggested,
                is_duplicate=is_dup,
            )
        )

    duplicates_count = sum(1 for r in preview_rows if r.is_duplicate)

    return CSVPreviewResponse(
        rows=preview_rows,
        total=len(preview_rows),
        duplicates_count=duplicates_count,
        parse_errors=parse_errors,
    )


@router.post("/csv/confirm", response_model=CSVImportResult)
@limiter.limit("10/minute")
async def confirm_csv_import(
    request: Request,
    payload: CSVConfirmRequest,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
) -> CSVImportResult:
    """
    Persist confirmed CSV rows as actual expenses.
    Rows with ``include=False`` are skipped without error.
    Uses the standard name+category upsert: updates actual_amount if matched, inserts otherwise.
    """
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    imported = 0
    skipped = 0

    # Cache loaded MonthlyData rows to avoid repeated full-table scans within one request
    month_cache: dict[str, MonthlyData] = {}
    all_month_rows = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
    for md in all_month_rows:
        month_cache[md.month] = md  # hybrid property decrypts on access

    for row in payload.rows:
        if not row.include:
            skipped += 1
            continue

        # Validate month format
        try:
            datetime.strptime(row.month, "%Y-%m")
        except ValueError:
            skipped += 1
            continue

        # Get or create MonthlyData for this month
        month_row = month_cache.get(row.month)
        if month_row is None:
            month_row = MonthlyData(user_id=user.id)
            month_row.month = row.month
            month_row.salary_planned = 0.0
            month_row.salary_actual = 0.0
            month_row.total_planned = 0.0
            month_row.total_actual = 0.0
            month_row.remaining_planned = 0.0
            month_row.remaining_actual = 0.0
            db.add(month_row)
            db.flush()
            month_cache[row.month] = month_row

        # Load active expenses for this month
        existing_expenses = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense.deleted_at.is_(None),
            )
            .all()
        )

        # Upsert: match by name (case-insensitive) + category
        existing_exp: Optional[MonthlyExpense] = None
        for exp in existing_expenses:
            if (exp.name or "").lower() == row.description.lower() and exp.category == row.category:
                existing_exp = exp
                break

        if existing_exp:
            before = {
                "name": existing_exp.name,
                "category": existing_exp.category,
                "actual_amount": float(existing_exp.actual_amount or 0),
            }
            existing_exp.actual_amount = row.amount
            db.flush()
            after = {
                "name": existing_exp.name,
                "category": existing_exp.category,
                "actual_amount": float(existing_exp.actual_amount),
            }
            audit = AuditLog(
                user_id=user.id,
                expense_id=existing_exp.id,
                action="update",
                changed_fields=json.dumps({"before": before, "after": after}),
            )
            db.add(audit)
        else:
            new_exp = MonthlyExpense(monthly_data_id=month_row.id)
            new_exp.name = row.description
            new_exp.category = row.category
            new_exp.actual_amount = row.amount
            new_exp.planned_amount = 0.0
            new_exp.currency = user.base_currency or "GBP"
            db.add(new_exp)
            db.flush()
            after = {
                "name": new_exp.name,
                "category": new_exp.category,
                "actual_amount": float(new_exp.actual_amount),
                "planned_amount": 0.0,
                "currency": new_exp.currency,
            }
            audit = AuditLog(
                user_id=user.id,
                expense_id=new_exp.id,
                action="create",
                changed_fields=json.dumps({"before": None, "after": after}),
            )
            db.add(audit)

        imported += 1

    db.commit()
    return CSVImportResult(imported=imported, skipped=skipped)
