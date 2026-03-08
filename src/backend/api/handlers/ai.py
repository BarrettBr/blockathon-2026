"""AI review handler."""
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import core
from handlers.auth import get_current_user
from db import get_db
from schemas import ApiResponse, UserProfileSchema

router = APIRouter(tags=["ai"])


class AiReviewRequest(BaseModel):
    wallet_addresses: list[str]
    days: int = 30

@router.post("/ai/review", response_model=ApiResponse)
def ai_review(
    payload: AiReviewRequest,
    current_user: UserProfileSchema = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return core.generate_wallet_review(payload.wallet_addresses, payload.days, db)
