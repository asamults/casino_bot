"""Stable idempotency keys for Telegram-driven game rounds (Phase 3)."""


def command_idempotency_key(*, telegram_user_id: int, update_id: int) -> str:
    return f"tg:{telegram_user_id}:cmd:{update_id}"


def callback_idempotency_key(*, telegram_user_id: int, callback_query_id: str) -> str:
    return f"tg:{telegram_user_id}:cb:{callback_query_id}"
