# Financial Snapshot Guide

## Purpose
A snapshot is an immutable financial report artifact for a user at a specific point in time.

- Derived from live DB records (payments, subscriptions, cycles, history)
- Stored as JSON on Pinata
- Indexed by metadata in SQLite
- Used for later review and Gemini Q&A over frozen data

## Endpoints (Auth Required)
- `POST /api/v1/snapshots`
- `GET /api/v1/snapshots`
- `GET /api/v1/snapshots/{id}`
- `POST /api/v1/snapshots/{id}/ask`

## Create Snapshot
```bash
curl -X POST http://127.0.0.1:8000/api/v1/snapshots \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"April Snapshot","days":30}'
```

Or explicit range:
```json
{
  "title": "Q1 Snapshot",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Ask Snapshot
```bash
curl -X POST http://127.0.0.1:8000/api/v1/snapshots/1/ask \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question":"How much of my spending is subscriptions vs direct payments?"}'
```

## Notes
- Snapshot artifacts do not mutate after creation.
- Snapshot list is DB-only for performance.
- Full content is fetched from Pinata only when opened or used for Q&A.
- Private Pinata setup (recommended):
  - `PINATA_UPLOAD_URL=https://uploads.pinata.cloud/v3/files`
  - `PINATA_UPLOAD_NETWORK=private`
  - `PINATA_GATEWAY_BASE_URL=https://<your-gateway>.mypinata.cloud` (or your configured gateway base)
  - `PINATA_GATEWAY_TOKEN=<gateway-token>`
  - If you see gateway errors like `1010`, your gateway access controls/token are not configured for backend fetch.
