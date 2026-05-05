from __future__ import annotations

import hashlib
import hmac
import json
import secrets

from fastapi import HTTPException

from casino_bot.billing.providers.base import (
    BillingProviderAdapter,
    CheckoutSessionResult,
    NormalizedBillingEvent,
    NotImplementedForProvider,
    PortalSessionResult,
)
from casino_bot.settings import settings


class PaddleAdapter(BillingProviderAdapter):
    provider_name = "paddle"

    def verify_signature(self, headers: dict[str, str], raw_body: bytes) -> None:
        if not settings.PADDLE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=503, detail="Billing temporarily unavailable"
            )
        signature = headers.get("paddle-signature", "")
        expected = hmac.new(
            settings.PADDLE_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    def parse_event(self, raw_body: bytes) -> NormalizedBillingEvent:
        payload = json.loads(raw_body.decode("utf-8"))
        # TODO: Expand Paddle event coverage when Paddle becomes primary.
        return NormalizedBillingEvent(
            provider=self.provider_name,
            external_event_id=str(payload.get("event_id") or payload.get("id") or ""),
            event_type=str(payload.get("event_type") or payload.get("type") or ""),
            occurred_at=None,
            customer_id=payload.get("customer_id"),
            subscription_id=payload.get("subscription_id"),
            status=payload.get("status"),
            plan_code=payload.get("plan_code"),
            current_period_end=None,
            cancel_at_period_end=bool(payload.get("cancel_at_period_end")),
            user_hint=None,
            raw=payload,
        )

    def parse_and_verify_webhook(
        self, *, headers: dict[str, str], raw_body: bytes
    ) -> NormalizedBillingEvent:
        self.verify_signature(headers, raw_body)
        return self.parse_event(raw_body)

    def create_or_get_customer(
        self, *, user_id: int, email_hint: str | None, existing_customer_id: str | None
    ) -> str:
        if existing_customer_id:
            return existing_customer_id
        return f"paddle_cus_{user_id}_{secrets.token_hex(6)}"

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        plan_code: str,
        success_url: str,
        cancel_url: str,
        user_id: int,
    ) -> CheckoutSessionResult:
        raise NotImplementedForProvider("Paddle checkout session not implemented yet")

    def create_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> PortalSessionResult:
        raise NotImplementedForProvider("Paddle portal session not implemented yet")

    def cancel_subscription(self, *, provider_subscription_id: str) -> dict:
        raise NotImplementedForProvider(
            "Paddle cancel subscription not implemented yet"
        )

    def resume_subscription(self, *, provider_subscription_id: str) -> dict:
        raise NotImplementedForProvider(
            "Paddle resume subscription not implemented yet"
        )

    def normalize_status(self, provider_status: str | None) -> str:
        return provider_status or "unknown"
