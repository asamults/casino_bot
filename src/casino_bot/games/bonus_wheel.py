"""Bonus wheel — weighted payout tiers (Phase 5, non–coin-flip mechanics).

Single ``rng.random()`` draw against a fixed cumulative distribution.
Net token delta is applied in one ``execute_game_round`` call (integer token_units).
"""

from __future__ import annotations

import secrets
from typing import Any

from casino_bot.games.rng import RNG_VERSION
from casino_bot.games.types import GameInput, GameMeta, GameResult
from casino_bot.services import token_amounts

BONUS_WHEEL_GAME_ID = "bonus_wheel"

# (outcome label, payout as rational multiple of stake_units via int ops, weight)
_TIERS: tuple[tuple[str, str, int], ...] = (
    ("bust", "bust", 55),
    ("bronze", "half", 25),
    ("silver", "equal", 12),
    ("gold", "two_and_half", 8),
)


def _payout_units_for_tier(kind: str, stake_units: int) -> int:
    if kind == "bust":
        return -stake_units
    if kind == "half":
        return stake_units // 2
    if kind == "equal":
        return stake_units
    if kind == "two_and_half":
        return (stake_units * 5) // 2
    raise ValueError(f"unknown tier kind {kind!r}")


class BonusWheelGame:
    """Asymmetric wheel: bust loses stake; other tiers pay multiples of stake (net)."""

    @property
    def game_id(self) -> str:
        return BONUS_WHEEL_GAME_ID

    def catalog_meta(self, settings: Any) -> GameMeta:
        return GameMeta(
            game_id=self.game_id,
            title="Bonus wheel",
            description=(
                "One spin — weighted tiers (bust / bronze / silver / gold). "
                "Payouts are multiples of your stake (not 50/50)."
            ),
            min_bet=int(settings.BONUS_WHEEL_MIN_BET),
            max_bet=int(settings.BONUS_WHEEL_MAX_BET),
        )

    def compute_outcome(self, inp: GameInput, rng: secrets.SystemRandom) -> GameResult:
        from casino_bot.settings import settings as app_settings

        scale = app_settings.TOKEN_UNIT_SCALE
        stake_units = token_amounts.tokens_whole_to_units(
            int(inp.bet_amount), scale=scale
        )
        u = rng.random()
        total_w = sum(t[2] for t in _TIERS)
        cumulative = 0.0
        outcome = _TIERS[-1][0]
        kind = _TIERS[-1][1]
        for name, tier_kind, w in _TIERS:
            cumulative += w / total_w
            if u < cumulative:
                outcome = name
                kind = tier_kind
                break
        payout_delta_units = _payout_units_for_tier(kind, stake_units)
        prize = max(0, payout_delta_units) // scale
        details = {
            "game": BONUS_WHEEL_GAME_ID,
            "outcome": outcome,
            "payout_delta_units": payout_delta_units,
            "prize": prize,
            "tier_kind": kind,
            "rng_version": RNG_VERSION,
        }
        return GameResult(
            outcome=outcome,
            payout_delta_units=payout_delta_units,
            prize=prize,
            details=details,
        )
