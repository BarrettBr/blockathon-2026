"""Pydantic request/response schemas for EquiPay API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class WalletImportRequest(BaseModel):
    seed: str = Field(..., min_length=8)


class WalletConnectRequest(BaseModel):
    seed: str = Field(..., min_length=8)
    nickname: str = Field(..., min_length=2, max_length=64)


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
    from_address: str
    destination_address: str
    amount_xrp: float

class RlusdPaymentSendRequest(BaseModel):
    from_address: str
    destination_address: str
    amount: float

class BootstrapRlusdRequest(BaseModel):
    user_wallet_address: str
    mint_amount: float

class SubscriptionRequestCreateRequest(BaseModel):
    vendor_tx_id: str = Field(..., min_length=2, max_length=128)
    username: str = Field(..., min_length=3, max_length=128)
    amount_xrp: float = Field(..., gt=0)
    interval_days: int = Field(30, ge=1)


class SubscriptionApproveRequest(BaseModel):
    username: str

class SubscriptionProcessCycleRequest(BaseModel):
    username: str

class SubscriptionCancelRequest(BaseModel):
    username: Optional[str] = None

class SpendingGuardSetRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    monthly_limit: float = Field(..., ge=0)
    currency: str = Field(default="RLUSD", min_length=3, max_length=16)


class SnapshotCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=256)
    days: Optional[int] = Field(default=None, ge=1, le=3650)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SnapshotAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)


class ApiResponse(BaseModel):
    message: str
    data: Any

class UserProfileSchema(BaseModel):
    id: int
    username: str
    wallet_address: str

    class Config:
        from_attributes = True
