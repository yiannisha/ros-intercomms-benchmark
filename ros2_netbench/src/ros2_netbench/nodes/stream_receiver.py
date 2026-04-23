"""Pub/sub stream benchmark receiver."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import rclpy
from rclpy.node import Node

from ros2_netbench_interfaces.msg import BenchmarkPacket

from ros2_netbench.nodes.common import (
    ArtifactManager,
    RunConfig,
    ShutdownFlag,
    add_common_arguments,
    base_summary,
    config_from_args,
    empty_latency_summary,
    one_way_latency_valid,
)
from ros2_netbench.nodes.sys_monitor import SystemMonitor
from ros2_netbench.utils.clocks import NS_PER_MS, iso_utc_from_wall_ns, monotonic_ns, wall_ns
from ros2_netbench.utils.network import apply_domain_id
from ros2_netbench.utils.qos import qos_profile
from ros2_netbench.utils.stats import (
    SequenceTracker,
    jitter_ms_from_timestamps,
    ns_latency_summary,
    rate,
    safe_ratio,
)


class StreamReceiver(Node):
    def __init__(self, config: RunConfig) -> None:
        super().__init__("netbench_stream_receiver")
        self.config = config
        self.subscription = self.create_subscription(
            BenchmarkPacket,
            config.topic,
            self._on_packet,
            qos_profile(config.qos),
        )
        self.active_session_id: int | None = None if config.session_id == 0 else config.session_id
        self.first_packet_mono_ns: int | None = None
        self.measure_start_ns: int | None = None
        self.measure_end_ns: int | None = None
        self.finished = False
        self.tracker = SequenceTracker(expected_start_seq=None)
        self.rows: list[dict[str, Any]] = []
        self.receive_monotonic_ns: list[int] = []
        self.one_way_ns: list[int] = []
        self.one_way_valid, self.one_way_reason = one_way_latency_valid(config)

    def _on_packet(self, packet: BenchmarkPacket) -> None:
        now_mono = monotonic_ns()
        if self.active_session_id is None:
            self.active_session_id = packet.session_id
        if packet.session_id != self.active_session_id:
            return

        if self.first_packet_mono_ns is None:
            self.first_packet_mono_ns = now_mono
            self.measure_start_ns = now_mono + int(self.config.warmup_s * 1_000_000_000)
            self.measure_end_ns = self.measure_start_ns + int(self.config.duration_s * 1_000_000_000)

        assert self.measure_start_ns is not None
        assert self.measure_end_ns is not None
        if now_mono < self.measure_start_ns:
            return
        if now_mono > self.measure_end_ns:
            self.finished = True
            return

        receive_wall_ns = wall_ns()
        event = self.tracker.observe(packet.seq)
        if self.one_way_valid:
            offset_ns = int((self.config.clock_offset_ms or 0.0) * 1_000_000)
            self.one_way_ns.append(receive_wall_ns - int(packet.sender_wall_ns) - offset_ns)
        self.receive_monotonic_ns.append(now_mono)
        self.rows.append(
            {
                "timestamp": iso_utc_from_wall_ns(receive_wall_ns),
                "seq": packet.seq,
                "send_time_ns": packet.sender_wall_ns,
                "receive_time_ns": receive_wall_ns,
                "local_receive_monotonic_ns": now_mono,
                "rtt_ns": None,
                "payload_size": packet.payload_size,
                "reordered": event.out_of_order,
                "duplicate": event.duplicate,
                "lost_gap_detected": event.lost_gap_detected,
                "gap_size": event.gap_size,
                "timeout": False,
            }
        )

    def maybe_finish_after_deadline(self) -> None:
        if self.measure_end_ns is not None and monotonic_ns() > self.measure_end_ns:
            self.finished = True


def run(config: RunConfig) -> int:
    apply_domain_id(config.domain_id)
    rclpy.init()
    node = StreamReceiver(config)
    artifacts = ArtifactManager(config, record_topics=[config.topic])
    monitor = SystemMonitor(interface=config.nic) if config.sample_system else None
    stop = ShutdownFlag()
    stop.install()
    started_wall = iso_utc_from_wall_ns()
    discovery_start_ns = monotonic_ns()
    discovery_time_ms: float | None = None
    try:
        artifacts.write_metadata()
        artifacts.start_optional_recorders()
        last_sample = 0
        while rclpy.ok() and not stop.requested and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.05)
            if discovery_time_ms is None and node.count_publishers(config.topic) > 0:
                discovery_time_ms = (monotonic_ns() - discovery_start_ns) / NS_PER_MS
            if node.first_packet_mono_ns is None:
                elapsed_s = (monotonic_ns() - discovery_start_ns) / 1_000_000_000
                if elapsed_s > config.discovery_timeout_s:
                    break
            node.maybe_finish_after_deadline()
            if monitor is not None and monotonic_ns() - last_sample >= 1_000_000_000:
                monitor.sample()
                last_sample = monotonic_ns()
    finally:
        ended_wall = iso_utc_from_wall_ns()
        artifacts.stop_optional_recorders()
        summary = base_summary(config, started_wall, ended_wall)
        inferred_sent = node.tracker.inferred_sent_count()
        received_total = len(node.rows)
        loss_count = node.tracker.final_loss_count()
        one_way = empty_latency_summary(valid=False, reason=node.one_way_reason)
        if node.one_way_valid:
            one_way = ns_latency_summary(node.one_way_ns)
            one_way["valid"] = True
            one_way["reason"] = node.one_way_reason
        summary.update(
            {
                "active_session_id": node.active_session_id,
                "sent_messages": inferred_sent,
                "received_messages": received_total,
                "unique_received_messages": node.tracker.unique_received_count,
                "application_level_loss_count": loss_count,
                "application_level_loss_rate": safe_ratio(loss_count, inferred_sent),
                "duplicate_count": node.tracker.duplicate_count,
                "out_of_order_count": node.tracker.out_of_order_count,
                "throughput_messages_per_sec": rate(received_total, config.duration_s),
                "throughput_bytes_per_sec": rate(received_total * config.payload_size, config.duration_s),
                "RTT": {"valid": False, "reason": "not_applicable_for_stream_receiver"},
                "one_way_latency": one_way,
                "inter_arrival_jitter_ms": jitter_ms_from_timestamps(node.receive_monotonic_ns),
                "publish_period_jitter_ms": None,
                "receiver_gap_events": node.tracker.receiver_gap_events,
                "timeout_count": 0 if node.first_packet_mono_ns is not None else 1,
                "discovery_time_ms": discovery_time_ms,
                "connection_ready_time_ms": (
                    (node.first_packet_mono_ns - discovery_start_ns) / NS_PER_MS
                    if node.first_packet_mono_ns is not None
                    else None
                ),
            }
        )
        if monitor is not None:
            summary.update(monitor.summary("receiver"))
            artifacts.write_system_samples(monitor.rows())
        artifacts.write_raw_samples(node.rows)
        artifacts.write_summary(summary)
        node.destroy_node()
        rclpy.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if "--mode" not in args_list:
        args_list = ["--mode", "stream", "--role", "receiver", *args_list]
    config = config_from_args(build_parser().parse_args(args_list))
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
