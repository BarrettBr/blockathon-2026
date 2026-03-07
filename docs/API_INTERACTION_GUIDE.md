# API Interaction Guide (EquiPay)

Base URL: `http://127.0.0.1:8000/api/v1`

Success shape:
```json
{ "message": "...", "data": {} }
```

Error shape:
```json
{ "detail": "..." }
```

## Health
- `GET /health`

## Wallets
- `POST /wallets/create`
- `POST /wallets/import`
- `POST /wallets/bootstrap-rlusd`
- `GET /wallets`
- `GET /wallets/{address}/balance`

## Payments
- `POST /payments/send`
- `POST /payments/send-rlusd`
- `GET /payments`
- `GET /payments/{tx_hash}`

If vendor auth header is sent on payment calls, EquiPay emits `payment.sent` webhook.

## Users
### POST `/users/register`
```json
{ "username": "alice", "wallet_address": "rUSER..." }
```

## Vendors
### POST `/vendors/upsert`
Create or update vendor and return shared secret.
```json
{
  "vendor_code": "spotify",
  "display_name": "Spotify",
  "wallet_address": "rVENDOR...",
  "webhook_url": "https://vendor.example.com/equipay/webhook"
}
```

### GET `/vendors/me`
Auth header: `X-Vendor-Secret: <shared_secret>`

### PATCH `/vendors/me`
Auth header required.

### POST `/vendors/me/secret/regenerate`
Auth header required.

## Subscriptions (Per-Cycle Escrow)
### POST `/subscriptions/requests`
Vendor-auth header required.
```json
{
  "vendor_tx_id": "VTX-001",
  "username": "alice",
  "amount_xrp": 1.25,
  "interval_days": 30
}
```

### GET `/subscriptions/pending/{username}`

### POST `/subscriptions/{id}/approve`
Creates cycle 1 escrow.
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```

### POST `/subscriptions/{id}/cycles/process`
Creates the next cycle escrow for approved auto-renew subscriptions.
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```

### GET `/subscriptions/{id}/cycles`
List all cycle escrow records for a subscription.

### POST `/subscriptions/{id}/cancel`
- Vendor-side: shared-secret header
- User-side body:
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```

Behavior:
- Pending request -> `cancelled`
- Active approved -> `auto_renew=false`, `status=non_renewing`

### GET `/subscriptions`
### GET `/subscriptions/{id}`
### GET `/subscriptions/contract/{contract_hash}`

## Dashboard APIs
- `POST /spending-guard/set`
- `GET /spending-guard/{user_wallet_address}`
- `GET /history/{user_wallet_address}`
- `GET /dashboard/{user_wallet_address}`

## Status Codes
- `200` success
- `400` invalid input/signature/wallet mismatch
- `401` invalid vendor shared secret
- `404` missing record
- `409` duplicate vendor tx or invalid subscription state (including non-renewing cycle processing)
- `500` internal/XRPL failure
