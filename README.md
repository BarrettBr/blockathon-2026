# EquiPay Backend MVP

Hackathon-ready FastAPI backend for XRPL Testnet using:
- Python 3.10+
- FastAPI
- SQLite + SQLAlchemy
- xrpl-py

This project is intentionally simple and monolithic:
- `src/backend/api/main.py`
- `src/backend/api/config.py`
- `src/backend/api/db.py`
- `src/backend/api/api.py`

Detailed request/response interaction docs:
- [docs/API_INTERACTION_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/API_INTERACTION_GUIDE.md)
- [docs/FRONTEND_USECASE_FLOW.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/FRONTEND_USECASE_FLOW.md)

## Important Hackathon Caveat
Wallet seeds are stored in plaintext in SQLite for demo speed.
This is **not production-safe**.

## Alignment With Project Vision
Current backend is close on core flows:
- Wallet creation/import, balance checks, and payment sending are live on XRPL Testnet.
- Subscriptions now use an explicit two-party handshake model before recurring processing.
- Handshake approvals are recorded on-chain as XRP transactions with terms-hash memos.
- Subscription terms are hashed and fixed per agreement (`terms_hash`), so processing uses the exact approved terms.
- Users can cancel subscriptions at any time.

Current escrow status:
- Escrow lock/release/cancel flow is now implemented for subscriptions (`use_escrow=true`).
- Remaining gap is advanced production escrow automation/recovery (migrations, retries, background reconciliation).

## Test Status + Updated TODOs
Latest local run (`pytest -q src/backend/api/tests`):
- `6 passed`
- Unit coverage includes: health, wallet import/list, payment persistence, subscription handshake + escrow process/cancel, RLUSD send endpoint, and dashboard/guard/history responses.
- Integration coverage added (env-gated): XRPL Testnet escrow create/finish/cancel and RLUSD trust-line/payment.

What worked:
- Route wiring under `/api/v1`
- DB writes/reads for wallets, payments, subscriptions
- Handshake state transitions before process
- Payment and subscription processing persistence paths

TODO based on real test outcomes:
- Add negative tests for XRPL failure responses/timeouts, faucet errors, and issuer/trust-line misconfiguration.
- Add schema migration tooling (currently requires manual SQLite reset on schema changes).
- Add periodic reconciliation job to confirm on-chain escrow state matches local DB.

## Running Live Testnet Integration Tests
Integration tests are in `src/backend/api/tests/test_integration_testnet.py` and are skipped unless required env vars are set.

Escrow flow vars:
- `TESTNET_USER_SEED`
- `TESTNET_MERCHANT_SEED`
- `TESTNET_ESCROW_AMOUNT_XRP` (optional, default `0.00001`)

RLUSD flow vars:
- `TESTNET_RLUSD_SENDER_SEED`
- `TESTNET_RLUSD_RECEIVER_SEED`
- `TESTNET_RLUSD_ISSUER`
- `TESTNET_RLUSD_CURRENCY` (optional, default `RLUSD`)
- `TESTNET_RLUSD_AMOUNT` (optional, default `0.01`)

Run:
```bash
pytest -q src/backend/api/tests/test_integration_testnet.py -m integration
```

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Makefile Quick Commands
```bash
make setup
make backend
make frontend
make test
make test-integration
```

## Environment Variables
Defaults are already set in `src/backend/api/config.py`.

- `APP_NAME` (default: `EquiPay`)
- `API_PREFIX` (default: `/api/v1`)
- `HOST` (default: `0.0.0.0`)
- `PORT` (default: `8000`)
- `DEBUG` (default: `true`)
- `SQLITE_URL` (default: `sqlite:///./equipay.db`)
- `XRPL_RPC_URL` (default: `https://s.altnet.rippletest.net:51234`)
- `XRPL_NETWORK` (default: `testnet`)
- `RLUSD_CURRENCY` (default: `RLUSD`)
- `RLUSD_ISSUER` (default: empty, set this for RLUSD transfers/balance)
- `AUTO_FUND_NEW_WALLETS` (default: `true`)
- `HANDSHAKE_APPROVAL_DROPS` (default: `1`)
- `DASHBOARD_RECENT_LIMIT` (default: `10`)
- `FAUCET_RETRIES` (default: `2`)
- `XRPL_REQUEST_TIMEOUT_SECONDS` (default: `20`)

## Run
From `src/backend/api`:
```bash
uvicorn main:app --reload
```

If you already had an older DB file, delete `src/backend/api/equipay.db` (or your configured SQLite file) after schema changes and restart.

Swagger docs:
- `http://127.0.0.1:8000/docs`

## API Endpoints
- `GET /api/v1/health`
- `POST /api/v1/wallets/create`
- `POST /api/v1/wallets/import`
- `GET /api/v1/wallets/{address}/balance`
- `GET /api/v1/wallets`
- `POST /api/v1/payments/send`
- `POST /api/v1/payments/send-rlusd`
- `GET /api/v1/payments/{tx_hash}`
- `GET /api/v1/payments`
- `POST /api/v1/subscriptions/create`
- `POST /api/v1/subscriptions/{id}/handshake/user-approve`
- `POST /api/v1/subscriptions/{id}/handshake/service-approve`
- `GET /api/v1/subscriptions`
- `GET /api/v1/subscriptions/user/{user_wallet_address}`
- `GET /api/v1/subscriptions/{id}`
- `POST /api/v1/subscriptions/{id}/process`
- `POST /api/v1/subscriptions/{id}/cancel`
- `POST /api/v1/spending-guard/set`
- `GET /api/v1/spending-guard/{user_wallet_address}`
- `GET /api/v1/history/{user_wallet_address}`
- `GET /api/v1/dashboard/{user_wallet_address}`

## Example Curl Flows

### 1) Create Wallet
```bash
curl -X POST http://127.0.0.1:8000/api/v1/wallets/create
```

### 2) Import Wallet
```bash
curl -X POST http://127.0.0.1:8000/api/v1/wallets/import \
  -H "Content-Type: application/json" \
  -d '{"seed":"sEd..."}'
```

### 3) List Wallets
```bash
curl http://127.0.0.1:8000/api/v1/wallets
```

### 4) Get Wallet Balance
```bash
curl http://127.0.0.1:8000/api/v1/wallets/rXXXXXXXXXXXXXXXXXXXXXXXXXXXX/balance
```

### 5) Send Payment
```bash
curl -X POST http://127.0.0.1:8000/api/v1/payments/send \
  -H "Content-Type: application/json" \
  -d '{
    "sender_seed":"sEd...",
    "destination_address":"rXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "amount_xrp":0.1
  }'
```

### 6) Get Payment By Hash
```bash
curl http://127.0.0.1:8000/api/v1/payments/PUT_TX_HASH_HERE
```

### 7) List Payments
```bash
curl http://127.0.0.1:8000/api/v1/payments
```

### 8) Create Subscription
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_wallet_address":"rUSER...",
    "merchant_wallet_address":"rMERCHANT...",
    "user_seed":"sEd...",
    "amount_xrp":0.25,
    "interval_days":30
  }'
```

### 9) Process Subscription Payment
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/process
```

### 10) User Approves Handshake (on-chain)
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/handshake/user-approve \
  -H "Content-Type: application/json" \
  -d '{"user_seed":"sEd..."}'
```

### 11) Service Approves Handshake (on-chain)
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/handshake/service-approve \
  -H "Content-Type: application/json" \
  -d '{"merchant_seed":"sEd..."}'
```

### 12) Cancel Subscription
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/cancel
```

### 13) List Subscriptions
```bash
curl http://127.0.0.1:8000/api/v1/subscriptions
```
