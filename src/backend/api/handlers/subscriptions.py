"""Subscription handlers."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import core
from db import get_db
from schemas import (
    ApiResponse,
    ServiceHandshakeApproveRequest,
    SubscriptionCreateRequest,
    SubscriptionProcessRequest,
    UserHandshakeApproveRequest,
)


router = APIRouter(tags=["subscriptions"])


@router.post("/subscriptions/create", response_model=ApiResponse)
def create_subscription(payload: SubscriptionCreateRequest, db: Session = Depends(get_db)):
    return core.create_subscription(payload, db)


@router.post("/subscriptions/{subscription_id}/handshake/user-approve", response_model=ApiResponse)
def user_approve_subscription_handshake(
    subscription_id: int,
    payload: UserHandshakeApproveRequest,
    db: Session = Depends(get_db),
):
    return core.user_approve_subscription_handshake(subscription_id, payload, db)


@router.post("/subscriptions/{subscription_id}/handshake/service-approve", response_model=ApiResponse)
def service_approve_subscription_handshake(
    subscription_id: int,
    payload: ServiceHandshakeApproveRequest,
    db: Session = Depends(get_db),
):
    return core.service_approve_subscription_handshake(subscription_id, payload, db)


@router.get("/subscriptions", response_model=ApiResponse)
def list_subscriptions(db: Session = Depends(get_db)):
    return core.list_subscriptions(db)


@router.get("/subscriptions/user/{user_wallet_address}", response_model=ApiResponse)
def list_subscriptions_for_user(user_wallet_address: str, db: Session = Depends(get_db)):
    return core.list_subscriptions_for_user(user_wallet_address, db)


@router.get("/subscriptions/{subscription_id}", response_model=ApiResponse)
def get_subscription(subscription_id: int, db: Session = Depends(get_db)):
    return core.get_subscription(subscription_id, db)


@router.post("/subscriptions/{subscription_id}/process", response_model=ApiResponse)
def process_subscription(
    subscription_id: int,
    payload: Optional[SubscriptionProcessRequest] = None,
    db: Session = Depends(get_db),
):
    return core.process_subscription(subscription_id, payload, db)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=ApiResponse)
def cancel_subscription(subscription_id: int, db: Session = Depends(get_db)):
    return core.cancel_subscription(subscription_id, db)
