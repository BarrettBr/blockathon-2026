"""Escrow/subscription-related XRPL service stubs."""

from typing import Any, Dict

from app.xrpl.client import get_client


def create_subscription(owner_address: str, amount: str, interval: str) -> Dict[str, Any]:
    """Create recurring subscription escrow flow (stub)."""
    _ = (owner_address, amount, interval)
    client = get_client()
    # TODO: Design escrow-based recurring payment mechanism for XRPL.
    return {
        "message": "Subscription creation is not implemented yet.",
        "rpc_url": str(client.url),
    }


def cancel_subscription(subscription_id: int) -> Dict[str, Any]:
    """Cancel an active subscription escrow flow (stub)."""
    _ = subscription_id
    # TODO: Implement escrow cancel/finish transaction handling.
    return {"message": "Subscription cancellation is not implemented yet."}
