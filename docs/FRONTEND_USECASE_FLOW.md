# Frontend Use Case Flow (Call Order)

Base URL: `http://127.0.0.1:8000/api/v1`

This is the exact API order for a typical user journey:

1. Connect existing wallet
2. Send money
3. Create + activate subscription
4. Process subscription payment
5. Cancel subscription

## 1) Connect Existing Wallet
User already has a wallet created elsewhere and wants to connect it.

### Call
`POST /wallets/import`

### Body
```json
{
  "seed": "sEdExampleUserSecretValue"
}
```

### Returns
- User wallet record (`address`, `seed`, `network`)

### Optional follow-up checks
1. `GET /wallets`
2. `GET /wallets/{address}/balance`

Use this balance response in dashboard cards:
- `balance_xrp`
- `rlusd_balance`

## 2) Send Money (One-Time)

### XRP transfer
`POST /payments/send`

Body:
```json
{
  "sender_seed": "sEdExampleUserSecretValue",
  "destination_address": "r...",
  "amount_xrp": 0.5
}
```

### RLUSD transfer
`POST /payments/send-rlusd`

Body:
```json
{
  "sender_seed": "sEdExampleUserSecretValue",
  "destination_address": "r...",
  "amount": 9.99
}
```

### Optional transaction/history checks
1. `GET /payments`
2. `GET /history/{user_wallet_address}`

## 3) Create and Activate Subscription

## 3A) Create subscription
`POST /subscriptions/create`

Body (escrow mode enabled):
```json
{
  "user_wallet_address": "rUSER...",
  "merchant_wallet_address": "rMERCHANT...",
  "user_seed": "sEdExampleUserSecretValue",
  "amount_xrp": 1.25,
  "interval_days": 30,
  "use_escrow": true
}
```

Save returned `id` as `subscription_id`.

## 3B) User handshake approval
`POST /subscriptions/{subscription_id}/handshake/user-approve`

Body:
```json
{
  "user_seed": "sEdExampleUserSecretValue"
}
```

## 3C) Service handshake approval
`POST /subscriptions/{subscription_id}/handshake/service-approve`

Body:
```json
{
  "merchant_seed": "sEdExampleMerchantSecretValue"
}
```
(If backend has `OPERATOR_WALLET_SEED`, frontend may omit merchant seed.)

After both approvals:
- `status` becomes `active`
- if `use_escrow=true`, backend creates escrow lock for current cycle

## 3D) Process cycle payment
`POST /subscriptions/{subscription_id}/process`

For escrow subscriptions, merchant seed is used:
```json
{
  "merchant_seed": "sEdExampleMerchantSecretValue"
}
```
If backend has `OPERATOR_WALLET_SEED`, body can be empty.

For non-escrow subscriptions (`use_escrow=false`), body can be empty.

### Optional subscription checks
1. `GET /subscriptions/{subscription_id}`
2. `GET /subscriptions/user/{user_wallet_address}`

## 4) Cancel Subscription

### Call
`POST /subscriptions/{subscription_id}/cancel`

### Body
None

### Result
- `status` becomes `cancelled`
- if escrow is currently locked, backend attempts escrow cancel

## Dashboard/Sidebar Calls for UI
Use these to populate dashboard widgets and history screens.

1. `GET /dashboard/{user_wallet_address}`
- Aggregated cards/charts:
  - balances (XRP + RLUSD)
  - locked in escrow
  - monthly guard stats
  - upcoming release
  - recent activity

2. `GET /spending-guard/{user_wallet_address}`
- Current monthly guard values

3. `POST /spending-guard/set`
- Set/update monthly limit

4. `GET /history/{user_wallet_address}?limit=50`
- Table feed sorted newest first

## Minimal Frontend State You Should Store
- `user_wallet_address`
- `user_seed` (if your flow allows client-side handling; otherwise use secure session/server strategy)
- `subscription_id` per created subscription
- `merchant_seed` only for merchant-side process actions

## Common Failure Cases to Handle
- `400`: bad seed, bad address, invalid payload
- `404`: subscription/tx not found
- `409`: subscription not active, cancelled, or handshake incomplete
- `500`: server/XRPL failure
