from casino_bot.billing.providers.base import (
    BillingProviderAdapter,
    CheckoutSessionResult,
    NormalizedBillingEvent,
    NotImplementedForProvider,
    PortalSessionResult,
)
from casino_bot.billing.providers.paddle_adapter import PaddleAdapter
from casino_bot.billing.providers.stripe_adapter import StripeAdapter
from casino_bot.settings import settings

PROVIDER_ADAPTERS: dict[str, BillingProviderAdapter] = {
    "stripe": StripeAdapter(),
    "paddle": PaddleAdapter(),
}


def get_primary_provider_adapter() -> BillingProviderAdapter:
    return PROVIDER_ADAPTERS[settings.BILLING_PROVIDER_PRIMARY]


__all__ = [
    "BillingProviderAdapter",
    "CheckoutSessionResult",
    "NormalizedBillingEvent",
    "NotImplementedForProvider",
    "PortalSessionResult",
    "PROVIDER_ADAPTERS",
    "get_primary_provider_adapter",
]
