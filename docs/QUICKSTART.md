# EquiPay Quick Start

## 1) Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Frontend:
```bash
cd src/frontend
npm install
cd ../..
```

## 2) Configure environment
Copy and edit:
```bash
cp .env.example .env
```

Minimum values for a full demo:
- `XRPL_RPC_URL` (Devnet/Testnet)
- `XRPL_NETWORK`
- `RLUSD_ISSUER`
- `RLUSD_ISSUER_SEED`
- `PINATA_JWT`
- `GEMINI_API_KEY`

## 3) Run everything
```bash
make demo-all
```

This starts:
- Backend API (`http://127.0.0.1:8000`)
- Frontend (`http://127.0.0.1:5173` or configured Vite port)
- NovaBeat vendor demo (`http://127.0.0.1:7777`, or next free port)

## 4) Core demo flow
1. Create/login user in EquiPay frontend.
2. Connect user wallet (seed) in Wallet tab.
3. Top up RLUSD for user wallet.
4. Register vendor in NovaBeat demo (wallet + shared secret).
5. Create subscription request in demo.
6. Approve request in EquiPay Subscriptions.
7. Check dashboard/history updates.
8. Cancel subscription and verify non-renewing behavior.

## 5) Helpful URLs
- Swagger docs: `http://127.0.0.1:8000/docs`
- Health: `GET /api/v1/health`
- Frontend flow reference: [FRONTEND_USECASE_FLOW.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/FRONTEND_USECASE_FLOW.md)
- API reference: [API_INTERACTION_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/API_INTERACTION_GUIDE.md)
