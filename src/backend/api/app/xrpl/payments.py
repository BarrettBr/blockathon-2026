"""Payment-related XRPL service stubs."""

from typing import Any, Dict

from app.xrpl.client import get_client


def send_payment(source: str, destination: str, amount: str) -> Dict[str, Any]:
    """Submit an XRPL payment transaction (stub)."""
    _ = (source, destination, amount)
    client = get_client()
    # TODO: Build Payment transaction, sign with wallet, submit, and persist tx.
    return {
        "message": "Payment submission is not implemented yet.",
        "rpc_url": str(client.url),
    }


def get_payment_status(tx_hash: str) -> Dict[str, Any]:
    """Retrieve transaction status/details by hash (stub)."""
    _ = tx_hash
    # TODO: Query XRPL tx endpoint and map ledger result to API response.
    return {"message": "Payment status lookup is not implemented yet."}
