"""API router for EquiPay MVP."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo, AccountLines, ServerInfo, Tx
from xrpl.models.transactions import (
    EscrowCancel,
    EscrowCreate,
    EscrowFinish,
    Memo,
    Payment,
    TrustSet,
)
from xrpl.transaction import submit_and_wait
from xrpl.utils import datetime_to_ripple_time, xrp_to_drops
from xrpl.wallet import Wallet as XRPLWallet
from xrpl.wallet import generate_faucet_wallet

from config import settings
from db import HistoryEvent, SpendingGuard, Subscription, Transaction, Wallet, get_db


router = APIRouter()


class WalletImportRequest(BaseModel):
    seed: str = Field(..., min_length=8)


class PaymentSendRequest(BaseModel):
    sender_seed: str = Field(..., min_length=8)
    destination_address: str = Field(..., min_length=25)
    amount_xrp: float = Field(..., gt=0)


class RlusdPaymentSendRequest(BaseModel):
    sender_seed: str = Field(..., min_length=8)
    destination_address: str = Field(..., min_length=25)
    amount: float = Field(..., gt=0)


class BootstrapRlusdRequest(BaseModel):
    user_seed: str = Field(..., min_length=8)
    mint_amount: float = Field(default=100.0, gt=0)


class SubscriptionCreateRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    merchant_wallet_address: str = Field(..., min_length=25)
    user_seed: str = Field(..., min_length=8)
    amount_xrp: float = Field(..., gt=0)
    interval_days: int = Field(30, ge=1)
    use_escrow: bool = True


class UserHandshakeApproveRequest(BaseModel):
    user_seed: str = Field(..., min_length=8)


class ServiceHandshakeApproveRequest(BaseModel):
    merchant_seed: Optional[str] = None


class SubscriptionProcessRequest(BaseModel):
    merchant_seed: Optional[str] = None


class SpendingGuardSetRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    monthly_limit: float = Field(..., ge=0)
    currency: str = Field(default="RLUSD", min_length=3, max_length=16)


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


# Normalize amount formatting for hashing/consistency.
def _amount_to_string(amount: float) -> str:
    return str(Decimal(str(amount)).quantize(Decimal("0.000001")))


# Encode memo text as hex for XRPL MemoData.
def _hex_text(value: str) -> str:
    return value.encode("utf-8").hex()


# Build wallet object from seed with user-friendly errors.
def _wallet_from_seed(seed: str) -> XRPLWallet:
    try:
        return XRPLWallet.from_seed(seed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid seed: {exc}") from exc


# Validate that a configured seed matches the expected classic address.
def _assert_seed_matches_address(seed: str, expected_address: str, config_name: str) -> None:
    if not expected_address:
        return
    actual_address = _wallet_from_seed(seed).classic_address
    if actual_address != expected_address:
        raise HTTPException(
            status_code=500,
            detail=f"{config_name} does not match its configured seed.",
        )


# Resolve merchant/operator seed for service actions.
def _resolve_service_seed(explicit_seed: Optional[str]) -> str:
    seed = (explicit_seed or "").strip()
    if seed:
        return seed

    operator_seed = settings.OPERATOR_WALLET_SEED.strip()
    if operator_seed:
        _assert_seed_matches_address(
            operator_seed,
            settings.OPERATOR_WALLET_ADDRESS.strip(),
            "OPERATOR_WALLET_ADDRESS",
        )
        return operator_seed

    raise HTTPException(
        status_code=400,
        detail="merchant_seed is required unless OPERATOR_WALLET_SEED is configured.",
    )


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


# Store dashboard history rows for user-centric feeds.
def _record_history(
    db: Session,
    user_wallet_address: str,
    event_type: str,
    tx_hash: Optional[str],
    counterparty_address: Optional[str],
    amount: Optional[float],
    currency: str,
    status: str,
    note: Optional[str] = None,
) -> None:
    row = HistoryEvent(
        user_wallet_address=user_wallet_address,
        event_type=event_type,
        tx_hash=tx_hash,
        counterparty_address=counterparty_address,
        amount=amount,
        currency=currency,
        status=status,
        note=note,
    )
    db.add(row)


# Get month key used for spending guard buckets.
def _current_month_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


# Fetch/create spending guard and auto-reset monthly spend each month.
def _get_or_create_spending_guard(db: Session, user_wallet_address: str, currency: str) -> SpendingGuard:
    guard = db.query(SpendingGuard).filter(SpendingGuard.user_wallet_address == user_wallet_address).first()
    if not guard:
        guard = SpendingGuard(
            user_wallet_address=user_wallet_address,
            currency=currency,
            monthly_limit=0.0,
            spent_this_month=0.0,
            month_key=_current_month_key(),
        )
        db.add(guard)
        db.commit()
        db.refresh(guard)
        return guard

    month_key = _current_month_key()
    if guard.month_key != month_key:
        guard.month_key = month_key
        guard.spent_this_month = 0.0
        guard.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(guard)

    return guard


# Increase spending guard usage for outbound flows.
def _apply_spending(db: Session, user_wallet_address: str, amount: float, currency: str) -> None:
    guard = _get_or_create_spending_guard(db, user_wallet_address, currency)
    guard.spent_this_month += float(amount)
    guard.updated_at = datetime.now(timezone.utc)


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


# Convert configured handshake drops to XRP float.
def _handshake_amount_xrp() -> float:
    return float(
        (Decimal(settings.HANDSHAKE_APPROVAL_DROPS) / Decimal("1000000")).quantize(
            Decimal("0.000001")
        )
    )


# Convert short issued-currency code to 160-bit XRPL hex representation.
def _currency_to_hex(currency: str) -> str:
    return currency.encode("utf-8").hex().upper().ljust(40, "0")


# Decode 160-bit XRPL currency hex into a readable code when possible.
def _currency_from_hex(currency_hex: str) -> str:
    if len(currency_hex) != 40:
        return currency_hex
    try:
        raw = bytes.fromhex(currency_hex)
        decoded = raw.rstrip(b"\x00").decode("utf-8")
        return decoded or currency_hex
    except Exception:
        return currency_hex


# Accept both ASCII and hex form for trust-line comparisons.
def _matches_currency(line_currency: str, currency: str) -> bool:
    return line_currency in {currency, _currency_to_hex(currency)}


# Read account trust lines from XRPL.
def _get_account_lines(address: str) -> list[dict[str, Any]]:
    client = _get_xrpl_client()
    result = client.request(AccountLines(account=address, ledger_index="validated")).result
    return result.get("lines", [])


# Read all issued-currency balances from trust lines for UI/dashboard use.
def _get_issued_balances(address: str) -> list[dict[str, Any]]:
    try:
        lines = _get_account_lines(address)
    except Exception:
        return []

    balances: list[dict[str, Any]] = []
    for line in lines:
        currency_raw = line.get("currency", "")
        balance_raw = line.get("balance", "0")
        try:
            balance = float(balance_raw)
        except (TypeError, ValueError):
            balance = 0.0

        balances.append(
            {
                "currency": _currency_from_hex(currency_raw),
                "currency_raw": currency_raw,
                "issuer": line.get("account"),
                "balance": balance,
            }
        )
    return balances


# Read RLUSD balance with issuer fallback to avoid false zero from misconfiguration.
def _get_rlusd_balance_info(address: str) -> dict[str, Any]:
    try:
        lines = _get_account_lines(address)
    except Exception:
        return {"balance": 0.0, "issuer": settings.RLUSD_ISSUER, "match_mode": "none"}

    candidates = [
        line
        for line in lines
        if _matches_currency(line.get("currency", ""), settings.RLUSD_CURRENCY)
    ]
    if not candidates:
        return {"balance": 0.0, "issuer": settings.RLUSD_ISSUER, "match_mode": "none"}

    configured_issuer = settings.RLUSD_ISSUER.strip()
    if configured_issuer:
        exact = [line for line in candidates if line.get("account") == configured_issuer]
        if exact:
            try:
                return {
                    "balance": float(exact[0].get("balance", "0")),
                    "issuer": configured_issuer,
                    "match_mode": "configured_issuer",
                }
            except (TypeError, ValueError):
                return {"balance": 0.0, "issuer": configured_issuer, "match_mode": "configured_issuer"}

    # Fallback when issuer env is not set or does not match current trust line.
    try:
        total = sum(Decimal(str(line.get("balance", "0"))) for line in candidates)
        return {
            "balance": float(total),
            "issuer": candidates[0].get("account"),
            "match_mode": "issuer_fallback",
        }
    except Exception:
        return {"balance": 0.0, "issuer": settings.RLUSD_ISSUER, "match_mode": "issuer_fallback"}


# Read RLUSD balance from trust lines.
def _get_rlusd_balance(address: str) -> float:
    return _get_rlusd_balance_info(address)["balance"]


# Check whether wallet already has trust line for configured RLUSD issuer.
def _has_rlusd_trustline(address: str) -> bool:
    if not settings.RLUSD_ISSUER:
        return False
    for line in _get_account_lines(address):
        if _matches_currency(line.get("currency", ""), settings.RLUSD_CURRENCY) and line.get(
            "account"
        ) == settings.RLUSD_ISSUER:
            return True
    return False


# Create RLUSD trust line for wallet if missing.
def _ensure_rlusd_trustline(user_wallet: XRPLWallet) -> bool:
    if _has_rlusd_trustline(user_wallet.classic_address):
        return False
    client = _get_xrpl_client()
    tx = TrustSet(
        account=user_wallet.classic_address,
        limit_amount=IssuedCurrencyAmount(
            currency=_currency_to_hex(settings.RLUSD_CURRENCY),
            issuer=settings.RLUSD_ISSUER,
            value="1000000",
        ),
    )
    submit_and_wait(tx, client, user_wallet)
    return True


# Mint configured RLUSD from issuer wallet to destination wallet.
def _mint_rlusd(destination_address: str, mint_amount: float) -> dict[str, Any]:
    if not settings.RLUSD_ISSUER or not settings.RLUSD_ISSUER_SEED:
        raise HTTPException(
            status_code=400,
            detail="RLUSD_ISSUER and RLUSD_ISSUER_SEED must be configured for RLUSD bootstrap.",
        )
    issuer_wallet = _wallet_from_seed(settings.RLUSD_ISSUER_SEED)
    _assert_seed_matches_address(
        settings.RLUSD_ISSUER_SEED,
        settings.RLUSD_ISSUER.strip(),
        "RLUSD_ISSUER",
    )
    client = _get_xrpl_client()
    tx = Payment(
        account=issuer_wallet.classic_address,
        destination=destination_address,
        amount=IssuedCurrencyAmount(
            currency=_currency_to_hex(settings.RLUSD_CURRENCY),
            issuer=settings.RLUSD_ISSUER,
            value=_amount_to_string(mint_amount),
        ),
    )
    try:
        response = submit_and_wait(tx, client, issuer_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"RLUSD mint failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    status = result.get("meta", {}).get("TransactionResult") or "unknown"
    return {"tx_hash": tx_hash, "status": status, "raw_result": result}


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
        memos = [Memo(memo_data=_hex_text(memo_text))] if memo_text else None

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
    tx_status = result.get("meta", {}).get("TransactionResult") or result.get("engine_result") or "unknown"

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


# Submit issued-currency payment (e.g., RLUSD).
def _send_issued_payment(
    sender_seed: str,
    destination_address: str,
    amount: float,
    currency: str,
    issuer: str,
    tx_type: str,
) -> dict[str, Any]:
    if not _is_valid_classic_address(destination_address):
        raise HTTPException(status_code=400, detail="Invalid destination address")
    if not issuer:
        raise HTTPException(status_code=400, detail="Issuer is required for issued-currency payments")

    client = _get_xrpl_client()

    try:
        sender_wallet = _wallet_from_seed(sender_seed)
        issued_amount = IssuedCurrencyAmount(
            currency=_currency_to_hex(currency),
            issuer=issuer,
            value=_amount_to_string(amount),
        )
        tx = Payment(
            account=sender_wallet.classic_address,
            destination=destination_address,
            amount=issued_amount,
        )
        response = submit_and_wait(tx, client, sender_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Issued payment failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_status = result.get("meta", {}).get("TransactionResult") or result.get("engine_result") or "unknown"

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


# Create an on-chain escrow lock for the next subscription cycle.
def _lock_subscription_escrow(db: Session, row: Subscription) -> dict[str, Any]:
    client = _get_xrpl_client()
    user_wallet = _wallet_from_seed(row.user_seed)
    if user_wallet.classic_address != row.user_wallet_address:
        raise HTTPException(status_code=400, detail="Stored user seed does not match subscription user wallet")

    now = datetime.now(timezone.utc)
    finish_after = datetime_to_ripple_time(now)
    cancel_after = datetime_to_ripple_time(now + timedelta(days=row.interval_days))

    memo = Memo(memo_data=_hex_text(f"SUBSCRIPTION_ESCROW_LOCK:{row.id}:{row.terms_hash}"))
    tx = EscrowCreate(
        account=row.user_wallet_address,
        destination=row.merchant_wallet_address,
        amount=_xrp_to_drops(row.amount_xrp),
        finish_after=finish_after,
        cancel_after=cancel_after,
        memos=[memo],
    )

    try:
        response = submit_and_wait(tx, client, user_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Escrow lock failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    offer_sequence = result.get("tx_json", {}).get("Sequence")
    tx_status = result.get("meta", {}).get("TransactionResult") or "unknown"

    row.escrow_amount_xrp = row.amount_xrp
    row.escrow_offer_sequence = offer_sequence
    row.escrow_create_tx_hash = tx_hash
    row.escrow_status = "locked"
    row.escrow_cancel_after = cancel_after
    row.updated_at = datetime.now(timezone.utc)

    db.add(
        Transaction(
            tx_hash=tx_hash,
            tx_type="subscription_escrow_lock",
            from_address=row.user_wallet_address,
            to_address=row.merchant_wallet_address,
            amount_xrp=row.amount_xrp,
            status=tx_status,
        )
    )
    _record_history(
        db,
        user_wallet_address=row.user_wallet_address,
        event_type="subscription_escrow_lock",
        tx_hash=tx_hash,
        counterparty_address=row.merchant_wallet_address,
        amount=row.amount_xrp,
        currency="XRP",
        status=tx_status,
        note=f"Subscription {row.id} escrow lock created",
    )
    db.commit()
    db.refresh(row)

    return {"tx_hash": tx_hash, "offer_sequence": offer_sequence, "status": tx_status}


# Release currently locked escrow for a subscription.
def _finish_subscription_escrow(db: Session, row: Subscription, merchant_seed: str) -> dict[str, Any]:
    if row.escrow_status != "locked" or not row.escrow_offer_sequence:
        raise HTTPException(status_code=409, detail="No active locked escrow to release")

    merchant_wallet = _wallet_from_seed(merchant_seed)
    if merchant_wallet.classic_address != row.merchant_wallet_address:
        raise HTTPException(status_code=400, detail="merchant_seed does not match merchant wallet")

    client = _get_xrpl_client()
    memo = Memo(memo_data=_hex_text(f"SUBSCRIPTION_ESCROW_RELEASE:{row.id}:{row.terms_hash}"))
    tx = EscrowFinish(
        account=row.merchant_wallet_address,
        owner=row.user_wallet_address,
        offer_sequence=row.escrow_offer_sequence,
        memos=[memo],
    )

    try:
        response = submit_and_wait(tx, client, merchant_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Escrow release failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_status = result.get("meta", {}).get("TransactionResult") or "unknown"

    row.last_tx_hash = tx_hash
    row.next_payment_date = row.next_payment_date + timedelta(days=row.interval_days)
    row.escrow_status = "released"
    row.updated_at = datetime.now(timezone.utc)

    db.add(
        Transaction(
            tx_hash=tx_hash,
            tx_type="subscription_escrow_release",
            from_address=row.user_wallet_address,
            to_address=row.merchant_wallet_address,
            amount_xrp=row.amount_xrp,
            status=tx_status,
        )
    )
    _record_history(
        db,
        user_wallet_address=row.user_wallet_address,
        event_type="subscription_release",
        tx_hash=tx_hash,
        counterparty_address=row.merchant_wallet_address,
        amount=row.amount_xrp,
        currency="XRP",
        status=tx_status,
        note=f"Subscription {row.id} escrow released",
    )
    _apply_spending(db, row.user_wallet_address, row.amount_xrp, "XRP")
    db.commit()
    db.refresh(row)

    return {"tx_hash": tx_hash, "status": tx_status}


# Cancel currently locked escrow for a subscription.
def _cancel_subscription_escrow(db: Session, row: Subscription) -> dict[str, Any]:
    if row.escrow_status != "locked" or not row.escrow_offer_sequence:
        return {"status": "no_locked_escrow"}

    user_wallet = _wallet_from_seed(row.user_seed)
    client = _get_xrpl_client()
    tx = EscrowCancel(
        account=row.user_wallet_address,
        owner=row.user_wallet_address,
        offer_sequence=row.escrow_offer_sequence,
    )

    try:
        response = submit_and_wait(tx, client, user_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Escrow cancel failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_status = result.get("meta", {}).get("TransactionResult") or "unknown"

    row.escrow_status = "cancelled"
    row.updated_at = datetime.now(timezone.utc)

    db.add(
        Transaction(
            tx_hash=tx_hash,
            tx_type="subscription_escrow_cancel",
            from_address=row.user_wallet_address,
            to_address=row.user_wallet_address,
            amount_xrp=row.escrow_amount_xrp or row.amount_xrp,
            status=tx_status,
        )
    )
    _record_history(
        db,
        user_wallet_address=row.user_wallet_address,
        event_type="subscription_escrow_cancel",
        tx_hash=tx_hash,
        counterparty_address=row.merchant_wallet_address,
        amount=row.escrow_amount_xrp or row.amount_xrp,
        currency="XRP",
        status=tx_status,
        note=f"Subscription {row.id} escrow cancelled",
    )
    db.commit()
    db.refresh(row)

    return {"tx_hash": tx_hash, "status": tx_status}


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
        "use_escrow": bool(row.use_escrow),
        "escrow_amount_xrp": row.escrow_amount_xrp,
        "escrow_offer_sequence": row.escrow_offer_sequence,
        "escrow_create_tx_hash": row.escrow_create_tx_hash,
        "escrow_status": row.escrow_status,
        "escrow_cancel_after": row.escrow_cancel_after,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


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


# Create a new network wallet and optionally fund with faucet.
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
                    faucet_host = settings.XRPL_FAUCET_URL.strip() or None
                    wallet = generate_faucet_wallet(client, faucet_host=faucet_host)
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


# Bootstrap RLUSD readiness: trust line + mint for an imported wallet.
@router.post("/wallets/bootstrap-rlusd", response_model=ApiResponse)
def bootstrap_rlusd_wallet(
    payload: BootstrapRlusdRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_wallet = _wallet_from_seed(payload.user_seed)
    _save_or_get_wallet(db, user_wallet.classic_address, payload.user_seed)

    trustline_created = _ensure_rlusd_trustline(user_wallet)
    mint_result = _mint_rlusd(user_wallet.classic_address, payload.mint_amount)
    balance = _get_rlusd_balance(user_wallet.classic_address)

    _record_history(
        db,
        user_wallet_address=user_wallet.classic_address,
        event_type="rlusd_bootstrap",
        tx_hash=mint_result["tx_hash"],
        counterparty_address=settings.RLUSD_ISSUER,
        amount=payload.mint_amount,
        currency=settings.RLUSD_CURRENCY,
        status=mint_result["status"],
        note="Trustline setup and mint bootstrap",
    )
    db.commit()

    return _success(
        "RLUSD bootstrap completed",
        {
            "address": user_wallet.classic_address,
            "trustline_created": trustline_created,
            "mint_tx_hash": mint_result["tx_hash"],
            "mint_status": mint_result["status"],
            "rlusd_balance": balance,
            "rlusd_currency": settings.RLUSD_CURRENCY,
            "rlusd_issuer": settings.RLUSD_ISSUER,
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


# Get XRP and RLUSD balances for a wallet address.
@router.get("/wallets/{address}/balance", response_model=ApiResponse)
def get_wallet_balance(address: str) -> dict[str, Any]:
    if not _is_valid_classic_address(address):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    client = _get_xrpl_client()

    try:
        result = client.request(AccountInfo(account=address, ledger_index="validated", strict=True)).result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Balance lookup failed: {exc}") from exc

    # Unfunded accounts may return no account_data; normalize to zeros for UI.
    account_data = result.get("account_data", {})
    drops = account_data.get("Balance")
    account_exists = bool(account_data)
    if drops is None:
        drops = "0"

    rlusd_info = _get_rlusd_balance_info(address)
    return _success(
        "Wallet balance",
        {
            "address": address,
            "balance_xrp": _drops_to_xrp_float(drops),
            "balance_drops": drops,
            "account_exists": account_exists,
            "rlusd_balance": rlusd_info["balance"],
            "rlusd_currency": settings.RLUSD_CURRENCY,
            "rlusd_issuer": rlusd_info["issuer"] or settings.RLUSD_ISSUER,
            "rlusd_match_mode": rlusd_info["match_mode"],
            "rlusd_ready": bool(settings.RLUSD_ISSUER),
            "issued_balances": _get_issued_balances(address),
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
    _record_history(
        db,
        user_wallet_address=payment_result["from_address"],
        event_type="payment_sent",
        tx_hash=payment_result["tx_hash"],
        counterparty_address=payment_result["to_address"],
        amount=payload.amount_xrp,
        currency="XRP",
        status=payment_result["status"],
    )
    _apply_spending(db, payment_result["from_address"], payload.amount_xrp, "XRP")
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


# Send RLUSD/issued-currency payment and persist to history.
@router.post("/payments/send-rlusd", response_model=ApiResponse)
def send_rlusd_payment(payload: RlusdPaymentSendRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    payment_result = _send_issued_payment(
        sender_seed=payload.sender_seed,
        destination_address=payload.destination_address,
        amount=payload.amount,
        currency=settings.RLUSD_CURRENCY,
        issuer=settings.RLUSD_ISSUER,
        tx_type="payment_rlusd",
    )

    tx_row = Transaction(
        tx_hash=payment_result["tx_hash"],
        tx_type="payment_rlusd",
        from_address=payment_result["from_address"],
        to_address=payment_result["to_address"],
        amount_xrp=0.0,
        status=payment_result["status"],
    )
    db.add(tx_row)
    _record_history(
        db,
        user_wallet_address=payment_result["from_address"],
        event_type="payment_sent_rlusd",
        tx_hash=payment_result["tx_hash"],
        counterparty_address=payment_result["to_address"],
        amount=payload.amount,
        currency=settings.RLUSD_CURRENCY,
        status=payment_result["status"],
    )
    _apply_spending(db, payment_result["from_address"], payload.amount, settings.RLUSD_CURRENCY)
    db.commit()
    db.refresh(tx_row)

    return _success(
        "RLUSD payment sent",
        {
            "tx_hash": tx_row.tx_hash,
            "status": tx_row.status,
            "from_address": tx_row.from_address,
            "to_address": tx_row.to_address,
            "amount": payload.amount,
            "currency": settings.RLUSD_CURRENCY,
            "issuer": settings.RLUSD_ISSUER,
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
def create_subscription(payload: SubscriptionCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
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
        use_escrow=1 if payload.use_escrow else 0,
        escrow_amount_xrp=payload.amount_xrp if payload.use_escrow else None,
        escrow_status="not_started" if payload.use_escrow else "disabled",
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

    db.add(
        Transaction(
            tx_hash=approval_result["tx_hash"],
            tx_type="subscription_handshake_user",
            from_address=approval_result["from_address"],
            to_address=approval_result["to_address"],
            amount_xrp=_handshake_amount_xrp(),
            status=approval_result["status"],
        )
    )
    _record_history(
        db,
        user_wallet_address=row.user_wallet_address,
        event_type="subscription_handshake_user",
        tx_hash=approval_result["tx_hash"],
        counterparty_address=row.merchant_wallet_address,
        amount=_handshake_amount_xrp(),
        currency="XRP",
        status=approval_result["status"],
    )

    row.user_approval_tx_hash = approval_result["tx_hash"]
    row.handshake_status = "user_approved"
    if row.service_approval_tx_hash:
        row.handshake_status = "completed"
        row.status = "active"
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)

    if row.status == "active" and bool(row.use_escrow) and row.escrow_status != "locked":
        _lock_subscription_escrow(db, row)

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

    service_seed = _resolve_service_seed(payload.merchant_seed)
    merchant_wallet = _wallet_from_seed(service_seed)
    if merchant_wallet.classic_address != row.merchant_wallet_address:
        raise HTTPException(status_code=400, detail="Provided seed does not match merchant wallet")

    approval_result = _send_xrp_payment(
        sender_seed=service_seed,
        destination_address=row.user_wallet_address,
        amount_xrp=_handshake_amount_xrp(),
        tx_type="subscription_handshake_service",
        memo_text=f"SUBSCRIPTION_HANDSHAKE_SERVICE:{row.terms_hash}",
    )

    db.add(
        Transaction(
            tx_hash=approval_result["tx_hash"],
            tx_type="subscription_handshake_service",
            from_address=approval_result["from_address"],
            to_address=approval_result["to_address"],
            amount_xrp=_handshake_amount_xrp(),
            status=approval_result["status"],
        )
    )
    _record_history(
        db,
        user_wallet_address=row.user_wallet_address,
        event_type="subscription_handshake_service",
        tx_hash=approval_result["tx_hash"],
        counterparty_address=row.merchant_wallet_address,
        amount=_handshake_amount_xrp(),
        currency="XRP",
        status=approval_result["status"],
    )

    row.service_approval_tx_hash = approval_result["tx_hash"]
    row.handshake_status = "service_approved"
    if row.user_approval_tx_hash:
        row.handshake_status = "completed"
        row.status = "active"
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)

    if row.status == "active" and bool(row.use_escrow) and row.escrow_status != "locked":
        _lock_subscription_escrow(db, row)

    return _success("Service handshake approval recorded on-chain", _subscription_to_dict(row))


# List all subscriptions and current handshake/payment state.
@router.get("/subscriptions", response_model=ApiResponse)
def list_subscriptions(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.query(Subscription).order_by(Subscription.created_at.desc()).all()
    return _success("Subscription list", [_subscription_to_dict(row) for row in rows])


# Fetch subscriptions by user sorted by newest first.
@router.get("/subscriptions/user/{user_wallet_address}", response_model=ApiResponse)
def list_subscriptions_for_user(user_wallet_address: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = (
        db.query(Subscription)
        .filter(Subscription.user_wallet_address == user_wallet_address)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    return _success("User subscriptions", [_subscription_to_dict(row) for row in rows])


# Fetch one subscription by ID.
@router.get("/subscriptions/{subscription_id}", response_model=ApiResponse)
def get_subscription(subscription_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return _success("Subscription details", _subscription_to_dict(row))


# Process next recurring payment (escrow release preferred when enabled).
@router.post("/subscriptions/{subscription_id}/process", response_model=ApiResponse)
def process_subscription(
    subscription_id: int,
    payload: SubscriptionProcessRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.status == "cancelled":
        raise HTTPException(status_code=409, detail="Subscription is cancelled")
    if row.status != "active" or row.handshake_status != "completed":
        raise HTTPException(status_code=409, detail="Subscription handshake is not fully approved")

    if bool(row.use_escrow):
        merchant_seed = _resolve_service_seed(payload.merchant_seed if payload else None)

        release_result = _finish_subscription_escrow(db, row, merchant_seed)
        _lock_subscription_escrow(db, row)
        return _success(
            "Subscription escrow released and next escrow lock created",
            {
                "subscription_id": row.id,
                "last_tx_hash": release_result["tx_hash"],
                "status": row.status,
                "next_payment_date": row.next_payment_date.isoformat(),
                "escrow_status": row.escrow_status,
                "escrow_offer_sequence": row.escrow_offer_sequence,
                "escrow_create_tx_hash": row.escrow_create_tx_hash,
            },
        )

    payment_result = _send_xrp_payment(
        sender_seed=row.user_seed,
        destination_address=row.merchant_wallet_address,
        amount_xrp=row.amount_xrp,
        tx_type="subscription_payment",
        memo_text=f"SUBSCRIPTION_PAYMENT:{row.id}:{row.terms_hash}",
    )

    db.add(
        Transaction(
            tx_hash=payment_result["tx_hash"],
            tx_type="subscription_payment",
            from_address=payment_result["from_address"],
            to_address=payment_result["to_address"],
            amount_xrp=row.amount_xrp,
            status=payment_result["status"],
        )
    )
    _record_history(
        db,
        user_wallet_address=row.user_wallet_address,
        event_type="subscription_payment",
        tx_hash=payment_result["tx_hash"],
        counterparty_address=row.merchant_wallet_address,
        amount=row.amount_xrp,
        currency="XRP",
        status=payment_result["status"],
    )

    row.last_tx_hash = payment_result["tx_hash"]
    row.next_payment_date = row.next_payment_date + timedelta(days=row.interval_days)
    row.updated_at = datetime.now(timezone.utc)
    _apply_spending(db, row.user_wallet_address, row.amount_xrp, "XRP")

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

    if bool(row.use_escrow) and row.escrow_status == "locked":
        _cancel_subscription_escrow(db, row)

    row.status = "cancelled"
    row.handshake_status = "cancelled"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)

    return _success("Subscription cancelled", {"id": row.id, "status": row.status})


# Configure monthly spending guard values for a user.
@router.post("/spending-guard/set", response_model=ApiResponse)
def set_spending_guard(payload: SpendingGuardSetRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.user_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid user_wallet_address")

    guard = _get_or_create_spending_guard(db, payload.user_wallet_address, payload.currency)
    guard.currency = payload.currency
    guard.monthly_limit = payload.monthly_limit
    guard.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(guard)

    return _success(
        "Spending guard updated",
        {
            "user_wallet_address": guard.user_wallet_address,
            "currency": guard.currency,
            "monthly_limit": guard.monthly_limit,
            "spent_this_month": guard.spent_this_month,
            "remaining": max(guard.monthly_limit - guard.spent_this_month, 0.0),
            "month_key": guard.month_key,
        },
    )


# Fetch spending guard for a user.
@router.get("/spending-guard/{user_wallet_address}", response_model=ApiResponse)
def get_spending_guard(user_wallet_address: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    guard = _get_or_create_spending_guard(db, user_wallet_address, settings.RLUSD_CURRENCY)
    return _success(
        "Spending guard",
        {
            "user_wallet_address": guard.user_wallet_address,
            "currency": guard.currency,
            "monthly_limit": guard.monthly_limit,
            "spent_this_month": guard.spent_this_month,
            "remaining": max(guard.monthly_limit - guard.spent_this_month, 0.0),
            "month_key": guard.month_key,
        },
    )


# Return sorted history rows for a user dashboard.
@router.get("/history/{user_wallet_address}", response_model=ApiResponse)
def get_user_history(
    user_wallet_address: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(HistoryEvent)
        .filter(HistoryEvent.user_wallet_address == user_wallet_address)
        .order_by(HistoryEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return _success(
        "User history",
        [
            {
                "id": row.id,
                "event_type": row.event_type,
                "tx_hash": row.tx_hash,
                "counterparty_address": row.counterparty_address,
                "amount": row.amount,
                "currency": row.currency,
                "status": row.status,
                "note": row.note,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    )


# Return dashboard aggregates for frontend cards/charts.
@router.get("/dashboard/{user_wallet_address}", response_model=ApiResponse)
def get_dashboard(user_wallet_address: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not _is_valid_classic_address(user_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid user wallet address")

    balance_payload = get_wallet_balance(user_wallet_address)["data"]
    guard = _get_or_create_spending_guard(db, user_wallet_address, settings.RLUSD_CURRENCY)

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    released_this_month = (
        db.query(func.coalesce(func.sum(HistoryEvent.amount), 0.0))
        .filter(HistoryEvent.user_wallet_address == user_wallet_address)
        .filter(HistoryEvent.event_type.in_(["subscription_release", "payment_sent", "payment_sent_rlusd"]))
        .filter(HistoryEvent.created_at >= month_start)
        .scalar()
    )

    locked_this_month = (
        db.query(func.coalesce(func.sum(HistoryEvent.amount), 0.0))
        .filter(HistoryEvent.user_wallet_address == user_wallet_address)
        .filter(HistoryEvent.event_type == "subscription_escrow_lock")
        .filter(HistoryEvent.created_at >= month_start)
        .scalar()
    )

    locked_in_escrow = (
        db.query(func.coalesce(func.sum(Subscription.escrow_amount_xrp), 0.0))
        .filter(Subscription.user_wallet_address == user_wallet_address)
        .filter(Subscription.escrow_status == "locked")
        .scalar()
    )

    upcoming_rows = (
        db.query(Subscription)
        .filter(Subscription.user_wallet_address == user_wallet_address)
        .filter(Subscription.status == "active")
        .order_by(Subscription.next_payment_date.asc())
        .limit(5)
        .all()
    )

    activity_rows = (
        db.query(HistoryEvent)
        .filter(HistoryEvent.user_wallet_address == user_wallet_address)
        .order_by(HistoryEvent.created_at.desc())
        .limit(settings.DASHBOARD_RECENT_LIMIT)
        .all()
    )

    return _success(
        "Dashboard",
        {
            "wallet": user_wallet_address,
            "balance_xrp": balance_payload["balance_xrp"],
            "balance_rlusd": balance_payload["rlusd_balance"],
            "locked_in_escrow_xrp": float(locked_in_escrow or 0.0),
            "monthly_guard": {
                "currency": guard.currency,
                "limit": guard.monthly_limit,
                "spent": guard.spent_this_month,
                "remaining": max(guard.monthly_limit - guard.spent_this_month, 0.0),
            },
            "this_month": {
                "released": float(released_this_month or 0.0),
                "locked": float(locked_this_month or 0.0),
            },
            "upcoming_release": [
                {
                    "subscription_id": row.id,
                    "merchant_wallet_address": row.merchant_wallet_address,
                    "amount_xrp": row.amount_xrp,
                    "next_payment_date": row.next_payment_date.isoformat(),
                    "escrow_status": row.escrow_status,
                }
                for row in upcoming_rows
            ],
            "recent_activity": [
                {
                    "event_type": row.event_type,
                    "tx_hash": row.tx_hash,
                    "counterparty_address": row.counterparty_address,
                    "amount": row.amount,
                    "currency": row.currency,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                }
                for row in activity_rows
            ],
        },
    )
