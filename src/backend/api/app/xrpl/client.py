"""Reusable XRPL JSON-RPC client configuration."""

from xrpl.clients import JsonRpcClient

from app.config.settings import settings


_client = JsonRpcClient(settings.XRPL_RPC_URL)


def get_client() -> JsonRpcClient:
    """Return the shared XRPL JSON-RPC client instance."""
    return _client
