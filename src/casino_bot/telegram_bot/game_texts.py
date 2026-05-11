"""Telegram copy for the coin flip flow (Phase 3)."""

from __future__ import annotations

from typing import Any

FLIP_HELP_LINE = "/flip — Play coin flip (buttons 1 / 5 / 10 tokens, or /flip <amount> with a whole number)"


def flip_keyboard_caption() -> str:
    return (
        "Coin flip (even money): tap a stake in tokens (1 / 5 / 10). Each tap is one round.\n"
        "Win credits your stake; lose debits your stake.\n"
        "Or send /flip <whole number> between min and max (server settings).\n"
        "Audio prizes are not delivered in Telegram yet — text only for now."
    )


GAME_ENGINE_REJECT_USER_MESSAGES: dict[str, str] = {
    "bet_below_min": "That stake is below the minimum allowed for this game.",
    "bet_above_max": "That stake is above the maximum allowed for this game.",
    "cooldown_active": "Please wait a moment before flipping again (cooldown).",
    "game_disabled": "This game is not available right now.",
    "unknown_game": "This game is not available right now.",
}


def game_engine_rejected_user_message(code: str) -> str:
    return GAME_ENGINE_REJECT_USER_MESSAGES.get(
        code,
        "This action cannot be completed. Try a different stake or try again later.",
    )


def flip_usage_hint() -> str:
    return (
        "Usage: /flip <whole number> (tokens), or use the buttons below.\n"
        "Example: /flip 10"
    )


def flip_win_message(*, balance_line: str) -> str:
    return (
        "You won this round (even money).\n"
        "Audio prize delivery in Telegram is not wired yet — coming later.\n\n"
        f"{balance_line}"
    )


def flip_lose_message(*, balance_line: str) -> str:
    return f"You lost this round.\n\n{balance_line}"


def flip_rejected_round_user_message(details: dict[str, Any] | None) -> str:
    """Map persisted rejection from round ledger to a safe user string."""
    if not details:
        return "This round could not be completed. Check your balance and try again."
    reason = str(details.get("rejection_reason", "") or "").lower()
    if "negative balance" in reason:
        return "Not enough tokens for that stake. Try a smaller amount or /balance."
    return "This round could not be completed. Try again later."


def flip_unexpected_error_message() -> str:
    return "Something went wrong. Please try again later."
