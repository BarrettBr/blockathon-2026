"""Payment handlers."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import core
from db import get_db
from schemas import ApiResponse, PaymentSendRequest, RlusdPaymentSendRequest


router = APIRouter(tags=["payments"])


@router.post("/payments/send", response_model=ApiResponse)
def send_payment(payload: PaymentSendRequest, db: Session = Depends(get_db)):
    return core.send_payment(payload, db)


@router.post("/payments/send-rlusd", response_model=ApiResponse)
def send_rlusd_payment(payload: RlusdPaymentSendRequest, db: Session = Depends(get_db)):
    return core.send_rlusd_payment(payload, db)


@router.get("/payments", response_model=ApiResponse)
def list_payments(db: Session = Depends(get_db)):
    return core.list_payments(db)


@router.get("/payments/{tx_hash}", response_model=ApiResponse)
def get_payment(tx_hash: str):
    return core.get_payment(tx_hash)
