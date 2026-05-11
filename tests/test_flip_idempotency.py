from casino_bot.telegram_bot.flip_idempotency import (
    callback_idempotency_key,
    command_idempotency_key,
)


def test_command_idempotency_key_format() -> None:
    assert (
        command_idempotency_key(telegram_user_id=999, update_id=1001)
        == "tg:999:cmd:1001"
    )


def test_callback_idempotency_key_format() -> None:
    assert (
        callback_idempotency_key(telegram_user_id=888, callback_query_id="abc123")
        == "tg:888:cb:abc123"
    )
