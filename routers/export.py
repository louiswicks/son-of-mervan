# routers/export.py
"""
Data export endpoints.

GET /export/csv?from_month=YYYY-MM&to_month=YYYY-MM  — expense CSV download
GET /export/pdf?month=YYYY-MM                         — monthly budget report PDF
GET /export/tax-summary?tax_year=YYYY                 — UK tax-year spending summary (JSON)
GET /export/tax-pdf?tax_year=YYYY                     — SA302-style tax summary PDF

CSV/PDF endpoints are rate-limited to 1 request/minute per IP.
Tax endpoints are rate-limited to 1 request/minute per IP.
"""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.limiter import limiter
from database import get_db, User, MonthlyData, MonthlyExpense
from models import TaxSummaryResponse, TaxCategoryBreakdown
from security import verify_token

# HMRC Self-Assessment expense category mapping.
# Keys: our internal category names.
# Values: (hmrc_heading, potentially_deductible)
# Note: deductibility depends on individual circumstances; users must verify with an accountant.
_HMRC_CATEGORY_MAP: dict[str, tuple[str, bool]] = {
    "Housing": ("Office, property and equipment", True),
    "Transportation": ("Car, van and travel expenses", True),
    "Food": ("Food and subsistence", False),
    "Utilities": ("Office, property and equipment", True),
    "Insurance": ("Financial costs", True),
    "Healthcare": ("Other allowable expenses", False),
    "Entertainment": ("Entertainment and hospitality", False),
    "Other": ("Other expenses", False),
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


# -------------------- helpers --------------------

def _require_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _validate_month(m: str) -> str:
    parts = (m or "").split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    try:
        year, mo = int(parts[0]), int(parts[1])
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    if not (1 <= mo <= 12):
        raise HTTPException(status_code=422, detail="month must be 'YYYY-MM'")
    return f"{year:04d}-{mo:02d}"


def _month_in_range(month_str: str, from_month: str, to_month: str) -> bool:
    return from_month <= month_str <= to_month


def _get_all_months(db: Session, user: User) -> list[MonthlyData]:
    return db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()


# -------------------- CSV export --------------------

@router.get("/csv")
@limiter.limit("1/minute")
def export_csv(
    request: Request,
    from_month: str = Query(..., alias="from", description="Start month YYYY-MM"),
    to_month: str = Query(..., alias="to", description="End month YYYY-MM"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream all expenses in the given month range as a CSV file."""
    from_norm = _validate_month(from_month)
    to_norm = _validate_month(to_month)
    if from_norm > to_norm:
        raise HTTPException(status_code=422, detail="'from' must not be after 'to'")

    user = _require_user(db, current_user)
    all_months = _get_all_months(db, user)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Month", "Category", "Name", "Planned Amount", "Actual Amount"])

    row_count = 0
    for month_row in sorted(all_months, key=lambda r: r.month or ""):
        month_str = month_row.month
        if not month_str or not _month_in_range(month_str, from_norm, to_norm):
            continue

        expenses = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == month_row.id,
                MonthlyExpense.deleted_at == None,  # noqa: E711
            )
            .all()
        )

        for e in expenses:
            writer.writerow([
                month_str,
                e.category or "",
                e.name or "",
                float(e.planned_amount or 0.0),
                float(e.actual_amount or 0.0),
            ])
            row_count += 1

    if row_count == 0:
        # Still return an empty CSV (just headers) rather than 404
        logger.info("CSV export: no rows found for user %s in range %s–%s", current_user, from_norm, to_norm)

    output.seek(0)
    filename = f"budget_export_{from_norm}_{to_norm}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -------------------- PDF export --------------------

@router.get("/pdf")
@limiter.limit("1/minute")
def export_pdf(
    request: Request,
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Generate a monthly budget report as a PDF."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PDF generation is not available (fpdf2 not installed)",
        )

    month_norm = _validate_month(month)
    user = _require_user(db, current_user)
    all_months = _get_all_months(db, user)

    month_row: Optional[MonthlyData] = None
    for r in all_months:
        if r.month == month_norm:
            month_row = r
            break

    if not month_row:
        raise HTTPException(status_code=404, detail=f"No data found for {month_norm}")

    expenses = (
        db.query(MonthlyExpense)
        .filter(
            MonthlyExpense.monthly_data_id == month_row.id,
            MonthlyExpense.deleted_at == None,  # noqa: E711
        )
        .all()
    )

    salary_planned = float(month_row.salary_planned or 0.0)
    salary_actual = float(month_row.salary_actual or 0.0)
    total_planned = float(month_row.total_planned or 0.0)
    total_actual = float(month_row.total_actual or 0.0)

    # Group expenses by category
    category_map: dict = {}
    for e in expenses:
        cat = e.category or "Other"
        if cat not in category_map:
            category_map[cat] = {"planned": 0.0, "actual": 0.0, "items": []}
        category_map[cat]["planned"] += float(e.planned_amount or 0.0)
        category_map[cat]["actual"] += float(e.actual_amount or 0.0)
        category_map[cat]["items"].append(e)

    # Build PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_fill_color(59, 130, 246)  # blue-500
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, f"Monthly Budget Report — {month_norm}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Generated: {generated_at}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Salary summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Income Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 11)
    col_w = [80, 50, 50]
    pdf.set_fill_color(240, 245, 255)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col_w[0], 8, "Item", border=1, fill=True)
    pdf.cell(col_w[1], 8, "Planned", border=1, fill=True, align="R")
    pdf.cell(col_w[2], 8, "Actual", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.cell(col_w[0], 8, "Salary / Income", border=1)
    pdf.cell(col_w[1], 8, f"£{salary_planned:,.2f}", border=1, align="R")
    pdf.cell(col_w[2], 8, f"£{salary_actual:,.2f}", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Category breakdown
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Expense Breakdown by Category", new_x="LMARGIN", new_y="NEXT")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_fill_color(240, 245, 255)
    pdf.cell(col_w[0], 8, "Category", border=1, fill=True)
    pdf.cell(col_w[1], 8, "Planned", border=1, fill=True, align="R")
    pdf.cell(col_w[2], 8, "Actual", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    fill = False
    for cat, totals in sorted(category_map.items()):
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        over = totals["actual"] > totals["planned"] and totals["planned"] > 0
        if over:
            pdf.set_text_color(220, 38, 38)  # red for overspend
        else:
            pdf.set_text_color(30, 30, 30)
        pdf.cell(col_w[0], 7, cat, border=1, fill=True)
        pdf.cell(col_w[1], 7, f"£{totals['planned']:,.2f}", border=1, align="R", fill=True)
        pdf.cell(col_w[2], 7, f"£{totals['actual']:,.2f}", border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
        fill = not fill

    pdf.set_text_color(30, 30, 30)
    pdf.ln(3)

    # Totals row
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(59, 130, 246)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_w[0], 8, "Total Expenses", border=1, fill=True)
    pdf.cell(col_w[1], 8, f"£{total_planned:,.2f}", border=1, fill=True, align="R")
    pdf.cell(col_w[2], 8, f"£{total_actual:,.2f}", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Net income row
    net_planned = salary_planned - total_planned
    net_actual = salary_actual - total_actual
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(16, 185, 129)  # green-500
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_w[0], 8, "Net Savings", border=1, fill=True)
    pdf.cell(col_w[1], 8, f"£{net_planned:,.2f}", border=1, fill=True, align="R")
    pdf.cell(col_w[2], 8, f"£{net_actual:,.2f}", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    # Footer note
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Son of Mervan — Personal Budget Tracker", new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()

    filename = f"budget_report_{month_norm}.pdf"
    return StreamingResponse(
        iter([bytes(pdf_bytes)]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -------------------- Tax helpers --------------------

def _tax_year_months(tax_year: int) -> list[str]:
    """Return the 12 YYYY-MM strings that fall within the UK tax year.

    UK tax year ``tax_year`` runs from 6 April ``tax_year`` to 5 April ``tax_year+1``.
    We treat whole calendar months, so the period is April ``tax_year`` through
    March ``tax_year+1`` inclusive.
    """
    months = []
    for m in range(4, 13):          # April → December of tax_year
        months.append(f"{tax_year:04d}-{m:02d}")
    for m in range(1, 4):           # January → March of tax_year+1
        months.append(f"{tax_year + 1:04d}-{m:02d}")
    return months


def _build_tax_summary(
    user: User,
    db: Session,
    tax_year: int,
) -> TaxSummaryResponse:
    """Aggregate MonthlyData for the given UK tax year and return a summary."""
    target_months = set(_tax_year_months(tax_year))
    all_monthly = _get_all_months(db, user)

    total_income = 0.0
    total_expenses = 0.0
    months_hit: set[str] = set()
    # category → {actual: float, month_set: set}
    cat_data: dict[str, dict] = {}

    for md in all_monthly:
        month_str = md.month
        if not month_str or month_str not in target_months:
            continue
        months_hit.add(month_str)
        total_income += float(md.salary_actual or 0.0)
        total_expenses += float(md.total_actual or 0.0)

        expenses = (
            db.query(MonthlyExpense)
            .filter(
                MonthlyExpense.monthly_data_id == md.id,
                MonthlyExpense.deleted_at == None,  # noqa: E711
            )
            .all()
        )
        for e in expenses:
            cat = e.category or "Other"
            if cat not in cat_data:
                cat_data[cat] = {"actual": 0.0, "months": set()}
            cat_data[cat]["actual"] += float(e.actual_amount or 0.0)
            cat_data[cat]["months"].add(month_str)

    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

    breakdown: list[TaxCategoryBreakdown] = []
    potentially_deductible_total = 0.0
    for cat, info in sorted(cat_data.items()):
        hmrc_heading, deductible = _HMRC_CATEGORY_MAP.get(cat, ("Other expenses", False))
        breakdown.append(
            TaxCategoryBreakdown(
                category=cat,
                hmrc_category=hmrc_heading,
                total_actual=round(info["actual"], 2),
                months_with_data=len(info["months"]),
                potentially_deductible=deductible,
            )
        )
        if deductible:
            potentially_deductible_total += info["actual"]

    return TaxSummaryResponse(
        tax_year=tax_year,
        period_start=f"{tax_year:04d}-04-06",
        period_end=f"{tax_year + 1:04d}-04-05",
        months_with_data=len(months_hit),
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_savings=round(net_savings, 2),
        savings_rate=round(savings_rate, 2),
        category_breakdown=breakdown,
        potentially_deductible_total=round(potentially_deductible_total, 2),
    )


# -------------------- Tax summary (JSON) --------------------

@router.get("/tax-summary", response_model=TaxSummaryResponse)
@limiter.limit("1/minute")
def export_tax_summary(
    request: Request,
    tax_year: int = Query(..., description="UK tax year start, e.g. 2024 for April 2024 – April 2025"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> TaxSummaryResponse:
    """Return a JSON spending summary for the given UK tax year."""
    current_year = datetime.utcnow().year
    if tax_year < 2000 or tax_year > current_year + 1:
        raise HTTPException(
            status_code=422,
            detail=f"tax_year must be between 2000 and {current_year + 1}",
        )
    user = _require_user(db, current_user)
    return _build_tax_summary(user, db, tax_year)


# -------------------- Tax PDF --------------------

@router.get("/tax-pdf")
@limiter.limit("1/minute")
def export_tax_pdf(
    request: Request,
    tax_year: int = Query(..., description="UK tax year start, e.g. 2024 for April 2024 – April 2025"),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Generate an SA302-style PDF summary for the given UK tax year."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PDF generation is not available (fpdf2 not installed)",
        )

    current_year = datetime.utcnow().year
    if tax_year < 2000 or tax_year > current_year + 1:
        raise HTTPException(
            status_code=422,
            detail=f"tax_year must be between 2000 and {current_year + 1}",
        )

    user = _require_user(db, current_user)
    summary = _build_tax_summary(user, db, tax_year)

    # ---- Build PDF ----
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header banner
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(30, 64, 175)   # blue-800
    pdf.set_text_color(255, 255, 255)
    pdf.cell(
        0, 12,
        f"Tax Year Summary — {tax_year}/{tax_year + 1}",
        fill=True, new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 5, f"Period: {summary.period_start} to {summary.period_end}  |  Generated: {generated_at}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(180, 60, 60)
    pdf.multi_cell(
        0, 5,
        "IMPORTANT: This summary is for personal reference only. Deductibility depends on "
        "your individual circumstances. Always consult a qualified accountant or HMRC guidance "
        "before submitting your Self Assessment tax return.",
    )
    pdf.ln(4)

    # Income & savings summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Income & Savings Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    col = [95, 45, 45]
    pdf.set_font("Helvetica", "", 10)
    pdf.set_fill_color(235, 243, 255)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col[0], 7, "Item", border=1, fill=True)
    pdf.cell(col[1], 7, "Amount (£)", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    rows = [
        ("Total Income (salary/actual)", summary.total_income),
        ("Total Expenses", summary.total_expenses),
        ("Net Savings", summary.net_savings),
        ("Savings Rate", None),   # percentage — handled separately
    ]
    for label, amount in rows:
        if label == "Net Savings":
            color = (16, 185, 129) if summary.net_savings >= 0 else (220, 38, 38)
            pdf.set_text_color(*color)
        else:
            pdf.set_text_color(30, 30, 30)
        pdf.cell(col[0], 7, label, border=1)
        if label == "Savings Rate":
            pdf.cell(col[1], 7, f"{summary.savings_rate:.1f}%", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(col[1], 7, f"{amount:,.2f}", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)
    pdf.ln(6)

    # Category breakdown
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Expense Breakdown by Category", new_x="LMARGIN", new_y="NEXT")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    col2 = [50, 55, 40, 30, 12]   # category, hmrc heading, actual, months, deductible flag
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(235, 243, 255)
    pdf.set_text_color(30, 30, 30)
    headers = ["Category", "HMRC Heading", "Actual (£)", "Months", "Ded."]
    for h, w in zip(headers, col2):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    fill = False
    for item in summary.category_breakdown:
        bg = (245, 250, 245) if item.potentially_deductible else (255, 255, 255)
        if fill:
            bg = tuple(max(0, c - 8) for c in bg)
        pdf.set_fill_color(*bg)
        pdf.cell(col2[0], 6, item.category, border=1, fill=True)
        pdf.cell(col2[1], 6, item.hmrc_category, border=1, fill=True)
        pdf.cell(col2[2], 6, f"{item.total_actual:,.2f}", border=1, fill=True, align="R")
        pdf.cell(col2[3], 6, str(item.months_with_data), border=1, fill=True, align="C")
        pdf.cell(col2[4], 6, "Y" if item.potentially_deductible else "N", border=1, fill=True, align="C")
        pdf.ln()
        fill = not fill

    pdf.ln(2)
    # Potentially deductible total
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 252, 231)  # green-100
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col2[0] + col2[1], 6, "Potentially Deductible Total", border=1, fill=True)
    pdf.cell(col2[2], 6, f"{summary.potentially_deductible_total:,.2f}", border=1, fill=True, align="R")
    pdf.cell(col2[3] + col2[4], 6, "", border=1, fill=True)
    pdf.ln()
    pdf.ln(6)

    # Months covered
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, f"Months with data in this tax year: {summary.months_with_data} / 12", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Disclaimer footer
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 4, "Son of Mervan — Personal Budget Tracker  |  This is not professional tax advice.", new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()
    filename = f"tax_summary_{tax_year}_{tax_year + 1}.pdf"
    return StreamingResponse(
        iter([bytes(pdf_bytes)]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
