"""Health handler."""
from typing import Any
from fastapi import APIRouter
from xrpl.models.requests import AccountInfo, ServerInfo
import core
from config import settings
from schemas import ApiResponse


router = APIRouter(tags=["health"])

def _success(message: str, data: Any) -> dict[str, Any]:
    return {"message": message, "data": data}

@router.get("/health", response_model=ApiResponse)
def health() -> dict[str, Any]:
    xrpl_ready = True
    xrpl_error = None
    issuer_ready = False
    issuer_error = None

    try:
        client = core._get_xrpl_client()
        client.request(ServerInfo())
        xrpl_ready = True
    except Exception as exc:
        xrpl_ready = False
        xrpl_error = str(exc)

    if xrpl_ready and settings.RLUSD_ISSUER:
        try:
            result = client.request(AccountInfo(
                account=settings.RLUSD_ISSUER,
                ledger_index="current",
            )).result
            if "account_data" in result:
                flags = result["account_data"].get("Flags", 0)
                issuer_ready = True
                if not (flags & 0x00800000):
                    issuer_error = "Issuer account exists but DefaultRipple is NOT enabled — peer transfers will fail"
            else:
                issuer_error = f"Issuer account {settings.RLUSD_ISSUER} not found on {settings.XRPL_NETWORK} — re-fund and update RLUSD_ISSUER"
        except Exception as exc:
            issuer_error = str(exc)
    elif not settings.RLUSD_ISSUER:
        issuer_error = "RLUSD_ISSUER is not configured"

    return _success(
        "Service health",
        {
            "status": "ok" if xrpl_ready and issuer_ready else "degraded",
            "app": settings.APP_NAME,
            "network": settings.XRPL_NETWORK,
            "xrpl_rpc_url": settings.XRPL_RPC_URL,
            "xrpl_ready": xrpl_ready,
            "xrpl_error": xrpl_error,
            "issuer_ready": issuer_ready,
            "issuer_error": issuer_error,
            "issuer_address": settings.RLUSD_ISSUER or None,
        },
    )
