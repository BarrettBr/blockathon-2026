# Subscription Flow Guide (Per-Cycle Escrow Model)

## Architecture Summary
EquiPay subscriptions are stored as backend records and coordinated across multiple XRPL escrow transactions.

- No single long-lived recurring on-ledger contract.
- Each billing period is represented by a **subscription cycle** with its own escrow.
- Cycle 1 escrow is created at user approval.
- Future cycle escrows are created with `POST /subscriptions/{id}/cycles/process`.
- Cancelling an active subscription sets `auto_renew=false` and `status=non_renewing`.
- Existing already-created cycle escrows are not force-cancelled by non-renewing.

## Required Config
- `VENDOR_SHARED_SECRET_HEADER` (default `X-Vendor-Secret`)
- `WEBHOOK_SIGNATURE_HEADER` (default `X-Equipay-Signature`)
- `WEBHOOK_TIMEOUT_SECONDS`

## 1) Register user
`POST /api/v1/users/register`
```json
{ "username": "alice", "wallet_address": "rUSER..." }
```

## 2) Create vendor account
`POST /api/v1/vendors/upsert`
```json
{
  "vendor_code": "spotify",
  "display_name": "Spotify",
  "wallet_address": "rVENDOR...",
  "webhook_url": "https://vendor.example.com/equipay/webhook"
}
```
Response includes `shared_secret`.

## 3) Vendor creates subscription request
`POST /api/v1/subscriptions/requests`
Header:
```text
X-Vendor-Secret: <shared_secret>
```
Body:
```json
{
  "vendor_tx_id": "VTX-001",
  "username": "alice",
  "amount_xrp": 1.25,
  "interval_days": 30
}
```

## 4) User approves request (creates cycle 1 escrow)
`POST /api/v1/subscriptions/{id}/approve`
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```

## 5) Create next billing cycle escrow
`POST /api/v1/subscriptions/{id}/cycles/process`
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```

## 6) Inspect cycle history
`GET /api/v1/subscriptions/{id}/cycles`

## 7) Cancel future renewals
`POST /api/v1/subscriptions/{id}/cancel`
- Vendor-side: pass `X-Vendor-Secret`
- User-side: send `{ "username", "user_seed" }`

Behavior:
- Pending request -> status becomes `cancelled`
- Active approved subscription -> `auto_renew=false`, `status=non_renewing`

## Webhook Events
- `subscription.requested`
- `subscription.approved`
- `subscription.cycle_created`
- `subscription.cancelled`

Webhook signature header:
- `t=<unix_timestamp>,v1=<hmac_sha256_hex>`
- signature input: `<timestamp>.<raw_json_payload>`

## Common Errors
- `401` invalid/missing vendor shared secret
- `404` unknown username/subscription/contract
- `409` duplicate vendor transaction id or non-renewing cycle processing attempt
- `400` invalid address/seed/signature mismatch
