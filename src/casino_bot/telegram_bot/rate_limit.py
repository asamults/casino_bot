"""In-process Telegram rate limits (sliding window per telegram_user_id).

Separate from HTTP ``InMemoryRateLimitMiddleware`` — used only on the Telegram path.
"""

from __future__ import annotations

import threading
from collections import deque
from time import monotonic

from casino_bot.settings import settings

_lock = threading.Lock()
_prompt_buckets: dict[int, deque[float]] = {}
_action_buckets: dict[int, deque[float]] = {}


def reset_telegram_rate_limiters_for_tests() -> None:
    """Clear all buckets (pytest only)."""
    with _lock:
        _prompt_buckets.clear()
        _action_buckets.clear()


def _prune(dq: deque[float], *, cutoff: float) -> None:
    while dq and dq[0] < cutoff:
        dq.popleft()


def _allow(
    buckets: dict[int, deque[float]],
    key: int,
    *,
    max_events: int,
    window_seconds: float,
) -> bool:
    if max_events <= 0:
        return True
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        dq = buckets.setdefault(key, deque())
        _prune(dq, cutoff=cutoff)
        if len(dq) >= max_events:
            return False
        dq.append(now)
        return True


def allow_flip_prompt(telegram_user_id: int) -> bool:
    """Rate limit for ``/flip`` without arguments (keyboard prompt)."""
    return _allow(
        _prompt_buckets,
        telegram_user_id,
        max_events=settings.TELEGRAM_FLIP_PROMPT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60.0,
    )


def allow_flip_action(telegram_user_id: int) -> bool:
    """Rate limit for stake actions: ``/flip <n>`` and inline callback buttons."""
    return _allow(
        _action_buckets,
        telegram_user_id,
        max_events=settings.TELEGRAM_FLIP_ACTION_RATE_LIMIT_PER_MINUTE,
        window_seconds=60.0,
    )
