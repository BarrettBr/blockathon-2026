"""Subscription handlers."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session
from handlers.auth import get_current_user

import core
from db import get_db
from schemas import (
    ApiResponse,
    SubscriptionApproveRequest,
    SubscriptionCancelRequest,
    SubscriptionClaimCycleRequest,
    SubscriptionProcessCycleRequest,
    SubscriptionRefundCycleRequest,
    SubscriptionRequestCreateRequest,
    UserProfileRegisterRequest,
    VendorCreateRequest,
    VendorUpdateRequest,
    UserProfileSchema,
)


router = APIRouter(tags=["subscriptions"])


@router.post("/users/register", response_model=ApiResponse)
def register_user_profile(payload: UserProfileRegisterRequest, db: Session = Depends(get_db)):
    return core.register_user_profile(payload, db)


@router.post("/vendors/upsert", response_model=ApiResponse)
def upsert_vendor(payload: VendorCreateRequest, db: Session = Depends(get_db)):
    return core.upsert_vendor(payload, db)


@router.get("/vendors/me", response_model=ApiResponse)
def get_vendor_me(request: Request, db: Session = Depends(get_db)):
    return core.get_vendor_me(request, db)


@router.patch("/vendors/me", response_model=ApiResponse)
def update_vendor(request: Request, payload: VendorUpdateRequest, db: Session = Depends(get_db)):
    return core.update_vendor(request, payload, db)


@router.post("/vendors/me/secret/regenerate", response_model=ApiResponse)
def regenerate_vendor_secret(request: Request, db: Session = Depends(get_db)):
    return core.regenerate_vendor_secret(request, db)


@router.post("/vendors/me/photo", response_model=ApiResponse)
def upload_vendor_photo(
    request: Request,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return core.upload_vendor_photo(request, photo, db)


@router.post("/subscriptions/requests", response_model=ApiResponse)
def create_subscription_request(
    request: Request,
    payload: SubscriptionRequestCreateRequest,
    db: Session = Depends(get_db),
):
    return core.create_subscription_request(request, payload, db)


@router.get("/subscriptions/pending/{username}", response_model=ApiResponse)
def list_pending_subscription_requests(username: str, db: Session = Depends(get_db)):
    return core.list_pending_subscription_requests(username, db)


@router.post("/subscriptions/{subscription_id}/approve", response_model=ApiResponse)
def approve_subscription_request(
    subscription_id: int,
    payload: SubscriptionApproveRequest,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    if not payload.username:
        payload.username = current_user.username
    return core.approve_subscription_request(subscription_id, payload, db)


@router.get("/subscriptions/{subscription_id}/cycles", response_model=ApiResponse)
def list_subscription_cycles(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    return core.list_subscription_cycles(subscription_id, db)


@router.post("/subscriptions/{subscription_id}/cycles/process", response_model=ApiResponse)
def process_subscription_cycle(
    subscription_id: int,
    payload: SubscriptionProcessCycleRequest,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    return core.process_subscription_cycle(subscription_id, payload, db)


@router.post("/subscriptions/{subscription_id}/cycles/{cycle_id}/claim", response_model=ApiResponse)
def claim_subscription_cycle(
    subscription_id: int,
    cycle_id: int,
    payload: SubscriptionClaimCycleRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return core.claim_subscription_cycle(subscription_id, cycle_id, payload, request, db)


@router.post("/subscriptions/{subscription_id}/cycles/{cycle_id}/refund", response_model=ApiResponse)
def refund_subscription_cycle(
    subscription_id: int,
    cycle_id: int,
    payload: SubscriptionRefundCycleRequest,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    if not payload.username:
        payload.username = current_user.username
    return core.refund_subscription_cycle(subscription_id, cycle_id, payload, db)


@router.get("/subscriptions/{subscription_id}", response_model=ApiResponse)
def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user)
):
    return core.get_subscription(subscription_id, db)


@router.get("/subscriptions/contract/{contract_hash}", response_model=ApiResponse)
def get_subscription_by_contract(
    contract_hash: str,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    return core.get_subscription_by_contract(contract_hash, db)


@router.get("/subscriptions", response_model=ApiResponse)
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    return core.list_subscriptions(db)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=ApiResponse)
def cancel_subscription(
    subscription_id: int,
    request: Request,
    payload: Optional[SubscriptionCancelRequest] = None,
    db: Session = Depends(get_db),
    current_user: UserProfileSchema = Depends(get_current_user),
):
    header_name = core.settings.VENDOR_SHARED_SECRET_HEADER
    vendor_secret = request.headers.get(header_name, "").strip()
    effective_payload = payload or SubscriptionCancelRequest()
    if not vendor_secret and not effective_payload.username:
        effective_payload.username = current_user.username
    return core.cancel_subscription_request(subscription_id, request, effective_payload, db)
