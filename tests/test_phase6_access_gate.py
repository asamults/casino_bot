"""Phase 6 — GAME_ACCESS_MIN_TOKENS gate and presentation helpers."""

from __future__ import annotations

import pytest

from casino_bot.db.models import GameRound, TokenAccount
from casino_bot.games.presentation import build_wheel_presentation
from casino_bot.games.service import GameEngineRejected, run_game
from casino_bot.services.economy_service import adjust_user_tokens
from casino_bot.services.token_amounts import tokens_whole_to_units
from casino_bot.settings import Settings
from casino_bot.telegram_bot import game_texts
from casino_bot.telegram_bot.user_ops import ensure_telegram_user


def _fund(db, *, user_id: int, whole_tokens: int) -> None:
    from casino_bot.settings import settings as app_settings

    adjust_user_tokens(
        db,
        user_id=user_id,
        delta_units=tokens_whole_to_units(
            whole_tokens, scale=app_settings.TOKEN_UNIT_SCALE
        ),
        reason="test:fund",
        actor="tests",
    )


def test_access_gate_blocks_below_threshold_no_round_no_balance_change(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Settings(
        _env_file=None,
        GAMES_ENABLED=["coin_flip"],
        GAME_ACCESS_MIN_TOKENS=10,
    )
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    user = ensure_telegram_user(sqlite_session, telegram_user_id=96001)
    _fund(sqlite_session, user_id=user.id, whole_tokens=5)
    sqlite_session.commit()
    bal_before = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    with pytest.raises(GameEngineRejected) as ei:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=1,
            idempotency_key="gate-1",
            actor="tests",
        )
    assert ei.value.code == "access_tokens_required"
    n = sqlite_session.query(GameRound).filter(GameRound.user_id == user.id).count()
    assert n == 0
    bal_after = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert bal_after == bal_before


def test_access_message_respects_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    import casino_bot.settings as smod

    monkeypatch.setattr(
        smod,
        "settings",
        Settings(_env_file=None, GAME_ACCESS_MIN_TOKENS=25),
    )
    assert "25" in game_texts.game_engine_rejected_user_message(
        "access_tokens_required"
    )


def test_wheel_presentation_has_three_steps() -> None:
    pres = build_wheel_presentation(
        stake_tokens=2,
        outcome="silver",
        net_change_tokens="2",
        balance_line="Token balance: 9",
        idempotent_replay=False,
    )
    assert len(pres.steps) == 3
    assert pres.steps[0].audio is not None
    assert pres.steps[0].audio.cue_type == "anticipation"
    assert pres.steps[1].text is not None
    assert pres.steps[2].audio is not None
