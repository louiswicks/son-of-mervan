# routers/export.py
"""
Data export endpoints.

GET /export/csv?from_month=YYYY-MM&to_month=YYYY-MM  — expense CSV download
GET /export/pdf?month=YYYY-MM                         — monthly budget report PDF

Both endpoints are rate-limited to 1 request/minute per IP.
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
from security import verify_token

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
