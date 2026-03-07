"""API router for XRPL Financial Hub MVP."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.models.requests import AccountInfo, ServerInfo, Tx
from xrpl.models.transactions import Memo, Payment
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet as XRPLWallet
from xrpl.wallet import generate_faucet_wallet

from config import settings
from db import Subscription, Transaction, Wallet, get_db


router = APIRouter()


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


class UserHandshakeApproveRequest(BaseModel):
    user_seed: str = Field(..., min_length=8)


class ServiceHandshakeApproveRequest(BaseModel):
    merchant_seed: str = Field(..., min_length=8)


class ApiResponse(BaseModel):
    message: str
    data: Any


# Standard API success shape.
def _success(message: str, data: Any) -> dict[str, Any]:
    return {"message": message, "data": data}


# Build the XRPL JSON-RPC client for requests.
def _get_xrpl_client() -> JsonRpcClient:
    return JsonRpcClient(settings.XRPL_RPC_URL)


# Validate classic address format.
def _is_valid_classic_address(address: str) -> bool:
    return is_valid_classic_address(address)


# Convert XRP decimal amount to drops string for XRPL transactions.
def _xrp_to_drops(amount_xrp: float) -> str:
    normalized = format(Decimal(str(amount_xrp)).quantize(Decimal("0.000001")), "f")
    return xrp_to_drops(normalized)


# Convert drops string to XRP float for API responses.
def _drops_to_xrp_float(drops: Optional[str]) -> Optional[float]:
    if drops is None:
        return None
    return float((Decimal(drops) / Decimal("1000000")).quantize(Decimal("0.000001")))


# Normalize XRP amount formatting for hashing/consistency.
def _amount_to_string(amount_xrp: float) -> str:
    return str(Decimal(str(amount_xrp)).quantize(Decimal("0.000001")))


# Encode memo text as hex for XRPL MemoData.
def _hex_text(value: str) -> str:
    return value.encode("utf-8").hex()


# Build wallet object from seed with user-friendly errors.
def _wallet_from_seed(seed: str) -> XRPLWallet:
    try:
        return XRPLWallet.from_seed(seed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid seed: {exc}") from exc


# Insert wallet once or refresh existing wallet seed/network.
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


# Create deterministic hash of subscription terms for handshake integrity.
def _subscription_terms_hash(
    user_wallet_address: str,
    merchant_wallet_address: str,
    amount_xrp: float,
    interval_days: int,
) -> str:
    terms_payload = {
        "user_wallet_address": user_wallet_address,
        "merchant_wallet_address": merchant_wallet_address,
        "amount_xrp": _amount_to_string(amount_xrp),
        "interval_days": interval_days,
        "currency": "XRP",
        "network": settings.XRPL_NETWORK,
    }
    canonical = json.dumps(terms_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Submit XRP payment and return summarized transaction metadata.
def _send_xrp_payment(
    sender_seed: str,
    destination_address: str,
    amount_xrp: float,
    tx_type: str = "payment",
    memo_text: Optional[str] = None,
) -> dict[str, Any]:
    if not _is_valid_classic_address(destination_address):
        raise HTTPException(status_code=400, detail="Invalid destination address")

    client = _get_xrpl_client()

    try:
        sender_wallet = _wallet_from_seed(sender_seed)
        memos = None
        if memo_text:
            memos = [Memo(memo_data=_hex_text(memo_text))]

        tx = Payment(
            account=sender_wallet.classic_address,
            destination=destination_address,
            amount=_xrp_to_drops(amount_xrp),
            memos=memos,
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
        "tx_type": tx_type,
        "from_address": sender_wallet.classic_address,
        "to_address": destination_address,
        "validated": result.get("validated", False),
        "ledger_index": result.get("ledger_index"),
        "raw_result": result,
    }


# Convert subscription ORM row to API-friendly response object.
def _subscription_to_dict(row: Subscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_wallet_address": row.user_wallet_address,
        "merchant_wallet_address": row.merchant_wallet_address,
        "amount_xrp": row.amount_xrp,
        "interval_days": row.interval_days,
        "status": row.status,
        "handshake_status": row.handshake_status,
        "terms_hash": row.terms_hash,
        "user_approval_tx_hash": row.user_approval_tx_hash,
        "service_approval_tx_hash": row.service_approval_tx_hash,
        "start_date": row.start_date.isoformat(),
        "next_payment_date": row.next_payment_date.isoformat(),
        "last_tx_hash": row.last_tx_hash,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# Convert configured handshake drops to XRP float.
def _handshake_amount_xrp() -> float:
    return float(
        (Decimal(settings.HANDSHAKE_APPROVAL_DROPS) / Decimal("1000000")).quantize(
            Decimal("0.000001")
        )
    )


# Health endpoint and XRPL connectivity probe.
@router.get("/health", response_model=ApiResponse)
def health() -> dict[str, Any]:
    xrpl_ready = True
    xrpl_error = None
    try:
        client = _get_xrpl_client()
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


# Create a new testnet wallet and optionally fund with faucet.
@router.post("/wallets/create", response_model=ApiResponse)
def create_wallet(db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _get_xrpl_client()

    try:
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


# Import wallet from seed and persist it for demo use.
@router.post("/wallets/import", response_model=ApiResponse)
def import_wallet(payload: WalletImportRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    wallet = _wallet_from_seed(payload.seed)
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


# List all known wallets in local SQLite.
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


# Get XRP balance for a classic address from validated ledger.
@router.get("/wallets/{address}/balance", response_model=ApiResponse)
def get_wallet_balance(address: str) -> dict[str, Any]:
    if not _is_valid_classic_address(address):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    client = _get_xrpl_client()

    try:
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


# Submit one XRP payment and store transaction summary.
@router.post("/payments/send", response_model=ApiResponse)
def send_payment(payload: PaymentSendRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    payment_result = _send_xrp_payment(
        sender_seed=payload.sender_seed,
        destination_address=payload.destination_address,
        amount_xrp=payload.amount_xrp,
        tx_type="payment",
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


# List all locally stored payment/transaction records.
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


# Fetch one XRPL transaction and return summarized metadata.
@router.get("/payments/{tx_hash}", response_model=ApiResponse)
def get_payment(tx_hash: str) -> dict[str, Any]:
    client = _get_xrpl_client()

    try:
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


# Create subscription terms and wait for both handshake approvals.
@router.post("/subscriptions/create", response_model=ApiResponse)
def create_subscription(
    payload: SubscriptionCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.user_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid user_wallet_address")
    if not _is_valid_classic_address(payload.merchant_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid merchant_wallet_address")

    user_wallet = _wallet_from_seed(payload.user_seed)
    if user_wallet.classic_address != payload.user_wallet_address:
        raise HTTPException(status_code=400, detail="user_seed does not match user_wallet_address")

    today = date.today()
    row = Subscription(
        user_wallet_address=payload.user_wallet_address,
        merchant_wallet_address=payload.merchant_wallet_address,
        user_seed=payload.user_seed,
        amount_xrp=payload.amount_xrp,
        interval_days=payload.interval_days,
        status="pending_handshake",
        terms_hash=_subscription_terms_hash(
            payload.user_wallet_address,
            payload.merchant_wallet_address,
            payload.amount_xrp,
            payload.interval_days,
        ),
        handshake_status="pending",
        user_approval_tx_hash=None,
        service_approval_tx_hash=None,
        start_date=today,
        next_payment_date=today,
        last_tx_hash=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return _success(
        "Subscription created. Handshake approvals required before recurring payments.",
        _subscription_to_dict(row),
    )


# Record user's on-chain approval of subscription terms.
@router.post("/subscriptions/{subscription_id}/handshake/user-approve", response_model=ApiResponse)
def user_approve_subscription_handshake(
    subscription_id: int,
    payload: UserHandshakeApproveRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.status == "cancelled":
        raise HTTPException(status_code=409, detail="Subscription is cancelled")
    if row.user_approval_tx_hash:
        return _success("User already approved handshake", _subscription_to_dict(row))

    user_wallet = _wallet_from_seed(payload.user_seed)
    if user_wallet.classic_address != row.user_wallet_address:
        raise HTTPException(status_code=400, detail="Provided seed does not match user wallet")

    approval_result = _send_xrp_payment(
        sender_seed=payload.user_seed,
        destination_address=row.merchant_wallet_address,
        amount_xrp=_handshake_amount_xrp(),
        tx_type="subscription_handshake_user",
        memo_text=f"SUBSCRIPTION_HANDSHAKE_USER:{row.terms_hash}",
    )

    tx_row = Transaction(
        tx_hash=approval_result["tx_hash"],
        tx_type="subscription_handshake_user",
        from_address=approval_result["from_address"],
        to_address=approval_result["to_address"],
        amount_xrp=_handshake_amount_xrp(),
        status=approval_result["status"],
    )
    db.add(tx_row)

    row.user_approval_tx_hash = approval_result["tx_hash"]
    row.handshake_status = "user_approved"
    if row.service_approval_tx_hash:
        row.handshake_status = "completed"
        row.status = "active"
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)

    return _success("User handshake approval recorded on-chain", _subscription_to_dict(row))


# Record service's on-chain approval of the same subscription terms.
@router.post("/subscriptions/{subscription_id}/handshake/service-approve", response_model=ApiResponse)
def service_approve_subscription_handshake(
    subscription_id: int,
    payload: ServiceHandshakeApproveRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.status == "cancelled":
        raise HTTPException(status_code=409, detail="Subscription is cancelled")
    if row.service_approval_tx_hash:
        return _success("Service already approved handshake", _subscription_to_dict(row))

    merchant_wallet = _wallet_from_seed(payload.merchant_seed)
    if merchant_wallet.classic_address != row.merchant_wallet_address:
        raise HTTPException(status_code=400, detail="Provided seed does not match merchant wallet")

    approval_result = _send_xrp_payment(
        sender_seed=payload.merchant_seed,
        destination_address=row.user_wallet_address,
        amount_xrp=_handshake_amount_xrp(),
        tx_type="subscription_handshake_service",
        memo_text=f"SUBSCRIPTION_HANDSHAKE_SERVICE:{row.terms_hash}",
    )

    tx_row = Transaction(
        tx_hash=approval_result["tx_hash"],
        tx_type="subscription_handshake_service",
        from_address=approval_result["from_address"],
        to_address=approval_result["to_address"],
        amount_xrp=_handshake_amount_xrp(),
        status=approval_result["status"],
    )
    db.add(tx_row)

    row.service_approval_tx_hash = approval_result["tx_hash"]
    row.handshake_status = "service_approved"
    if row.user_approval_tx_hash:
        row.handshake_status = "completed"
        row.status = "active"
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)

    return _success("Service handshake approval recorded on-chain", _subscription_to_dict(row))


# List all subscriptions and current handshake/payment state.
@router.get("/subscriptions", response_model=ApiResponse)
def list_subscriptions(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.query(Subscription).order_by(Subscription.created_at.desc()).all()
    return _success("Subscription list", [_subscription_to_dict(row) for row in rows])


# Fetch one subscription by ID.
@router.get("/subscriptions/{subscription_id}", response_model=ApiResponse)
def get_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return _success("Subscription details", _subscription_to_dict(row))


# Process next recurring payment after completed handshake.
@router.post("/subscriptions/{subscription_id}/process", response_model=ApiResponse)
def process_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.status == "cancelled":
        raise HTTPException(status_code=409, detail="Subscription is cancelled")
    if row.status != "active" or row.handshake_status != "completed":
        raise HTTPException(status_code=409, detail="Subscription handshake is not fully approved")

    payment_result = _send_xrp_payment(
        sender_seed=row.user_seed,
        destination_address=row.merchant_wallet_address,
        amount_xrp=row.amount_xrp,
        tx_type="subscription_payment",
        memo_text=f"SUBSCRIPTION_PAYMENT:{row.id}:{row.terms_hash}",
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
    row.updated_at = datetime.now(timezone.utc)

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


# Cancel subscription and block future processing.
@router.post("/subscriptions/{subscription_id}/cancel", response_model=ApiResponse)
def cancel_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if row.status == "cancelled":
        return _success("Subscription already cancelled", {"id": row.id, "status": row.status})

    row.status = "cancelled"
    row.handshake_status = "cancelled"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)

    return _success("Subscription cancelled", {"id": row.id, "status": row.status})
