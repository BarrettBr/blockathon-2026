"""Wallet API router skeleton."""

from pydantic import BaseModel
from fastapi import APIRouter

from app.xrpl.wallet import create_wallet, get_wallet_balance, import_wallet


router = APIRouter(prefix="/wallets", tags=["wallets"])


class ImportWalletRequest(BaseModel):
    seed: str


@router.post("/create")
def create_wallet_endpoint():
    """Create wallet endpoint placeholder."""
    result = create_wallet()
    return {"success": True, "data": result}


@router.post("/import")
def import_wallet_endpoint(payload: ImportWalletRequest):
    """Import wallet endpoint placeholder."""
    result = import_wallet(payload.seed)
    return {"success": True, "data": result}


@router.get("/{address}/balance")
def get_wallet_balance_endpoint(address: str):
    """Balance endpoint placeholder."""
    result = get_wallet_balance(address)
    return {"success": True, "address": address, "data": result}
