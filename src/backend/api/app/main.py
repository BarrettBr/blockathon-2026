"""FastAPI app initialization and router registration."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.api.subscriptions import router as subscriptions_router
from app.api.wallets import router as wallets_router
from app.config.settings import settings
from app.db import models  # noqa: F401 - Ensures model metadata is registered.
from app.db.session import Base, engine


app = FastAPI(title=settings.APP_NAME)


@app.on_event("startup")
def on_startup():
    """Create local database tables for development."""
    Base.metadata.create_all(bind=engine)


app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(wallets_router, prefix=settings.API_V1_PREFIX)
app.include_router(payments_router, prefix=settings.API_V1_PREFIX)
app.include_router(subscriptions_router, prefix=settings.API_V1_PREFIX)
