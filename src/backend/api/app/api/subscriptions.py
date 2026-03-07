"""Subscriptions API router skeleton."""

from pydantic import BaseModel
from fastapi import APIRouter

from app.xrpl.escrow import cancel_subscription, create_subscription


router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class CreateSubscriptionRequest(BaseModel):
    owner_address: str
    amount: str
    interval: str = "monthly"


@router.post("/create")
def create_subscription_endpoint(payload: CreateSubscriptionRequest):
    """Create subscription endpoint placeholder."""
    result = create_subscription(
        owner_address=payload.owner_address,
        amount=payload.amount,
        interval=payload.interval,
    )
    return {"success": True, "data": result}


@router.post("/{subscription_id}/cancel")
def cancel_subscription_endpoint(subscription_id: int):
    """Cancel subscription endpoint placeholder."""
    result = cancel_subscription(subscription_id)
    return {"success": True, "subscription_id": subscription_id, "data": result}
