"""In-process registry of built-in games."""

from __future__ import annotations

from casino_bot.games.types import Game

_GAMES: dict[str, Game] = {}


def register(game: Game) -> None:
    _GAMES[game.game_id] = game


def get(game_id: str) -> Game:
    return _GAMES[game_id]


def list_games() -> list[Game]:
    # Import inside function so tests can monkeypatch ``casino_bot.settings.settings``.
    from casino_bot.settings import settings as app_settings

    enabled = set(app_settings.GAMES_ENABLED)
    return [g for gid, g in _GAMES.items() if gid in enabled]


def _bootstrap() -> None:
    from casino_bot.games.coin_flip import CoinFlipGame

    register(CoinFlipGame())


_bootstrap()
