"""Stable idempotency keys for Telegram-driven game rounds (Phase 3 / 4A).

Contract (single source of truth is ``game_rounds``):

- Commands: ``tg:{telegram_user_id}:cmd:{update_id}`` — one flip per ``update_id``.
- Callbacks: ``tg:{telegram_user_id}:cb:{callback_query.id}`` — Telegram guarantees
  ``callback_query.id`` uniqueness per bot; duplicate deliveries replay the same round.

See ``docs/telegram-local-run.md`` (Phase 4A — Idempotency) for edge cases.
"""


def command_idempotency_key(*, telegram_user_id: int, update_id: int) -> str:
    return f"tg:{telegram_user_id}:cmd:{update_id}"


def callback_idempotency_key(*, telegram_user_id: int, callback_query_id: str) -> str:
    return f"tg:{telegram_user_id}:cb:{callback_query_id}"
