from __future__ import annotations

from itertools import count
from pathlib import Path
from types import SimpleNamespace
import sys

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import core as api_module
import db
import main


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


def test_health_ok(client, monkeypatch):
    class DummyClient:
        def request(self, _req):
            return SimpleNamespace(result={"ok": True})

    monkeypatch.setattr(api_module, "_get_xrpl_client", lambda: DummyClient())

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "ok"
    assert payload["xrpl_ready"] is True


def test_cors_preflight_wallet_import(client):
    response = client.options(
        "/api/v1/wallets/import",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_wallet_import_and_list(client, monkeypatch):
    monkeypatch.setattr(
        api_module,
        "_wallet_from_seed",
        lambda _seed: SimpleNamespace(classic_address="rTESTUSER1111111111111111111111111"),
    )

    import_resp = client.post("/api/v1/wallets/import", json={"seed": "seed-user-001"})
    assert import_resp.status_code == 200
    assert import_resp.json()["data"]["address"] == "rTESTUSER1111111111111111111111111"

    list_resp = client.get("/api/v1/wallets")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1


def test_wallet_balance_uses_issuer_fallback_when_config_mismatch(client, monkeypatch):
    class DummyClient:
        def request(self, req):
            req_name = req.__class__.__name__
            if req_name == "AccountInfo":
                return SimpleNamespace(
                    result={"account_data": {"Balance": "1000000"}, "ledger_index": 123}
                )
            if req_name == "AccountLines":
                return SimpleNamespace(
                    result={
                        "lines": [
                            {"currency": "RLUSD", "account": "rACTUALISSUER111", "balance": "42.5"}
                        ]
                    }
                )
            return SimpleNamespace(result={})

    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(api_module, "_get_xrpl_client", lambda: DummyClient())

    original_issuer = api_module.settings.RLUSD_ISSUER
    object.__setattr__(api_module.settings, "RLUSD_ISSUER", "rMISCONFIGUREDISSUER")
    try:
        response = client.get("/api/v1/wallets/rTESTUSER1111111111111111111111111/balance")
    finally:
        object.__setattr__(api_module.settings, "RLUSD_ISSUER", original_issuer)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["rlusd_balance"] == 42.5
    assert payload["rlusd_match_mode"] == "issuer_fallback"
    assert payload["issued_balances"][0]["currency"] == "RLUSD"


def test_subscription_handshake_escrow_and_process_flow(client, monkeypatch):
    user_address = "rUSER111111111111111111111111111111"
    merchant_address = "rMERCHANT11111111111111111111111111"

    def fake_wallet_from_seed(seed: str):
        mapping = {
            "user-seed-123": user_address,
            "merchant-seed-123": merchant_address,
        }
        if seed not in mapping:
            raise ValueError("unknown seed")
        return SimpleNamespace(classic_address=mapping[seed])

    tx_counter = count(1)

    def fake_send_payment(sender_seed, destination_address, amount_xrp, tx_type="payment", memo_text=None):
        idx = next(tx_counter)
        sender_address = fake_wallet_from_seed(sender_seed).classic_address
        return {
            "tx_hash": f"TX-{idx}",
            "status": "tesSUCCESS",
            "tx_type": tx_type,
            "from_address": sender_address,
            "to_address": destination_address,
            "validated": True,
            "ledger_index": 1000 + idx,
            "raw_result": {"hash": f"TX-{idx}"},
        }

    def fake_lock_escrow(db_session, sub_row):
        sub_row.escrow_status = "locked"
        sub_row.escrow_offer_sequence = 999
        sub_row.escrow_create_tx_hash = "ESCROW-LOCK-1"
        sub_row.escrow_amount_xrp = sub_row.amount_xrp
        db_session.commit()
        db_session.refresh(sub_row)
        return {"tx_hash": "ESCROW-LOCK-1", "offer_sequence": 999, "status": "tesSUCCESS"}

    def fake_finish_escrow(db_session, sub_row, _merchant_seed):
        sub_row.last_tx_hash = "ESCROW-FINISH-1"
        sub_row.escrow_status = "released"
        db_session.commit()
        db_session.refresh(sub_row)
        return {"tx_hash": "ESCROW-FINISH-1", "status": "tesSUCCESS"}

    def fake_cancel_escrow(db_session, sub_row):
        sub_row.escrow_status = "cancelled"
        db_session.commit()
        db_session.refresh(sub_row)
        return {"tx_hash": "ESCROW-CANCEL-1", "status": "tesSUCCESS"}

    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(api_module, "_wallet_from_seed", fake_wallet_from_seed)
    monkeypatch.setattr(api_module, "_send_xrp_payment", fake_send_payment)
    monkeypatch.setattr(api_module, "_lock_subscription_escrow", fake_lock_escrow)
    monkeypatch.setattr(api_module, "_finish_subscription_escrow", fake_finish_escrow)
    monkeypatch.setattr(api_module, "_cancel_subscription_escrow", fake_cancel_escrow)

    create_resp = client.post(
        "/api/v1/subscriptions/create",
        json={
            "user_wallet_address": user_address,
            "merchant_wallet_address": merchant_address,
            "user_seed": "user-seed-123",
            "amount_xrp": 1.5,
            "interval_days": 30,
            "use_escrow": True,
        },
    )
    assert create_resp.status_code == 200
    sub_id = create_resp.json()["data"]["id"]

    blocked_resp = client.post(f"/api/v1/subscriptions/{sub_id}/process")
    assert blocked_resp.status_code == 409

    user_approve_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/handshake/user-approve",
        json={"user_seed": "user-seed-123"},
    )
    assert user_approve_resp.status_code == 200
    assert user_approve_resp.json()["data"]["user_approval_tx_hash"] == "TX-1"

    service_approve_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/handshake/service-approve",
        json={"merchant_seed": "merchant-seed-123"},
    )
    assert service_approve_resp.status_code == 200
    assert service_approve_resp.json()["data"]["service_approval_tx_hash"] == "TX-2"

    process_resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/process",
        json={"merchant_seed": "merchant-seed-123"},
    )
    assert process_resp.status_code == 200
    assert process_resp.json()["data"]["last_tx_hash"] == "ESCROW-FINISH-1"

    cancel_resp = client.post(f"/api/v1/subscriptions/{sub_id}/cancel")
    assert cancel_resp.status_code == 200

    blocked_after_cancel = client.post(f"/api/v1/subscriptions/{sub_id}/process")
    assert blocked_after_cancel.status_code == 409


def test_send_payment_records_transaction(client, monkeypatch):
    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
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

    send_resp = client.post(
        "/api/v1/payments/send",
        json={
            "sender_seed": "seed-pay-123",
            "destination_address": "rDST1111111111111111111111111111",
            "amount_xrp": 2.0,
        },
    )
    assert send_resp.status_code == 200
    assert send_resp.json()["data"]["tx_hash"] == "TX-PAY-1"

    list_resp = client.get("/api/v1/payments")
    assert list_resp.status_code == 200
    assert any(row["tx_hash"] == "TX-PAY-1" for row in list_resp.json()["data"])


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


def test_dashboard_spending_guard_and_history(client, monkeypatch):
    user_address = "rDASHUSER11111111111111111111111111"

    class DummyClient:
        def request(self, req):
            req_name = req.__class__.__name__
            if req_name == "AccountInfo":
                return SimpleNamespace(result={"account_data": {"Balance": "2000000"}, "ledger_index": 1})
            if req_name == "AccountLines":
                return SimpleNamespace(result={"lines": []})
            return SimpleNamespace(result={})

    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(api_module, "_get_xrpl_client", lambda: DummyClient())

    guard_resp = client.post(
        "/api/v1/spending-guard/set",
        json={
            "user_wallet_address": user_address,
            "monthly_limit": 500.0,
            "currency": "RLUSD",
        },
    )
    assert guard_resp.status_code == 200

    history_resp = client.get(f"/api/v1/history/{user_address}")
    assert history_resp.status_code == 200

    dashboard_resp = client.get(f"/api/v1/dashboard/{user_address}")
    assert dashboard_resp.status_code == 200
    data = dashboard_resp.json()["data"]
    assert data["wallet"] == user_address
    assert "monthly_guard" in data
    assert "recent_activity" in data


def test_send_rlusd_payment_endpoint(client, monkeypatch):
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

    resp = client.post(
        "/api/v1/payments/send-rlusd",
        json={
            "sender_seed": "seed-rlusd-1",
            "destination_address": "rDSTRLUSD111111111111111111111111",
            "amount": 9.99,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["tx_hash"] == "TX-RLUSD-1"
    assert resp.json()["data"]["currency"] == api_module.settings.RLUSD_CURRENCY
