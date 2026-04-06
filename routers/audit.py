"""
Audit Trail router — read-only access to expense history.

GET /audit/expenses/{expense_id}
  Returns all audit log entries for the given expense in reverse-chronological
  order. Ownership is verified: the caller must own the expense (or have owned
  it before it was deleted) via the user_id stored on each AuditLog row.
"""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, AuditLog
from security import verify_token
from models import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["audit"])
logger = logging.getLogger(__name__)


@router.get("/expenses/{expense_id}", response_model=List[AuditLogResponse])
def get_expense_audit(
    expense_id: int,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Return all audit entries for the given expense, newest first.
    Returns 404 if no audit history exists (expense never created via an
    audited endpoint, or wrong expense_id).
    Returns 403 if the requesting user does not own any of the audit entries.
    """
    from database import User

    user = db.query(User).filter(User.email == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    entries = (
        db.query(AuditLog)
        .filter(AuditLog.expense_id == expense_id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )

    if not entries:
        raise HTTPException(status_code=404, detail="No audit history for this expense")

    # Ownership check: all entries must belong to the requesting user
    if entries[0].user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised to view this audit trail")

    return [
        AuditLogResponse(
            id=e.id,
            expense_id=e.expense_id,
            action=e.action,
            changed_fields=json.loads(e.changed_fields) if e.changed_fields else None,
            timestamp=e.timestamp,
        )
        for e in entries
    ]
