#!/usr/bin/env bash
# telegram_polling_smoke.sh — optional deploy sanity for systemd Telegram polling.
#
# - Validates env file with casino_bot Settings + telegram preflight (no secret output).
# - Optionally checks systemd unit active state.
# - Optionally curls an existing API /ready URL (does not start HTTP here).
#
# Usage:
#   ./scripts/ops/telegram_polling_smoke.sh --env-file /etc/casino-bot/telegram.env
#   TELEGRAM_POLLING_UNIT=casino-bot-telegram-polling.service ./scripts/ops/telegram_polling_smoke.sh --env-file ./path.env --skip-systemd
#
# Exit: 0 success, 1 validation/runtime failure, 2 usage error.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE=""
SKIP_SYSTEMD=0
API_READY_URL=""
UNIT_NAME="${TELEGRAM_POLLING_UNIT:-casino-bot-telegram-polling.service}"

usage() {
  sed -n '1,20p' "$0" | tail -n +2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --skip-systemd)
      SKIP_SYSTEMD=1
      shift
      ;;
    --api-ready-url)
      API_READY_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ENV_FILE" ]]; then
  echo "error: --env-file is required" >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ ! -r "$ENV_FILE" ]]; then
  echo "error: env file not readable: $ENV_FILE" >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

SMOKE_PY='
from __future__ import annotations

import os
import sys

from casino_bot.settings import Settings
from casino_bot.telegram_bot.preflight import telegram_polling_startup_error

path = os.environ["TELEGRAM_SMOKE_ENV_FILE"]
try:
    cfg = Settings(_env_file=path, _env_file_encoding="utf-8")
except Exception as exc:
    print("Settings load failed:", type(exc).__name__, file=sys.stderr)
    sys.exit(1)

err = telegram_polling_startup_error(cfg)
if err:
    print(err, file=sys.stderr)
    sys.exit(1)

token = (cfg.TELEGRAM_BOT_TOKEN or "").strip()
bad_markers = (
    "REPLACE_WITH_BOTFATHER",
    "TOKEN_FROM_BOTFATHER",
    "your_token_from_botfather",
    "<set on host",
)
low = token.lower()
if any(m.lower() in low for m in bad_markers):
    print("TELEGRAM_BOT_TOKEN looks like a placeholder", file=sys.stderr)
    sys.exit(1)
'

export TELEGRAM_SMOKE_ENV_FILE="$ENV_FILE"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PY="${ROOT_DIR}/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" ]]; then
  echo "error: no python (.venv/bin/python or python3 on PATH)" >&2
  exit 1
fi
if ! "$PY" -c "$SMOKE_PY"; then
  exit 1
fi

if [[ "$SKIP_SYSTEMD" -eq 0 ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    state="$(systemctl is-active "$UNIT_NAME" 2>/dev/null || true)"
    if [[ "$state" != "active" ]]; then
      echo "error: systemd unit not active: $UNIT_NAME (state=${state:-unknown})" >&2
      echo "hint: use --skip-systemd if checking env only" >&2
      exit 1
    fi
  else
    echo "warning: systemctl not found; skipping unit check" >&2
  fi
fi

if [[ -n "$API_READY_URL" ]]; then
  if ! curl -fsS "$API_READY_URL" >/dev/null; then
    echo "error: API readiness curl failed: $API_READY_URL" >&2
    exit 1
  fi
fi

echo "OK: telegram polling smoke checks passed"
