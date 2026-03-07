# Subscription Flow Guide (Vendor Request + User Approval)

## Overview
1. User registers `username -> wallet_address`.
2. Vendor creates/updates their account and gets a shared secret.
3. Vendor creates subscription request using shared secret header.
4. User fetches pending requests and approves with seed.
5. Backend verifies signed contract terms and creates XRPL escrow.
6. Backend sends signed webhook events to vendor URL on state changes.
   - `subscription.requested`
   - `subscription.approved`
   - `subscription.cancelled`
   - `payment.sent` (for vendor-authenticated payment send endpoints)

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

## 3) Optional vendor profile operations
- `GET /api/v1/vendors/me` (auth via `X-Vendor-Secret`)
- `PATCH /api/v1/vendors/me` (update display name/wallet/webhook)
- `POST /api/v1/vendors/me/secret/regenerate`

## 4) Create subscription request
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

## 5) User checks pending
`GET /api/v1/subscriptions/pending/alice`

## 6) User approves
`POST /api/v1/subscriptions/{id}/approve`
```json
{ "username": "alice", "user_seed": "sEdExample..." }
```

On success:
- contract hash/signature verified
- XRPL escrow created
- status changes to `active/approved`
- webhook event `subscription.approved` sent

## 7) Cancel
`POST /api/v1/subscriptions/{id}/cancel`
- Vendor cancel: pass `X-Vendor-Secret`
- User cancel: send `{ "username", "user_seed" }`

If escrow is locked, user seed is required for escrow cancel transaction.

## Webhook Signature
Webhook header value format:
- `t=<unix_timestamp>,v1=<hmac_sha256_hex>`

Signature input:
- `<timestamp>.<raw_json_payload>`
- HMAC-SHA256 using vendor `shared_secret`

## Common Errors
- `401` missing/invalid vendor shared secret
- `404` unknown username/subscription/contract
- `409` duplicate `vendor_tx_id` or invalid state
- `400` invalid address/seed/signature mismatch
