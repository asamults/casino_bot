"""Coin flip — even money vertical slice (Phase 2)."""

from __future__ import annotations

import secrets

from casino_bot.games.rng import RNG_VERSION
from casino_bot.games.types import GameInput, GameResult

COIN_FLIP_GAME_ID = "coin_flip"


class CoinFlipGame:
    """50/50 outcome; win credits ``+bet``, lose debits ``-bet``; no house edge."""

    @property
    def game_id(self) -> str:
        return COIN_FLIP_GAME_ID

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
