from __future__ import annotations

from itertools import count
from pathlib import Path
from types import SimpleNamespace
import sys

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import api as api_module
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


def test_subscription_handshake_and_process_flow(client, monkeypatch):
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

    monkeypatch.setattr(api_module, "_is_valid_classic_address", lambda _address: True)
    monkeypatch.setattr(api_module, "_wallet_from_seed", fake_wallet_from_seed)
    monkeypatch.setattr(api_module, "_send_xrp_payment", fake_send_payment)

    create_resp = client.post(
        "/api/v1/subscriptions/create",
        json={
            "user_wallet_address": user_address,
            "merchant_wallet_address": merchant_address,
            "user_seed": "user-seed-123",
            "amount_xrp": 1.5,
            "interval_days": 30,
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

    process_resp = client.post(f"/api/v1/subscriptions/{sub_id}/process")
    assert process_resp.status_code == 200
    assert process_resp.json()["data"]["last_tx_hash"] == "TX-3"

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
