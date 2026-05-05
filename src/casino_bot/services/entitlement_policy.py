from __future__ import annotations

from casino_bot.services.entitlement import require_active_entitlement

# Central map for paywalled write operations.
PAYWALL_POLICY: dict[str, bool] = {
    "user.tokens.adjust": True,
    "billing.checkout.session": False,
    "billing.subscription.cancel": False,
    "billing.subscription.resume": False,
    "billing.portal.create": False,
}


def enforce_if_required(operation: str, *, db, user_id: int) -> None:
    if not PAYWALL_POLICY.get(operation, False):
        return
    require_active_entitlement(db, user_id=user_id)
