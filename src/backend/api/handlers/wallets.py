"""Wallet handlers."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import core
from db import get_db
from schemas import ApiResponse, BootstrapRlusdRequest, WalletConnectRequest, WalletImportRequest
from handlers.auth import get_current_user
from db import UserProfile


router = APIRouter(tags=["wallets"])


@router.post("/wallets/create", response_model=ApiResponse)
def create_wallet(db: Session = Depends(get_db)):
    return core.create_wallet(db)


@router.post("/wallets/import", response_model=ApiResponse)
def import_wallet(
        payload: WalletImportRequest,
        db: Session = Depends(get_db),
        current_user: UserProfile = Depends(get_current_user),
):
    return core.import_wallet(payload, db)


@router.post("/wallets/connect", response_model=ApiResponse)
def connect_wallet(
    payload: WalletConnectRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    return core.connect_user_wallet(payload, current_user, db)


@router.post("/wallets/bootstrap-rlusd", response_model=ApiResponse)
def bootstrap_rlusd_wallet(
        payload: BootstrapRlusdRequest, 
        db: Session = Depends(get_db),
        current_user: UserProfile = Depends(get_current_user)
):
    return core.bootstrap_rlusd_wallet(payload, db)


@router.get("/wallets", response_model=ApiResponse)
def list_wallets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    return core.list_connected_wallets(current_user, db, page, page_size)


@router.delete("/wallets/connected/{link_id}", response_model=ApiResponse)
def delete_connected_wallet(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    return core.delete_connected_wallet(link_id, current_user, db)


@router.get("/wallets/aggregate/balance", response_model=ApiResponse)
def get_aggregate_balance(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    return core.get_aggregate_wallet_balance(current_user, db)


@router.get("/wallets/{address}/balance", response_model=ApiResponse)
def get_wallet_balance(address: str, current_user: UserProfile = Depends(get_current_user)):
    return core.get_wallet_balance(address)
