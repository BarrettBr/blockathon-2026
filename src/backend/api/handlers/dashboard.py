"""Dashboard/history/spending-guard handlers."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import core
from db import get_db
from schemas import ApiResponse, SpendingGuardSetRequest


router = APIRouter(tags=["dashboard"])


@router.post("/spending-guard/set", response_model=ApiResponse)
def set_spending_guard(payload: SpendingGuardSetRequest, db: Session = Depends(get_db)):
    return core.set_spending_guard(payload, db)


@router.get("/spending-guard/{user_wallet_address}", response_model=ApiResponse)
def get_spending_guard(user_wallet_address: str, db: Session = Depends(get_db)):
    return core.get_spending_guard(user_wallet_address, db)


@router.get("/history/{user_wallet_address}", response_model=ApiResponse)
def get_user_history(
    user_wallet_address: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return core.get_user_history(user_wallet_address, limit, db)


@router.get("/dashboard/{user_wallet_address}", response_model=ApiResponse)
def get_dashboard(user_wallet_address: str, db: Session = Depends(get_db)):
    return core.get_dashboard(user_wallet_address, db)
