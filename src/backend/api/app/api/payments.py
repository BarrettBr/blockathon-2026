"""Payments API router skeleton."""

from pydantic import BaseModel
from fastapi import APIRouter

from app.xrpl.payments import get_payment_status, send_payment


router = APIRouter(prefix="/payments", tags=["payments"])


class SendPaymentRequest(BaseModel):
    source: str
    destination: str
    amount: str


@router.post("/send")
def send_payment_endpoint(payload: SendPaymentRequest):
    """Send payment endpoint placeholder."""
    result = send_payment(
        source=payload.source,
        destination=payload.destination,
        amount=payload.amount,
    )
    return {"success": True, "data": result}


@router.get("/{tx_hash}")
def get_payment_endpoint(tx_hash: str):
    """Payment status endpoint placeholder."""
    result = get_payment_status(tx_hash)
    return {"success": True, "tx_hash": tx_hash, "data": result}
