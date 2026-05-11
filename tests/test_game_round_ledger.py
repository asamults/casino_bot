from __future__ import annotations

import threading
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from casino_bot.db.base import Base
from casino_bot.db.models import LedgerEntry, TokenAccount
from casino_bot.services.economy_service import adjust_user_tokens
from casino_bot.services.game_round_service import execute_game_round
from casino_bot.telegram_bot.user_ops import ensure_telegram_user


def _fund(db, *, user_id: int, amount: float) -> None:
    adjust_user_tokens(
        db,
        user_id=user_id,
        delta=amount,
        reason="test:fund",
        actor="tests",
    )


def test_round_idempotency_same_key_no_double_spend(sqlite_session) -> None:
    user = ensure_telegram_user(sqlite_session, telegram_user_id=91001)
    _fund(sqlite_session, user_id=user.id, amount=10.0)
    sqlite_session.commit()

    gr1 = execute_game_round(
        sqlite_session,
        user_id=user.id,
        game_id="phase1:test",
        idempotency_key="k-1",
        bet_amount=3.0,
        actor="tests",
        details={"test": True},
    )
    sqlite_session.commit()

    bal_after_1 = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance
    )

    gr2 = execute_game_round(
        sqlite_session,
        user_id=user.id,
        game_id="phase1:test",
        idempotency_key="k-1",
        bet_amount=3.0,
        actor="tests",
        details={"test": True},
    )
    sqlite_session.commit()

    bal_after_2 = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance
    )

    assert gr1.id == gr2.id
    assert gr1.round_id == gr2.round_id
    assert gr1.status == "committed"
    assert bal_after_1 == 7.0
    assert bal_after_2 == 7.0


def test_round_insufficient_funds_rejected_no_balance_change(sqlite_session) -> None:
    user = ensure_telegram_user(sqlite_session, telegram_user_id=91002)
    _fund(sqlite_session, user_id=user.id, amount=1.0)
    sqlite_session.commit()

    ledger_before = (
        sqlite_session.query(LedgerEntry).filter(LedgerEntry.user_id == user.id).count()
    )

    gr = execute_game_round(
        sqlite_session,
        user_id=user.id,
        game_id="phase1:test",
        idempotency_key="k-insufficient",
        bet_amount=5.0,
        actor="tests",
        details={"case": "insufficient"},
    )
    sqlite_session.commit()

    bal = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance
    )
    ledger_after = (
        sqlite_session.query(LedgerEntry).filter(LedgerEntry.user_id == user.id).count()
    )

    assert gr.status == "rejected"
    assert gr.payout_delta == 0.0
    assert bal == 1.0
    assert ledger_after == ledger_before


def test_round_concurrent_same_key_single_commit(tmp_path: Path) -> None:
    # Use a file-backed SQLite DB so two sessions can operate concurrently.
    db_path = tmp_path / "rounds.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    s0 = Session()
    user = ensure_telegram_user(s0, telegram_user_id=91003)
    user_id = user.id
    _fund(s0, user_id=user.id, amount=10.0)
    s0.commit()
    s0.close()

    barrier = threading.Barrier(2)
    results: list[tuple[str, str, int]] = []
    errors: list[BaseException] = []

    def _run() -> None:
        s = Session()
        try:
            barrier.wait(timeout=2)
            gr = execute_game_round(
                s,
                user_id=user_id,
                game_id="phase1:test",
                idempotency_key="k-concurrent",
                bet_amount=4.0,
                actor="tests",
            )
            s.commit()
            results.append((gr.status, gr.round_id, gr.id))
        except BaseException as e:
            errors.append(e)
        finally:
            s.close()

    t1 = threading.Thread(target=_run)
    t2 = threading.Thread(target=_run)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    assert results[0][2] == results[1][2]  # same DB row id
    assert results[0][1] == results[1][1]  # same round_id
    assert results[0][0] == "committed"
    assert results[1][0] == "committed"

    s_check = Session()
    bal = (
        s_check.query(TokenAccount)
        .filter(TokenAccount.user_id == user_id)
        .one()
        .balance
    )
    s_check.close()
    assert bal == 6.0
