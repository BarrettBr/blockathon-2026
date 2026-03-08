"""API router for EquiPay MVP."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json as _json
import json
import hmac
import secrets
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo, AccountLines, ServerInfo, Tx
from xrpl.models.transactions import (
    AccountSet,
    AccountSetAsfFlag,
    EscrowCreate,
    Memo,
    Payment,
    TrustSet,
    TrustSetFlag,
)
from xrpl.transaction import submit_and_wait
from xrpl.utils import datetime_to_ripple_time, xrp_to_drops
from xrpl.wallet import Wallet as XRPLWallet
from xrpl.wallet import generate_faucet_wallet

from config import settings
from db import (
    HistoryEvent,
    SpendingGuard,
    Subscription,
    SubscriptionCycle,
    Transaction,
    UserProfile,
    UserWallet,
    Vendor,
    Wallet,
    WebhookDelivery,
    Snapshot,
    get_db,
)
from schemas import (
    BootstrapRlusdRequest,
    PaymentSendRequest,
    RlusdPaymentSendRequest,
    SnapshotAskRequest,
    SnapshotCreateRequest,
    SpendingGuardSetRequest,
    SubscriptionApproveRequest,
    SubscriptionCancelRequest,
    SubscriptionProcessCycleRequest,
    SubscriptionRequestCreateRequest,
    UserProfileRegisterRequest,
    VendorCreateRequest,
    VendorUpdateRequest,
    WalletConnectRequest,
    WalletImportRequest,
)

# Look up stored seed for a wallet address, raising clearly if missing.
def _get_seed_for_address(db: Session, address: str) -> str:
    wallet_row = db.query(Wallet).filter(Wallet.address == address).first()
    if not wallet_row or not wallet_row.seed:
        raise HTTPException(
            status_code=400,
            detail=f"No seed on file for wallet {address}. Re-import or reconnect the wallet.",
        )
    return wallet_row.seed

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
    normalized = Decimal(str(amount_xrp)).quantize(Decimal("0.000001"))
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


# SHA256 helper used for contract hashes.
def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# Resolve vendor from shared-secret header.
def _get_vendor_from_request(request: Request, db: Session) -> Vendor:
    header_name = settings.VENDOR_SHARED_SECRET_HEADER
    shared_secret = request.headers.get(header_name, "").strip()
    if not shared_secret:
        raise HTTPException(status_code=401, detail=f"Missing vendor shared secret header: {header_name}")
    vendor = db.query(Vendor).filter(Vendor.shared_secret == shared_secret).first()
    if not vendor or not vendor.is_active:
        raise HTTPException(status_code=401, detail="Invalid vendor shared secret")
    return vendor


# Build canonical contract payload for signature/hash.
def _build_subscription_contract_payload(
    vendor: Vendor,
    user_profile: UserProfile,
    vendor_tx_id: str,
    amount_xrp: float,
    interval_days: int,
    version: str = "v1",
) -> dict[str, Any]:
    return {
        "version": version,
        "vendor_id": vendor.id,
        "vendor_code": vendor.vendor_code,
        "vendor_tx_id": vendor_tx_id,
        "username": user_profile.username,
        "user_wallet": user_profile.wallet_address,
        "vendor_wallet": vendor.wallet_address,
        "amount_xrp": _amount_to_string(amount_xrp),
        "interval_days": interval_days,
        "network": settings.XRPL_NETWORK,
    }


# Compute stable hash for contract lookup/audits.
def _contract_hash(payload: dict[str, Any]) -> str:
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _sha256_text(canonical)


# Sign contract payload with vendor shared secret.
def _sign_subscription_contract(payload: dict[str, Any], shared_secret: str) -> str:
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(shared_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


# Verify contract payload and signature using vendor shared secret.
def _verify_subscription_contract(payload: dict[str, Any], signature: str, shared_secret: str) -> None:
    expected = _sign_subscription_contract(payload, shared_secret)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid subscription contract signature")


# Generate a vendor shared secret.
def _generate_shared_secret() -> str:
    return secrets.token_urlsafe(32)


def _vendor_photo_url(filename: str) -> str:
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    return f"{base}/static/vendor-photos/{filename}"


# Build and sign a webhook event payload.
def _sign_webhook_event(shared_secret: str, payload_json: str, timestamp: int) -> str:
    signed_payload = f"{timestamp}.{payload_json}".encode("utf-8")
    digest = hmac.new(shared_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


# Send webhook callback and persist delivery details.
def _send_vendor_webhook(db: Session, vendor: Vendor, event_type: str, payload: dict[str, Any]) -> None:
    payload_json = _json.dumps(payload, separators=(",", ":"), sort_keys=True)
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signature = _sign_webhook_event(vendor.shared_secret, payload_json, timestamp)
    row = WebhookDelivery(
        vendor_id=vendor.id,
        event_type=event_type,
        payload=payload_json,
        signature=signature,
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if not vendor.webhook_url:
        row.status = "skipped"
        row.error = "No webhook URL configured"
        db.commit()
        return

    request_obj = urllib_request.Request(
        vendor.webhook_url,
        data=payload_json.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            settings.WEBHOOK_SIGNATURE_HEADER: signature,
            "User-Agent": "EquiPay-Webhook/1.0",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(request_obj, timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as response:
            row.status = "delivered"
            row.http_status = int(response.getcode())
            row.error = None
    except urllib_error.HTTPError as exc:
        row.status = "failed"
        row.http_status = int(exc.code)
        row.error = str(exc.reason)
    except Exception as exc:
        row.status = "failed"
        row.error = str(exc)
    db.commit()


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


# Get all user-wallet link rows joined with wallet rows.
def _get_user_wallet_links(db: Session, user_id: int) -> list[tuple[UserWallet, Wallet]]:
    rows = (
        db.query(UserWallet, Wallet)
        .join(Wallet, UserWallet.wallet_id == Wallet.id)
        .filter(UserWallet.user_profile_id == user_id)
        .order_by(UserWallet.created_at.desc())
        .all()
    )
    return rows


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


# Parse optional ISO date/datetime value into UTC datetime.
def _parse_snapshot_datetime(raw: Optional[str], field_name: str) -> Optional[datetime]:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}, expected ISO date/datetime") from exc


def _encode_multipart_form(fields: dict[str, str], file_name: str, file_bytes: bytes) -> tuple[bytes, str]:
    boundary = f"----equipay{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        "Content-Type: application/json\r\n\r\n".encode("utf-8")
    )
    body.extend(file_bytes)
    body.extend("\r\n".encode("utf-8"))
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


# Upload full snapshot artifact JSON to Pinata and return CID + file id.
def _upload_snapshot_to_pinata(snapshot_json: dict[str, Any], title: str) -> dict[str, Optional[str]]:
    if not settings.PINATA_JWT.strip():
        raise HTTPException(status_code=500, detail="PINATA_JWT is not configured")

    network = settings.PINATA_UPLOAD_NETWORK.strip().lower() or "private"
    upload_url = settings.PINATA_UPLOAD_URL.strip()
    if "/v3/files" in upload_url:
        payload_bytes, content_type = _encode_multipart_form(
            fields={"network": network, "name": title},
            file_name=f"{title.replace(' ', '_').lower()}.json",
            file_bytes=_json.dumps(snapshot_json).encode("utf-8"),
        )
        request_obj = urllib_request.Request(
            upload_url,
            data=payload_bytes,
            headers={
                "Content-Type": content_type,
                "Authorization": f"Bearer {settings.PINATA_JWT.strip()}",
                "Accept": "application/json",
                "User-Agent": "EquiPay/1.0 (+https://equipay.local)",
            },
            method="POST",
        )
    else:
        if network == "private":
            raise HTTPException(
                status_code=500,
                detail=(
                    "PINATA_UPLOAD_NETWORK is 'private' but PINATA_UPLOAD_URL is not the v3 files endpoint. "
                    "Use PINATA_UPLOAD_URL=https://uploads.pinata.cloud/v3/files for private uploads."
                ),
            )
        payload = {
            "pinataContent": snapshot_json,
            "pinataMetadata": {"name": title},
            "pinataOptions": {"cidVersion": 1},
        }
        request_obj = urllib_request.Request(
            upload_url,
            data=_json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.PINATA_JWT.strip()}",
                "Accept": "application/json",
                "User-Agent": "EquiPay/1.0 (+https://equipay.local)",
            },
            method="POST",
        )
    try:
        with urllib_request.urlopen(request_obj, timeout=settings.PINATA_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            parsed = _json.loads(body) if body else {}
    except urllib_error.HTTPError as exc:
        message = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
        raise HTTPException(status_code=502, detail=f"Pinata upload failed: {message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pinata upload failed: {exc}") from exc

    data = parsed.get("data") if isinstance(parsed, dict) else None
    cid = parsed.get("IpfsHash") or parsed.get("cid") or (data.get("cid") if isinstance(data, dict) else None)
    if not cid:
        raise HTTPException(status_code=502, detail="Pinata upload succeeded but no CID returned")
    file_id = parsed.get("id") or (data.get("id") if isinstance(data, dict) else None)
    return {"cid": cid, "file_id": file_id}


# Fetch snapshot artifact JSON from Pinata by CID or file_id.
def _fetch_snapshot_from_pinata(cid: str, file_id: Optional[str] = None) -> dict[str, Any]:
    if file_id:
        file_url = f"https://uploads.pinata.cloud/v3/files/{urllib_parse.quote(file_id)}"
        request_obj = urllib_request.Request(
            file_url,
            headers={
                "Authorization": f"Bearer {settings.PINATA_JWT.strip()}",
                "Accept": "application/json",
                "User-Agent": "EquiPay/1.0 (+https://equipay.local)",
            },
            method="GET",
        )
        try:
            with urllib_request.urlopen(request_obj, timeout=settings.PINATA_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
                parsed = _json.loads(body)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            # Fall back to CID gateway resolution below.
            pass

    gateway = settings.PINATA_GATEWAY_BASE_URL.rstrip("/")
    quoted_cid = urllib_parse.quote(cid)
    candidate_urls: list[str] = []
    if "{cid}" in gateway:
        candidate_urls.append(gateway.replace("{cid}", quoted_cid))
    else:
        parsed_gateway = urllib_parse.urlparse(gateway)
        path = (parsed_gateway.path or "").rstrip("/")
        if path.endswith("/ipfs") or path.endswith("/files"):
            candidate_urls.append(f"{gateway}/{quoted_cid}")
        elif path:
            candidate_urls.append(f"{gateway}/files/{quoted_cid}")
            candidate_urls.append(f"{gateway}/ipfs/{quoted_cid}")
        else:
            candidate_urls.append(f"{gateway}/files/{quoted_cid}")
            candidate_urls.append(f"{gateway}/ipfs/{quoted_cid}")

    gateway_token = settings.PINATA_GATEWAY_TOKEN.strip()
    headers = {}
    if settings.PINATA_JWT.strip():
        headers["Authorization"] = f"Bearer {settings.PINATA_JWT.strip()}"
    if gateway_token:
        headers["x-pinata-gateway-token"] = gateway_token
    headers["Accept"] = "application/json"
    headers["User-Agent"] = "EquiPay/1.0 (+https://equipay.local)"

    errors: list[str] = []
    parsed: Any = None
    for raw_url in candidate_urls:
        url = raw_url
        if gateway_token and "pinataGatewayToken=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}pinataGatewayToken={urllib_parse.quote(gateway_token)}"
        request_obj = urllib_request.Request(url, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(request_obj, timeout=settings.PINATA_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
                parsed = _json.loads(body)
                break
        except urllib_error.HTTPError as exc:
            message = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
            errors.append(f"{url} -> {message}")
        except Exception as exc:
            errors.append(f"{url} -> {exc}")

    if parsed is None:
        raise HTTPException(status_code=502, detail=f"Pinata fetch failed: {' | '.join(errors)}")

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Pinata returned invalid snapshot JSON")
    return parsed


# Send question + snapshot artifact to Gemini and return answer text.
def _ask_gemini_with_snapshot(snapshot_json: dict[str, Any], question: str) -> str:
    if not settings.GEMINI_API_KEY.strip():
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")
    configured_model = settings.GEMINI_MODEL.strip() or "gemini-2.0-flash"
    candidate_models = []
    for model_name in [configured_model, "gemini-2.0-flash", "gemini-2.5-flash"]:
        if model_name and model_name not in candidate_models:
            candidate_models.append(model_name)
    base_url = settings.GEMINI_API_BASE_URL.rstrip("/")
    prompt = (
        "You are a financial assistant working only from a fixed snapshot artifact. "
        "Do not assume data not present in the snapshot. "
        "Give concise practical guidance and show any simple calculations.\n\n"
        f"User question:\n{question}\n\n"
        "Snapshot JSON:\n"
        f"{_json.dumps(snapshot_json)}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    last_error: Optional[str] = None
    for model in candidate_models:
        url = f"{base_url}/models/{model}:generateContent?key={urllib_parse.quote(settings.GEMINI_API_KEY.strip())}"
        request_obj = urllib_request.Request(
            url,
            data=_json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(request_obj, timeout=30) as response:
                parsed = _json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            message = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
            last_error = message
            if exc.code == 404:
                continue
            raise HTTPException(status_code=502, detail=f"Gemini request failed: {message}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc

        candidates = parsed.get("candidates") or []
        if not candidates:
            last_error = "Gemini returned no candidates"
            continue
        content = candidates[0].get("content", {})
        parts = content.get("parts") or []
        answer = "".join(str(part.get("text", "")) for part in parts).strip()
        if answer:
            return answer
        last_error = "Gemini returned empty response"

    raise HTTPException(
        status_code=502,
        detail=f"Gemini request failed: {last_error or 'No supported Gemini model available for generateContent'}",
    )

def generate_wallet_review(
    wallet_addresses: list[str],
    days: int,
    db: Session,
) -> dict[str, Any]:
    from datetime import datetime, timedelta, timezone
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    all_transactions = []
    all_subscriptions = []

    for address in wallet_addresses:
        txs = (
            db.query(Transaction)
            .filter(Transaction.from_address == address)
            .filter(Transaction.created_at >= period_start)
            .order_by(Transaction.created_at.desc())
            .all()
        )
        all_transactions.extend([
            {
                "wallet": address,
                "tx_hash": row.tx_hash,
                "tx_type": row.tx_type,
                "to_address": row.to_address,
                "amount_xrp": row.amount_xrp,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
            for row in txs
        ])

        subs = (
            db.query(Subscription)
            .filter(Subscription.user_wallet_address == address)
            .filter(Subscription.status.in_(["active", "non_renewing"]))
            .all()
        )
        all_subscriptions.extend([
            {
                "wallet": address,
                "vendor_tx_id": row.vendor_tx_id,
                "amount_xrp": row.amount_xrp,
                "interval_days": row.interval_days,
                "status": row.status,
                "next_payment_date": row.next_payment_date.isoformat(),
                "auto_renew": bool(row.auto_renew),
            }
            for row in subs
        ])

    prompt_data = {
        "period_days": days,
        "wallets_reviewed": wallet_addresses,
        "transactions": all_transactions,
        "active_subscriptions": all_subscriptions,
    }

    prompt = (
        f"You are a personal finance assistant reviewing a user's XRPL blockchain wallet activity "
        f"over the past {days} days. Analyze the following data and provide a concise, friendly summary covering:\n"
        "1. Overall spending patterns\n"
        "2. Notable transactions\n"
        "3. Active subscriptions and their cost\n"
        "4. Any observations or suggestions\n\n"
        "Keep the tone conversational and helpful. Use bullet points where appropriate.\n\n"
        f"Data:\n{_json.dumps(prompt_data, indent=2)}"
    )

    if not settings.GEMINI_API_KEY.strip():
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    model = settings.GEMINI_MODEL.strip() or "gemini-1.5-flash"
    base_url = settings.GEMINI_API_BASE_URL.rstrip("/")
    url = f"{base_url}/models/{model}:generateContent?key={urllib_parse.quote(settings.GEMINI_API_KEY.strip())}"

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    request_obj = urllib_request.Request(
        url,
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request_obj, timeout=30) as response:
            parsed = _json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        message = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc

    candidates = parsed.get("candidates") or []
    if not candidates:
        raise HTTPException(status_code=502, detail="Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts") or []
    summary = "".join(str(p.get("text", "")) for p in parts).strip()
    if not summary:
        raise HTTPException(status_code=502, detail="Gemini returned empty response")

    return _success(
        "AI review generated",
        {
            "summary": summary,
            "wallets_reviewed": wallet_addresses,
            "period_days": days,
            "transaction_count": len(all_transactions),
            "subscription_count": len(all_subscriptions),
        },
    )


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
            monthly_limit=500.0,
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
    if (guard.currency or "").upper() != (currency or "").upper():
        return
    guard.spent_this_month += float(amount)
    guard.updated_at = datetime.now(timezone.utc)


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


# Create RLUSD trust line for wallet if missing.
def _ensure_rlusd_trustline(user_wallet: XRPLWallet) -> bool:
    if user_wallet.classic_address == settings.RLUSD_ISSUER:
        return False  # Issuer doesn't need a trustline to itself
    client = _get_xrpl_client()
    tx = TrustSet(
        account=user_wallet.classic_address,
        limit_amount=IssuedCurrencyAmount(
            currency=_currency_to_hex(settings.RLUSD_CURRENCY),
            issuer=settings.RLUSD_ISSUER,
            value="1000000",
        ),
        flags=TrustSetFlag.TF_CLEAR_NO_RIPPLE,
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

    # Ensure DefaultRipple is enabled on issuer — required for peer-to-peer IOU transfers
    try:
        acct_info = client.request(AccountInfo(
            account=issuer_wallet.classic_address,
            ledger_index="validated"
        )).result
        flags = acct_info.get("account_data", {}).get("Flags", 0)
        if not (flags & 0x00800000):  # lsfDefaultRipple not set
            set_flag_tx = AccountSet(
                account=issuer_wallet.classic_address,
                set_flag=AccountSetAsfFlag.ASF_DEFAULT_RIPPLE,
            )
            submit_and_wait(set_flag_tx, client, issuer_wallet)
    except Exception:
        pass  # Non-fatal — payment attempt will fail with clear error if still needed

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
    if not str(tx_status).startswith("tes"):
        raise HTTPException(status_code=400, detail=f"Payment failed with XRPL status: {tx_status}")

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
            send_max=issued_amount,
        )
        response = submit_and_wait(tx, client, sender_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Issued payment failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_status = result.get("meta", {}).get("TransactionResult") or result.get("engine_result") or "unknown"
    if tx_status == "tecPATH_DRY":
        raise HTTPException(
            status_code=400,
            detail=(
                "Issued payment failed with tecPATH_DRY. "
                "Destination trust line may be missing, sender balance may be insufficient, "
                "or no valid path exists for issuer/currency."
            ),
        )
    if not str(tx_status).startswith("tes"):
        raise HTTPException(status_code=400, detail=f"Issued payment failed with XRPL status: {tx_status}")

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


# Convert cycle ORM row into API response shape.
def _cycle_to_dict(row: SubscriptionCycle) -> dict[str, Any]:
    return {
        "id": row.id,
        "subscription_id": row.subscription_id,
        "cycle_index": row.cycle_index,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "status": row.status,
        "escrow_amount_xrp": row.escrow_amount_xrp,
        "escrow_offer_sequence": row.escrow_offer_sequence,
        "escrow_create_tx_hash": row.escrow_create_tx_hash,
        "escrow_finish_tx_hash": row.escrow_finish_tx_hash,
        "escrow_cancel_tx_hash": row.escrow_cancel_tx_hash,
        "escrow_cancel_after": row.escrow_cancel_after,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# Create an escrow-backed billing cycle and persist both cycle + subscription state.
def _create_subscription_cycle_with_escrow(
    db: Session,
    subscription: Subscription,
    user_seed: str,
    cycle_index: int,
    period_start: date,
    period_end: date,
) -> SubscriptionCycle:
    client = _get_xrpl_client()
    user_wallet = _wallet_from_seed(user_seed)
    if user_wallet.classic_address != subscription.user_wallet_address:
        raise HTTPException(status_code=400, detail="Provided seed does not match subscription user wallet")

    finish_after_dt = datetime.combine(period_end, datetime.min.time(), tzinfo=timezone.utc)
    cancel_after_dt = finish_after_dt + timedelta(days=max(subscription.interval_days, 1))

    tx = EscrowCreate(
        account=subscription.user_wallet_address,
        destination=subscription.merchant_wallet_address,
        amount=_xrp_to_drops(subscription.amount_xrp),
        finish_after=datetime_to_ripple_time(finish_after_dt),
        cancel_after=datetime_to_ripple_time(cancel_after_dt),
        memos=[Memo(memo_data=_hex_text(f"CYCLE_ESCROW:{subscription.id}:{cycle_index}:{subscription.contract_hash}"))],
    )

    try:
        response = submit_and_wait(tx, client, user_wallet)
        result = response.result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cycle escrow lock failed: {exc}") from exc

    tx_hash = result.get("hash") or result.get("tx_json", {}).get("hash")
    tx_status = result.get("meta", {}).get("TransactionResult") or "unknown"
    offer_sequence = result.get("tx_json", {}).get("Sequence")

    cycle_row = SubscriptionCycle(
        subscription_id=subscription.id,
        cycle_index=cycle_index,
        period_start=period_start,
        period_end=period_end,
        status="locked",
        escrow_amount_xrp=subscription.amount_xrp,
        escrow_offer_sequence=offer_sequence,
        escrow_create_tx_hash=tx_hash,
        escrow_cancel_after=datetime_to_ripple_time(cancel_after_dt),
    )
    db.add(cycle_row)

    subscription.escrow_amount_xrp = subscription.amount_xrp
    subscription.escrow_offer_sequence = offer_sequence
    subscription.escrow_create_tx_hash = tx_hash
    subscription.escrow_status = "locked"
    subscription.escrow_cancel_after = datetime_to_ripple_time(cancel_after_dt)
    subscription.last_tx_hash = tx_hash
    subscription.updated_at = datetime.now(timezone.utc)

    db.add(
        Transaction(
            tx_hash=tx_hash,
            tx_type="subscription_cycle_escrow_lock",
            from_address=subscription.user_wallet_address,
            to_address=subscription.merchant_wallet_address,
            amount_xrp=subscription.amount_xrp,
            status=tx_status,
        )
    )
    _record_history(
        db,
        user_wallet_address=subscription.user_wallet_address,
        event_type="subscription_cycle_escrow_lock",
        tx_hash=tx_hash,
        counterparty_address=subscription.merchant_wallet_address,
        amount=subscription.amount_xrp,
        currency="XRP",
        status=tx_status,
        note=f"Subscription {subscription.id} cycle {cycle_index} escrow created",
    )
    db.commit()
    db.refresh(cycle_row)
    db.refresh(subscription)
    return cycle_row


# Convert subscription ORM row to API-friendly response object.
def _subscription_to_dict(row: Subscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "vendor_id": row.vendor_id,
        "user_profile_id": row.user_profile_id,
        "vendor_tx_id": row.vendor_tx_id,
        "user_wallet_address": row.user_wallet_address,
        "merchant_wallet_address": row.merchant_wallet_address,
        "amount_xrp": row.amount_xrp,
        "interval_days": row.interval_days,
        "status": row.status,
        "request_status": row.request_status,
        "contract_hash": row.contract_hash,
        "contract_alg": row.contract_alg,
        "contract_version": row.contract_version,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by_username": row.approved_by_username,
        "start_date": row.start_date.isoformat(),
        "next_payment_date": row.next_payment_date.isoformat(),
        "last_tx_hash": row.last_tx_hash,
        "auto_renew": bool(row.auto_renew),
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
def import_wallet(payload: WalletImportRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    wallet = _wallet_from_seed(payload.seed)
    wallet_row = _save_or_get_wallet(db, wallet.classic_address, payload.seed)
    return _success(
        "Wallet imported",
        {
            "id": wallet_row.id,
            "address": wallet_row.address,
            "network": wallet_row.network,
        },
    )

# Connect a wallet to the current user with a shorthand nickname.
def connect_user_wallet(payload: WalletConnectRequest, current_user: UserProfile, db: Session) -> dict[str, Any]:
    wallet = _wallet_from_seed(payload.seed)
    wallet_row = _save_or_get_wallet(db, wallet.classic_address, payload.seed)

    existing_nickname = (
        db.query(UserWallet)
        .filter(UserWallet.user_profile_id == current_user.id)
        .filter(UserWallet.nickname == payload.nickname)
        .first()
    )
    if existing_nickname and existing_nickname.wallet_id != wallet_row.id:
        raise HTTPException(status_code=409, detail="Nickname already used for another wallet")

    link = (
        db.query(UserWallet)
        .filter(UserWallet.user_profile_id == current_user.id)
        .filter(UserWallet.wallet_id == wallet_row.id)
        .first()
    )
    if link:
        link.nickname = payload.nickname
        db.commit()
        db.refresh(link)
    else:
        link = UserWallet(user_profile_id=current_user.id, wallet_id=wallet_row.id, nickname=payload.nickname)
        db.add(link)
        db.commit()
        db.refresh(link)

    if not current_user.wallet_address:
        current_user.wallet_address = wallet_row.address
        db.commit()

    return _success(
        "Wallet connected",
        {
            "link_id": link.id,
            "nickname": link.nickname,
            "wallet_id": wallet_row.id,
            "address": wallet_row.address,
            "network": wallet_row.network,
            "created_at": link.created_at.isoformat(),
        },
    )


# List connected wallets for current user with pagination.
def list_connected_wallets(current_user: UserProfile, db: Session, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = (
        db.query(UserWallet, Wallet)
        .join(Wallet, UserWallet.wallet_id == Wallet.id)
        .filter(UserWallet.user_profile_id == current_user.id)
    )
    total = query.count()
    rows = (
        query.order_by(UserWallet.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = [
        {
            "link_id": link.id,
            "nickname": link.nickname,
            "wallet_id": wallet_row.id,
            "address": wallet_row.address,
            "network": wallet_row.network,
            "created_at": link.created_at.isoformat(),
        }
        for link, wallet_row in rows
    ]
    return _success(
        "Connected wallets",
        {
            "items": data,
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    )

# Remove a connected wallet link for current user only.
def delete_connected_wallet(link_id: int, current_user: UserProfile, db: Session) -> dict[str, Any]:
    link = (
        db.query(UserWallet)
        .filter(UserWallet.id == link_id)
        .filter(UserWallet.user_profile_id == current_user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Connected wallet link not found")
    db.delete(link)
    db.commit()
    return _success("Connected wallet removed", {"link_id": link_id})


# Bootstrap RLUSD readiness: trust line + mint for an imported wallet.
def bootstrap_rlusd_wallet(
    payload: BootstrapRlusdRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.user_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid user_wallet_address")
    user_seed = _get_seed_for_address(db, payload.user_wallet_address)
    user_wallet = _wallet_from_seed(user_seed)

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
def list_wallets(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.query(Wallet).order_by(Wallet.created_at.desc()).all()
    return _success(
        "Wallet list",
        [
            {
                "id": row.id,
                "address": row.address,
                "network": row.network,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    )


# Get XRP and RLUSD balances for a wallet address.
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


# Aggregate XRP and RLUSD balances across all connected wallets for current user.
def get_aggregate_wallet_balance(current_user: UserProfile, db: Session) -> dict[str, Any]:
    links = _get_user_wallet_links(db, current_user.id)
    wallets = []
    total_xrp = 0.0
    total_rlusd = 0.0
    for link, wallet_row in links:
        balance = get_wallet_balance(wallet_row.address)["data"]
        xrp = float(balance.get("balance_xrp") or 0.0)
        rlusd = float(balance.get("rlusd_balance") or 0.0)
        total_xrp += xrp
        total_rlusd += rlusd
        wallets.append(
            {
                "link_id": link.id,
                "nickname": link.nickname,
                "address": wallet_row.address,
                "balance_xrp": xrp,
                "rlusd_balance": rlusd,
            }
        )
    return _success(
        "Aggregate wallet balance",
        {
            "wallet_count": len(wallets),
            "total_balance_xrp": round(total_xrp, 6),
            "total_balance_rlusd": round(total_rlusd, 6),
            "wallets": wallets,
        },
    )


# Submit one XRP payment and store transaction summary.
def send_payment(
    payload: PaymentSendRequest,
    db: Session = Depends(get_db),
    request: Request = None,
) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.from_address):
        raise HTTPException(status_code=400, detail="Invalid from_address")
    sender_seed = _get_seed_for_address(db, payload.from_address)

    payment_result = _send_xrp_payment(
        sender_seed=sender_seed,
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
    if request:
        try:
            vendor = _get_vendor_from_request(request, db)
            _send_vendor_webhook(
                db, vendor, "payment.sent",
                {
                    "event": "payment.sent",
                    "tx_hash": tx_row.tx_hash,
                    "from_address": tx_row.from_address,
                    "to_address": tx_row.to_address,
                    "amount_xrp": tx_row.amount_xrp,
                    "status": tx_row.status,
                },
            )
        except HTTPException:
            pass

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
def send_rlusd_payment(
    payload: RlusdPaymentSendRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    if not _is_valid_classic_address(payload.from_address):
        raise HTTPException(status_code=400, detail="Invalid from_address")
    sender_seed = _get_seed_for_address(db, payload.from_address)

    payment_result = _send_issued_payment(
        sender_seed=sender_seed,
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
    if request:
        try:
            vendor = _get_vendor_from_request(request, db)
            _send_vendor_webhook(
                db, vendor, "payment.sent",
                {
                    "event": "payment.sent",
                    "tx_hash": tx_row.tx_hash,
                    "from_address": tx_row.from_address,
                    "to_address": tx_row.to_address,
                    "amount": payload.amount,
                    "currency": settings.RLUSD_CURRENCY,
                    "issuer": settings.RLUSD_ISSUER,
                    "status": tx_row.status,
                },
            )
        except HTTPException:
            pass

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


# Register or update a user profile for username-based subscription lookup.
def register_user_profile(payload: UserProfileRegisterRequest, db: Session) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.wallet_address):
        raise HTTPException(status_code=400, detail="Invalid wallet_address")

    row = db.query(UserProfile).filter(UserProfile.username == payload.username).first()
    if row:
        row.wallet_address = payload.wallet_address
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _success(
            "User profile updated",
            {
                "id": row.id,
                "username": row.username,
                "wallet_address": row.wallet_address,
            },
        )

    row = UserProfile(username=payload.username, wallet_address=payload.wallet_address)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _success(
        "User profile created",
        {
            "id": row.id,
            "username": row.username,
            "wallet_address": row.wallet_address,
        },
    )


# Create or update vendor and return shared-secret credentials.
def upsert_vendor(payload: VendorCreateRequest, db: Session) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.wallet_address):
        raise HTTPException(status_code=400, detail="Invalid wallet_address")

    row = db.query(Vendor).filter(Vendor.vendor_code == payload.vendor_code).first()
    shared_secret = (payload.shared_secret or "").strip() or _generate_shared_secret()
    if row:
        row.display_name = payload.display_name
        row.wallet_address = payload.wallet_address
        row.webhook_url = payload.webhook_url
        row.vendor_photo_url = payload.vendor_photo_url
        row.shared_secret = shared_secret
        row.is_active = True
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return _success(
            "Vendor updated",
            {
                "id": row.id,
                "vendor_code": row.vendor_code,
                "display_name": row.display_name,
                "wallet_address": row.wallet_address,
                "webhook_url": row.webhook_url,
                "vendor_photo_url": row.vendor_photo_url,
                "shared_secret": row.shared_secret,
                "is_active": row.is_active,
            },
        )

    row = Vendor(
        vendor_code=payload.vendor_code,
        display_name=payload.display_name,
        wallet_address=payload.wallet_address,
        shared_secret=shared_secret,
        webhook_url=payload.webhook_url,
        vendor_photo_url=payload.vendor_photo_url,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _success(
        "Vendor created",
        {
            "id": row.id,
            "vendor_code": row.vendor_code,
            "display_name": row.display_name,
            "wallet_address": row.wallet_address,
            "webhook_url": row.webhook_url,
            "vendor_photo_url": row.vendor_photo_url,
            "shared_secret": row.shared_secret,
            "is_active": row.is_active,
        },
    )


# Return vendor profile for authenticated vendor.
def get_vendor_me(request: Request, db: Session) -> dict[str, Any]:
    vendor = _get_vendor_from_request(request, db)
    return _success(
        "Vendor profile",
        {
            "id": vendor.id,
            "vendor_code": vendor.vendor_code,
            "display_name": vendor.display_name,
            "wallet_address": vendor.wallet_address,
            "webhook_url": vendor.webhook_url,
            "vendor_photo_url": vendor.vendor_photo_url,
            "shared_secret": vendor.shared_secret,
            "is_active": vendor.is_active,
        },
    )


# Update authenticated vendor profile fields.
def update_vendor(request: Request, payload: VendorUpdateRequest, db: Session) -> dict[str, Any]:
    vendor = _get_vendor_from_request(request, db)
    if payload.wallet_address:
        if not _is_valid_classic_address(payload.wallet_address):
            raise HTTPException(status_code=400, detail="Invalid wallet_address")
        vendor.wallet_address = payload.wallet_address
    if payload.display_name:
        vendor.display_name = payload.display_name
    if payload.webhook_url is not None:
        vendor.webhook_url = payload.webhook_url
    if payload.vendor_photo_url is not None:
        vendor.vendor_photo_url = payload.vendor_photo_url
    vendor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vendor)
    return _success(
        "Vendor updated",
        {
            "id": vendor.id,
            "vendor_code": vendor.vendor_code,
            "display_name": vendor.display_name,
            "wallet_address": vendor.wallet_address,
            "webhook_url": vendor.webhook_url,
            "vendor_photo_url": vendor.vendor_photo_url,
            "shared_secret": vendor.shared_secret,
            "is_active": vendor.is_active,
        },
    )


def upload_vendor_photo(request: Request, photo: UploadFile, db: Session) -> dict[str, Any]:
    vendor = _get_vendor_from_request(request, db)
    if not photo.filename:
        raise HTTPException(status_code=400, detail="Photo filename is required")
    ext = Path(photo.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported photo format. Use png/jpg/jpeg/webp.")

    photo_dir = Path(settings.VENDOR_PHOTO_DIR)
    photo_dir.mkdir(parents=True, exist_ok=True)
    filename = f"vendor-{vendor.id}-{uuid.uuid4().hex}{ext}"
    dest = photo_dir / filename
    content = photo.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo too large (max 5MB)")
    dest.write_bytes(content)

    vendor.vendor_photo_url = _vendor_photo_url(filename)
    vendor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vendor)
    return _success(
        "Vendor photo uploaded",
        {
            "vendor_code": vendor.vendor_code,
            "vendor_photo_url": vendor.vendor_photo_url,
        },
    )


# Rotate shared secret for authenticated vendor.
def regenerate_vendor_secret(request: Request, db: Session) -> dict[str, Any]:
    vendor = _get_vendor_from_request(request, db)
    vendor.shared_secret = _generate_shared_secret()
    vendor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vendor)
    return _success(
        "Vendor shared secret regenerated",
        {
            "vendor_code": vendor.vendor_code,
            "shared_secret": vendor.shared_secret,
        },
    )


# Create a vendor-authenticated subscription payment request and signed contract.
def create_subscription_request(
    request: Request,
    payload: SubscriptionRequestCreateRequest,
    db: Session,
) -> dict[str, Any]:
    vendor = _get_vendor_from_request(request, db)
    user_profile = db.query(UserProfile).filter(UserProfile.username == payload.username).first()
    if not user_profile:
        raise HTTPException(status_code=404, detail="Unknown username")

    existing = (
        db.query(Subscription)
        .filter(Subscription.vendor_id == vendor.id)
        .filter(Subscription.vendor_tx_id == payload.vendor_tx_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate vendor_tx_id for this vendor")

    if not user_profile.wallet_address or not _is_valid_classic_address(user_profile.wallet_address):
        raise HTTPException(
            status_code=400,
            detail="User has no wallet address configured. They must connect a wallet before subscribing."
        )

    contract_payload = _build_subscription_contract_payload(
        vendor=vendor,
        user_profile=user_profile,
        vendor_tx_id=payload.vendor_tx_id,
        amount_xrp=payload.amount_xrp,
        interval_days=payload.interval_days,
    )
    contract_signature = _sign_subscription_contract(contract_payload, vendor.shared_secret)
    contract_hash = _contract_hash(contract_payload)

    today = date.today()
    row = Subscription(
        vendor_id=vendor.id,
        user_profile_id=user_profile.id,
        vendor_tx_id=payload.vendor_tx_id,
        user_wallet_address=user_profile.wallet_address,
        merchant_wallet_address=vendor.wallet_address,
        amount_xrp=payload.amount_xrp,
        interval_days=payload.interval_days,
        status="pending",
        request_status="pending",
        contract_signature=contract_signature,
        contract_hash=contract_hash,
        contract_alg="HMAC-SHA256",
        contract_version="v1",
        start_date=today,
        next_payment_date=today,
        auto_renew=True,
        use_escrow=1,
        escrow_amount_xrp=payload.amount_xrp,
        escrow_status="not_started",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _send_vendor_webhook(
        db,
        vendor,
        "subscription.requested",
        {
            "event": "subscription.requested",
            "subscription_id": row.id,
            "vendor_tx_id": row.vendor_tx_id,
            "contract_hash": row.contract_hash,
            "request_status": row.request_status,
            "status": row.status,
            "username": user_profile.username,
            "user_wallet_address": row.user_wallet_address,
            "merchant_wallet_address": row.merchant_wallet_address,
            "amount_xrp": row.amount_xrp,
            "interval_days": row.interval_days,
        },
    )

    return _success(
        "Subscription request created",
        {
            "ok": True,
            "subscription_id": row.id,
            "vendor_tx_id": row.vendor_tx_id,
            "contract_hash": row.contract_hash,
            "request_status": row.request_status,
        },
    )


# Return pending requests for a username.
def list_pending_subscription_requests(username: str, db: Session) -> dict[str, Any]:
    profile = db.query(UserProfile).filter(UserProfile.username == username).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Unknown username")

    rows = (
        db.query(Subscription)
        .filter(Subscription.user_profile_id == profile.id)
        .filter(Subscription.request_status == "pending")
        .order_by(Subscription.created_at.desc())
        .all()
    )
    vendor_by_id = {v.id: v for v in db.query(Vendor).all()}
    return _success(
        "Pending subscriptions",
        [
            {**_subscription_to_dict(row),
             "vendor_name": vendor_by_id.get(row.vendor_id).display_name if vendor_by_id.get(row.vendor_id) else None,
             "vendor_photo_url": vendor_by_id.get(row.vendor_id).vendor_photo_url if vendor_by_id.get(row.vendor_id) else None}
            for row in rows
        ],
    )


# Approve pending request, verify contract signature/payload, and create escrow.
def approve_subscription_request(
    subscription_id: int,
    payload: SubscriptionApproveRequest,
    db: Session,
) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.request_status != "pending":
        raise HTTPException(status_code=409, detail="Subscription request is not pending")

    profile = db.query(UserProfile).filter(UserProfile.id == row.user_profile_id).first()
    if not profile or profile.username != payload.username:
        raise HTTPException(status_code=400, detail="Username does not match subscription")

    user_seed = _get_seed_for_address(db, row.user_wallet_address)

    vendor = db.query(Vendor).filter(Vendor.id == row.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    contract_payload = _build_subscription_contract_payload(
        vendor=vendor,
        user_profile=profile,
        vendor_tx_id=row.vendor_tx_id,
        amount_xrp=row.amount_xrp,
        interval_days=row.interval_days,
        version=row.contract_version or "v1",
    )
    _verify_subscription_contract(contract_payload, row.contract_signature, vendor.shared_secret)
    expected_hash = _contract_hash(contract_payload)
    if expected_hash != row.contract_hash:
        raise HTTPException(status_code=400, detail="Contract hash mismatch")

    first_cycle_start = row.start_date
    first_cycle_end = first_cycle_start + timedelta(days=row.interval_days)
    cycle_row = _create_subscription_cycle_with_escrow(
        db=db,
        subscription=row,
        user_seed=user_seed,
        cycle_index=1,
        period_start=first_cycle_start,
        period_end=first_cycle_end,
    )

    row.status = "active"
    row.request_status = "approved"
    row.approved_at = datetime.now(timezone.utc)
    row.approved_by_username = payload.username
    row.next_payment_date = first_cycle_end
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    _send_vendor_webhook(
        db, vendor, "subscription.approved",
        {
            "event": "subscription.approved",
            "subscription_id": row.id,
            "vendor_tx_id": row.vendor_tx_id,
            "contract_hash": row.contract_hash,
            "request_status": row.request_status,
            "status": row.status,
            "escrow_create_tx_hash": cycle_row.escrow_create_tx_hash,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        },
    )

    return _success(
        "Subscription approved",
        {
            "ok": True,
            "subscription_id": row.id,
            "vendor_tx_id": row.vendor_tx_id,
            "contract_hash": row.contract_hash,
            "escrow_create_tx_hash": row.escrow_create_tx_hash,
            "cycle_id": cycle_row.id,
            "cycle_index": cycle_row.cycle_index,
            "request_status": row.request_status,
            "status": row.status,
        },
    )

# Lookup subscription by contract hash for auditing/inspection.
def get_subscription_by_contract(contract_hash: str, db: Session) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.contract_hash == contract_hash).first()
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    return _success("Subscription by contract", _subscription_to_dict(row))


# Cancel by vendor shared-secret or user credentials.
def cancel_subscription_request(
    subscription_id: int,
    request: Request,
    payload: Optional[SubscriptionCancelRequest],
    db: Session,
) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if row.status == "cancelled":
        return _success(
            "Subscription already cancelled",
            {"id": row.id, "status": row.status, "request_status": row.request_status, "auto_renew": bool(row.auto_renew)},
        )

    authorized = False
    vendor_secret = request.headers.get(settings.VENDOR_SHARED_SECRET_HEADER, "").strip()
    vendor: Optional[Vendor] = None
    if vendor_secret:
        vendor = _get_vendor_from_request(request, db)
        if vendor.id == row.vendor_id:
            authorized = True

    if payload and payload.username:
        profile = db.query(UserProfile).filter(UserProfile.id == row.user_profile_id).first()
        if profile and profile.username == payload.username:
            authorized = True

    if not authorized:
        raise HTTPException(status_code=401, detail="Not authorized to cancel this subscription")

    if row.request_status == "pending":
        row.status = "cancelled"
        row.request_status = "cancelled"
        _record_history(
            db=db,
            user_wallet_address=row.user_wallet_address,
            event_type="subscription_request_cancelled",
            tx_hash=None,
            counterparty_address=row.merchant_wallet_address,
            amount=row.amount_xrp,
            currency="XRP",
            status=row.status,
            note=f"Subscription request cancelled (vendor_tx_id={row.vendor_tx_id})",
        )
    else:
        row.auto_renew = False
        row.status = "non_renewing"
        _record_history(
            db=db,
            user_wallet_address=row.user_wallet_address,
            event_type="subscription_non_renewing",
            tx_hash=None,
            counterparty_address=row.merchant_wallet_address,
            amount=row.amount_xrp,
            currency="XRP",
            status=row.status,
            note=f"Auto-renew disabled (vendor_tx_id={row.vendor_tx_id})",
        )
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    if not vendor:
        vendor = db.query(Vendor).filter(Vendor.id == row.vendor_id).first()
    if vendor:
        _send_vendor_webhook(
            db, vendor, "subscription.cancelled",
            {
                "event": "subscription.cancelled",
                "subscription_id": row.id,
                "vendor_tx_id": row.vendor_tx_id,
                "contract_hash": row.contract_hash,
                "request_status": row.request_status,
                "status": row.status,
                "auto_renew": bool(row.auto_renew),
            },
        )
    return _success(
        "Subscription updated",
        {
            "id": row.id,
            "status": row.status,
            "request_status": row.request_status,
            "auto_renew": bool(row.auto_renew),
            "contract_hash": row.contract_hash,
            "vendor_tx_id": row.vendor_tx_id,
        },
    )


# List all subscriptions for admin/dashboard views.
def list_subscriptions(db: Session) -> dict[str, Any]:
    rows = db.query(Subscription).order_by(Subscription.created_at.desc()).all()
    vendor_by_id = {v.id: v for v in db.query(Vendor).all()}
    return _success(
        "Subscription list",
        [
            {**_subscription_to_dict(row),
             "vendor_name": vendor_by_id.get(row.vendor_id).display_name if vendor_by_id.get(row.vendor_id) else None,
             "vendor_photo_url": vendor_by_id.get(row.vendor_id).vendor_photo_url if vendor_by_id.get(row.vendor_id) else None}
            for row in rows
        ],
    )


# Fetch one subscription by ID.
def get_subscription(subscription_id: int, db: Session) -> dict[str, Any]:
    row = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return _success("Subscription details", _subscription_to_dict(row))


# Build immutable financial snapshot artifact from current live data and store on Pinata.
def create_financial_snapshot(
    current_user: UserProfile,
    payload: SnapshotCreateRequest,
    db: Session,
) -> dict[str, Any]:
    if not current_user.wallet_address:
        raise HTTPException(status_code=400, detail="Current user has no wallet_address configured")

    period_end = _parse_snapshot_datetime(payload.end_date, "end_date") or datetime.now(timezone.utc)
    period_start = _parse_snapshot_datetime(payload.start_date, "start_date")
    if period_start is None:
        days = payload.days if payload.days is not None else settings.SNAPSHOT_DEFAULT_DAYS
        period_start = period_end - timedelta(days=days)
    if period_start > period_end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    wallet_address = current_user.wallet_address
    title = (payload.title or "").strip() or f"Snapshot {period_start.date().isoformat()} to {period_end.date().isoformat()}"

    payment_rows = (
        db.query(Transaction)
        .filter(Transaction.from_address == wallet_address)
        .filter(Transaction.created_at >= period_start)
        .filter(Transaction.created_at <= period_end)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    subscription_rows = (
        db.query(Subscription)
        .filter(Subscription.user_wallet_address == wallet_address)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    sub_ids = [row.id for row in subscription_rows]
    cycle_rows = []
    if sub_ids:
        cycle_rows = (
            db.query(SubscriptionCycle)
            .filter(SubscriptionCycle.subscription_id.in_(sub_ids))
            .filter(SubscriptionCycle.created_at >= period_start)
            .filter(SubscriptionCycle.created_at <= period_end)
            .order_by(SubscriptionCycle.created_at.desc())
            .all()
        )
    history_rows = (
        db.query(HistoryEvent)
        .filter(HistoryEvent.user_wallet_address == wallet_address)
        .filter(HistoryEvent.created_at >= period_start)
        .filter(HistoryEvent.created_at <= period_end)
        .order_by(HistoryEvent.created_at.desc())
        .all()
    )

    one_time_payment_spend_xrp = float(
        sum(
            row.amount_xrp or 0.0
            for row in payment_rows
            if row.tx_type == "payment"
        )
    )
    recurring_subscription_spend_xrp = float(sum(row.escrow_amount_xrp or 0.0 for row in cycle_rows))
    total_spend_xrp = float(one_time_payment_spend_xrp + recurring_subscription_spend_xrp)
    active_subscription_count = sum(1 for row in subscription_rows if row.status in {"active", "non_renewing"})

    artifact = {
        "artifact_type": "financial_snapshot",
        "artifact_version": "v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner": {
            "username": current_user.username,
            "wallet_address": wallet_address,
        },
        "title": title,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "summary": {
            "one_time_payment_spend_xrp": one_time_payment_spend_xrp,
            "recurring_subscription_spend_xrp": recurring_subscription_spend_xrp,
            "total_spend_xrp": total_spend_xrp,
            "active_subscription_count": active_subscription_count,
            "payment_count": len(payment_rows),
            "subscription_event_count": len(cycle_rows),
        },
        "payments": [
            {
                "tx_hash": row.tx_hash,
                "tx_type": row.tx_type,
                "from_address": row.from_address,
                "to_address": row.to_address,
                "amount_xrp": row.amount_xrp,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
            for row in payment_rows
        ],
        "subscriptions": [_subscription_to_dict(row) for row in subscription_rows],
        "subscription_cycles": [_cycle_to_dict(row) for row in cycle_rows],
        "history": [
            {
                "event_type": row.event_type,
                "tx_hash": row.tx_hash,
                "counterparty_address": row.counterparty_address,
                "amount": row.amount,
                "currency": row.currency,
                "status": row.status,
                "note": row.note,
                "created_at": row.created_at.isoformat(),
            }
            for row in history_rows
        ],
    }

    pinata = _upload_snapshot_to_pinata(artifact, title)
    row = Snapshot(
        user_profile_id=current_user.id,
        username=current_user.username,
        wallet_address=wallet_address,
        title=title,
        period_start=period_start,
        period_end=period_end,
        summary_total_subscription_xrp=recurring_subscription_spend_xrp,
        summary_total_one_time_xrp=one_time_payment_spend_xrp,
        summary_total_spend_xrp=total_spend_xrp,
        active_subscription_count=active_subscription_count,
        payment_count=len(payment_rows),
        subscription_event_count=len(cycle_rows),
        pinata_cid=pinata["cid"] or "",
        pinata_file_id=pinata["file_id"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _success(
        "Snapshot created",
        {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at.isoformat(),
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "summary_total_subscription_xrp": row.summary_total_subscription_xrp,
            "summary_total_one_time_xrp": row.summary_total_one_time_xrp,
            "summary_total_spend_xrp": row.summary_total_spend_xrp,
            "active_subscription_count": row.active_subscription_count,
            "payment_count": row.payment_count,
            "subscription_event_count": row.subscription_event_count,
            "pinata_cid": row.pinata_cid,
        },
    )


# List snapshot metadata for current user (DB-only for fast list rendering).
def list_financial_snapshots(current_user: UserProfile, db: Session) -> dict[str, Any]:
    rows = (
        db.query(Snapshot)
        .filter(Snapshot.user_profile_id == current_user.id)
        .order_by(Snapshot.created_at.desc())
        .all()
    )
    return _success(
        "Snapshot list",
        [
            {
                "id": row.id,
                "title": row.title,
                "created_at": row.created_at.isoformat(),
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "summary_total_subscription_xrp": row.summary_total_subscription_xrp,
                "summary_total_one_time_xrp": row.summary_total_one_time_xrp,
                "summary_total_spend_xrp": row.summary_total_spend_xrp,
                "active_subscription_count": row.active_subscription_count,
                "payment_count": row.payment_count,
                "subscription_event_count": row.subscription_event_count,
                "pinata_cid": row.pinata_cid,
            }
            for row in rows
        ],
    )


# Fetch full immutable snapshot artifact from Pinata.
def get_financial_snapshot(snapshot_id: int, current_user: UserProfile, db: Session) -> dict[str, Any]:
    row = (
        db.query(Snapshot)
        .filter(Snapshot.id == snapshot_id)
        .filter(Snapshot.user_profile_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    artifact = _fetch_snapshot_from_pinata(row.pinata_cid, row.pinata_file_id)
    return _success(
        "Snapshot details",
        {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at.isoformat(),
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "summary_total_subscription_xrp": row.summary_total_subscription_xrp,
            "summary_total_one_time_xrp": row.summary_total_one_time_xrp,
            "summary_total_spend_xrp": row.summary_total_spend_xrp,
            "active_subscription_count": row.active_subscription_count,
            "payment_count": row.payment_count,
            "subscription_event_count": row.subscription_event_count,
            "pinata_cid": row.pinata_cid,
            "artifact": artifact,
        },
    )


# Ask Gemini a question grounded only on a fixed snapshot artifact.
def ask_financial_snapshot_question(
    snapshot_id: int,
    payload: SnapshotAskRequest,
    current_user: UserProfile,
    db: Session,
) -> dict[str, Any]:
    row = (
        db.query(Snapshot)
        .filter(Snapshot.id == snapshot_id)
        .filter(Snapshot.user_profile_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    artifact = _fetch_snapshot_from_pinata(row.pinata_cid, row.pinata_file_id)
    answer = _ask_gemini_with_snapshot(artifact, payload.question)
    return _success(
        "Snapshot question answered",
        {
            "snapshot_id": row.id,
            "question": payload.question,
            "answer": answer,
        },
    )


# List billing cycles for a subscription.
def list_subscription_cycles(subscription_id: int, db: Session) -> dict[str, Any]:
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    rows = (
        db.query(SubscriptionCycle)
        .filter(SubscriptionCycle.subscription_id == subscription_id)
        .order_by(SubscriptionCycle.cycle_index.desc())
        .all()
    )
    return _success("Subscription cycles", [_cycle_to_dict(row) for row in rows])


# Create the next billing-cycle escrow for an active auto-renewing subscription.
def process_subscription_cycle(
    subscription_id: int,
    payload: SubscriptionProcessCycleRequest,
    db: Session,
) -> dict[str, Any]:
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if subscription.request_status != "approved":
        raise HTTPException(status_code=409, detail="Subscription is not approved")
    if not subscription.auto_renew:
        raise HTTPException(status_code=409, detail="Subscription is non-renewing; no future cycles can be created")

    profile = db.query(UserProfile).filter(UserProfile.id == subscription.user_profile_id).first()
    if not profile or profile.username != payload.username:
        raise HTTPException(status_code=400, detail="Username does not match subscription")
    user_seed = _get_seed_for_address(db, subscription.user_wallet_address)

    latest_cycle = (
        db.query(SubscriptionCycle)
        .filter(SubscriptionCycle.subscription_id == subscription.id)
        .order_by(SubscriptionCycle.cycle_index.desc())
        .first()
    )
    next_cycle_index = (latest_cycle.cycle_index + 1) if latest_cycle else 1
    period_start = subscription.next_payment_date
    period_end = period_start + timedelta(days=subscription.interval_days)

    cycle_row = _create_subscription_cycle_with_escrow(
        db=db,
        subscription=subscription,
        user_seed=user_seed,
        cycle_index=next_cycle_index,
        period_start=period_start,
        period_end=period_end,
    )
    subscription.next_payment_date = period_end
    subscription.status = "active"
    subscription.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(subscription)

    vendor = db.query(Vendor).filter(Vendor.id == subscription.vendor_id).first()
    if vendor:
        _send_vendor_webhook(
            db,
            vendor,
            "subscription.cycle_created",
            {
                "event": "subscription.cycle_created",
                "subscription_id": subscription.id,
                "vendor_tx_id": subscription.vendor_tx_id,
                "cycle_id": cycle_row.id,
                "cycle_index": cycle_row.cycle_index,
                "period_start": cycle_row.period_start.isoformat(),
                "period_end": cycle_row.period_end.isoformat(),
                "escrow_create_tx_hash": cycle_row.escrow_create_tx_hash,
                "auto_renew": bool(subscription.auto_renew),
            },
        )

    return _success(
        "Subscription cycle created",
        {
            "subscription_id": subscription.id,
            "cycle": _cycle_to_dict(cycle_row),
            "next_payment_date": subscription.next_payment_date.isoformat(),
            "auto_renew": bool(subscription.auto_renew),
            "status": subscription.status,
        },
    )


# Configure monthly spending guard values for a user.
def set_spending_guard(payload: SpendingGuardSetRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not _is_valid_classic_address(payload.user_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid user_wallet_address")

    guard = _get_or_create_spending_guard(db, payload.user_wallet_address, payload.currency)
    if (guard.currency or "").upper() != (payload.currency or "").upper():
        guard.spent_this_month = 0.0
        guard.month_key = _current_month_key()
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
def get_user_history(
    user_wallet_address: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(HistoryEvent)
        .filter(
            or_(
                HistoryEvent.user_wallet_address == user_wallet_address,
                HistoryEvent.counterparty_address == user_wallet_address,
            )
        )
        .order_by(HistoryEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    vendor_by_wallet = {
        row.wallet_address: row.display_name
        for row in db.query(Vendor).all()
    }
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
                "vendor_name": vendor_by_wallet.get(row.counterparty_address),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    )


# Return dashboard aggregates for frontend cards/charts.
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
    vendor_rows = db.query(Vendor).all()
    vendor_by_wallet = {row.wallet_address: row for row in vendor_rows}
    vendor_by_id = {row.id: row for row in vendor_rows}

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
                    "vendor_name": (
                        (vendor_by_id.get(row.vendor_id).display_name if vendor_by_id.get(row.vendor_id) else None)
                        or (vendor_by_wallet.get(row.merchant_wallet_address).display_name if vendor_by_wallet.get(row.merchant_wallet_address) else None)
                    ),
                    "vendor_photo_url": (
                        (vendor_by_id.get(row.vendor_id).vendor_photo_url if vendor_by_id.get(row.vendor_id) else None)
                        or (vendor_by_wallet.get(row.merchant_wallet_address).vendor_photo_url if vendor_by_wallet.get(row.merchant_wallet_address) else None)
                    ),
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


# Aggregate dashboard across all connected wallets for current user.
def get_dashboard_aggregate(current_user: UserProfile, db: Session) -> dict[str, Any]:
    links = _get_user_wallet_links(db, current_user.id)
    if not links:
        return _success(
            "Aggregate dashboard",
            {
                "wallet_count": 0,
                "wallets": [],
                "balance_xrp": 0.0,
                "balance_rlusd": 0.0,
                "locked_in_escrow_xrp": 0.0,
                "monthly_guard": {"currency": "RLUSD", "limit": 0.0, "spent": 0.0, "remaining": 0.0},
                "this_month": {"released": 0.0, "locked": 0.0},
                "upcoming_release": [],
                "recent_activity": [],
            },
        )

    wallet_entries = []
    total_balance_xrp = 0.0
    total_balance_rlusd = 0.0
    total_locked = 0.0
    total_guard_limit = 0.0
    total_guard_spent = 0.0
    total_guard_remaining = 0.0
    total_released = 0.0
    total_locked_month = 0.0
    upcoming_release = []
    recent_activity = []

    for link, wallet_row in links:
        data = get_dashboard(wallet_row.address, db)["data"]
        wallet_entries.append({"link_id": link.id, "nickname": link.nickname, "address": wallet_row.address})
        total_balance_xrp += float(data.get("balance_xrp") or 0.0)
        total_balance_rlusd += float(data.get("balance_rlusd") or 0.0)
        total_locked += float(data.get("locked_in_escrow_xrp") or 0.0)
        guard = data.get("monthly_guard") or {}
        total_guard_limit += float(guard.get("limit") or 0.0)
        total_guard_spent += float(guard.get("spent") or 0.0)
        total_guard_remaining += float(guard.get("remaining") or 0.0)
        month = data.get("this_month") or {}
        total_released += float(month.get("released") or 0.0)
        total_locked_month += float(month.get("locked") or 0.0)
        for row in data.get("upcoming_release") or []:
            enriched = dict(row)
            enriched["wallet_address"] = wallet_row.address
            enriched["wallet_nickname"] = link.nickname
            upcoming_release.append(enriched)
        for row in data.get("recent_activity") or []:
            enriched = dict(row)
            enriched["wallet_address"] = wallet_row.address
            enriched["wallet_nickname"] = link.nickname
            recent_activity.append(enriched)

    upcoming_release.sort(key=lambda r: r.get("next_payment_date") or "")
    recent_activity.sort(key=lambda r: r.get("created_at") or "", reverse=True)

    return _success(
        "Aggregate dashboard",
        {
            "wallet_count": len(wallet_entries),
            "wallets": wallet_entries,
            "balance_xrp": round(total_balance_xrp, 6),
            "balance_rlusd": round(total_balance_rlusd, 6),
            "locked_in_escrow_xrp": round(total_locked, 6),
            "monthly_guard": {
                "currency": "RLUSD",
                "limit": round(total_guard_limit, 6),
                "spent": round(total_guard_spent, 6),
                "remaining": round(total_guard_remaining, 6),
            },
            "this_month": {
                "released": round(total_released, 6),
                "locked": round(total_locked_month, 6),
            },
            "upcoming_release": upcoming_release[:20],
            "recent_activity": recent_activity[:50],
        },
    )
