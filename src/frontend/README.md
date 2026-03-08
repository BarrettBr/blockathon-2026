# EquiPay Frontend

Vue 3 + TypeScript frontend for EquiPay.

## Run
```bash
npm install
npm run dev
```

## Build
```bash
npm run build
```

## Environment
- `VITE_API_BASE_URL` (optional explicit override)
- `VITE_XRPL_EXPLORER_TX_BASE_URL` (optional transaction explorer base URL, default: `https://devnet.xrpl.org/transactions`)
- If not set, frontend auto-targets `http://<current-browser-host>:8000/api/v1`
  - Example: if frontend is opened via `http://127.0.0.1:5173`, API defaults to `http://127.0.0.1:8000/api/v1`

## Main Structure
- `src/main.ts` app bootstrap
- `src/router/index.ts` route map
- `src/layout/*` shell (sidebar + topbar)
- `src/views/*` pages (Dashboard, Wallet, Subscriptions, Spending Guard, History)
- `src/stores/*` Pinia stores for API-backed state
- `src/utils/apiHelper.ts` backend API client
