import pytest

from ros2_netbench.utils.stats import (
    SequenceTracker,
    jitter_ms_from_timestamps,
    ns_latency_summary,
    percentile,
    safe_ratio,
    summary_stats,
)


def test_percentile_empty_and_single_sample():
    assert percentile([], 95) is None
    assert percentile([10], 95) == 10.0


def test_percentile_interpolates():
    assert percentile([0, 10, 20, 30], 50) == 15.0
    assert percentile([0, 10, 20, 30], 90) == pytest.approx(27.0)


def test_summary_handles_small_counts():
    empty = summary_stats([])
    assert empty["count"] == 0
    assert empty["mean"] is None

    one = summary_stats([5])
    assert one["count"] == 1
    assert one["std"] == 0.0
    assert one["p99"] == 5.0


def test_ns_latency_summary_reports_milliseconds():
    result = ns_latency_summary([1_000_000, 2_000_000, 3_000_000])
    assert result["min"] == 1.0
    assert result["mean"] == 2.0
    assert result["max"] == 3.0


def test_sequence_gap_loss_detection():
    tracker = SequenceTracker(expected_start_seq=0)
    events = [tracker.observe(seq) for seq in [0, 1, 4]]
    assert events[-1].lost_gap_detected is True
    assert events[-1].gap_size == 2
    assert tracker.receiver_gap_events == 1
    assert tracker.final_loss_count() == 2
    assert tracker.inferred_sent_count() == 5


def test_duplicate_detection():
    tracker = SequenceTracker(expected_start_seq=0)
    tracker.observe(0)
    event = tracker.observe(0)
    assert event.duplicate is True
    assert tracker.duplicate_count == 1
    assert tracker.unique_received_count == 1


def test_reorder_detection_reduces_final_loss_when_late_packet_arrives():
    tracker = SequenceTracker(expected_start_seq=0)
    tracker.observe(0)
    tracker.observe(2)
    late = tracker.observe(1)
    assert late.out_of_order is True
    assert tracker.out_of_order_count == 1
    assert tracker.final_loss_count() == 0


def test_sequence_tracker_unknown_start_uses_first_observed_range():
    tracker = SequenceTracker(expected_start_seq=None)
    tracker.observe(10)
    tracker.observe(12)
    assert tracker.inferred_sent_count() == 3
    assert tracker.final_loss_count() == 1


def test_jitter_from_timestamps():
    assert jitter_ms_from_timestamps([]) is None
    assert jitter_ms_from_timestamps([0, 1_000_000]) == 0.0
    assert jitter_ms_from_timestamps([0, 1_000_000, 3_000_000]) is not None


def test_safe_ratio_zero_denominator():
    assert safe_ratio(5, 0) == 0.0
