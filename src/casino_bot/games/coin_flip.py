"""Coin flip — even money vertical slice (Phase 2)."""

from __future__ import annotations

import secrets
from typing import Any

from casino_bot.games.rng import RNG_VERSION
from casino_bot.games.types import GameInput, GameResult, GameMeta

COIN_FLIP_GAME_ID = "coin_flip"


class CoinFlipGame:
    """50/50 outcome; win credits ``+bet``, lose debits ``-bet``; no house edge."""

    @property
    def game_id(self) -> str:
        return COIN_FLIP_GAME_ID

    def catalog_meta(self, settings: Any) -> GameMeta:
        return GameMeta(
            game_id=self.game_id,
            title="Coin flip",
            description="Fair 50/50 even money — win adds your stake, lose removes it.",
            min_bet=int(settings.COIN_FLIP_MIN_BET),
            max_bet=int(settings.COIN_FLIP_MAX_BET),
        )

    def compute_outcome(self, inp: GameInput, rng: secrets.SystemRandom) -> GameResult:
        bet = float(inp.bet_amount)
        is_win = rng.random() < 0.5
        if is_win:
            outcome = "win"
            payout_delta = bet
            prize = 10
        else:
            outcome = "lose"
            payout_delta = -bet
            prize = 0
        details = {
            "game": COIN_FLIP_GAME_ID,
            "outcome": outcome,
            "payout_delta": payout_delta,
            "prize": prize,
            "rng_version": RNG_VERSION,
        }
        return GameResult(
            outcome=outcome,
            payout_delta=payout_delta,
            prize=prize,
            details=details,
        )
