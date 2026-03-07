"""Pydantic request/response schemas for EquiPay API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class WalletImportRequest(BaseModel):
    seed: str = Field(..., min_length=8)


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


class SubscriptionCreateRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    merchant_wallet_address: str = Field(..., min_length=25)
    user_seed: str = Field(..., min_length=8)
    amount_xrp: float = Field(..., gt=0)
    interval_days: int = Field(30, ge=1)
    use_escrow: bool = True


class UserHandshakeApproveRequest(BaseModel):
    user_seed: str = Field(..., min_length=8)


class ServiceHandshakeApproveRequest(BaseModel):
    merchant_seed: Optional[str] = None


class SubscriptionProcessRequest(BaseModel):
    merchant_seed: Optional[str] = None


class SpendingGuardSetRequest(BaseModel):
    user_wallet_address: str = Field(..., min_length=25)
    monthly_limit: float = Field(..., ge=0)
    currency: str = Field(default="RLUSD", min_length=3, max_length=16)


class ApiResponse(BaseModel):
    message: str
    data: Any
