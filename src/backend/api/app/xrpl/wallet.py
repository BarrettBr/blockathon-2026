"""Wallet-related XRPL service stubs."""

from typing import Any, Dict

from app.xrpl.client import get_client


def create_wallet() -> Dict[str, Any]:
    """Create a new XRPL wallet (stub)."""
    client = get_client()
    # TODO: Use xrpl-py wallet generation and (optional) testnet funding flow.
    return {
        "message": "Wallet creation is not implemented yet.",
        "rpc_url": str(client.url),
    }


def import_wallet(seed: str) -> Dict[str, Any]:
    """Import an existing XRPL wallet from seed/private key material (stub)."""
    _ = seed
    # TODO: Validate wallet credentials and derive classic address.
    return {"message": "Wallet import is not implemented yet."}


def get_wallet_balance(address: str) -> Dict[str, Any]:
    """Fetch wallet balance from XRPL (stub)."""
    _ = address
    # TODO: Call account_info and parse XRP balance / trust line balances.
    return {"message": "Wallet balance lookup is not implemented yet."}
