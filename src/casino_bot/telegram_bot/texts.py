"""User-visible Telegram copy (pure functions for reuse in tests)."""

from __future__ import annotations


BALANCE_UNAVAILABLE = "Balance unavailable — your token account is not initialized yet."

NOT_LINKED_BALANCE = "Balance unavailable — send /start to link your account first."


def welcome_message(*, internal_user_id: int) -> str:
    return (
        "Welcome! Your Telegram account is linked to this bot.\n\n"
        f"Internal user id: {internal_user_id}.\n\n"
        "Use /help for available commands."
    )


def help_message() -> str:
    return (
        "Available commands:\n"
        "/start — Register or reconnect (links your Telegram account)\n"
        "/help — Show this message\n"
        "/me — Show your Telegram id and linked internal user id\n"
        "/balance — Show your token balance (if initialized)"
    )


def me_message(*, telegram_user_id: int, internal_user_id: int | None) -> str:
    if internal_user_id is None:
        return (
            f"Telegram user id: {telegram_user_id}\n\n"
            "Internal user id: not linked yet. Send /start to link your account."
        )
    return f"Telegram user id: {telegram_user_id}\nInternal user id: {internal_user_id}"


def format_balance_message(balance: float) -> str:
    return f"Token balance: {balance}"
