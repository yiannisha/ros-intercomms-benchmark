"""Clock helpers.

Benchmark interval timing uses monotonic clocks. Wall-clock timestamps are
recorded only for cross-host one-way latency when the operator has confirmed
clock synchronization.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time


NS_PER_MS = 1_000_000
NS_PER_SEC = 1_000_000_000


def monotonic_ns() -> int:
    """Return a steady monotonic timestamp in nanoseconds."""

    return time.monotonic_ns()


def wall_ns() -> int:
    """Return Unix wall-clock time in nanoseconds."""

    return time.time_ns()


def iso_utc_from_wall_ns(value: int | None = None) -> str:
    """Return an ISO-8601 UTC timestamp for a wall-clock nanosecond value."""

    ns = wall_ns() if value is None else value
    return datetime.fromtimestamp(ns / NS_PER_SEC, tz=timezone.utc).isoformat()


def ns_to_ms(value: int | float | None) -> float | None:
    """Convert nanoseconds to milliseconds."""

    if value is None:
        return None
    return float(value) / NS_PER_MS


def monotonic_deadline(duration_s: float) -> int:
    """Return a monotonic deadline duration seconds from now."""

    return monotonic_ns() + int(duration_s * NS_PER_SEC)
