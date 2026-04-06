"""
routers/alerts.py — Budget alert configuration and in-app notifications.

Endpoints:
  GET    /budget-alerts                   List active alerts for current user
  POST   /budget-alerts                   Create a new alert
  PUT    /budget-alerts/{id}              Update an alert
  DELETE /budget-alerts/{id}              Soft-delete an alert

  GET    /notifications                   List notifications (newest first) + unread count
  PATCH  /notifications/{id}/read         Mark a single notification as read
  PATCH  /notifications/read-all          Mark all notifications as read
  DELETE /notifications/{id}              Delete a notification

Background job (called by APScheduler):
  check_budget_alerts(session_factory)    Evaluate thresholds and fire notifications
"""
import logging
from collections import defaultdict
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from database import (
    BudgetAlert,
    MonthlyData,
    MonthlyExpense,
    Notification,
    User,
    get_db,
)
from email_utils import send_budget_alert_email
from models import (
    BudgetAlertCreate,
    BudgetAlertResponse,
    BudgetAlertUpdate,
    NotificationListResponse,
    NotificationResponse,
    VALID_CATEGORIES,
)
from security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()


# -------------------- Helpers --------------------

def _get_user(email: str, db: Session) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _get_owned_alert(alert_id: int, user: User, db: Session) -> BudgetAlert:
    alert = db.query(BudgetAlert).filter(
        BudgetAlert.id == alert_id,
        BudgetAlert.user_id == user.id,
        BudgetAlert.deleted_at == None,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _alert_to_response(a: BudgetAlert) -> BudgetAlertResponse:
    return BudgetAlertResponse(
        id=a.id,
        category=a.category or "",
        threshold_pct=a.threshold_pct,
        active=a.active,
        created_at=a.created_at,
    )


def _notif_to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        type=n.type,
        title=n.title or "",
        message=n.message or "",
        read_at=n.read_at,
        created_at=n.created_at,
    )


# -------------------- Budget Alert Endpoints --------------------

@router.get("/budget-alerts", response_model=List[BudgetAlertResponse])
def list_alerts(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    alerts = (
        db.query(BudgetAlert)
        .filter(BudgetAlert.user_id == user.id, BudgetAlert.deleted_at == None)
        .order_by(BudgetAlert.created_at.desc())
        .all()
    )
    return [_alert_to_response(a) for a in alerts]


@router.post("/budget-alerts", response_model=BudgetAlertResponse, status_code=201)
def create_alert(
    payload: BudgetAlertCreate,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"category must be one of: {sorted(VALID_CATEGORIES)}",
        )
    if not (1 <= payload.threshold_pct <= 100):
        raise HTTPException(status_code=422, detail="threshold_pct must be between 1 and 100")

    user = _get_user(current_user, db)

    # Prevent duplicate active alerts for the same category
    existing_alerts = (
        db.query(BudgetAlert)
        .filter(BudgetAlert.user_id == user.id, BudgetAlert.deleted_at == None)
        .all()
    )
    for a in existing_alerts:
        if a.category == payload.category:
            raise HTTPException(
                status_code=409,
                detail=f"An active alert for '{payload.category}' already exists",
            )

    alert = BudgetAlert(
        user_id=user.id,
        threshold_pct=payload.threshold_pct,
        active=True,
    )
    alert.category = payload.category
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_to_response(alert)


@router.put("/budget-alerts/{alert_id}", response_model=BudgetAlertResponse)
def update_alert(
    alert_id: int = Path(...),
    payload: BudgetAlertUpdate = None,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    alert = _get_owned_alert(alert_id, user, db)

    if payload.category is not None:
        if payload.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=422,
                detail=f"category must be one of: {sorted(VALID_CATEGORIES)}",
            )
        alert.category = payload.category
    if payload.threshold_pct is not None:
        if not (1 <= payload.threshold_pct <= 100):
            raise HTTPException(status_code=422, detail="threshold_pct must be between 1 and 100")
        alert.threshold_pct = payload.threshold_pct
    if payload.active is not None:
        alert.active = payload.active

    db.commit()
    db.refresh(alert)
    return _alert_to_response(alert)


@router.delete("/budget-alerts/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int = Path(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    alert = _get_owned_alert(alert_id, user, db)
    alert.deleted_at = datetime.utcnow()
    db.commit()


# -------------------- Notification Endpoints --------------------

@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread_count = sum(1 for n in notifications if n.read_at is None)
    return NotificationListResponse(
        items=[_notif_to_response(n) for n in notifications],
        unread_count=unread_count,
    )


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int = Path(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.read_at is None:
        notif.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notif)
    return _notif_to_response(notif)


@router.patch("/notifications/read-all", status_code=204)
def mark_all_read(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    now = datetime.utcnow()
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.read_at == None,
    ).update({"read_at": now})
    db.commit()


@router.delete("/notifications/{notification_id}", status_code=204)
def delete_notification(
    notification_id: int = Path(...),
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = _get_user(current_user, db)
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()


# -------------------- Background Job --------------------

def check_budget_alerts(session_factory):
    """
    Evaluate all active budget alerts and create in-app notifications +
    send emails when a category's actual spending breaches the threshold.

    Called daily by APScheduler (00:10 UTC) after recurring expense generation.
    Deduplication: one notification per alert per calendar month.
    """
    db = session_factory()
    try:
        current_month = datetime.utcnow().strftime("%Y-%m")

        # Load all active, non-deleted alerts
        alerts = (
            db.query(BudgetAlert)
            .filter(BudgetAlert.deleted_at == None, BudgetAlert.active == True)
            .all()
        )
        if not alerts:
            return

        # Group alerts by user_id to avoid redundant DB lookups
        alerts_by_user: dict[int, list[BudgetAlert]] = defaultdict(list)
        for a in alerts:
            alerts_by_user[a.user_id].append(a)

        for user_id, user_alerts in alerts_by_user.items():
            user = db.query(User).filter(User.id == user_id).first()
            if not user or user.deleted_at is not None:
                continue

            # Find the MonthlyData row for the current month
            all_months = (
                db.query(MonthlyData)
                .filter(MonthlyData.user_id == user_id)
                .all()
            )
            month_row = next((m for m in all_months if m.month == current_month), None)
            if not month_row:
                continue

            # Fetch and decrypt all active expenses for the month
            expenses = (
                db.query(MonthlyExpense)
                .filter(
                    MonthlyExpense.monthly_data_id == month_row.id,
                    MonthlyExpense.deleted_at == None,
                )
                .all()
            )

            # Aggregate planned/actual by category
            category_planned: dict[str, float] = defaultdict(float)
            category_actual: dict[str, float] = defaultdict(float)
            for e in expenses:
                cat = e.category or "Other"
                category_planned[cat] += e.planned_amount or 0.0
                category_actual[cat] += e.actual_amount or 0.0

            for alert in user_alerts:
                cat = alert.category or ""
                planned = category_planned.get(cat, 0.0)
                if planned <= 0:
                    continue

                actual = category_actual.get(cat, 0.0)
                ratio_pct = (actual / planned) * 100.0

                if ratio_pct < alert.threshold_pct:
                    continue

                # Deduplication: one notification per alert per month
                dedup_key = f"ba:{alert.id}:{current_month}"
                already_sent = (
                    db.query(Notification)
                    .filter(Notification.dedup_key == dedup_key)
                    .first()
                )
                if already_sent:
                    continue

                pct_display = round(ratio_pct, 1)
                notif = Notification(
                    user_id=user_id,
                    type="budget_alert",
                    dedup_key=dedup_key,
                )
                notif.title = f"{cat} Budget Alert"
                notif.message = (
                    f"Your {cat} spending has reached {pct_display}% of your planned budget "
                    f"(£{actual:.2f} of £{planned:.2f} planned)."
                )
                db.add(notif)
                db.commit()

                try:
                    send_budget_alert_email(
                        user.email, cat, pct_display, actual, planned, current_month
                    )
                except Exception:
                    logger.exception(
                        "Failed to send budget alert email to %s for category %s",
                        user.email, cat,
                    )

    except Exception:
        logger.exception("check_budget_alerts background job failed")
    finally:
        db.close()
