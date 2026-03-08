"""Main app wiring and local run entrypoint."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models.requests import AccountInfo

from api import router as api_router
from config import settings
from db import init_db

logger = logging.getLogger("equipay")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize resources once at startup."""
    init_db()
    await _check_issuer()
    yield


async def _check_issuer():
    if not settings.RLUSD_ISSUER:
        logger.warning("⚠️  RLUSD_ISSUER is not configured")
        return
    try:
        client = AsyncJsonRpcClient(settings.XRPL_RPC_URL)
        response = await client.request(
            AccountInfo(account=settings.RLUSD_ISSUER, ledger_index="current")
        )
        result = response.result
        if "account_data" not in result:
            logger.warning(f"⚠️  RLUSD issuer {settings.RLUSD_ISSUER} NOT FOUND on {settings.XRPL_NETWORK} — re-fund and update RLUSD_ISSUER in .env")
        else:
            flags = result["account_data"].get("Flags", 0)
            if not (flags & 0x00800000):
                logger.warning(f"⚠️  RLUSD issuer {settings.RLUSD_ISSUER} exists but DefaultRipple is OFF")
            else:
                logger.info(f"✅  RLUSD issuer {settings.RLUSD_ISSUER} OK")
    except Exception as exc:
        logger.warning(f"⚠️  Could not verify RLUSD issuer: {exc}")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Enable browser preflight/JSON requests from local frontend hosts.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)

static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
