"""Phase 4B — Prometheus game metrics emitted from ``run_game_detailed``."""

from __future__ import annotations

import re

import pytest
from prometheus_client import REGISTRY, generate_latest

from casino_bot.games.service import GameEngineRejected, run_game
from casino_bot.settings import Settings
from casino_bot.telegram_bot.user_ops import ensure_telegram_user
from casino_bot.services.economy_service import adjust_user_tokens


def _labeled_counter_value(metric_base: str, labels: dict[str, str]) -> float:
    blob = generate_latest(REGISTRY).decode()
    for line in blob.splitlines():
        if not line.startswith(metric_base + "{"):
            continue
        m = re.match(r"^\w+\{([^}]*)\}\s+(\S+)", line)
        if not m:
            continue
        lbls: dict[str, str] = {}
        for part in m.group(1).split(","):
            k, _, v = part.partition("=")
            lbls[k.strip()] = v.strip().strip('"')
        if all(lbls.get(k) == v for k, v in labels.items()):
            return float(m.group(2))
    return 0.0


def _fund(db, *, user_id: int, amount: float) -> None:
    adjust_user_tokens(
        db,
        user_id=user_id,
        delta=amount,
        reason="test:fund",
        actor="tests",
    )


class _FakeRng:
    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def test_metrics_increment_on_winning_round(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip"])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)

    before_win = _labeled_counter_value(
        "casino_bot_game_rounds_total",
        {
            "game_id": "coin_flip",
            "status": "committed",
            "outcome": "win",
        },
    )
    before_stake = _labeled_counter_value(
        "casino_bot_game_token_volume_total",
        {"game_id": "coin_flip", "direction": "stake"},
    )
    before_payout = _labeled_counter_value(
        "casino_bot_game_token_volume_total",
        {"game_id": "coin_flip", "direction": "payout"},
    )

    user = ensure_telegram_user(sqlite_session, telegram_user_id=93001)
    _fund(sqlite_session, user_id=user.id, amount=100.0)
    sqlite_session.commit()

    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=5,
        idempotency_key="m-win",
        actor="tests",
    )
    sqlite_session.commit()

    after_win = _labeled_counter_value(
        "casino_bot_game_rounds_total",
        {
            "game_id": "coin_flip",
            "status": "committed",
            "outcome": "win",
        },
    )
    after_stake = _labeled_counter_value(
        "casino_bot_game_token_volume_total",
        {"game_id": "coin_flip", "direction": "stake"},
    )
    after_payout = _labeled_counter_value(
        "casino_bot_game_token_volume_total",
        {"game_id": "coin_flip", "direction": "payout"},
    )

    assert after_win == before_win + 1
    assert after_stake == before_stake + 5.0
    assert after_payout == before_payout + 5.0


def test_metrics_idempotent_replay_does_not_double_count(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.99))
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip"])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)

    user = ensure_telegram_user(sqlite_session, telegram_user_id=93002)
    _fund(sqlite_session, user_id=user.id, amount=100.0)
    sqlite_session.commit()

    key = "idem-1"
    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=2,
        idempotency_key=key,
        actor="tests",
    )
    sqlite_session.commit()
    lose_before = _labeled_counter_value(
        "casino_bot_game_rounds_total",
        {
            "game_id": "coin_flip",
            "status": "committed",
            "outcome": "lose",
        },
    )

    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=2,
        idempotency_key=key,
        actor="tests",
    )
    sqlite_session.commit()
    lose_after = _labeled_counter_value(
        "casino_bot_game_rounds_total",
        {
            "game_id": "coin_flip",
            "status": "committed",
            "outcome": "lose",
        },
    )
    assert lose_after == lose_before


def test_metrics_engine_rejection_increments_rejected_total(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip"])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)

    user = ensure_telegram_user(sqlite_session, telegram_user_id=93003)
    _fund(sqlite_session, user_id=user.id, amount=1.0)
    sqlite_session.commit()

    before = _labeled_counter_value(
        "casino_bot_game_round_rejected_total",
        {"game_id": "coin_flip", "code": "insufficient_balance"},
    )
    with pytest.raises(GameEngineRejected):
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=100,
            idempotency_key="too-big-bet",
            actor="tests",
        )
    after = _labeled_counter_value(
        "casino_bot_game_round_rejected_total",
        {"game_id": "coin_flip", "code": "insufficient_balance"},
    )
    assert after == before + 1


def test_metrics_bonus_wheel_committed_bust_outcome(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    cfg = Settings(_env_file=None, GAMES_ENABLED=["bonus_wheel"])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)

    before = _labeled_counter_value(
        "casino_bot_game_rounds_total",
        {
            "game_id": "bonus_wheel",
            "status": "committed",
            "outcome": "bust",
        },
    )
    user = ensure_telegram_user(sqlite_session, telegram_user_id=93004)
    _fund(sqlite_session, user_id=user.id, amount=50.0)
    sqlite_session.commit()
    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="bonus_wheel",
        bet_amount=5,
        idempotency_key="bw-met",
        actor="tests",
    )
    sqlite_session.commit()
    after = _labeled_counter_value(
        "casino_bot_game_rounds_total",
        {
            "game_id": "bonus_wheel",
            "status": "committed",
            "outcome": "bust",
        },
    )
    assert after == before + 1
