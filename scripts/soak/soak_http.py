from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Sample:
    path: str
    status: int
    latency_ms: float


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    v = sorted(values)
    if p <= 0:
        return v[0]
    if p >= 100:
        return v[-1]
    k = (len(v) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return v[int(k)]
    d0 = v[f] * (c - k)
    d1 = v[c] * (k - f)
    return d0 + d1


def _fetch(
    url: str, *, host_header: str | None, timeout_s: float
) -> tuple[int, float, str]:
    headers = {}
    if host_header:
        headers["Host"] = host_header
    req = urllib.request.Request(url, headers=headers)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            body = r.read(1024 * 256).decode("utf-8", errors="replace")
            status = int(getattr(r, "status", 0) or 0)
    except urllib.error.HTTPError as e:
        # Read body for debugging if present.
        body = ""
        try:
            body = (e.read(1024 * 64) or b"").decode("utf-8", errors="replace")
        except Exception:
            body = ""
        status = int(getattr(e, "code", 0) or 0)
    except urllib.error.URLError as e:
        # Network errors (e.g. connection refused) should be counted, not crash the soak.
        body = str(getattr(e, "reason", e))
        status = 0
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return status, elapsed_ms, body


def _parse_counter(text: str, metric_name: str) -> float | None:
    # very small parser: match lines like `name 123` or `name{...} 123` (sum)
    total = 0.0
    found = False
    for line in text.splitlines():
        if not line.startswith(metric_name):
            continue
        if line.startswith("#"):
            continue
        try:
            val = float(line.rsplit(" ", 1)[1])
        except Exception:
            continue
        total += val
        found = True
    return total if found else None


def _parse_gauge(text: str, metric_name: str) -> float | None:
    for line in text.splitlines():
        if not line.startswith(metric_name):
            continue
        if line.startswith("#"):
            continue
        try:
            return float(line.rsplit(" ", 1)[1])
        except Exception:
            return None
    return None


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HTTP soak harness (no extra deps).")
    p.add_argument(
        "--base-url", default=os.environ.get("SOAK_BASE_URL", "http://127.0.0.1:8000")
    )
    p.add_argument("--host-header", default=os.environ.get("SOAK_HOST_HEADER", ""))
    p.add_argument(
        "--duration-seconds",
        type=int,
        default=int(os.environ.get("SOAK_DURATION_SECONDS", "300")),
    )
    p.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("SOAK_INTERVAL_SECONDS", "1")),
    )
    p.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.environ.get("SOAK_TIMEOUT_SECONDS", "3")),
    )
    p.add_argument(
        "--paths",
        default=os.environ.get("SOAK_PATHS", "/health,/ready,/metrics"),
        help="Comma-separated paths to hit each iteration.",
    )
    p.add_argument(
        "--max-5xx-rate",
        type=float,
        default=float(os.environ.get("SOAK_MAX_5XX_RATE", "0.01")),
    )
    p.add_argument(
        "--max-ready-fail-rate",
        type=float,
        default=float(os.environ.get("SOAK_MAX_READY_FAIL_RATE", "0.001")),
    )
    p.add_argument(
        "--max-p95-ms",
        type=float,
        default=float(os.environ.get("SOAK_MAX_P95_MS", "500")),
    )
    p.add_argument(
        "--report-json",
        default=os.environ.get("SOAK_REPORT_JSON", ""),
        help="If set, write machine-readable JSON summary to this path.",
    )
    args = p.parse_args(argv)

    host_header = args.host_header.strip() or None
    paths = [x.strip() for x in str(args.paths).split(",") if x.strip()]
    if not paths:
        print("FAIL: no paths provided", file=sys.stderr)
        return 2

    end_at = time.monotonic() + max(1, int(args.duration_seconds))
    samples: list[Sample] = []
    status_counts: dict[str, dict[int, int]] = {p: {} for p in paths}
    metrics_db_ready: list[float] = []
    metrics_dead_letter_total: list[float] = []

    # baseline: metrics counters at start
    start_metrics_text = ""
    try:
        st, _, body = _fetch(
            f"{args.base_url}/metrics",
            host_header=host_header,
            timeout_s=args.timeout_seconds,
        )
        if st == 200:
            start_metrics_text = body
    except Exception:
        start_metrics_text = ""

    while time.monotonic() < end_at:
        for path in paths:
            url = f"{args.base_url}{path}"
            st, ms, body = _fetch(
                url, host_header=host_header, timeout_s=args.timeout_seconds
            )
            samples.append(Sample(path=path, status=st, latency_ms=ms))
            status_counts[path][st] = status_counts[path].get(st, 0) + 1

            if path == "/metrics" and st == 200:
                v = _parse_gauge(body, "casino_bot_db_ready_state")
                if v is not None:
                    metrics_db_ready.append(v)
                dl = _parse_counter(body, "casino_bot_webhook_dead_letter_total")
                if dl is not None:
                    metrics_dead_letter_total.append(dl)

        time.sleep(max(0.0, float(args.interval_seconds)))

    # end metrics
    end_metrics_text = ""
    st, _, body = _fetch(
        f"{args.base_url}/metrics",
        host_header=host_header,
        timeout_s=args.timeout_seconds,
    )
    if st == 200:
        end_metrics_text = body

    # stats
    all_lat = [s.latency_ms for s in samples]
    p95 = _percentile(all_lat, 95)
    p99 = _percentile(all_lat, 99)

    total = len(samples)
    total_5xx = sum(1 for s in samples if 500 <= s.status <= 599)
    rate_5xx = (total_5xx / total) if total else 0.0

    ready_total = sum(1 for s in samples if s.path == "/ready")
    ready_fail = sum(1 for s in samples if s.path == "/ready" and s.status != 200)
    ready_fail_rate = (ready_fail / ready_total) if ready_total else 0.0

    # metrics deltas
    start_dead_letter = (
        _parse_counter(start_metrics_text, "casino_bot_webhook_dead_letter_total")
        if start_metrics_text
        else None
    )
    end_dead_letter = (
        _parse_counter(end_metrics_text, "casino_bot_webhook_dead_letter_total")
        if end_metrics_text
        else None
    )
    dead_letter_delta = None
    if start_dead_letter is not None and end_dead_letter is not None:
        dead_letter_delta = end_dead_letter - start_dead_letter

    # PASS/FAIL evaluation (minimal)
    failures: list[str] = []
    if rate_5xx > float(args.max_5xx_rate):
        failures.append(f"5xx_rate={rate_5xx:.4f} > {float(args.max_5xx_rate):.4f}")
    if ready_fail_rate > float(args.max_ready_fail_rate):
        failures.append(
            f"ready_fail_rate={ready_fail_rate:.4f} > {float(args.max_ready_fail_rate):.4f}"
        )
    if p95 > float(args.max_p95_ms):
        failures.append(f"p95_ms={p95:.1f} > {float(args.max_p95_ms):.1f}")
    if metrics_db_ready and min(metrics_db_ready) < 1:
        failures.append("db_ready_state dipped below 1 during soak")
    if dead_letter_delta is not None and dead_letter_delta > 0:
        failures.append(f"dead_letter_total increased by {dead_letter_delta:.0f}")

    summary: dict[str, Any] = {
        "duration_seconds": int(args.duration_seconds),
        "interval_seconds": float(args.interval_seconds),
        "base_url": str(args.base_url),
        "host_header": host_header or "",
        "paths": paths,
        "total_requests": total,
        "status_counts": status_counts,
        "latency_ms": {
            "mean": statistics.fmean(all_lat) if all_lat else 0.0,
            "p95": p95,
            "p99": p99,
            "max": max(all_lat) if all_lat else 0.0,
        },
        "rates": {
            "5xx": rate_5xx,
            "ready_fail": ready_fail_rate,
        },
        "metrics_observed": {
            "db_ready_state_min": min(metrics_db_ready) if metrics_db_ready else None,
            "dead_letter_total_delta": dead_letter_delta,
        },
        "pass": not failures,
        "failures": failures,
    }

    if args.report_json:
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=True)

    if failures:
        print("FAIL: soak criteria not met")
        for fmsg in failures:
            print(f"- {fmsg}")
    else:
        print("PASS: soak criteria met")

    print(
        "SUMMARY: total=%d 5xx_rate=%.4f ready_fail_rate=%.4f p95_ms=%.1f p99_ms=%.1f dead_letter_delta=%s db_ready_min=%s"
        % (
            total,
            rate_5xx,
            ready_fail_rate,
            p95,
            p99,
            "n/a" if dead_letter_delta is None else f"{dead_letter_delta:.0f}",
            "n/a" if not metrics_db_ready else f"{min(metrics_db_ready):.0f}",
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(run())
