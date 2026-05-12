"""Per-game stake and cooldown policy for ``run_game`` (Phase 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from casino_bot.settings import Settings

_STAKE_GAMES: frozenset[str] = frozenset({"coin_flip", "bonus_wheel"})


def game_has_stake_policy(game_id: str) -> bool:
    return game_id in _STAKE_GAMES


def min_max_bet(game_id: str, settings: Settings) -> tuple[int, int]:
    if game_id == "coin_flip":
        return settings.COIN_FLIP_MIN_BET, settings.COIN_FLIP_MAX_BET
    if game_id == "bonus_wheel":
        return settings.BONUS_WHEEL_MIN_BET, settings.BONUS_WHEEL_MAX_BET
    raise KeyError(game_id)


def effective_cooldown_seconds(game_id: str, settings: Settings) -> int:
    if game_id == "coin_flip":
        return settings.effective_coin_flip_cooldown_seconds()
    if game_id == "bonus_wheel":
        return settings.effective_bonus_wheel_cooldown_seconds()
    return 0
