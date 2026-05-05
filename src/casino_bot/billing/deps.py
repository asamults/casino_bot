from __future__ import annotations

from fastapi import Header, HTTPException

from casino_bot.settings import settings


def get_current_user_id(
    x_user_id: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
) -> int:
    if x_internal_token != settings.USER_API_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid user token")
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user identity")
    try:
        return int(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid user identity") from exc
