# Games observability (Phase 4B)

- **Metrics**: recorded only from `run_game_detailed()` (`src/casino_bot/games/service.py`) — single entrypoint for gameplay counters and latency histogram.
- **Series** (low cardinality): `casino_bot_game_rounds_total`, `casino_bot_game_round_rejected_total`, `casino_bot_game_round_duration_seconds`, `casino_bot_game_token_volume_total` — see `src/casino_bot/core/metrics.py`.
- **Grafana**: provisioning mounts `monitoring/grafana_games_dashboard.json` as dashboard **Casino Bot - Games (Phase 4B)** (`uid=casino-bot-games`). Variables: **game_id**.
- **Alerts**: `monitoring/alert_rules.yml` group `casino_bot_games` — runbooks: `docs/runbooks/game-reject-burst.md`, `docs/runbooks/game-round-latency.md`.
- **Heuristic scan** (no Prometheus user labels): `PYTHONPATH=src python scripts/ops/game_activity_scan.py` — env `GAME_ACTIVITY_WINDOW_MINUTES`, `GAME_SUSPICIOUS_COMMITTED_ROUNDS_THRESHOLD`; logs **warnings** when a user exceeds committed-round count in the window.
