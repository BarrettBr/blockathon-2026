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

Note: if a vendor sends `X-Vendor-Secret` on payment send calls, EquiPay also emits a `payment.sent` webhook event to that vendor.

## Users
### POST `/users/register`
```json
{ "username": "alice", "wallet_address": "rUSER..." }
```

## Vendors
### POST `/vendors/upsert`
Create/update vendor and return shared secret.
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
```json
{
  "display_name": "Spotify US",
  "wallet_address": "rVENDOR...",
  "webhook_url": "https://vendor.example.com/equipay/webhook"
}
```

### POST `/vendors/me/secret/regenerate`
Auth header required. Returns new shared secret.

## Subscription Flow
### POST `/subscriptions/requests`
Auth header required.
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
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```
### POST `/subscriptions/{id}/cancel`
- Vendor-side: auth header
- User-side body:
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```
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
- `409` duplicate vendor tx or invalid state
- `500` internal/XRPL failure
