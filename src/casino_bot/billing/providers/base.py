from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass
class NormalizedBillingEvent:
    provider: str
    external_event_id: str
    event_type: str
    occurred_at: datetime | None
    customer_id: str | None
    subscription_id: str | None
    status: str | None
    plan_code: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    user_hint: int | None
    raw: dict[str, Any]


@dataclass
class CheckoutSessionResult:
    provider: str
    checkout_url: str
    session_id: str
    customer_id: str


@dataclass
class PortalSessionResult:
    provider: str
    portal_url: str


class NotImplementedForProvider(Exception):
    pass


class BillingProviderAdapter(Protocol):
    provider_name: str

    def verify_signature(self, headers: dict[str, str], raw_body: bytes) -> None: ...

    def parse_event(self, raw_body: bytes) -> NormalizedBillingEvent: ...

    def parse_and_verify_webhook(
        self, *, headers: dict[str, str], raw_body: bytes
    ) -> NormalizedBillingEvent: ...

    def create_or_get_customer(
        self, *, user_id: int, email_hint: str | None, existing_customer_id: str | None
    ) -> str: ...

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        plan_code: str,
        success_url: str,
        cancel_url: str,
        user_id: int,
    ) -> CheckoutSessionResult: ...

    def create_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> PortalSessionResult: ...

    def cancel_subscription(
        self, *, provider_subscription_id: str
    ) -> dict[str, Any]: ...

    def resume_subscription(
        self, *, provider_subscription_id: str
    ) -> dict[str, Any]: ...

    def normalize_status(self, provider_status: str | None) -> str: ...
