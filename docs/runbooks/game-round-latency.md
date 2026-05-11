# Game round latency high (p95)

When firing: **`casino_bot_game_round_duration_seconds` p95 > 2s**. **Check**: Postgres health/slow queries, lock waits on `game_rounds` / ledger, API vs Telegram worker CPU; reproduce with `/metrics` scrape aligned to load.
