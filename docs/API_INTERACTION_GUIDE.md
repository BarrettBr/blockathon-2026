# API Interaction Guide (XRPL Financial Hub)

Base URL (local): `http://127.0.0.1:8000/api/v1`

Response shape for success:
```json
{
  "message": "...",
  "data": {}
}
```

Errors return normal FastAPI error format:
```json
{
  "detail": "..."
}
```

## Health
### GET `/health`
Input: none  
Output:
```json
{
  "message": "Service health",
  "data": {
    "status": "ok",
    "app": "XRPL Financial Hub",
    "network": "testnet",
    "xrpl_rpc_url": "https://s.altnet.rippletest.net:51234",
    "xrpl_ready": true,
    "xrpl_error": null
  }
}
```

## Wallets
### POST `/wallets/create`
Input: none  
Output (example):
```json
{
  "message": "Wallet created",
  "data": {
    "id": 1,
    "address": "r...",
    "seed": "sEd...",
    "network": "testnet",
    "funded": true,
    "funding_message": null
  }
}
```

### POST `/wallets/import`
Input:
```json
{ "seed": "sEd..." }
```
Output:
```json
{
  "message": "Wallet imported",
  "data": {
    "id": 2,
    "address": "r...",
    "seed": "sEd...",
    "network": "testnet"
  }
}
```

### GET `/wallets`
Input: none  
Output: list of wallet rows.

### GET `/wallets/{address}/balance`
Input: path `address`  
Output:
```json
{
  "message": "Wallet balance",
  "data": {
    "address": "r...",
    "balance_xrp": 12.345,
    "balance_drops": "12345000",
    "ledger_index": 12345678
  }
}
```

## Payments
### POST `/payments/send`
Input:
```json
{
  "sender_seed": "sEd...",
  "destination_address": "r...",
  "amount_xrp": 0.5
}
```
Output:
```json
{
  "message": "Payment sent",
  "data": {
    "id": 10,
    "tx_hash": "ABC...",
    "status": "tesSUCCESS",
    "from_address": "r...",
    "to_address": "r...",
    "amount_xrp": 0.5,
    "validated": true,
    "ledger_index": 12345678
  }
}
```

### GET `/payments/{tx_hash}`
Input: path `tx_hash`  
Output: transaction summary + `raw_result` from XRPL.

### GET `/payments`
Input: none  
Output: list of transaction records stored locally.

## Subscriptions
### POST `/subscriptions/create`
Input:
```json
{
  "user_wallet_address": "r...",
  "merchant_wallet_address": "r...",
  "user_seed": "sEd...",
  "amount_xrp": 1.25,
  "interval_days": 30
}
```
Output: subscription with `status=pending_handshake`, `handshake_status=pending`, and `terms_hash`.

### POST `/subscriptions/{id}/handshake/user-approve`
Input:
```json
{ "user_seed": "sEd..." }
```
Output: subscription updated with `user_approval_tx_hash`.

### POST `/subscriptions/{id}/handshake/service-approve`
Input:
```json
{ "merchant_seed": "sEd..." }
```
Output: subscription updated with `service_approval_tx_hash`. If both approvals exist: `status=active` and `handshake_status=completed`.

### POST `/subscriptions/{id}/process`
Input: none  
Behavior: sends one recurring payment using stored subscription terms.  
Output:
```json
{
  "message": "Subscription payment processed",
  "data": {
    "subscription_id": 3,
    "last_tx_hash": "ABC...",
    "status": "active",
    "next_payment_date": "2026-04-06"
  }
}
```

### POST `/subscriptions/{id}/cancel`
Input: none  
Output:
```json
{
  "message": "Subscription cancelled",
  "data": {
    "id": 3,
    "status": "cancelled"
  }
}
```

### GET `/subscriptions`
Input: none  
Output: list of subscriptions.

### GET `/subscriptions/{id}`
Input: path `id`  
Output: one subscription row.

## HTTP Status Behavior
- `200`: success
- `400`: invalid seed/address/input or payment build/submit failures
- `404`: missing tx/subscription
- `409`: invalid subscription state (cancelled or handshake incomplete)
- `500`: server/runtime errors

## Notes
- Seeds are stored in plaintext for hackathon demo speed only.
- Existing DB schema changes require deleting old SQLite DB when fields change (no migrations in MVP).
