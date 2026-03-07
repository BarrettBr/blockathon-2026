# EquiPay Backend MVP

FastAPI backend for XRPL Devnet with wallets, payments, vendor-managed subscriptions, escrow cycles, and dashboard APIs.

## Stack
- Python 3.10+
- FastAPI
- SQLite + SQLAlchemy
- xrpl-py

## Hackathon Caveat
Seeds and vendor shared secrets are stored/handled in plaintext for MVP speed.
This is not production-safe.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run from `src/backend/api`:
```bash
uvicorn main:app --reload
```

Swagger:
- `http://127.0.0.1:8000/docs`

## Subscription Architecture (Current)
Subscriptions are **application-managed records** in SQLite.

The backend creates **per-billing-cycle XRPL escrows** (one escrow transaction per cycle), not a single long-lived recurring on-ledger contract.

- `approve` creates cycle 1 escrow.
- `process cycle` creates the next cycle escrow.
- `cancel` on active subscriptions sets `auto_renew=false` and `status=non_renewing`.
- Non-renewing subscriptions stop creating future cycles.
- Existing already-created cycle escrows are left as-is to finish/cancel on-chain.

## Environment Variables
Defaults are in `src/backend/api/config.py`.

Core/XRPL:
- `APP_NAME`, `API_PREFIX`, `HOST`, `PORT`, `DEBUG`
- `CORS_ALLOW_ORIGINS`
- `SQLITE_URL`
- `XRPL_RPC_URL`, `XRPL_NETWORK`, `XRPL_FAUCET_URL`

RLUSD:
- `RLUSD_CURRENCY`, `RLUSD_ISSUER`, `RLUSD_ISSUER_SEED`

Vendor auth/webhooks:
- `VENDOR_SHARED_SECRET_HEADER` (default `X-Vendor-Secret`)
- `WEBHOOK_SIGNATURE_HEADER` (default `X-Equipay-Signature`)
- `WEBHOOK_TIMEOUT_SECONDS`

Misc:
- `AUTO_FUND_NEW_WALLETS`, `FAUCET_RETRIES`, `XRPL_REQUEST_TIMEOUT_SECONDS`
- `DASHBOARD_RECENT_LIMIT`

## API Endpoints
- Health: `GET /api/v1/health`
- Wallets: `POST /wallets/create`, `POST /wallets/import`, `POST /wallets/bootstrap-rlusd`, `GET /wallets`, `GET /wallets/{address}/balance`
- Payments: `POST /payments/send`, `POST /payments/send-rlusd`, `GET /payments`, `GET /payments/{tx_hash}`
- Users: `POST /users/register`
- Vendors: `POST /vendors/upsert`, `GET /vendors/me`, `PATCH /vendors/me`, `POST /vendors/me/secret/regenerate`
- Subscriptions:
  - `POST /subscriptions/requests`
  - `GET /subscriptions/pending/{username}`
  - `POST /subscriptions/{id}/approve`
  - `POST /subscriptions/{id}/cycles/process`
  - `GET /subscriptions/{id}/cycles`
  - `POST /subscriptions/{id}/cancel`
  - `GET /subscriptions`
  - `GET /subscriptions/{id}`
  - `GET /subscriptions/contract/{contract_hash}`
- Dashboard: `POST /spending-guard/set`, `GET /spending-guard/{wallet}`, `GET /history/{wallet}`, `GET /dashboard/{wallet}`

## Quick Subscription Flow
1. Register user profile:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","wallet_address":"rUSER..."}'
```

2. Create/update vendor (returns shared secret):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/vendors/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_code":"spotify",
    "display_name":"Spotify",
    "wallet_address":"rVENDOR...",
    "webhook_url":"https://vendor.example.com/equipay/webhook"
  }'
```

3. Vendor creates subscription request:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/requests \
  -H "Content-Type: application/json" \
  -H "X-Vendor-Secret: VENDOR_SHARED_SECRET" \
  -d '{"vendor_tx_id":"VTX-001","username":"alice","amount_xrp":1.25,"interval_days":30}'
```

4. User approves (creates cycle 1 escrow):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/approve \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","user_seed":"sEdExample..."}'
```

5. Create next cycle escrow when needed:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/cycles/process \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","user_seed":"sEdExample..."}'
```

6. Cancel future renewals (non-renewing):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/subscriptions/1/cancel \
  -H "X-Vendor-Secret: VENDOR_SHARED_SECRET"
```

Webhook events are signed and sent to the configured vendor webhook URL for:
- `subscription.requested`
- `subscription.approved`
- `subscription.cycle_created`
- `subscription.cancelled`
- `payment.sent` (when vendor-authenticated payment send calls are used)

See:
- [docs/SUBSCRIPTION_FLOW_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/SUBSCRIPTION_FLOW_GUIDE.md)
- [docs/API_INTERACTION_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/API_INTERACTION_GUIDE.md)
