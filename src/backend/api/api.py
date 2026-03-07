"""Single-file API endpoints for hackathon iteration speed.

TODO:
- Add auth layer for wallet/payment endpoints.
- Add request validation for XRPL address formats and amount precision.
- Extract service helpers once this file becomes hard to navigate.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from db import Subscription, Transaction, Wallet, get_db


router = APIRouter()


def _get_xrpl_client() -> Any:
    try:
        from xrpl.clients import JsonRpcClient
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "xrpl-py is not installed. Install it with `pip install xrpl-py` "
                "to enable XRPL features."
            ),
        ) from exc
    return JsonRpcClient(settings.XRPL_RPC_URL)


class ImportWalletRequest(BaseModel):
    seed: str


class SendPaymentRequest(BaseModel):
    seed: str = Field(..., description="Source wallet seed")
    destination: str
    amount_xrp: float = Field(..., gt=0)


class CreateSubscriptionRequest(BaseModel):
    owner_address: str
    amount_xrp: float = Field(..., gt=0)
    interval: str = "monthly"


@router.get("/health")
def health():
    client_ok = True
    error = None
    try:
        _get_xrpl_client()
    except HTTPException as exc:
        client_ok = False
        error = exc.detail

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "network": settings.XRPL_NETWORK,
        "xrpl_client_ready": client_ok,
        "error": error,
    }


@router.post("/wallets/create")
def create_wallet(db: Session = Depends(get_db)):
    """Create XRPL wallet (and optionally fund on testnet/devnet)."""
    client = _get_xrpl_client()

    try:
        from xrpl.wallet import Wallet as XRPLWallet
        from xrpl.wallet import generate_faucet_wallet

        if settings.AUTO_FUND_NEW_WALLETS:
            wallet = generate_faucet_wallet(client)
        else:
            wallet = XRPLWallet.create()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Wallet creation failed: {exc}") from exc

    record = Wallet(address=wallet.classic_address, seed=wallet.seed, network=settings.XRPL_NETWORK)
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Wallet created",
        "wallet": {
            "id": record.id,
            "address": record.address,
            "seed": record.seed,
            "network": record.network,
        },
    }


@router.post("/wallets/import")
def import_wallet(payload: ImportWalletRequest, db: Session = Depends(get_db)):
    """Connect/import an existing wallet from seed."""
    try:
        from xrpl.wallet import Wallet as XRPLWallet

        wallet = XRPLWallet.from_seed(payload.seed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid seed: {exc}") from exc

    existing = db.query(Wallet).filter(Wallet.address == wallet.classic_address).first()
    if not existing:
        existing = Wallet(
            address=wallet.classic_address,
            seed=payload.seed,
            network=settings.XRPL_NETWORK,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

    return {
        "message": "Wallet connected",
        "wallet": {
            "id": existing.id,
            "address": existing.address,
            "network": existing.network,
        },
    }


@router.post("/wallets/connect")
def connect_wallet(payload: ImportWalletRequest, db: Session = Depends(get_db)):
    """Alias for wallet import to match hackathon terminology."""
    return import_wallet(payload, db)


@router.get("/wallets/{address}/balance")
def wallet_balance(address: str):
    client = _get_xrpl_client()

    try:
        from xrpl.models.requests import AccountInfo

        result = client.request(
            AccountInfo(account=address, ledger_index="validated", strict=True)
        ).result
        drops = result.get("account_data", {}).get("Balance")
        balance_xrp = (int(drops) / 1_000_000) if drops is not None else None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Balance fetch failed: {exc}") from exc

    return {
        "address": address,
        "balance_xrp": balance_xrp,
        "ledger_index": result.get("ledger_index"),
    }


@router.post("/payments/send")
def send_payment(payload: SendPaymentRequest, db: Session = Depends(get_db)):
    client = _get_xrpl_client()

    try:
        from xrpl.models.transactions import Payment
        from xrpl.transaction import submit_and_wait
        from xrpl.utils import xrp_to_drops
        from xrpl.wallet import Wallet as XRPLWallet

        wallet = XRPLWallet.from_seed(payload.seed)
        tx = Payment(
            account=wallet.classic_address,
            destination=payload.destination,
            amount=xrp_to_drops(str(payload.amount_xrp)),
        )
        tx_response = submit_and_wait(tx, client, wallet)
        result = tx_response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Payment failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_record = Transaction(
        tx_hash=tx_hash,
        source_address=wallet.classic_address,
        destination_address=payload.destination,
        amount_xrp=payload.amount_xrp,
        status=(result.get("meta", {}).get("TransactionResult") or "submitted"),
    )
    db.add(tx_record)
    db.commit()
    db.refresh(tx_record)

    return {
        "message": "Payment submitted",
        "transaction": {
            "id": tx_record.id,
            "tx_hash": tx_record.tx_hash,
            "status": tx_record.status,
        },
    }


@router.get("/payments/{tx_hash}")
def payment_status(tx_hash: str):
    client = _get_xrpl_client()

    try:
        from xrpl.models.requests import Tx

        result = client.request(Tx(transaction=tx_hash)).result
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {exc}") from exc

    return {
        "tx_hash": tx_hash,
        "validated": result.get("validated"),
        "status": result.get("meta", {}).get("TransactionResult"),
        "result": result,
    }


@router.post("/subscriptions/create")
def create_subscription(payload: CreateSubscriptionRequest, db: Session = Depends(get_db)):
    """Basic DB-only subscription placeholder for later XRPL escrow logic."""
    sub = Subscription(
        owner_address=payload.owner_address,
        amount_xrp=payload.amount_xrp,
        interval=payload.interval,
        status="active",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {
        "message": "Subscription created",
        "subscription": {
            "id": sub.id,
            "owner_address": sub.owner_address,
            "amount_xrp": sub.amount_xrp,
            "interval": sub.interval,
            "status": sub.status,
        },
    }


@router.post("/subscriptions/{subscription_id}/cancel")
def cancel_subscription(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.status = "cancelled"
    db.commit()

    return {
        "message": "Subscription cancelled",
        "subscription": {
            "id": sub.id,
            "status": sub.status,
        },
    }
