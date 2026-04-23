"""Statistical helpers and sequence-quality accounting."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import fmean
from typing import Iterable, Sequence

from ros2_netbench.utils.clocks import NS_PER_MS


PERCENTILES = (50, 90, 95, 99)


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Return a percentile using linear interpolation.

    The function handles empty and single-sample inputs cleanly and does not
    mutate the caller's sequence.
    """

    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    if pct <= 0:
        return float(min(values))
    if pct >= 100:
        return float(max(values))

    ordered = sorted(float(v) for v in values)
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def sample_stddev(values: Sequence[float]) -> float | None:
    """Return sample standard deviation, or 0 for one sample."""

    if not values:
        return None
    if len(values) == 1:
        return 0.0
    mean = fmean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def summary_stats(values: Iterable[float]) -> dict[str, float | int | None]:
    """Return min/mean/std/percentile/max summary values."""

    materialized = [float(v) for v in values]
    if not materialized:
        return {
            "count": 0,
            "min": None,
            "mean": None,
            "std": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "count": len(materialized),
        "min": min(materialized),
        "mean": fmean(materialized),
        "std": sample_stddev(materialized),
        "p50": percentile(materialized, 50),
        "p90": percentile(materialized, 90),
        "p95": percentile(materialized, 95),
        "p99": percentile(materialized, 99),
        "max": max(materialized),
    }


def ns_latency_summary(values_ns: Iterable[int]) -> dict[str, float | int | None]:
    """Return latency stats in milliseconds for nanosecond samples."""

    return summary_stats(float(value) / NS_PER_MS for value in values_ns)


@dataclass(slots=True)
class SequenceEvent:
    seq: int
    duplicate: bool
    out_of_order: bool
    lost_gap_detected: bool
    gap_size: int


class SequenceTracker:
    """Track app-level duplicate, out-of-order, and sequence-gap behavior."""

    def __init__(self, expected_start_seq: int | None = 0) -> None:
        self.expected_start_seq = expected_start_seq
        self.seen: set[int] = set()
        self.max_seq_seen: int | None = None
        self.min_seq_seen: int | None = None
        self.duplicate_count = 0
        self.out_of_order_count = 0
        self.receiver_gap_events = 0
        self.gap_count_detected_online = 0

    def observe(self, seq: int) -> SequenceEvent:
        duplicate = seq in self.seen
        out_of_order = False
        lost_gap_detected = False
        gap_size = 0

        if duplicate:
            self.duplicate_count += 1
        else:
            if self.max_seq_seen is not None:
                if seq < self.max_seq_seen:
                    out_of_order = True
                    self.out_of_order_count += 1
                elif seq > self.max_seq_seen + 1:
                    lost_gap_detected = True
                    gap_size = seq - self.max_seq_seen - 1
                    self.receiver_gap_events += 1
                    self.gap_count_detected_online += gap_size
            self.seen.add(seq)
            self.min_seq_seen = seq if self.min_seq_seen is None else min(self.min_seq_seen, seq)
            self.max_seq_seen = seq if self.max_seq_seen is None else max(self.max_seq_seen, seq)

        return SequenceEvent(
            seq=seq,
            duplicate=duplicate,
            out_of_order=out_of_order,
            lost_gap_detected=lost_gap_detected,
            gap_size=gap_size,
        )

    @property
    def unique_received_count(self) -> int:
        return len(self.seen)

    def inferred_sent_count(self) -> int:
        """Return inferred sent count from the expected start to max seq seen."""

        if self.max_seq_seen is None:
            return 0
        start = self.expected_start_seq
        if start is None:
            start = self.min_seq_seen if self.min_seq_seen is not None else self.max_seq_seen
        if self.max_seq_seen < start:
            return 0
        return self.max_seq_seen - start + 1

    def final_loss_count(self) -> int:
        """Return missing sequence numbers in the observed measurement range."""

        if self.max_seq_seen is None:
            return 0
        start = self.expected_start_seq
        if start is None:
            start = self.min_seq_seen if self.min_seq_seen is not None else self.max_seq_seen
        if self.max_seq_seen < start:
            return 0
        expected = set(range(start, self.max_seq_seen + 1))
        return len(expected - self.seen)


def rate(count: int, duration_s: float) -> float:
    if duration_s <= 0:
        return 0.0
    return float(count) / duration_s


def safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def jitter_ms_from_timestamps(monotonic_ns_values: Sequence[int]) -> float | None:
    """Return sample stddev of inter-arrival periods in milliseconds."""

    if len(monotonic_ns_values) < 3:
        return 0.0 if len(monotonic_ns_values) >= 2 else None
    deltas_ms = [
        (later - earlier) / NS_PER_MS
        for earlier, later in zip(monotonic_ns_values, monotonic_ns_values[1:])
    ]
    return sample_stddev(deltas_ms)
