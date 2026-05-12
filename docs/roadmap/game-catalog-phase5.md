# Game catalog (Phase 5)

This project runs **catalog games** through a single path: `run_game()` → `execute_game_round()` → `economy_service.adjust_user_tokens()`. Telegram uses stable idempotency keys (`flip_idempotency.py`) and shared rate limits (`rate_limit.py`). Prometheus records `game_id` as a **low-cardinality** label (see Phase 4B observability docs).

## Adding a third built-in game (checklist)

1. **Registry** — Add `games/<your_game>.py` implementing `Game` (`game_id`, `compute_outcome`, `catalog_meta`). Register in `games/registry.py` `_bootstrap()`.
2. **Policy** — Add the game id to `game_has_stake_policy` / `min_max_bet` / `effective_cooldown_seconds` in `games/policy.py` (or extend the helpers so `run_game` stays small).
3. **Settings** — Add `GAMES_ENABLED` entry and any per-game limits to `settings.py` with validators; document keys in `.env.example`.
4. **Service** — No direct balance writes in the game module; `games/service.py` already routes registered games through `execute_game_round`.
5. **Telegram** — Add command/callback handlers mirroring `/flip` (async → `asyncio.to_thread` + `SessionLocal`), user strings in `telegram_bot/game_texts.py`, wire handlers in `telegram_bot/polling.py`.
6. **Metrics smoke** — Run a committed round in dev; confirm `casino_bot_game_rounds_total{game_id="..."}` appears. Grafana variable `game_id` is label-driven (no code change required unless you add a game-specific panel).
7. **Tests** — Registry/catalog test, `run_game` happy + reject paths, one Telegram-facing test, keep existing coin flip regression tests green.

## Built-in games (current)

| `game_id`     | Mechanics                         | Telegram entry |
|---------------|-----------------------------------|----------------|
| `coin_flip`   | 50/50 even money                  | `/flip`        |
| `bonus_wheel` | Weighted tiers (asymmetric pays) | `/wheel`       |

Use `/games` for the live catalog (intersection of `GAMES_ENABLED` and registered games).
