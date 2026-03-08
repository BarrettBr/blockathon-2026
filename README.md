# EquiPay

EquiPay is a hackathon-ready app that makes recurring payments feel simple and user-controlled on XRPL.

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

## Why These Technologies
- **XRPL**: fast and low-cost rails for wallet-based payments and subscription cycles
- **RLUSD**: stable-value unit for subscription billing in demo flows
- **Pinata (Private IPFS)**: immutable snapshot storage so reports stay fixed over time
- **Gemini**: natural-language Q&A over a frozen financial snapshot

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
See: [QUICKSTART.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/QUICKSTART.md)

## Useful Docs
- API details: [API_INTERACTION_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/API_INTERACTION_GUIDE.md)
- Subscription flow: [SUBSCRIPTION_FLOW_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/SUBSCRIPTION_FLOW_GUIDE.md)
- Snapshot flow: [SNAPSHOT_GUIDE.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/SNAPSHOT_GUIDE.md)
- Frontend call flow: [FRONTEND_USECASE_FLOW.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/FRONTEND_USECASE_FLOW.md)
- Backend extension notes: [EXTENDING_BACKEND.md](/home/barrett/workspaces/github.com/blockathon-2026/docs/EXTENDING_BACKEND.md)

## Future Additions
- Production-grade key management and encrypted secrets
- Automated cycle scheduler/worker
- Richer budgeting categories and analytics
- Multi-vendor reputation/verification layer
- More robust webhook retries/observability
- Mobile-first onboarding and social login
