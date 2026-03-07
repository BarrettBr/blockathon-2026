# Frontend Use Case Flow (Current API Order)

Base URL: `http://127.0.0.1:8000/api/v1`

## 1) Connect Existing Wallet
1. `POST /wallets/import`
2. `GET /wallets/{address}/balance`

## 2) Send One-Time Money
- XRP: `POST /payments/send`
- RLUSD: `POST /payments/send-rlusd`

## 3) Subscription (Vendor Request Model)

### Vendor side
1. Ensure user exists in backend lookup:
   - `POST /users/register`
2. Ensure vendor exists:
   - `POST /vendors/upsert`
3. Create request (with shared-secret vendor auth header, default `X-Vendor-Secret`):
   - `POST /subscriptions/requests`

### User side
4. Fetch pending requests:
   - `GET /subscriptions/pending/{username}`
5. Approve selected request:
   - `POST /subscriptions/{id}/approve`
6. Create next cycle escrow (when due/needed):
   - `POST /subscriptions/{id}/cycles/process`

### Optional lookup / management
7. Contract lookup by hash:
   - `GET /subscriptions/contract/{contract_hash}`
8. List cycle records:
   - `GET /subscriptions/{id}/cycles`
9. Cancel subscription:
   - `POST /subscriptions/{id}/cancel`
10. List subscriptions:
   - `GET /subscriptions`
   - `GET /subscriptions/{id}`

## 4) Dashboard Data
- `GET /dashboard/{user_wallet_address}`
- `GET /spending-guard/{user_wallet_address}`
- `GET /history/{user_wallet_address}?limit=50`

## 5) Financial Snapshots (Auth Required)
1. Create snapshot:
   - `POST /snapshots`
2. List snapshots:
   - `GET /snapshots`
3. Open snapshot:
   - `GET /snapshots/{id}`
4. Ask Gemini about snapshot:
   - `POST /snapshots/{id}/ask`

## Typical Failure Handling
- `400`: invalid seed/address/payload/contract mismatch
- `401`: vendor shared-secret header invalid or missing
- `404`: username/subscription/contract not found
- `409`: duplicate vendor transaction id, non-renewing cycle process, or invalid state
- `500`: backend/XRPL unexpected failure
