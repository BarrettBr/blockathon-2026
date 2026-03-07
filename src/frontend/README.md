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
- `VITE_API_BASE_URL` (default: `http://localhost:8000/api/v1`)

## Main Structure
- `src/main.ts` app bootstrap
- `src/router/index.ts` route map
- `src/layout/*` shell (sidebar + topbar)
- `src/views/*` pages (Dashboard, Wallet, Subscriptions, Spending Guard, History)
- `src/stores/*` Pinia stores for API-backed state
- `src/utils/apiHelper.ts` backend API client
