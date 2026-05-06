from __future__ import annotations


def mask_token_like(value: str | None) -> str | None:
    """Mask IDs/tokens in logs/audit (keeps prefix/suffix for debugging)."""
    if not value:
        return None
    v = str(value)
    if len(v) <= 6:
        return "***"
    return f"{v[:3]}***{v[-3:]}"


def mask_email(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value)
    if "@" not in v:
        return mask_token_like(v)
    name, domain = v.split("@", 1)
    if not name:
        return f"***@{domain}"
    if len(name) <= 2:
        return f"{name[0]}***@{domain}"
    return f"{name[0]}***{name[-1]}@{domain}"
