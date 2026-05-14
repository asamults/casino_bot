"""Phase 6D — systemd unit and ops docs contract (no secrets in repo templates)."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_systemd_telegram_polling_unit_uses_environment_file_not_inline_token() -> None:
    unit = _repo_root() / "ops/systemd/casino-bot-telegram-polling.service"
    text = unit.read_text(encoding="utf-8")
    assert "EnvironmentFile=/etc/casino-bot/telegram.env" in text
    assert "telegram_bot.polling" in text
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "ExecStart=" in text
    assert "Restart=on-failure" in text


def test_telegram_polling_smoke_script_exists_and_skips_systemd_flag() -> None:
    script = _repo_root() / "scripts/ops/telegram_polling_smoke.sh"
    body = script.read_text(encoding="utf-8")
    assert "--skip-systemd" in body
    assert "TELEGRAM_SMOKE_ENV_FILE" in body
    assert "telegram_polling_startup_error" in body


def test_telegram_polling_prod_env_example_documents_polling_allowlist() -> None:
    frag = _repo_root() / "docs/ops/telegram-polling-prod-env.example"
    text = frag.read_text(encoding="utf-8")
    assert "TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS" in text
    assert "production" in text
