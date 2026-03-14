# EquiPay

**User-controlled recurring payments on XRPL.**

EquiPay is a hackathon-built platform that demonstrates a transparent, approval-based subscription model using XRPL and RLUSD. Users explicitly approve recurring payments, inspect billing cycles, and generate immutable financial snapshots.

## Awards
**Open Innovation Award - Midwest Blockathon 2026**

EquiPay was built during the 36-hour Midwest Blockathon and received the **Open Innovation Award**, recognizing projects that push creative uses of decentralized technology.

Prize: **$500**

[View project on Devpost](https://devpost.com/software/equipay-ucnpqm)

## What This Is
EquiPay combines:
- A FastAPI backend for wallets, payments, subscriptions, snapshots, and dashboard data
- A Vue frontend for non-crypto-native users
- A demo vendor app (NovaBeat) to simulate real merchant subscription requests

The core idea: users explicitly approve subscriptions, and every billing cycle is transparent and inspectable.

## Motivation
Traditional recurring billing is easy to forget and hard to audit.  
EquiPay is designed to show a cleaner model: user consent first, visible payment rails, and clear cancellation behavior.

## Problem We Solve
- Hidden recurring charges and poor visibility
- Low user control after initial checkout
- Hard-to-trust payment histories

EquiPay gives users:
- Approval-based subscription onboarding
- Clear per-cycle payment records
- Spending guard + dashboard visibility
- Immutable financial snapshots for later review


## Technology Choices

**XRPL**
- Used as the payment rail for subscription cycles
- Enables low-cost micro-transactions and transparent ledger history

**RLUSD**
- Stable unit for recurring payments
- Avoids volatility problems typical with crypto billing

**Pinata (Private IPFS)**
- Stores immutable financial snapshots
- Ensures historical reports cannot be modified

**Gemini**
- Provides natural-language queries over financial snapshots
- Allows users to ask questions like:
  - "How much did I spend on subscriptions last month?"

## Hackathon Challenges We Addressed
- Converting crypto-native flows into beginner-friendly UX
- Keeping vendor/user handshake secure but simple
- Handling devnet/testnet trustline and issued-token edge cases
- Keeping dashboard performance responsive under repeated polling

## Current State
- Wallet connect, balance, and RLUSD top-up
- XRP + RLUSD transfers
- Vendor request -> user approval subscription flow
- Manual cycle processing + cancellation (non-renewing behavior)
- Dashboard, history, spending guard
- Snapshot create/open/ask flow with Pinata + Gemini

## Important MVP Caveat
For speed in a hackathon, seeds/shared secrets are handled in plaintext in local storage/DB paths.  
This is **not production-safe** and must be replaced with secure custody/secrets management.

## Quick Start
See: [QUICKSTART.md](docs/QUICKSTART.md)

## Useful Docs
- API details: [API_INTERACTION_GUIDE.md](docs/API_INTERACTION_GUIDE.md)
- Subscription flow: [SUBSCRIPTION_FLOW_GUIDE.md](docs/SUBSCRIPTION_FLOW_GUIDE.md)
- Snapshot flow: [SNAPSHOT_GUIDE.md](docs/SNAPSHOT_GUIDE.md)
- Frontend call flow: [FRONTEND_USECASE_FLOW.md](docs/FRONTEND_USECASE_FLOW.md)
- Backend extension notes: [EXTENDING_BACKEND.md](docs/EXTENDING_BACKEND.md)

## Future Additions
- Production-grade key management and encrypted secrets
- Automated cycle scheduler/worker
- Richer budgeting categories and analytics
- Multi-vendor reputation/verification layer
- More robust webhook retries/observability
- Mobile-first onboarding and social login
