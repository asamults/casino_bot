from __future__ import annotations

import re
import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram

APP_NAMESPACE = "casino_bot"

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
