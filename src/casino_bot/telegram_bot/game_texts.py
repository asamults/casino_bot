"""Telegram copy for the coin flip flow (Phase 3 / 4A polish)."""

from __future__ import annotations

from typing import Any

FLIP_HELP_LINE = (
    "/flip — Coin flip (quick-stake buttons only show amounts you can afford, "
    "or /flip <amount> with a whole number)"
)

ROUNDS_HELP_LINE = "/rounds — Recent committed coin flip rounds (UTC, capped)"

AUDIO_STUB_LINE = "Audio prize delivery in Telegram is not wired yet — text only."


def flip_keyboard_caption() -> str:
    return (
        "Coin flip (even money): tap a quick stake (buttons show only amounts you can afford).\n"
        "Each tap is one round. Win credits your stake; lose debits your stake.\n"
        "Or send /flip <whole number> between min and max (server settings).\n"
        f"{AUDIO_STUB_LINE}"
    )


def flip_no_quick_stakes_message() -> str:
    return (
        "You do not have enough tokens for any of the quick stakes (1 / 5 / 10). "
        "Try /balance, or /flip <amount> once you have enough for that stake."
    )


TELEGRAM_RATE_LIMITED_MESSAGE = (
    "Too many requests. Please slow down and try again shortly."
)


GAME_ENGINE_REJECT_USER_MESSAGES: dict[str, str] = {
    "bet_below_min": "That stake is below the minimum allowed for this game.",
    "bet_above_max": "That stake is above the maximum allowed for this game.",
    "game_disabled": "This game is not available right now.",
    "unknown_game": "This game is not available right now.",
    "insufficient_balance": (
        "Not enough tokens for that stake. Check /balance or use a smaller amount."
    ),
}


def game_engine_rejected_user_message(
    code: str,
    *,
    cooldown_remaining_seconds: int | None = None,
) -> str:
    if code == "cooldown_active" and cooldown_remaining_seconds is not None:
        return (
            "Cooldown active — try again in about "
            f"{cooldown_remaining_seconds} second(s)."
        )
    return GAME_ENGINE_REJECT_USER_MESSAGES.get(
        code,
        "This action cannot be completed. Try a different stake or try again later.",
    )


def flip_usage_hint() -> str:
    return (
        "Usage: /flip <whole number> (tokens), or use the buttons below.\n"
        "Example: /flip 10"
    )


def flip_result_compact(
    *,
    stake_tokens: int,
    outcome: str,
    balance_line: str,
    idempotent_replay: bool,
) -> str:
    """Unified committed-round layout (Phase 4A)."""
    result_word = "Win" if outcome == "win" else "Lose"
    lines = [
        "Coin flip",
        f"Stake: {stake_tokens} tokens",
        f"Result: {result_word}",
        balance_line,
    ]
    body = "\n".join(lines)
    if outcome == "win":
        body += f"\n\n{AUDIO_STUB_LINE}"
    if idempotent_replay:
        body += "\n\n(Already processed — duplicate tap.)"
    return body


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


def rounds_history_header(*, limit: int) -> str:
    return f"Last {limit} committed round(s), UTC (newest first):"


def rounds_empty_message() -> str:
    return "No committed coin flip rounds yet. Play with /flip."
