# XRPL Financial Hub Backend MVP

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

Remaining gap:
- Full escrow-based locked-funds rail is not implemented yet. The MVP currently uses handshake + per-cycle payment processing.

## Test Status + Updated TODOs
Latest local run (`pytest -q src/backend/api/tests`):
- `4 passed`
- Unit coverage includes: health, wallet import/list, payment persistence, and full subscription handshake/process/cancel flow.

What worked:
- Route wiring under `/api/v1`
- DB writes/reads for wallets, payments, subscriptions
- Handshake state transitions before process
- Payment and subscription processing persistence paths

TODO based on real test outcomes:
- Add true XRPL integration tests against Testnet (current tests mock XRPL calls).
- Add negative tests for XRPL failure responses/timeouts and faucet errors.
- Add schema migration tooling (currently requires manual SQLite reset on schema changes).
- Add escrow lock mode if you need full “locked funds” semantics.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables
Defaults are already set in `src/backend/api/config.py`.

- `APP_NAME` (default: `XRPL Financial Hub`)
- `API_PREFIX` (default: `/api/v1`)
- `HOST` (default: `0.0.0.0`)
- `PORT` (default: `8000`)
- `DEBUG` (default: `true`)
- `SQLITE_URL` (default: `sqlite:///./xrpl_financial_hub.db`)
- `XRPL_RPC_URL` (default: `https://s.altnet.rippletest.net:51234`)
- `XRPL_NETWORK` (default: `testnet`)
- `AUTO_FUND_NEW_WALLETS` (default: `true`)
- `FAUCET_RETRIES` (default: `2`)
- `XRPL_REQUEST_TIMEOUT_SECONDS` (default: `20`)

## Run
From `src/backend/api`:
```bash
uvicorn main:app --reload
```

If you already had an older DB file, delete `src/backend/api/xrpl_financial_hub.db` (or your configured SQLite file) after schema changes and restart.

Swagger docs:
- `http://127.0.0.1:8000/docs`

## API Endpoints
- `GET /api/v1/health`
- `POST /api/v1/wallets/create`
- `POST /api/v1/wallets/import`
- `GET /api/v1/wallets/{address}/balance`
- `GET /api/v1/wallets`
- `POST /api/v1/payments/send`
- `GET /api/v1/payments/{tx_hash}`
- `GET /api/v1/payments`
- `POST /api/v1/subscriptions/create`
- `POST /api/v1/subscriptions/{id}/handshake/user-approve`
- `POST /api/v1/subscriptions/{id}/handshake/service-approve`
- `GET /api/v1/subscriptions`
- `GET /api/v1/subscriptions/{id}`
- `POST /api/v1/subscriptions/{id}/process`
- `POST /api/v1/subscriptions/{id}/cancel`

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
