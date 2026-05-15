from __future__ import annotations

import re
import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram

APP_NAMESPACE = "casino_bot"

# Games (Phase 4B) — low-cardinality labels only; record from ``run_game_detailed``.
game_rounds_total = Counter(
    f"{APP_NAMESPACE}_game_rounds_total",
    "Persisted game rounds (first write only; not idempotent replays)",
    labelnames=("game_id", "status", "outcome"),
)
game_round_rejected_total = Counter(
    f"{APP_NAMESPACE}_game_round_rejected_total",
    "Game engine rejections before a new round is persisted (GameEngineRejected)",
    labelnames=("game_id", "code"),
)
game_round_duration_seconds = Histogram(
    f"{APP_NAMESPACE}_game_round_duration_seconds",
    "Wall time for run_game_detailed (seconds), including idempotent replay",
    labelnames=("game_id",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
game_token_volume_total = Counter(
    f"{APP_NAMESPACE}_game_token_volume_total",
    "Token amounts on newly persisted committed rounds (not replays)",
    labelnames=("game_id", "direction"),
)

audio_delivery_total = Counter(
    f"{APP_NAMESPACE}_audio_delivery_total",
    "Telegram voice cue delivery attempts (Phase 6)",
    labelnames=("channel", "cue_type", "status"),
)


def _committed_outcome_label(details: dict | None) -> str:
    if not details:
        return "unknown"
    o = details.get("outcome")
    if o in ("win", "lose", "bust", "bronze", "silver", "gold"):
        return str(o)
    return "unknown"


def record_audio_delivery(*, channel: str, cue_type: str, status: str) -> None:
    """``status`` is ``sent``, ``fallback`` (no asset), or ``failed`` (API error)."""
    audio_delivery_total.labels(channel, cue_type, status).inc()


def record_game_engine_rejection(
    *, game_id: str, code: str, duration_seconds: float
) -> None:
    game_round_rejected_total.labels(game_id, code).inc()
    game_round_duration_seconds.labels(game_id).observe(duration_seconds)


def record_game_round_completion(
    *,
    game_id: str,
    status: str,
    details: dict | None,
    bet_tokens: int,
    payout_volume_tokens: float,
    idempotent_replay: bool,
    duration_seconds: float,
) -> None:
    """Histogram always; counters only on first persistence (not Telegram replay)."""
    game_round_duration_seconds.labels(game_id).observe(duration_seconds)
    if idempotent_replay:
        return
    if status == "committed":
        oc = _committed_outcome_label(details)
        game_rounds_total.labels(game_id, "committed", oc).inc()
        game_token_volume_total.labels(game_id, "stake").inc(float(bet_tokens))
        if payout_volume_tokens > 0:
            game_token_volume_total.labels(game_id, "payout").inc(payout_volume_tokens)
    elif status == "rejected":
        game_rounds_total.labels(game_id, "rejected", "unknown").inc()
    elif status == "failed":
        game_rounds_total.labels(game_id, "failed", "unknown").inc()


# HTTP
http_requests_total = Counter(
    f"{APP_NAMESPACE}_http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "route", "status"),
)
http_request_duration_seconds = Histogram(
    f"{APP_NAMESPACE}_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    labelnames=("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Legacy admin usage
legacy_admin_requests_total = Counter(
    f"{APP_NAMESPACE}_legacy_admin_requests_total",
    "Legacy /admin/* requests (deprecated)",
    labelnames=("method", "route"),
)

# Billing webhooks
webhook_processed_total = Counter(
    f"{APP_NAMESPACE}_webhook_processed_total",
    "Processed webhook events",
    labelnames=("provider",),
)
webhook_failed_total = Counter(
    f"{APP_NAMESPACE}_webhook_failed_total",
    "Failed webhook events",
    labelnames=("provider", "error_code"),
)
webhook_dead_letter_total = Counter(
    f"{APP_NAMESPACE}_webhook_dead_letter_total",
    "Dead-lettered webhook events",
    labelnames=("provider", "error_code"),
)
webhook_processing_seconds = Histogram(
    f"{APP_NAMESPACE}_webhook_processing_seconds",
    "Webhook processing duration (seconds)",
    labelnames=("provider",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# DB readiness
db_ready_state = Gauge(
    f"{APP_NAMESPACE}_db_ready_state",
    "Database readiness state from last /ready check (1=ready, 0=not ready)",
)

_ROUTE_ID_RE = re.compile(r"/\d+($|/)")


def safe_route_label(route: str | None) -> str:
    """Normalize route label to avoid high cardinality.

    Prefer FastAPI/Starlette route templates (e.g. ``/admin/users/{id}``).
    If a raw path slips through, coarse-sanitize numeric segments.
    """
    if not route:
        return "unknown"
    r = str(route)
    if "{" in r:
        return r
    # last-resort: sanitize integer ids in raw paths
    return _ROUTE_ID_RE.sub("/{id}\\1", r)


def is_noisy_metrics_route(route: str) -> bool:
    return route in {"/metrics"}


def observe_duration_seconds(
    hist: Histogram, labels: tuple[str, ...], fn: Callable[[], str]
):
    start = time.perf_counter()
    try:
        return fn()
    finally:
        hist.labels(*labels).observe(time.perf_counter() - start)
