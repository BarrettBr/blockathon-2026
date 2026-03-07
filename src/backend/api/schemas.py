"""Pydantic request/response schemas for EquiPay API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class WalletImportRequest(BaseModel):
    seed: str = Field(..., min_length=8)


class UserProfileRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    wallet_address: str = Field(..., min_length=25)


class VendorCreateRequest(BaseModel):
    vendor_code: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=128)
    wallet_address: str = Field(..., min_length=25)
    webhook_url: Optional[str] = Field(default=None, max_length=512)
    shared_secret: Optional[str] = Field(default=None, min_length=8, max_length=256)


class VendorUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    wallet_address: Optional[str] = Field(default=None, min_length=25)
    webhook_url: Optional[str] = Field(default=None, max_length=512)


class PaymentSendRequest(BaseModel):
    sender_seed: str = Field(..., min_length=8)
    destination_address: str = Field(..., min_length=25)
    amount_xrp: float = Field(..., gt=0)


class RlusdPaymentSendRequest(BaseModel):
    sender_seed: str = Field(..., min_length=8)
    destination_address: str = Field(..., min_length=25)
    amount: float = Field(..., gt=0)


class BootstrapRlusdRequest(BaseModel):
    user_seed: str = Field(..., min_length=8)
    mint_amount: float = Field(default=100.0, gt=0)


class SubscriptionRequestCreateRequest(BaseModel):
    vendor_tx_id: str = Field(..., min_length=2, max_length=128)
    username: str = Field(..., min_length=3, max_length=128)
    amount_xrp: float = Field(..., gt=0)
    interval_days: int = Field(30, ge=1)


class SubscriptionApproveRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    user_seed: str = Field(..., min_length=8)


class SubscriptionCancelRequest(BaseModel):
    username: Optional[str] = None
    user_seed: Optional[str] = None


class SpendingGuardSetRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    monthly_limit: float = Field(..., ge=0)
    currency: str = Field(default="RLUSD", min_length=3, max_length=16)


class ApiResponse(BaseModel):
    message: str
    data: Any
