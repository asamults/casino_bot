"""User-visible Telegram copy (pure functions for reuse in tests)."""

from __future__ import annotations

from casino_bot.telegram_bot import game_texts


BALANCE_UNAVAILABLE = "Balance unavailable — your token account is not initialized yet."

NOT_LINKED_BALANCE = "Balance unavailable — send /start to link your account first."

NOT_LINKED_PROFILE = "Profile unavailable — send /start to link your account first."

GENERIC_SUPPORT_LINE = "For help, contact your operator through the support channel configured for your deployment."


def welcome_message(*, internal_user_id: int) -> str:
    return (
        "Welcome! Your Telegram account is linked to this bot.\n\n"
        f"Internal user id: {internal_user_id}.\n\n"
        "Use /help for available commands."
    )


def help_message() -> str:
    from casino_bot.games.bonus_wheel import BONUS_WHEEL_GAME_ID
    from casino_bot.settings import settings

    wheel_help = ""
    if BONUS_WHEEL_GAME_ID in settings.GAMES_ENABLED:
        wheel_help = f"{game_texts.WHEEL_HELP_LINE}\n"
    return (
        "Available commands:\n"
        "/start — Register or reconnect (links your Telegram account)\n"
        "/help — Show this message\n"
        "/me — Show your Telegram id and linked internal user id\n"
        "/balance — Show your token balance (if initialized)\n"
        f"{game_texts.GAMES_HELP_LINE}\n"
        f"{game_texts.FLIP_HELP_LINE}\n"
        f"{wheel_help}"
        f"{game_texts.ROUNDS_HELP_LINE}\n"
        "/status — Liveness vs database readiness (high level)\n"
        "/profile — Your linked account summary (non-sensitive fields)\n"
        "/admin — Where admin tools live (not in Telegram)\n"
        "/support — How to get help for this deployment"
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


def status_summary_text(*, database_ready: bool) -> str:
    """Human-readable liveness vs readiness (Telegram-facing; keep high level)."""
    db_line = "ok" if database_ready else "unavailable"
    return f"Liveness: ok\nDatabase readiness: {db_line}"


def profile_message(
    *,
    internal_user_id: int,
    telegram_user_id: int,
    is_active: bool,
    created_at_iso: str,
) -> str:
    active_word = "active" if is_active else "inactive"
    return (
        f"User id: {internal_user_id}\n"
        f"Telegram user id: {telegram_user_id}\n"
        f"Account: {active_word}\n"
        f"Created: {created_at_iso}"
    )


def admin_message() -> str:
    return (
        "Admin actions are not available via Telegram.\n\n"
        "Use the HTTP Admin API under /api/v1/admin/ (see the project README). "
        "Sign in via POST /api/v1/admin/login from a trusted client — do not send "
        "credentials or tokens in this chat."
    )


def support_reply(*, support_text: str, contact_url: str) -> str:
    """Build /support body from configured settings (both may be empty)."""
    chunks: list[str] = []
    st = support_text.strip()
    if st:
        chunks.append(st)
    cu = contact_url.strip()
    if cu:
        chunks.append(f"Contact link: {cu}")
    if not chunks:
        return GENERIC_SUPPORT_LINE
    return "\n\n".join(chunks)
