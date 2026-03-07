from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.transactions import TrustSet
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet as XRPLWallet


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import api as api_module
import db
import main


pytestmark = pytest.mark.integration


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Missing required env var: {name}")
    return value


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[db.get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def test_testnet_escrow_create_finish_cancel_flow(client):
    user_seed = _require_env("TESTNET_USER_SEED")
    merchant_seed = _require_env("TESTNET_MERCHANT_SEED")
    amount_xrp = float(os.getenv("TESTNET_ESCROW_AMOUNT_XRP", "0.00001"))

    user_wallet = XRPLWallet.from_seed(user_seed)
    merchant_wallet = XRPLWallet.from_seed(merchant_seed)

    # 1) Import both wallets into local DB.
    assert client.post("/api/v1/wallets/import", json={"seed": user_seed}).status_code == 200
    assert client.post("/api/v1/wallets/import", json={"seed": merchant_seed}).status_code == 200

    # 2) Create escrow-enabled subscription.
    create_resp = client.post(
        "/api/v1/subscriptions/create",
        json={
            "user_wallet_address": user_wallet.classic_address,
            "merchant_wallet_address": merchant_wallet.classic_address,
            "user_seed": user_seed,
            "amount_xrp": amount_xrp,
            "interval_days": 1,
            "use_escrow": True,
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    sub_id = create_resp.json()["data"]["id"]

    # 3) Handshake approvals should trigger first escrow lock.
    user_approve_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/handshake/user-approve",
        json={"user_seed": user_seed},
    )
    assert user_approve_resp.status_code == 200, user_approve_resp.text

    service_approve_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/handshake/service-approve",
        json={"merchant_seed": merchant_seed},
    )
    assert service_approve_resp.status_code == 200, service_approve_resp.text

    sub_after_handshake = client.get(f"/api/v1/subscriptions/{sub_id}")
    assert sub_after_handshake.status_code == 200
    sub_data = sub_after_handshake.json()["data"]
    assert sub_data["status"] == "active"
    assert sub_data["handshake_status"] == "completed"
    assert sub_data["escrow_status"] == "locked"
    assert sub_data["escrow_offer_sequence"] is not None

    # 4) Process should finish current escrow and lock next cycle.
    process_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/process",
        json={"merchant_seed": merchant_seed},
    )
    assert process_resp.status_code == 200, process_resp.text
    process_data = process_resp.json()["data"]
    assert process_data["last_tx_hash"]

    # 5) Cancel should cancel any active lock and mark subscription cancelled.
    cancel_resp = client.post(f"/api/v1/subscriptions/{sub_id}/cancel")
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["data"]["status"] == "cancelled"


def test_testnet_rlusd_trustline_and_payment_flow(client):
    sender_seed = _require_env("TESTNET_RLUSD_SENDER_SEED")
    receiver_seed = _require_env("TESTNET_RLUSD_RECEIVER_SEED")
    issuer = _require_env("TESTNET_RLUSD_ISSUER")
    currency = os.getenv("TESTNET_RLUSD_CURRENCY", "RLUSD")
    amount = float(os.getenv("TESTNET_RLUSD_AMOUNT", "0.01"))

    # Point API settings at provided issuer/currency for this test run.
    object.__setattr__(api_module.settings, "RLUSD_ISSUER", issuer)
    object.__setattr__(api_module.settings, "RLUSD_CURRENCY", currency)

    sender_wallet = XRPLWallet.from_seed(sender_seed)
    receiver_wallet = XRPLWallet.from_seed(receiver_seed)

    assert client.post("/api/v1/wallets/import", json={"seed": sender_seed}).status_code == 200
    assert client.post("/api/v1/wallets/import", json={"seed": receiver_seed}).status_code == 200

    # Ensure receiver trust line exists for RLUSD issuer.
    xrpl_client = JsonRpcClient(api_module.settings.XRPL_RPC_URL)
    trust_tx = TrustSet(
        account=receiver_wallet.classic_address,
        limit_amount=IssuedCurrencyAmount(
            currency=currency,
            issuer=issuer,
            value="1000000",
        ),
    )
    trust_resp = submit_and_wait(trust_tx, xrpl_client, receiver_wallet)
    trust_result = trust_resp.result.get("meta", {}).get("TransactionResult")
    assert trust_result and trust_result.startswith("tes"), trust_resp.result

    # Send RLUSD through API.
    send_resp = client.post(
        "/api/v1/payments/send-rlusd",
        json={
            "sender_seed": sender_seed,
            "destination_address": receiver_wallet.classic_address,
            "amount": amount,
        },
    )
    assert send_resp.status_code == 200, send_resp.text
    send_data = send_resp.json()["data"]
    assert send_data["tx_hash"]
    assert send_data["currency"] == currency

    # Confirm API balance payload includes RLUSD fields.
    balance_resp = client.get(f"/api/v1/wallets/{receiver_wallet.classic_address}/balance")
    assert balance_resp.status_code == 200, balance_resp.text
    balance_data = balance_resp.json()["data"]
    assert "rlusd_balance" in balance_data
    assert balance_data["rlusd_issuer"] == issuer
