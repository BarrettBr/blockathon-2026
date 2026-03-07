"""Health handler."""

from fastapi import APIRouter

import core
from schemas import ApiResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse)
def health():
    return core.health()
