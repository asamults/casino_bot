"""Bonus wheel — weighted payout tiers (Phase 5, non–coin-flip mechanics).

Single ``rng.random()`` draw against a fixed cumulative distribution.
Net token delta is applied in one ``execute_game_round`` call (same contract as coin flip).
"""

from __future__ import annotations

import secrets
from typing import Any

from casino_bot.games.rng import RNG_VERSION
from casino_bot.games.types import GameInput, GameMeta, GameResult

BONUS_WHEEL_GAME_ID = "bonus_wheel"

# (outcome label, net payout as multiple of stake, weight). Weights sum to 1.0.
_TIERS: tuple[tuple[str, float, float], ...] = (
    ("bust", -1.0, 0.55),
    ("bronze", 0.5, 0.25),
    ("silver", 1.0, 0.12),
    ("gold", 2.5, 0.08),
)


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
        u = rng.random()
        cumulative = 0.0
        outcome = _TIERS[-1][0]
        mult = _TIERS[-1][1]
        for name, m, w in _TIERS:
            cumulative += w
            if u < cumulative:
                outcome = name
                mult = m
                break
        bet = float(inp.bet_amount)
        payout_delta = mult * bet
        prize = int(round(max(0.0, payout_delta)))
        details = {
            "game": BONUS_WHEEL_GAME_ID,
            "outcome": outcome,
            "payout_delta": payout_delta,
            "prize": prize,
            "tier_multiplier": mult,
            "rng_version": RNG_VERSION,
        }
        return GameResult(
            outcome=outcome,
            payout_delta=payout_delta,
            prize=prize,
            details=details,
        )
