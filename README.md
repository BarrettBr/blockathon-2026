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

## Important Hackathon Caveat
Wallet seeds are stored in plaintext in SQLite for demo speed.
This is **not production-safe**.

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

### 10) Cancel Subscription
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/cancel
```

### 11) List Subscriptions
```bash
curl http://127.0.0.1:8000/api/v1/subscriptions
```
