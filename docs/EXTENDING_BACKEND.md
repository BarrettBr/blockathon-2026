# Extending the Backend (Hackathon Guide)

This project is intentionally monolithic for speed:
- `src/backend/api/main.py`
- `src/backend/api/api.py`
- `src/backend/api/db.py`
- `src/backend/api/config.py`

Use this guide to extend features quickly without fighting architecture.

## 1. Add/Change Config Values
Edit `src/backend/api/config.py`.

Pattern:
```python
NEW_SETTING: str = os.getenv("NEW_SETTING", "default")
```

Use config in other files:
```python
from config import settings
print(settings.NEW_SETTING)
```

## 2. Add a New Table
Edit `src/backend/api/db.py` and define a new SQLAlchemy model.

Pattern:
```python
class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String(128), nullable=False)
```

Then restart app so startup `init_db()` creates the table.

## 3. Add a New Endpoint
Edit `src/backend/api/api.py`.

Pattern:
```python
class CreateInvoiceRequest(BaseModel):
    owner: str

@router.post("/invoices/create")
def create_invoice(payload: CreateInvoiceRequest, db: Session = Depends(get_db)):
    # DB/XRPL logic here
    return {"ok": True}
```

All routes are mounted under `settings.API_PREFIX` (default `/api/v1`).

## 4. XRPL Integration Pattern
Use the existing top-level `xrpl-py` imports in `api.py` and keep XRPL logic in helper functions near the top of that file.

Pattern:
```python
client = _get_xrpl_client()
result = client.request(AccountInfo(account=address)).result
```

## 5. Suggested Next Refactor Trigger
Keep monolithic until velocity drops. Split files only when one of these happens:
- `api.py` exceeds ~700 lines
- feature work causes repeated merge conflicts
- business logic is duplicated across handlers

At that point, extract:
- `services/wallets.py`
- `services/payments.py`
- `services/subscriptions.py`

## 6. Minimal Production Readiness Checklist
- Add authentication and authorization
- Encrypt or avoid storing wallet seeds
- Add migrations (Alembic)
- Add tests for each endpoint path
- Add request/response logging and rate limiting
