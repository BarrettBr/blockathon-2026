"""API router for XRPL Financial Hub MVP."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from db import Subscription, Transaction, Wallet, get_db


router = APIRouter()


def _success(message: str, data: Any) -> dict[str, Any]:
    return {"message": message, "data": data}


def _require_xrpl() -> None:
    try:
        import xrpl  # noqa: F401
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="xrpl-py is not installed. Run: pip install xrpl-py",
        ) from exc


def _get_xrpl_client() -> Any:
    _require_xrpl()
    from xrpl.clients import JsonRpcClient

    return JsonRpcClient(settings.XRPL_RPC_URL)


def _is_valid_classic_address(address: str) -> bool:
    _require_xrpl()
    from xrpl.core.addresscodec import is_valid_classic_address

    return is_valid_classic_address(address)


def _xrp_to_drops(amount_xrp: float) -> str:
    _require_xrpl()
    from xrpl.utils import xrp_to_drops

    return xrp_to_drops(str(amount_xrp))


def _drops_to_xrp_float(drops: Optional[str]) -> Optional[float]:
    if drops is None:
        return None
    return float((Decimal(drops) / Decimal("1000000")).quantize(Decimal("0.000001")))


def _save_or_get_wallet(db: Session, address: str, seed: str) -> Wallet:
    wallet_row = db.query(Wallet).filter(Wallet.address == address).first()
    if wallet_row:
        wallet_row.seed = seed
        wallet_row.network = settings.XRPL_NETWORK
        db.commit()
        db.refresh(wallet_row)
        return wallet_row

    wallet_row = Wallet(address=address, seed=seed, network=settings.XRPL_NETWORK)
    db.add(wallet_row)
    db.commit()
    db.refresh(wallet_row)
    return wallet_row


def _send_xrp_payment(sender_seed: str, destination_address: str, amount_xrp: float) -> dict[str, Any]:
    if not _is_valid_classic_address(destination_address):
        raise HTTPException(status_code=400, detail="Invalid destination address")

    client = _get_xrpl_client()

    try:
        from xrpl.models.transactions import Payment
        from xrpl.transaction import submit_and_wait
        from xrpl.wallet import Wallet as XRPLWallet

        sender_wallet = XRPLWallet.from_seed(sender_seed)
        tx = Payment(
            account=sender_wallet.classic_address,
            destination=destination_address,
            amount=_xrp_to_drops(amount_xrp),
        )
        response = submit_and_wait(tx, client, sender_wallet)
        result = response.result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Payment failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_status = (
        result.get("meta", {}).get("TransactionResult")
        or result.get("engine_result")
        or "unknown"
    )

    return {
        "tx_hash": tx_hash,
        "status": tx_status,
        "from_address": sender_wallet.classic_address,
        "to_address": destination_address,
        "validated": result.get("validated", False),
        "ledger_index": result.get("ledger_index"),
        "raw_result": result,
    }


class WalletImportRequest(BaseModel):
    seed: str = Field(..., min_length=8)


class PaymentSendRequest(BaseModel):
    sender_seed: str = Field(..., min_length=8)
    destination_address: str = Field(..., min_length=25)
    amount_xrp: float = Field(..., gt=0)


class SubscriptionCreateRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    merchant_wallet_address: str = Field(..., min_length=25)
    user_seed: str = Field(..., min_length=8)
    amount_xrp: float = Field(..., gt=0)
    interval_days: int = Field(30, ge=1)


class ApiResponse(BaseModel):
    message: str
    data: Any


@router.get("/health", response_model=ApiResponse)
def health() -> dict[str, Any]:
    xrpl_ready = True
    xrpl_error = None
    try:
        client = _get_xrpl_client()
        from xrpl.models.requests import ServerInfo

        client.request(ServerInfo())
    except Exception as exc:
        xrpl_ready = False
        xrpl_error = str(exc)

    return _success(
        "Service health",
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "network": settings.XRPL_NETWORK,
            "xrpl_rpc_url": settings.XRPL_RPC_URL,
            "xrpl_ready": xrpl_ready,
            "xrpl_error": xrpl_error,
        },
    )


@router.post("/wallets/create", response_model=ApiResponse)
def create_wallet(db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _get_xrpl_client()

    try:
        from xrpl.wallet import Wallet as XRPLWallet
        from xrpl.wallet import generate_faucet_wallet

        funding_message = None
        funded = False
        wallet = None

        if settings.AUTO_FUND_NEW_WALLETS:
            attempts = max(settings.FAUCET_RETRIES, 0) + 1
            last_error = None
            for _ in range(attempts):
                try:
                    wallet = generate_faucet_wallet(client)
                    funded = True
                    break
                except Exception as exc:
                    last_error = str(exc)
            if wallet is None:
                wallet = XRPLWallet.create()
                funding_message = f"Faucet funding failed, returned unfunded wallet: {last_error}"
        else:
            wallet = XRPLWallet.create()
            funding_message = "AUTO_FUND_NEW_WALLETS=false, wallet not faucet-funded"

        wallet_row = _save_or_get_wallet(db, wallet.classic_address, wallet.seed)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Wallet creation failed: {exc}") from exc

    return _success(
        "Wallet created",
        {
            "id": wallet_row.id,
            "address": wallet_row.address,
            "seed": wallet_row.seed,
            "network": wallet_row.network,
            "funded": funded,
            "funding_message": funding_message,
        },
    )


@router.post("/wallets/import", response_model=ApiResponse)
def import_wallet(payload: WalletImportRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        from xrpl.wallet import Wallet as XRPLWallet

        wallet = XRPLWallet.from_seed(payload.seed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid seed: {exc}") from exc

    wallet_row = _save_or_get_wallet(db, wallet.classic_address, payload.seed)
    return _success(
        "Wallet imported",
        {
            "id": wallet_row.id,
            "address": wallet_row.address,
            "seed": wallet_row.seed,
            "network": wallet_row.network,
        },
    )


@router.get("/wallets", response_model=ApiResponse)
def list_wallets(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.query(Wallet).order_by(Wallet.created_at.desc()).all()
    return _success(
        "Wallet list",
        [
            {
                "id": row.id,
                "address": row.address,
                "seed": row.seed,
                "network": row.network,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    )


@router.get("/wallets/{address}/balance", response_model=ApiResponse)
def get_wallet_balance(address: str) -> dict[str, Any]:
    if not _is_valid_classic_address(address):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    client = _get_xrpl_client()

    try:
        from xrpl.models.requests import AccountInfo

        result = client.request(
            AccountInfo(account=address, ledger_index="validated", strict=True)
        ).result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Balance lookup failed: {exc}") from exc

    drops = result.get("account_data", {}).get("Balance")
    return _success(
        "Wallet balance",
        {
            "address": address,
            "balance_xrp": _drops_to_xrp_float(drops),
            "balance_drops": drops,
            "ledger_index": result.get("ledger_index"),
        },
    )


@router.post("/payments/send", response_model=ApiResponse)
def send_payment(payload: PaymentSendRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    payment_result = _send_xrp_payment(
        sender_seed=payload.sender_seed,
        destination_address=payload.destination_address,
        amount_xrp=payload.amount_xrp,
    )

    tx_row = Transaction(
        tx_hash=payment_result["tx_hash"],
        tx_type="payment",
        from_address=payment_result["from_address"],
        to_address=payment_result["to_address"],
        amount_xrp=payload.amount_xrp,
        status=payment_result["status"],
    )
    db.add(tx_row)
    db.commit()
    db.refresh(tx_row)

    return _success(
        "Payment sent",
        {
            "id": tx_row.id,
            "tx_hash": tx_row.tx_hash,
            "status": tx_row.status,
            "from_address": tx_row.from_address,
            "to_address": tx_row.to_address,
            "amount_xrp": tx_row.amount_xrp,
            "validated": payment_result["validated"],
            "ledger_index": payment_result["ledger_index"],
        },
    )


@router.get("/payments", response_model=ApiResponse)
def list_payments(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.query(Transaction).order_by(Transaction.created_at.desc()).all()
    return _success(
        "Payment list",
        [
            {
                "id": row.id,
                "tx_hash": row.tx_hash,
                "tx_type": row.tx_type,
                "from_address": row.from_address,
                "to_address": row.to_address,
                "amount_xrp": row.amount_xrp,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    )


@router.get("/payments/{tx_hash}", response_model=ApiResponse)
def get_payment(tx_hash: str) -> dict[str, Any]:
    client = _get_xrpl_client()

    try:
        from xrpl.models.requests import Tx

        result = client.request(Tx(transaction=tx_hash)).result
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {exc}") from exc

    tx_json = result.get("tx_json", {})
    amount_raw = tx_json.get("Amount")
    amount_xrp = None
    if isinstance(amount_raw, str) and amount_raw.isdigit():
        amount_xrp = _drops_to_xrp_float(amount_raw)

    return _success(
        "Payment details",
        {
            "tx_hash": tx_hash,
            "validated": result.get("validated", False),
            "status": result.get("meta", {}).get("TransactionResult"),
            "tx_type": tx_json.get("TransactionType"),
            "from_address": tx_json.get("Account"),
            "to_address": tx_json.get("Destination"),
            "amount_xrp": amount_xrp,
            "ledger_index": result.get("ledger_index"),
            "raw_result": result,
        },
    )


@router.post("/subscriptions/create", response_model=ApiResponse)
def create_subscription(
    payload: SubscriptionCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.user_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid user_wallet_address")
    if not _is_valid_classic_address(payload.merchant_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid merchant_wallet_address")

    today = date.today()
    row = Subscription(
        user_wallet_address=payload.user_wallet_address,
        merchant_wallet_address=payload.merchant_wallet_address,
        user_seed=payload.user_seed,
        amount_xrp=payload.amount_xrp,
        interval_days=payload.interval_days,
        status="active",
        start_date=today,
        next_payment_date=today,
        last_tx_hash=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return _success(
        "Subscription created",
        {
            "id": row.id,
            "user_wallet_address": row.user_wallet_address,
            "merchant_wallet_address": row.merchant_wallet_address,
            "amount_xrp": row.amount_xrp,
            "interval_days": row.interval_days,
            "status": row.status,
            "start_date": row.start_date.isoformat(),
            "next_payment_date": row.next_payment_date.isoformat(),
            "last_tx_hash": row.last_tx_hash,
        },
    )


@router.get("/subscriptions", response_model=ApiResponse)
def list_subscriptions(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.query(Subscription).order_by(Subscription.created_at.desc()).all()
    return _success(
        "Subscription list",
        [
            {
                "id": row.id,
                "user_wallet_address": row.user_wallet_address,
                "merchant_wallet_address": row.merchant_wallet_address,
                "amount_xrp": row.amount_xrp,
                "interval_days": row.interval_days,
                "status": row.status,
                "start_date": row.start_date.isoformat(),
                "next_payment_date": row.next_payment_date.isoformat(),
                "last_tx_hash": row.last_tx_hash,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ],
    )


@router.get("/subscriptions/{subscription_id}", response_model=ApiResponse)
def get_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return _success(
        "Subscription details",
        {
            "id": row.id,
            "user_wallet_address": row.user_wallet_address,
            "merchant_wallet_address": row.merchant_wallet_address,
            "amount_xrp": row.amount_xrp,
            "interval_days": row.interval_days,
            "status": row.status,
            "start_date": row.start_date.isoformat(),
            "next_payment_date": row.next_payment_date.isoformat(),
            "last_tx_hash": row.last_tx_hash,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        },
    )


@router.post("/subscriptions/{subscription_id}/process", response_model=ApiResponse)
def process_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.status != "active":
        raise HTTPException(status_code=409, detail="Subscription is not active")

    payment_result = _send_xrp_payment(
        sender_seed=row.user_seed,
        destination_address=row.merchant_wallet_address,
        amount_xrp=row.amount_xrp,
    )

    tx_row = Transaction(
        tx_hash=payment_result["tx_hash"],
        tx_type="subscription_payment",
        from_address=payment_result["from_address"],
        to_address=payment_result["to_address"],
        amount_xrp=row.amount_xrp,
        status=payment_result["status"],
    )
    db.add(tx_row)

    row.last_tx_hash = tx_row.tx_hash
    row.next_payment_date = row.next_payment_date + timedelta(days=row.interval_days)
    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)

    return _success(
        "Subscription payment processed",
        {
            "subscription_id": row.id,
            "last_tx_hash": row.last_tx_hash,
            "status": row.status,
            "next_payment_date": row.next_payment_date.isoformat(),
        },
    )


@router.post("/subscriptions/{subscription_id}/cancel", response_model=ApiResponse)
def cancel_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if row.status == "cancelled":
        return _success(
            "Subscription already cancelled",
            {
                "id": row.id,
                "status": row.status,
            },
        )

    row.status = "cancelled"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)

    return _success(
        "Subscription cancelled",
        {
            "id": row.id,
            "status": row.status,
        },
    )
