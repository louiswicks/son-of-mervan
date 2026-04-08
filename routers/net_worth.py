# routers/net_worth.py
"""
Net Worth Tracker — CRUD endpoints for point-in-time net worth snapshots.

Routes:
  GET    /net-worth/snapshots          list all snapshots (chronological)
  POST   /net-worth/snapshots          create a snapshot
  PUT    /net-worth/snapshots/{id}     update a snapshot
  DELETE /net-worth/snapshots/{id}     soft-delete a snapshot
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from database import get_db, NetWorthSnapshot, User
from security import verify_token
from models import (
    NetWorthSnapshotCreate,
    NetWorthSnapshotUpdate,
    NetWorthSnapshotResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/net-worth/snapshots", tags=["net_worth"])


# ---------- helpers ----------

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_snapshot(snapshot_id: int, user: User, db: Session) -> NetWorthSnapshot:
    snap = (
        db.query(NetWorthSnapshot)
        .filter(
            NetWorthSnapshot.id == snapshot_id,
            NetWorthSnapshot.user_id == user.id,
            NetWorthSnapshot.deleted_at == None,
        )
        .first()
    )
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


def _snap_to_response(snap: NetWorthSnapshot) -> dict:
    return {
        "id": snap.id,
        "snapshot_date": snap.snapshot_date,
        "assets": snap.assets_json or [],
        "liabilities": snap.liabilities_json or [],
        "total_assets": snap.total_assets,
        "total_liabilities": snap.total_liabilities,
        "net_worth": round(snap.total_assets - snap.total_liabilities, 2),
        "created_at": snap.created_at,
    }


# ---------- endpoints ----------

@router.get("", response_model=List[NetWorthSnapshotResponse])
def list_snapshots(
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    snaps = (
        db.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.user_id == user.id, NetWorthSnapshot.deleted_at == None)
        .order_by(NetWorthSnapshot.snapshot_date.asc())
        .all()
    )
    return [_snap_to_response(s) for s in snaps]


@router.post("", response_model=NetWorthSnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    body: NetWorthSnapshotCreate,
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)

    if not body.assets and not body.liabilities:
        raise HTTPException(
            status_code=422,
            detail="At least one asset or liability is required",
        )

    assets = [{"name": a.name, "value": a.value} for a in body.assets]
    liabilities = [{"name": lib.name, "value": lib.value} for lib in body.liabilities]
    total_assets = round(sum(a["value"] for a in assets), 2)
    total_liabilities = round(sum(lib["value"] for lib in liabilities), 2)

    snap = NetWorthSnapshot(
        user_id=user.id,
        snapshot_date=body.snapshot_date,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
    )
    snap.assets_json = assets
    snap.liabilities_json = liabilities

    db.add(snap)
    db.commit()
    db.refresh(snap)
    log.info("Created net worth snapshot id=%s for user=%s", snap.id, user.id)
    return _snap_to_response(snap)


@router.put("/{snapshot_id}", response_model=NetWorthSnapshotResponse)
def update_snapshot(
    body: NetWorthSnapshotUpdate,
    snapshot_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    snap = _get_snapshot(snapshot_id, user, db)

    if "snapshot_date" in body.model_fields_set and body.snapshot_date is not None:
        snap.snapshot_date = body.snapshot_date

    if "assets" in body.model_fields_set and body.assets is not None:
        assets = [{"name": a.name, "value": a.value} for a in body.assets]
        snap.assets_json = assets
        snap.total_assets = round(sum(a["value"] for a in assets), 2)

    if "liabilities" in body.model_fields_set and body.liabilities is not None:
        liabilities = [{"name": lib.name, "value": lib.value} for lib in body.liabilities]
        snap.liabilities_json = liabilities
        snap.total_liabilities = round(sum(lib["value"] for lib in liabilities), 2)

    db.commit()
    db.refresh(snap)
    return _snap_to_response(snap)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    snapshot_id: int = Path(...),
    db: Session = Depends(get_db),
    email: str = Depends(verify_token),
):
    user = _get_user(db, email)
    snap = _get_snapshot(snapshot_id, user, db)
    snap.deleted_at = datetime.utcnow()
    db.commit()
