"""Integer token_units helpers (Phase 7).

``TOKEN_UNIT_SCALE`` (default 1000) maps whole visible tokens to integer units:
``1`` token → ``1000`` units. Runtime economy math uses ``int`` only; floats are
used only when syncing deprecated ORM float columns for backward compatibility.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def validate_units(value: Any, *, name: str = "amount") -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be a non-boolean int, got {type(value).__name__}")
    return value


def tokens_whole_to_units(tokens: int, *, scale: int) -> int:
    """Convert whole visible tokens (non-negative int) to token_units."""
    validate_units(scale, name="scale")
    if scale < 1:
        raise ValueError("scale must be >= 1")
    t = validate_units(tokens, name="tokens")
    if t < 0:
        raise ValueError("tokens must be >= 0")
    return t * scale


def units_to_whole_tokens_floor(units: int, *, scale: int) -> int:
    """Floor whole visible tokens from units (non-negative semantics)."""
    u = validate_units(units, name="units")
    validate_units(scale, name="scale")
    if scale < 1:
        raise ValueError("scale must be >= 1")
    if u < 0:
        raise ValueError("units must be >= 0 for floor token conversion")
    return u // scale


def units_to_storage_float(units: int, *, scale: int) -> float:
    """Deprecated ORM float column sync only; do not use for arithmetic."""
    u = validate_units(units, name="units")
    validate_units(scale, name="scale")
    if scale < 1:
        raise ValueError("scale must be >= 1")
    return float(Decimal(u) / Decimal(scale))


def format_signed_token_amount(units: int, *, scale: int) -> str:
    """Human-readable signed token quantity (e.g. ``+2.5``, ``-10``) without float math."""
    validate_units(scale, name="scale")
    if scale < 1:
        raise ValueError("scale must be >= 1")
    u = validate_units(units, name="units")
    sign = "-" if u < 0 else ""
    mag = abs(u)
    q = Decimal(mag) / Decimal(scale)
    text = format(q.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{sign}{text}"


def parse_whole_tokens_to_units(raw: str, *, scale: int) -> int:
    """Parse a decimal string / int string into units; reject non-whole-token amounts."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty token amount")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("invalid token amount") from exc
    if d != d.to_integral_value():
        raise ValueError("token amount must be a whole number of visible tokens")
    if d < 0:
        raise ValueError("token amount must be non-negative")
    s_int = validate_units(scale, name="scale")
    if s_int < 1:
        raise ValueError("scale must be >= 1")
    return int(d) * s_int


# Spec / roadmap naming aliases
tokens_to_units = tokens_whole_to_units


def units_to_display_tokens(units: int, *, scale: int) -> str:
    """Signed decimal token string for UI (alias of ``format_signed_token_amount``)."""
    return format_signed_token_amount(units, scale=scale)


def format_balance_message_units(units: int, *, scale: int) -> str:
    """Telegram/API one-line balance (non-negative ``units``)."""
    u = validate_units(units, name="units")
    if u < 0:
        raise ValueError("balance units must be non-negative")
    body = format_signed_token_amount(u, scale=scale).lstrip("+")
    return f"Token balance: {body}"
