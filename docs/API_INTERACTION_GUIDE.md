# API Interaction Guide (EquiPay)

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
    "app": "EquiPay",
    "network": "devnet",
    "xrpl_rpc_url": "https://s.devnet.rippletest.net:51234",
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
    "seed": "sEdExampleUserSecretValue",
    "network": "devnet",
    "funded": true,
    "funding_message": null
  }
}
```

### POST `/wallets/import`
Input:
```json
{ "seed": "sEdExampleUserSecretValue" }
```
Output:
```json
{
  "message": "Wallet imported",
  "data": {
    "id": 2,
    "address": "r...",
    "seed": "sEdExampleUserSecretValue",
    "network": "devnet"
  }
}
```

### GET `/wallets`
Input: none  
Output: list of wallet rows.

### POST `/wallets/bootstrap-rlusd`
Input:
```json
{
  "user_seed": "sEdExampleUserSecretValue",
  "mint_amount": 100
}
```
Output: trustline setup + mint transaction details + updated RLUSD balance.

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
    "rlusd_balance": 0.0,
    "rlusd_currency": "RLUSD",
    "rlusd_issuer": "r....",
    "ledger_index": 12345678
  }
}
```

## Payments
### POST `/payments/send`
Input:
```json
{
  "sender_seed": "sEdExampleUserSecretValue",
  "destination_address": "r...",
  "amount_xrp": 0.5
}
```

### POST `/payments/send-rlusd`
Input:
```json
{
  "sender_seed": "sEdExampleUserSecretValue",
  "destination_address": "r...",
  "amount": 9.99
}
```
Output: RLUSD transfer summary including `currency` and `issuer`.
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
  "user_seed": "sEdExampleUserSecretValue",
  "amount_xrp": 1.25,
  "interval_days": 30,
  "use_escrow": true
}
```
Output: subscription with `status=pending_handshake`, `handshake_status=pending`, and `terms_hash`.

### POST `/subscriptions/{id}/handshake/user-approve`
Input:
```json
{ "user_seed": "sEdExampleUserSecretValue" }
```
Output: subscription updated with `user_approval_tx_hash`.

### POST `/subscriptions/{id}/handshake/service-approve`
Input:
```json
{ "merchant_seed": "sEdExampleMerchantSecretValue" }
```
Or omit `merchant_seed` if `OPERATOR_WALLET_SEED` is configured.
Output: subscription updated with `service_approval_tx_hash`. If both approvals exist: `status=active` and `handshake_status=completed`.

### POST `/subscriptions/{id}/process`
Input for escrow subscriptions:
```json
{ "merchant_seed": "sEdExampleMerchantSecretValue" }
```
Or omit `merchant_seed` if `OPERATOR_WALLET_SEED` is configured.
Behavior:
- `use_escrow=true`: releases currently locked escrow and creates the next lock.
- `use_escrow=false`: sends direct recurring payment.
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

### GET `/subscriptions/user/{user_wallet_address}`
Input: path `user_wallet_address`  
Output: user's subscriptions sorted by newest first.

### GET `/subscriptions/{id}`
Input: path `id`  
Output: one subscription row.

## Spending Guard
### POST `/spending-guard/set`
Input:
```json
{
  "user_wallet_address": "r...",
  "monthly_limit": 500,
  "currency": "RLUSD"
}
```
Output: current guard with `limit`, `spent_this_month`, and `remaining`.

### GET `/spending-guard/{user_wallet_address}`
Output: current monthly guard state.

## History
### GET `/history/{user_wallet_address}?limit=50`
Output: history table rows sorted by date descending.

## Dashboard
### GET `/dashboard/{user_wallet_address}`
Output: aggregated card/chart payload:
- XRP and RLUSD balances
- locked in escrow
- monthly guard summary
- this-month released/locked totals
- upcoming releases
- recent activity

## HTTP Status Behavior
- `200`: success
- `400`: invalid seed/address/input or payment build/submit failures
- `404`: missing tx/subscription
- `409`: invalid subscription state (cancelled or handshake incomplete)
- `500`: server/runtime errors

## Notes
- Seeds are stored in plaintext for hackathon demo speed only.
- Existing DB schema changes require deleting old SQLite DB when fields change (no migrations in MVP).
