"""Grouped API handlers."""

from fastapi import APIRouter

from handlers.dashboard import router as dashboard_router
from handlers.health import router as health_router
from handlers.payments import router as payments_router
from handlers.subscriptions import router as subscriptions_router
from handlers.wallets import router as wallets_router
from handlers.auth import router as auth_router


router = APIRouter()
router.include_router(health_router)
router.include_router(wallets_router)
router.include_router(payments_router)
router.include_router(subscriptions_router)
router.include_router(dashboard_router)
router.include_router(auth_router)
