"""Payment handlers."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

import core
from db import get_db
from handlers.auth import get_current_user
from schemas import ApiResponse, PaymentSendRequest, RlusdPaymentSendRequest, UserProfileSchema


router = APIRouter(tags=["payments"])


@router.post("/payments/send", response_model=ApiResponse)
def send_payment(
    request: Request,
    payload: PaymentSendRequest,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user)
):
    return core.send_payment(payload, db, request)


@router.post("/payments/send-rlusd", response_model=ApiResponse)
def send_rlusd_payment(
    request: Request,
    payload: RlusdPaymentSendRequest,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user)
):
    return core.send_rlusd_payment(payload, db, request)


@router.get("/payments", response_model=ApiResponse)
def list_payments(db: Session = Depends(get_db), current_user: UserProfileSchema = Depends(get_current_user)):
    return core.list_payments(db)


@router.get("/payments/{tx_hash}", response_model=ApiResponse)
def get_payment(tx_hash: str):
    return core.get_payment(tx_hash)
