from __future__ import annotations

import os
from pathlib import Path
import sys

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

import core as api_module
import db
from schemas import (
    RlusdPaymentSendRequest,
    SubscriptionApproveRequest,
    SubscriptionCancelRequest,
    SubscriptionProcessCycleRequest,
    SubscriptionRequestCreateRequest,
    UserProfileRegisterRequest,
    VendorCreateRequest,
    WalletImportRequest,
)


pytestmark = pytest.mark.integration


class DummyRequest:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Missing required env var: {name}")
    return value


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.Base.metadata.create_all(bind=engine)
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_testnet_escrow_create_and_cancel_flow(session):
    user_seed = _require_env("TESTNET_USER_SEED")
    merchant_seed = _require_env("TESTNET_MERCHANT_SEED")
    amount_xrp = float(os.getenv("TESTNET_ESCROW_AMOUNT_XRP", "0.00001"))

    user_wallet = XRPLWallet.from_seed(user_seed)
    merchant_wallet = XRPLWallet.from_seed(merchant_seed)

    api_module.import_wallet(WalletImportRequest(seed=user_seed), session)
    api_module.import_wallet(WalletImportRequest(seed=merchant_seed), session)

    api_module.register_user_profile(
        UserProfileRegisterRequest(
            username="integration_user",
            wallet_address=user_wallet.classic_address,
        ),
        session,
    )

    vendor_key = "integration-vendor-key"
    api_module.upsert_vendor(
        VendorCreateRequest(
            vendor_code="integration_vendor",
            display_name="Integration Vendor",
            wallet_address=merchant_wallet.classic_address,
            shared_secret=vendor_key,
        ),
        session,
    )

    req_resp = api_module.create_subscription_request(
        DummyRequest(headers={"X-Vendor-Secret": vendor_key}),
        SubscriptionRequestCreateRequest(
            vendor_tx_id="INT-TX-1",
            username="integration_user",
            amount_xrp=amount_xrp,
            interval_days=1,
        ),
        session,
    )
    sub_id = req_resp["data"]["subscription_id"]

    approve_resp = api_module.approve_subscription_request(
        sub_id,
        SubscriptionApproveRequest(username="integration_user", user_seed=user_seed),
        session,
    )
    assert approve_resp["data"]["status"] == "active"

    process_resp = api_module.process_subscription_cycle(
        sub_id,
        SubscriptionProcessCycleRequest(username="integration_user", user_seed=user_seed),
        session,
    )
    assert process_resp["data"]["cycle"]["cycle_index"] == 2

    sub_data = api_module.get_subscription(sub_id, session)["data"]
    assert sub_data["escrow_status"] == "locked"
    assert sub_data["escrow_offer_sequence"] is not None
    assert sub_data["auto_renew"] is True

    cancel_resp = api_module.cancel_subscription_request(
        sub_id,
        DummyRequest(),
        SubscriptionCancelRequest(username="integration_user", user_seed=user_seed),
        session,
    )
    assert cancel_resp["data"]["status"] == "non_renewing"
    assert cancel_resp["data"]["auto_renew"] is False


def test_testnet_rlusd_trustline_and_payment_flow(session):
    sender_seed = _require_env("TESTNET_RLUSD_SENDER_SEED")
    receiver_seed = _require_env("TESTNET_RLUSD_RECEIVER_SEED")
    issuer = _require_env("TESTNET_RLUSD_ISSUER")
    currency = os.getenv("TESTNET_RLUSD_CURRENCY", "RLUSD")
    amount = float(os.getenv("TESTNET_RLUSD_AMOUNT", "0.01"))

    object.__setattr__(api_module.settings, "RLUSD_ISSUER", issuer)
    object.__setattr__(api_module.settings, "RLUSD_CURRENCY", currency)

    sender_wallet = XRPLWallet.from_seed(sender_seed)
    receiver_wallet = XRPLWallet.from_seed(receiver_seed)

    api_module.import_wallet(WalletImportRequest(seed=sender_seed), session)
    api_module.import_wallet(WalletImportRequest(seed=receiver_seed), session)

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

    send_resp = api_module.send_rlusd_payment(
        RlusdPaymentSendRequest(
            sender_seed=sender_seed,
            destination_address=receiver_wallet.classic_address,
            amount=amount,
        ),
        session,
    )
    assert send_resp["data"]["tx_hash"]
    assert send_resp["data"]["currency"] == currency

    balance_data = api_module.get_wallet_balance(receiver_wallet.classic_address)["data"]
    assert "rlusd_balance" in balance_data
    assert balance_data["rlusd_issuer"] == issuer
