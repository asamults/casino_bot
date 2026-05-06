"""Pydantic response/request models for Admin API v1."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    balance: float


class SubscriptionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider: str
    status: str
    plan_code: str
    current_period_end: datetime | None
    cancel_at_period_end: bool = False
    entitlement_active: bool = False
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None
    # external_subscription_id omitted (provider secret / token-like)


class UserListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    is_active: bool
    internal_note: str | None
    telegram_user_id: int | None
    whatsapp_phone_e164: str | None
    billing_customer_id: str | None


class UserDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    is_active: bool
    internal_note: str | None
    telegram_user_id: int | None
    whatsapp_phone_e164: str | None
    billing_customer_id: str | None
    token_account: TokenAccountOut | None
    subscriptions: list[SubscriptionSummaryOut]


class UsersListResponse(BaseModel):
    items: list[UserListItemOut]
    total: int


class UserCreateBody(BaseModel):
    internal_note: str | None = Field(None, max_length=512)
    telegram_user_id: int | None = None
    whatsapp_phone_e164: str | None = Field(None, max_length=32)
    billing_customer_id: str | None = Field(None, max_length=255)


class TokenAdjustBody(BaseModel):
    delta: float
    reason: str = Field(..., min_length=1, max_length=255)


class AuditLogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor: str
    action: str
    details: dict | list | None
    created_at: datetime | None


class AuditLogsListResponse(BaseModel):
    items: list[AuditLogItemOut]
    total: int


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime | None


class AdminsListResponse(BaseModel):
    items: list[AdminUserOut]
    total: int


class AdminCreateBody(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(..., description="admin or superadmin")


class AdminPatchBody(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AdminPasswordResetBody(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class MePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class SubscriptionListResponse(BaseModel):
    items: list[SubscriptionSummaryOut]
    total: int


class ActivateTestPlanBody(BaseModel):
    plan_code: str = Field("test_plan", min_length=1, max_length=64)
    period_days: int = Field(30, ge=1, le=3650)


class LinkSubscriptionBody(BaseModel):
    provider: str = Field(..., min_length=1, max_length=32)
    provider_customer_id: str | None = Field(default=None, max_length=255)
    provider_subscription_id: str | None = Field(default=None, max_length=255)
    plan_code: str = Field("manual_link", min_length=1, max_length=64)
    status: str = Field("active", min_length=1, max_length=32)


class BillingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider: str
    external_event_id: str
    event_type: str
    received_at: datetime
    processed_at: datetime | None
    status: str
    attempts_count: int
    dead_letter: bool
    last_attempt_at: datetime | None = None
    last_error_code: str | None = None


class BillingEventsListResponse(BaseModel):
    items: list[BillingEventOut]
    total: int


class BillingEventsCleanupResponse(BaseModel):
    deleted: int = Field(..., ge=0)
    cutoff: str
    note: str = Field(
        default=(
            "Cleanup only deletes terminal safe statuses: processed, ignored, idempotent. "
            "failed/dead_letter are intentionally retained."
        )
    )
