"""Wallet handlers."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import core
from db import get_db
from schemas import ApiResponse, BootstrapRlusdRequest, WalletImportRequest


router = APIRouter(tags=["wallets"])


@router.post("/wallets/create", response_model=ApiResponse)
def create_wallet(db: Session = Depends(get_db)):
    return core.create_wallet(db)


@router.post("/wallets/import", response_model=ApiResponse)
def import_wallet(payload: WalletImportRequest, db: Session = Depends(get_db)):
    return core.import_wallet(payload, db)


@router.post("/wallets/bootstrap-rlusd", response_model=ApiResponse)
def bootstrap_rlusd_wallet(payload: BootstrapRlusdRequest, db: Session = Depends(get_db)):
    return core.bootstrap_rlusd_wallet(payload, db)


@router.get("/wallets", response_model=ApiResponse)
def list_wallets(db: Session = Depends(get_db)):
    return core.list_wallets(db)


@router.get("/wallets/{address}/balance", response_model=ApiResponse)
def get_wallet_balance(address: str):
    return core.get_wallet_balance(address)
