#!/usr/bin/env bash
set -e

PROJECT_DIR="$HOME/Documents/MyCode/MyPython_Code/casino_bot"
VENV_DIR="$PROJECT_DIR/.venv"
SRC_DIR="$PROJECT_DIR/src"
PORT=8000

cd "$PROJECT_DIR"

source "$VENV_DIR/bin/activate"

export PYTHONPATH="$SRC_DIR"

fuser -k "$PORT"/tcp || true

exec "$VENV_DIR/bin/uvicorn" casino_bot.main:app \
    --reload \
    --host 127.0.0.1 \
    --port "$PORT"
