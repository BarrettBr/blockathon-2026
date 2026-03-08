from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from config import settings
from handlers.auth import create_access_token, get_current_user, hash_password, login, verify_password

import core as api_module
import db
from db import UserProfile
from db import Wallet as WalletModel
from schemas import (
    PaymentSendRequest,
    RlusdPaymentSendRequest,
    SnapshotAskRequest,
    SnapshotCreateRequest,
    SubscriptionApproveRequest,
    SubscriptionCancelRequest,
    SubscriptionProcessCycleRequest,
    SubscriptionRequestCreateRequest,
    UserProfileRegisterRequest,
    VendorCreateRequest,
    WalletImportRequest,
)


class DummyRequest:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_health_ok(monkeypatch):
    class DummyClient:
        def request(self, _req):
            return SimpleNamespace(result={"ok": True})

    monkeypatch.setattr(api_module, "_get_xrpl_client", lambda: DummyClient())
    response = api_module.health()
    assert response["data"]["status"] == "ok"
    assert response["data"]["xrpl_ready"] is True


def test_wallet_import_and_list(monkeypatch):
    session = _session()
    monkeypatch.setattr(
        api_module,
        "_wallet_from_seed",
        lambda _seed: SimpleNamespace(classic_address="rTESTUSER1111111111111111111111111"),
    )

    import_resp = api_module.import_wallet(WalletImportRequest(seed="seed-user-001"), session)
    assert import_resp["data"]["address"] == "rTESTUSER1111111111111111111111111"

    list_resp = api_module.list_wallets(session)
    assert len(list_resp["data"]) == 1


def test_subscription_vendor_request_approve_cancel_flow(monkeypatch):
    session = _session()

    user_address = "rUSER111111111111111111111111111111"
    vendor_address = "rVENDOR111111111111111111111111111"

    def fake_wallet_from_seed(seed: str):
        mapping = {
            "user-seed-123": user_address,
        }
        if seed not in mapping:
            raise ValueError("unknown seed")
        return SimpleNamespace(classic_address=mapping[seed])

    def fake_create_cycle(**kwargs):
        db_session = kwargs["db"]
        subscription = kwargs["subscription"]
        cycle_index = kwargs["cycle_index"]
        period_start = kwargs["period_start"]
        period_end = kwargs["period_end"]
        cycle = db.SubscriptionCycle(
            subscription_id=subscription.id,
            cycle_index=cycle_index,
            period_start=period_start,
            period_end=period_end,
            status="locked",
            escrow_amount_xrp=subscription.amount_xrp,
            escrow_offer_sequence=999 + cycle_index,
            escrow_create_tx_hash=f"ESCROW-LOCK-{cycle_index}",
            escrow_cancel_after=12345 + cycle_index,
        )
        db_session.add(cycle)
        subscription.escrow_status = "locked"
        subscription.escrow_offer_sequence = cycle.escrow_offer_sequence
        subscription.escrow_create_tx_hash = cycle.escrow_create_tx_hash
        subscription.escrow_amount_xrp = subscription.amount_xrp
        subscription.last_tx_hash = cycle.escrow_create_tx_hash
        db_session.commit()
        db_session.refresh(cycle)
        db_session.refresh(subscription)
        return cycle

    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(api_module, "_wallet_from_seed", fake_wallet_from_seed)
    monkeypatch.setattr(api_module, "_create_subscription_cycle_with_escrow", fake_create_cycle)

    api_module.register_user_profile(
        UserProfileRegisterRequest(username="alice", wallet_address=user_address),
        session,
    )

    session.add(WalletModel(address=user_address, seed="user-seed-123", network="testnet"))
    session.commit()
    api_module.upsert_vendor(
        VendorCreateRequest(
            vendor_code="spotify",
            display_name="Spotify",
            wallet_address=vendor_address,
            shared_secret="vendor-secret-123",
        ),
        session,
    )

    req_resp = api_module.create_subscription_request(
        DummyRequest(headers={"X-Vendor-Secret": "vendor-secret-123"}),
        SubscriptionRequestCreateRequest(
            vendor_tx_id="VTX-001",
            username="alice",
            amount_xrp=1.5,
            interval_days=30,
        ),
        session,
    )
    sub_id = req_resp["data"]["subscription_id"]
    contract_hash = req_resp["data"]["contract_hash"]
    webhook_rows = session.query(db.WebhookDelivery).all()
    assert len(webhook_rows) == 1
    assert webhook_rows[0].event_type == "subscription.requested"

    pending_resp = api_module.list_pending_subscription_requests("alice", session)
    assert len(pending_resp["data"]) == 1

    approve_resp = api_module.approve_subscription_request(
        sub_id,
        SubscriptionApproveRequest(username="alice", user_seed="user-seed-123"),
        session,
    )
    assert approve_resp["data"]["request_status"] == "approved"
    assert approve_resp["data"]["escrow_create_tx_hash"] == "ESCROW-LOCK-1"

    lookup_resp = api_module.get_subscription_by_contract(contract_hash, session)
    assert lookup_resp["data"]["contract_hash"] == contract_hash

    process_resp = api_module.process_subscription_cycle(
        sub_id,
        SubscriptionProcessCycleRequest(username="alice", user_seed="user-seed-123"),
        session,
    )
    assert process_resp["data"]["cycle"]["cycle_index"] == 2

    cancel_resp = api_module.cancel_subscription_request(
        sub_id,
        DummyRequest(),
        SubscriptionCancelRequest(username="alice", user_seed="user-seed-123"),
        session,
    )
    assert cancel_resp["data"]["status"] == "non_renewing"
    assert cancel_resp["data"]["auto_renew"] is False
    with pytest.raises(HTTPException) as non_renewing_err:
        api_module.process_subscription_cycle(
            sub_id,
            SubscriptionProcessCycleRequest(username="alice", user_seed="user-seed-123"),
            session,
        )
    assert non_renewing_err.value.status_code == 409

    cycles = api_module.list_subscription_cycles(sub_id, session)
    assert len(cycles["data"]) == 2
    assert session.query(db.WebhookDelivery).count() >= 3


def test_vendor_profile_and_secret_rotation(monkeypatch):
    session = _session()
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)

    created = api_module.upsert_vendor(
        VendorCreateRequest(
            vendor_code="acme",
            display_name="Acme Inc.",
            wallet_address="rACME1111111111111111111111111111",
            webhook_url="https://example.com/webhook",
            shared_secret="secret-1",
        ),
        session,
    )
    assert created["data"]["shared_secret"] == "secret-1"

    profile = api_module.get_vendor_me(DummyRequest(headers={"X-Vendor-Secret": "secret-1"}), session)
    assert profile["data"]["vendor_code"] == "acme"

    rotated = api_module.regenerate_vendor_secret(
        DummyRequest(headers={"X-Vendor-Secret": "secret-1"}),
        session,
    )
    assert rotated["data"]["shared_secret"] != "secret-1"


def test_subscription_request_duplicate_and_vendor_auth_errors(monkeypatch):
    session = _session()
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)

    api_module.register_user_profile(
        UserProfileRegisterRequest(
            username="bob",
            wallet_address="rBOB111111111111111111111111111111",
        ),
        session,
    )
    api_module.upsert_vendor(
        VendorCreateRequest(
            vendor_code="netflix",
            display_name="Netflix",
            wallet_address="rVEND2222222222222222222222222222",
            shared_secret="vendor-secret-456",
        ),
        session,
    )

    with pytest.raises(HTTPException) as bad_auth:
        api_module.create_subscription_request(
            DummyRequest(headers={"X-Vendor-Secret": "wrong-key"}),
            SubscriptionRequestCreateRequest(
                vendor_tx_id="VTX-001",
                username="bob",
                amount_xrp=2.0,
                interval_days=30,
            ),
            session,
        )
    assert bad_auth.value.status_code == 401

    api_module.create_subscription_request(
        DummyRequest(headers={"X-Vendor-Secret": "vendor-secret-456"}),
        SubscriptionRequestCreateRequest(
            vendor_tx_id="VTX-001",
            username="bob",
            amount_xrp=2.0,
            interval_days=30,
        ),
        session,
    )

    with pytest.raises(HTTPException) as dup:
        api_module.create_subscription_request(
            DummyRequest(headers={"X-Vendor-Secret": "vendor-secret-456"}),
            SubscriptionRequestCreateRequest(
                vendor_tx_id="VTX-001",
                username="bob",
                amount_xrp=2.0,
                interval_days=30,
            ),
            session,
        )
    assert dup.value.status_code == 409


def test_send_payment_records_transaction(monkeypatch):
    session = _session()
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(api_module, "_get_seed_for_address", lambda db, address: "seed-pay-123")
    monkeypatch.setattr(
        api_module,
        "_send_xrp_payment",
        lambda **kwargs: {
            "tx_hash": "TX-PAY-1",
            "status": "tesSUCCESS",
            "tx_type": "payment",
            "from_address": "rSRC1111111111111111111111111111",
            "to_address": kwargs["destination_address"],
            "validated": True,
            "ledger_index": 999,
            "raw_result": {"hash": "TX-PAY-1"},
        },
    )

    send_resp = api_module.send_payment(
        PaymentSendRequest(
            from_address="rSRC1111111111111111111111111111",
            destination_address="rDST1111111111111111111111111111",
            amount_xrp=2.0,
        ),
        session,
    )
    assert send_resp["data"]["tx_hash"] == "TX-PAY-1"

    list_resp = api_module.list_payments(session)
    assert any(row["tx_hash"] == "TX-PAY-1" for row in list_resp["data"])

def test_send_xrp_payment_surfaces_non_success_status(monkeypatch):
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(
        api_module,
        "_wallet_from_seed",
        lambda _seed: SimpleNamespace(classic_address="rSRC1111111111111111111111111111"),
    )
    monkeypatch.setattr(api_module, "_get_xrpl_client", lambda: SimpleNamespace())
    monkeypatch.setattr(
        api_module,
        "submit_and_wait",
        lambda *_args, **_kwargs: SimpleNamespace(
            result={
                "hash": "TX-FAIL-1",
                "meta": {"TransactionResult": "tecUNFUNDED_PAYMENT"},
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        api_module._send_xrp_payment(
            sender_seed="seed-123",
            destination_address="rDST1111111111111111111111111111",
            amount_xrp=1.0,
        )
    assert exc.value.status_code == 400
    assert "tecUNFUNDED_PAYMENT" in exc.value.detail


def test_send_issued_payment_surfaces_path_dry(monkeypatch):
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(
        api_module,
        "_wallet_from_seed",
        lambda _seed: SimpleNamespace(classic_address="rSRC1111111111111111111111111111"),
    )
    monkeypatch.setattr(api_module, "_get_xrpl_client", lambda: SimpleNamespace())
    monkeypatch.setattr(
        api_module,
        "submit_and_wait",
        lambda *_args, **_kwargs: SimpleNamespace(
            result={
                "hash": "TX-FAIL-2",
                "meta": {"TransactionResult": "tecPATH_DRY"},
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        api_module._send_issued_payment(
            sender_seed="seed-123",
            destination_address="rDST1111111111111111111111111111",
            amount=10,
            currency="RLUSD",
            issuer="rISSUER1111111111111111111111111111",
            tx_type="payment_rlusd",
        )
    assert exc.value.status_code == 400
    assert "tecPATH_DRY" in exc.value.detail


def test_send_rlusd_payment_endpoint(monkeypatch):
    session = _session()
    monkeypatch.setattr(
        api_module,
        "_send_issued_payment",
        lambda **kwargs: {
            "tx_hash": "TX-RLUSD-1",
            "status": "tesSUCCESS",
            "tx_type": "payment_rlusd",
            "from_address": "rSRCRLUSD111111111111111111111111",
            "to_address": kwargs["destination_address"],
            "validated": True,
            "ledger_index": 101,
            "raw_result": {"hash": "TX-RLUSD-1"},
        },
    )
    monkeypatch.setattr(api_module, "_get_seed_for_address", lambda db, address: "seed-rlusd-1")
    monkeypatch.setattr(api_module, "_get_seed_for_address", lambda db, address: "seed-rlusd-1")
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)

    resp = api_module.send_rlusd_payment(
        RlusdPaymentSendRequest(
            from_address="rSRCRLUSD111111111111111111111111",
            destination_address="rDSTRLUSD111111111111111111111111",
            amount=9.99,
        ),
        session,
    )
    assert resp["data"]["tx_hash"] == "TX-RLUSD-1"
    assert resp["data"]["currency"] == api_module.settings.RLUSD_CURRENCY


def test_snapshot_create_list_get_ask(monkeypatch):
    session = _session()
    user = db.UserProfile(username="snapuser", wallet_address="rSNAP111111111111111111111111111111")
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(
        db.Transaction(
            tx_hash="TX-SNAP-1",
            tx_type="payment",
            from_address=user.wallet_address,
            to_address="rDEST1111111111111111111111111111",
            amount_xrp=12.5,
            status="tesSUCCESS",
        )
    )
    session.add(
        db.Vendor(
            vendor_code="snap-vendor",
            display_name="Snap Vendor",
            wallet_address="rMERCHANT111111111111111111111111",
            shared_secret="snap-secret",
            is_active=True,
        )
    )
    session.commit()
    vendor = session.query(db.Vendor).first()

    session.add(
        db.Subscription(
            vendor_id=vendor.id,
            user_profile_id=user.id,
            vendor_tx_id="VTX-SNAP-1",
            user_wallet_address=user.wallet_address,
            merchant_wallet_address="rMERCHANT111111111111111111111111",
            amount_xrp=3.0,
            interval_days=30,
            status="active",
            request_status="approved",
            contract_signature="sig",
            contract_hash="hash",
            contract_alg="HMAC-SHA256",
            contract_version="v1",
            start_date=api_module.date.today(),
            next_payment_date=api_module.date.today(),
            auto_renew=True,
        )
    )
    session.commit()
    sub = session.query(db.Subscription).first()
    session.add(
        db.SubscriptionCycle(
            subscription_id=sub.id,
            cycle_index=1,
            period_start=api_module.date.today(),
            period_end=api_module.date.today(),
            status="locked",
            escrow_amount_xrp=3.0,
            escrow_create_tx_hash="ESCROW-SNAP-1",
        )
    )
    session.add(
        db.HistoryEvent(
            user_wallet_address=user.wallet_address,
            event_type="subscription_cycle_escrow_lock",
            tx_hash="ESCROW-SNAP-1",
            amount=3.0,
            currency="XRP",
            status="tesSUCCESS",
        )
    )
    session.commit()

    monkeypatch.setattr(
        api_module,
        "_upload_snapshot_to_pinata",
        lambda snapshot_json, _title: {"cid": "bafy-snapshot-cid", "file_id": "file-1"},
    )
    monkeypatch.setattr(
        api_module,
        "_fetch_snapshot_from_pinata",
        lambda _cid: {"artifact_type": "financial_snapshot", "summary": {"total_spend_xrp": 15.5}},
    )
    monkeypatch.setattr(
        api_module,
        "_ask_gemini_with_snapshot",
        lambda _snapshot_json, question: f"Answer for: {question}",
    )

    create_resp = api_module.create_financial_snapshot(
        user,
        SnapshotCreateRequest(title="March Snapshot", days=30),
        session,
    )
    snapshot_id = create_resp["data"]["id"]
    assert create_resp["data"]["pinata_cid"] == "bafy-snapshot-cid"

    list_resp = api_module.list_financial_snapshots(user, session)
    assert len(list_resp["data"]) == 1
    assert list_resp["data"][0]["id"] == snapshot_id

    get_resp = api_module.get_financial_snapshot(snapshot_id, user, session)
    assert get_resp["data"]["artifact"]["artifact_type"] == "financial_snapshot"

    ask_resp = api_module.ask_financial_snapshot_question(
        snapshot_id,
        SnapshotAskRequest(question="How much is recurring?"),
        user,
        session,
    )
    assert "How much is recurring?" in ask_resp["data"]["answer"]



def _make_form(username: str, password: str):
    class FormData:
        pass
    form = FormData()
    form.username = username
    form.password = password
    return form


def test_hash_password_is_not_plaintext():
    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    assert verify_password("correcthorse", hash_password("correcthorse")) is True


def test_verify_password_wrong():
    assert verify_password("wrongpassword", hash_password("correcthorse")) is False


def test_create_access_token_contains_subject():
    token = create_access_token({"sub": "alice"})
    # decode via the same function chain — just check login round-trip below
    assert isinstance(token, str)
    assert len(token) > 0


def test_login_returns_token():
    session = _session()
    session.add(UserProfile(
        username="loginuser",
        wallet_address="rLOGIN111111111111111111111111111",
        hashed_password=hash_password("password123"),
    ))
    session.commit()

    result = login(form_data=_make_form("loginuser", "password123"), db=session)
    assert "access_token" in result
    assert result["token_type"] == "bearer"


def test_login_wrong_password():
    session = _session()
    session.add(UserProfile(
        username="loginuser2",
        wallet_address="rLOGIN222222222222222222222222222",
        hashed_password=hash_password("correctpassword"),
    ))
    session.commit()

    with pytest.raises(HTTPException) as exc:
        login(form_data=_make_form("loginuser2", "wrongpassword"), db=session)
    assert exc.value.status_code == 401


def test_login_unknown_user():
    session = _session()
    with pytest.raises(HTTPException) as exc:
        login(form_data=_make_form("nobody", "doesntmatter"), db=session)
    assert exc.value.status_code == 401


def test_login_user_without_password():
    session = _session()
    session.add(UserProfile(
        username="nopwduser",
        wallet_address="rNOPWD11111111111111111111111111",
        hashed_password=None,
    ))
    session.commit()

    with pytest.raises(HTTPException) as exc:
        login(form_data=_make_form("nopwduser", "anything"), db=session)
    assert exc.value.status_code == 401


def test_get_current_user_valid_token():
    session = _session()
    session.add(UserProfile(
        username="tokenuser",
        wallet_address="rTOKEN11111111111111111111111111",
        hashed_password=hash_password("pw"),
    ))
    session.commit()

    token = create_access_token({"sub": "tokenuser"})
    result = get_current_user(token=token, db=session)
    assert result.username == "tokenuser"


def test_get_current_user_invalid_token():
    session = _session()
    with pytest.raises(HTTPException) as exc:
        get_current_user(token="not.a.valid.token", db=session)
    assert exc.value.status_code == 401


def test_get_current_user_unknown_user():
    session = _session()
    token = create_access_token({"sub": "ghost"})
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=token, db=session)
    assert exc.value.status_code == 401
