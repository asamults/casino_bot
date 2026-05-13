"""Telegram copy for the coin flip flow (Phase 3 / 4A polish)."""

from __future__ import annotations

from typing import Any

from casino_bot.games.types import GameMeta

FLIP_HELP_LINE = (
    "/flip — Coin flip (quick-stake buttons only show amounts you can afford, "
    "or /flip <amount> with a whole number)"
)

ROUNDS_HELP_LINE = "/rounds — Recent committed rounds for enabled games (UTC, capped)"

GAMES_HELP_LINE = "/games — List enabled games and stake limits"

WHEEL_HELP_LINE = (
    "/wheel — Bonus wheel (weighted tiers; quick buttons or /wheel <whole number>)"
)

WHEEL_NOT_ENABLED_MESSAGE = (
    "Bonus wheel is turned off on this bot. "
    'The operator must add "bonus_wheel" to the GAMES_ENABLED setting '
    '(JSON list, e.g. ["coin_flip","bonus_wheel"]) and restart the bot process.'
)

AUDIO_STUB_LINE = "Audio prize delivery in Telegram is not wired yet — text only."


def games_catalog_message(metas: list[GameMeta]) -> str:
    if not metas:
        return "No games are enabled on this bot deployment."
    lines = [
        "Games you can play (also see /help):",
        "",
    ]
    for m in metas:
        lines.append(f"• {m.title} — {m.description}")
        lines.append(f"  Stake: {m.min_bet}–{m.max_bet} tokens.")
        if m.game_id == "coin_flip":
            lines.append("  Play: /flip")
        elif m.game_id == "bonus_wheel":
            lines.append("  Play: /wheel")
        lines.append("")
    lines.append("Use /rounds for your recent committed rounds.")
    return "\n".join(lines).rstrip()


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


def wheel_keyboard_caption() -> str:
    return (
        "Bonus wheel: one spin, weighted tiers (bust / bronze / silver / gold).\n"
        "Tap a quick stake or send /wheel <whole number> within server min/max.\n"
        f"{AUDIO_STUB_LINE}"
    )


def wheel_no_quick_stakes_message() -> str:
    return (
        "You do not have enough tokens for any of the quick stakes (1 / 5 / 10). "
        "Try /balance, or /wheel <amount> once you have enough for that stake."
    )


def wheel_usage_hint() -> str:
    return (
        "Usage: /wheel <whole number> (tokens), or use the quick buttons.\n"
        "Example: /wheel 10"
    )


_WHEEL_TIER_LABELS = {
    "bust": "Bust (lost stake)",
    "bronze": "Bronze (+0.5× stake)",
    "silver": "Silver (+1× stake)",
    "gold": "Gold (+2.5× stake)",
}


def wheel_result_compact(
    *,
    stake_tokens: int,
    outcome: str,
    payout_delta: float,
    balance_line: str,
    idempotent_replay: bool,
) -> str:
    tier = _WHEEL_TIER_LABELS.get(outcome, outcome)
    lines = [
        "Bonus wheel",
        f"Stake: {stake_tokens} tokens",
        f"Tier: {tier}",
        f"Net change: {payout_delta:g} tokens",
        balance_line,
    ]
    body = "\n".join(lines)
    if idempotent_replay:
        body += "\n\n(Already processed — duplicate tap.)"
    return body


def rounds_empty_message() -> str:
    return "No committed rounds yet for enabled games. Try /games, /flip, or /wheel."
