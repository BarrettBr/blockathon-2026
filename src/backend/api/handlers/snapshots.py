"""Snapshot handlers."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import core
from handlers.auth import get_current_user
from db import get_db
from schemas import ApiResponse, SnapshotAskRequest, SnapshotCreateRequest, UserProfileSchema


router = APIRouter(tags=["snapshots"])


@router.post("/snapshots", response_model=ApiResponse)
def create_snapshot(
    payload: SnapshotCreateRequest,
    current_user: UserProfileSchema = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return core.create_financial_snapshot(current_user, payload, db)


@router.get("/snapshots", response_model=ApiResponse)
def list_snapshots(
    current_user: UserProfileSchema = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return core.list_financial_snapshots(current_user, db)


@router.get("/snapshots/{snapshot_id}", response_model=ApiResponse)
def get_snapshot(
    snapshot_id: int,
    current_user: UserProfileSchema = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return core.get_financial_snapshot(snapshot_id, current_user, db)


@router.post("/snapshots/{snapshot_id}/ask", response_model=ApiResponse)
def ask_snapshot(
    snapshot_id: int,
    payload: SnapshotAskRequest,
    current_user: UserProfileSchema = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return core.ask_financial_snapshot_question(snapshot_id, payload, current_user, db)
