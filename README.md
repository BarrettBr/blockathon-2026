# XRPL Financial Hub Backend (Hackathon Skeleton)

Monolithic backend for fast iteration:
- `src/backend/api/main.py`: app wiring + startup + local run
- `src/backend/api/api.py`: all API endpoints
- `src/backend/api/db.py`: SQLAlchemy setup + models
- `src/backend/api/config.py`: environment-driven config

## Current Status
- FastAPI app is wired and runs under `/api/v1`.
- SQLite tables are auto-created on startup.
- Basic XRPL flows are implemented:
  - create wallet (optional faucet fund)
  - import/connect wallet by seed
  - wallet balance lookup
  - payment submit + payment status lookup
- Subscription endpoints are DB-backed placeholders (no escrow logic yet).

## Quick Start
1. Install dependencies:
```bash
pip install fastapi uvicorn sqlalchemy xrpl-py
```
2. Run API:
```bash
cd src/backend/api
python3 main.py
```
3. Open docs:
- `http://localhost:8000/docs`

## What Still Needs To Be Done
### High Priority
- Security hardening:
  - remove plaintext seed storage in DB
  - add auth for sensitive endpoints
  - add input validation for XRPL addresses and amount precision
- Error handling:
  - normalize API error format
  - map XRPL exceptions to stable status codes/messages
- Payments:
  - support destination tags and issued currencies
  - verify tx finality before reporting success

### By File
- `src/backend/api/config.py`
  - add separate profiles for local/devnet/testnet
  - add rate limit and secret management settings
- `src/backend/api/db.py`
  - add migrations (`alembic`) and schema versioning
  - add indexes/constraints for scale and integrity
- `src/backend/api/api.py`
  - split business logic from route handlers if complexity grows
  - implement escrow-backed subscription flow
  - add idempotency for payment submission
- `src/backend/api/main.py`
  - add structured logging, startup checks, and graceful shutdown hooks

## Extension Guide
See [docs/EXTENDING_BACKEND.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/EXTENDING_BACKEND.md) for a practical guide to extend this quickly.
