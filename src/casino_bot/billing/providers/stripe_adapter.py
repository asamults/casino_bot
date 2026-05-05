from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException

from casino_bot.billing.providers.base import (
    BillingProviderAdapter,
    CheckoutSessionResult,
    NormalizedBillingEvent,
    PortalSessionResult,
)
from casino_bot.settings import settings


class StripeAdapter(BillingProviderAdapter):
    provider_name = "stripe"

    def verify_signature(self, headers: dict[str, str], raw_body: bytes) -> None:
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=503, detail="Billing temporarily unavailable"
            )
        sig_header = headers.get("stripe-signature", "")
        parts = {}
        for item in sig_header.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                parts[k.strip()] = v.strip()
        ts = parts.get("t")
        signature = parts.get("v1")
        if not ts or not signature:
            raise HTTPException(status_code=401, detail="Invalid signature")
        if (
            abs(int(datetime.now(tz=UTC).timestamp()) - int(ts))
            > settings.BILLING_WEBHOOK_TOLERANCE_SECONDS
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")
        signed_payload = f"{ts}.{raw_body.decode('utf-8')}".encode("utf-8")
        expected = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    def parse_and_verify_webhook(
        self, *, headers: dict[str, str], raw_body: bytes
    ) -> NormalizedBillingEvent:
        self.verify_signature(headers, raw_body)
        return self.parse_event(raw_body)

    def parse_event(self, raw_body: bytes) -> NormalizedBillingEvent:
        payload = json.loads(raw_body.decode("utf-8"))
        data = payload.get("data", {}).get("object", {})
        metadata = data.get("metadata") or {}
        plan = (
            data.get("items", {})
            .get("data", [{}])[0]
            .get("price", {})
            .get("lookup_key")
        )
        period_end = data.get("current_period_end")
        status = _normalize_status(data.get("status"))
        return NormalizedBillingEvent(
            provider=self.provider_name,
            external_event_id=str(payload.get("id") or ""),
            event_type=str(payload.get("type") or ""),
            occurred_at=_to_dt(payload.get("created")),
            customer_id=data.get("customer"),
            subscription_id=data.get("id"),
            status=status,
            plan_code=plan or data.get("plan", {}).get("id"),
            current_period_end=_to_dt(period_end),
            cancel_at_period_end=bool(data.get("cancel_at_period_end")),
            user_hint=_to_int(metadata.get("user_id")),
            raw=payload,
        )

    def create_or_get_customer(
        self, *, user_id: int, email_hint: str | None, existing_customer_id: str | None
    ) -> str:
        if existing_customer_id:
            return existing_customer_id
        return f"cus_{user_id}_{secrets.token_hex(6)}"

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        plan_code: str,
        success_url: str,
        cancel_url: str,
        user_id: int,
    ) -> CheckoutSessionResult:
        session_id = f"cs_test_{secrets.token_hex(10)}"
        checkout_url = (
            f"https://checkout.stripe.test/{session_id}?plan={plan_code}&uid={user_id}"
        )
        return CheckoutSessionResult(
            provider=self.provider_name,
            checkout_url=checkout_url,
            session_id=session_id,
            customer_id=customer_id,
        )

    def create_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> PortalSessionResult:
        return PortalSessionResult(
            provider=self.provider_name,
            portal_url=f"https://billing.stripe.test/portal/{customer_id}?return_url={return_url}",
        )

    def cancel_subscription(self, *, provider_subscription_id: str) -> dict:
        return {
            "status": "active",
            "cancel_at_period_end": True,
            "provider_subscription_id": provider_subscription_id,
        }

    def resume_subscription(self, *, provider_subscription_id: str) -> dict:
        return {
            "status": "active",
            "cancel_at_period_end": False,
            "provider_subscription_id": provider_subscription_id,
        }

    def normalize_status(self, provider_status: str | None) -> str:
        return _normalize_status(provider_status)


def _to_dt(value) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_status(stripe_status: str | None) -> str | None:
    mapping = {
        "active": "active",
        "trialing": "trialing",
        "canceled": "canceled",
        "past_due": "past_due",
        "unpaid": "past_due",
        "incomplete_expired": "canceled",
        "paused": "paused",
    }
    return mapping.get(stripe_status or "", "unknown")
