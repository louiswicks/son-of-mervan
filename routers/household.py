# routers/household.py
"""
Household Accounts — shared budget between an owner and invited members.

Routes:
  POST   /households                     Create a new household (caller becomes owner)
  GET    /households/me                  Get the household the current user belongs to
  POST   /households/invite              Owner invites a user by email (sends link)
  POST   /households/join                Accept an invite via token
  DELETE /households/members/{user_id}   Owner removes a member (cannot remove self)
  DELETE /households                     Owner dissolves the household
  GET    /households/budget?month=…      Combined budget view for all members
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import List

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import (
    get_db,
    Household,
    HouseholdInvite,
    HouseholdMembership,
    MonthlyData,
    User,
)
from security import verify_token
from models import (
    HouseholdBudgetMemberSummary,
    HouseholdBudgetResponse,
    HouseholdCreate,
    HouseholdInviteRequest,
    HouseholdJoinRequest,
    HouseholdResponse,
    MemberResponse,
)

log = logging.getLogger(__name__)

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@sonofmervan.app")

router = APIRouter(prefix="/households", tags=["household"])


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_membership(db: Session, user_id: int) -> HouseholdMembership | None:
    return (
        db.query(HouseholdMembership)
        .join(Household)
        .filter(
            HouseholdMembership.user_id == user_id,
            Household.deleted_at == None,
        )
        .first()
    )


def _require_household(db: Session, user: User) -> tuple[Household, HouseholdMembership]:
    membership = _get_membership(db, user.id)
    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of any household")
    household = db.query(Household).filter(Household.id == membership.household_id).first()
    return household, membership


def _require_owner(membership: HouseholdMembership) -> None:
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the household owner can perform this action")


def _build_response(household: Household, db: Session) -> HouseholdResponse:
    members: List[MemberResponse] = []
    for m in household.memberships:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u:
            members.append(
                MemberResponse(
                    user_id=u.id,
                    email=u.email,
                    username=u.username,
                    role=m.role,
                    joined_at=m.joined_at,
                )
            )

    pending = [
        inv.invitee_email
        for inv in household.invites
        if inv.accepted_at is None and inv.expires_at > datetime.utcnow()
    ]

    return HouseholdResponse(
        id=household.id,
        name=household.name,
        owner_id=household.owner_id,
        members=members,
        pending_invites=pending,
        created_at=household.created_at,
    )


def _send_household_invite_email(to_email: str, invite_url: str, household_name: str) -> None:
    if not SENDGRID_API_KEY:
        log.info("[DEV] Household invite link for %s: %s", to_email, invite_url)
        return

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": EMAIL_FROM},
        "subject": f"You've been invited to join '{household_name}' — Son of Mervan",
        "content": [{
            "type": "text/plain",
            "value": (
                f"You've been invited to join the household budget '{household_name}' on Son of Mervan.\n\n"
                f"Click the link below to accept the invitation:\n{invite_url}\n\n"
                "This invitation expires in 7 days. If you do not have a Son of Mervan account, "
                "please sign up first.\n\n"
                "If you were not expecting this invitation, you can safely ignore this email."
            ),
        }],
    }

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 202):
            log.info("[SG] household invite accepted (%d) to=%s", r.status_code, to_email)
        else:
            log.error("[SG] household invite ERROR %d: %s", r.status_code, r.text)
    except Exception as exc:
        log.exception("[SG] EXCEPTION sending household invite to %s: %s", to_email, exc)


# ---------- endpoints ----------

@router.post("", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create_household(
    body: HouseholdCreate,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """Create a new household. The caller becomes the owner."""
    user = _get_user(db, email)

    # A user can only belong to one household at a time
    if _get_membership(db, user.id):
        raise HTTPException(status_code=409, detail="You already belong to a household")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Household name cannot be empty")

    household = Household(owner_id=user.id, name=name)
    db.add(household)
    db.flush()  # get household.id before adding membership

    membership = HouseholdMembership(
        household_id=household.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(household)
    log.info("Created household id=%s owner=%s", household.id, user.id)
    return _build_response(household, db)


@router.get("/me", response_model=HouseholdResponse)
def get_my_household(
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """Return the household the current user belongs to."""
    user = _get_user(db, email)
    household, _ = _require_household(db, user)
    return _build_response(household, db)


@router.post("/invite", status_code=status.HTTP_204_NO_CONTENT)
def invite_member(
    body: HouseholdInviteRequest,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """Owner sends an invite email to a new member."""
    user = _get_user(db, email)
    household, membership = _require_household(db, user)
    _require_owner(membership)

    invitee_email = body.email.strip().lower()
    if not invitee_email:
        raise HTTPException(status_code=422, detail="email is required")

    # Cannot invite yourself
    if invitee_email == user.email.lower():
        raise HTTPException(status_code=422, detail="You cannot invite yourself")

    # Cannot invite someone already in this household
    invitee_user = db.query(User).filter(User.email == invitee_email, User.deleted_at == None).first()
    if invitee_user:
        existing_membership = (
            db.query(HouseholdMembership)
            .filter(
                HouseholdMembership.household_id == household.id,
                HouseholdMembership.user_id == invitee_user.id,
            )
            .first()
        )
        if existing_membership:
            raise HTTPException(status_code=409, detail="This user is already a member of the household")

    # Expire any previous pending invite for this email in this household
    old_invites = (
        db.query(HouseholdInvite)
        .filter(
            HouseholdInvite.household_id == household.id,
            HouseholdInvite.invitee_email == invitee_email,
            HouseholdInvite.accepted_at == None,
        )
        .all()
    )
    for inv in old_invites:
        inv.expires_at = datetime.utcnow()  # expire immediately

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invite = HouseholdInvite(
        household_id=household.id,
        invitee_email=invitee_email,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)
    db.commit()

    invite_url = f"{FRONTEND_BASE_URL}/household/join?token={raw_token}"
    _send_household_invite_email(invitee_email, invite_url, household.name)
    log.info("Household invite sent household=%s to=%s", household.id, invitee_email)


@router.post("/join", response_model=HouseholdResponse)
def join_household(
    body: HouseholdJoinRequest,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """Accept a household invite using the token from the email link."""
    user = _get_user(db, email)

    if _get_membership(db, user.id):
        raise HTTPException(status_code=409, detail="You already belong to a household")

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    invite = (
        db.query(HouseholdInvite)
        .filter(
            HouseholdInvite.token_hash == token_hash,
            HouseholdInvite.accepted_at == None,
        )
        .first()
    )

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already used")

    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Invite has expired")

    # The invite is addressed to the user's email; enforce that only the right account can accept
    if invite.invitee_email != user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="This invite was sent to a different email address",
        )

    household = db.query(Household).filter(
        Household.id == invite.household_id,
        Household.deleted_at == None,
    ).first()
    if not household:
        raise HTTPException(status_code=404, detail="Household no longer exists")

    invite.accepted_at = datetime.utcnow()
    membership = HouseholdMembership(
        household_id=household.id,
        user_id=user.id,
        role="member",
    )
    db.add(membership)
    db.commit()
    db.refresh(household)
    log.info("User id=%s joined household id=%s", user.id, household.id)
    return _build_response(household, db)


@router.delete("/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    member_user_id: int,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """Owner removes a member (cannot remove self/owner row)."""
    user = _get_user(db, email)
    household, membership = _require_household(db, user)
    _require_owner(membership)

    if member_user_id == user.id:
        raise HTTPException(status_code=422, detail="Owner cannot remove themselves; dissolve the household instead")

    target = (
        db.query(HouseholdMembership)
        .filter(
            HouseholdMembership.household_id == household.id,
            HouseholdMembership.user_id == member_user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found in this household")

    db.delete(target)
    db.commit()
    log.info("Removed user id=%s from household id=%s by owner=%s", member_user_id, household.id, user.id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def dissolve_household(
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """Owner dissolves the household (soft-delete). All members lose access."""
    user = _get_user(db, email)
    household, membership = _require_household(db, user)
    _require_owner(membership)

    household.deleted_at = datetime.utcnow()
    db.commit()
    log.info("Household id=%s dissolved by owner=%s", household.id, user.id)


@router.get("/budget", response_model=HouseholdBudgetResponse)
def get_household_budget(
    month: str = Query(..., description="Month in YYYY-MM format"),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    """
    Return a combined budget view for all household members for a given month.
    Each member's MonthlyData is fetched; totals are aggregated across all members.
    """
    user = _get_user(db, email)
    household, _ = _require_household(db, user)

    member_summaries: List[HouseholdBudgetMemberSummary] = []

    combined_salary_planned = 0.0
    combined_salary_actual = 0.0
    combined_expenses_planned = 0.0
    combined_expenses_actual = 0.0

    for m in household.memberships:
        member_user = db.query(User).filter(User.id == m.user_id).first()
        if not member_user:
            continue

        # Decrypt all monthly records and find the one matching this month (O(n) by design)
        all_monthly = (
            db.query(MonthlyData)
            .filter(MonthlyData.user_id == member_user.id)
            .all()
        )
        monthly = next((r for r in all_monthly if r.month == month), None)

        if monthly:
            sp = monthly.salary_planned
            sa = monthly.salary_actual
            tp = monthly.total_planned
            ta = monthly.total_actual
            rp = monthly.remaining_planned
            ra = monthly.remaining_actual
        else:
            sp = sa = tp = ta = rp = ra = 0.0

        member_summaries.append(
            HouseholdBudgetMemberSummary(
                user_id=member_user.id,
                email=member_user.email,
                username=member_user.username,
                salary_planned=sp,
                salary_actual=sa,
                total_expenses_planned=tp,
                total_expenses_actual=ta,
                remaining_planned=rp,
                remaining_actual=ra,
            )
        )

        combined_salary_planned += sp
        combined_salary_actual += sa
        combined_expenses_planned += tp
        combined_expenses_actual += ta

    combined_remaining_planned = round(combined_salary_planned - combined_expenses_planned, 2)
    combined_remaining_actual = round(combined_salary_actual - combined_expenses_actual, 2)

    return HouseholdBudgetResponse(
        month=month,
        members=member_summaries,
        combined_salary_planned=round(combined_salary_planned, 2),
        combined_salary_actual=round(combined_salary_actual, 2),
        combined_expenses_planned=round(combined_expenses_planned, 2),
        combined_expenses_actual=round(combined_expenses_actual, 2),
        combined_remaining_planned=combined_remaining_planned,
        combined_remaining_actual=combined_remaining_actual,
    )
