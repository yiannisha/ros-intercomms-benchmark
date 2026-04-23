"""Ping/pong RTT benchmark client."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
    packet_payload,
    timer_period,
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


@dataclass(slots=True)
class PendingPing:
    seq: int
    sent_monotonic_ns: int
    sent_wall_ns: int
    warmup: bool
    timed_out: bool = False


class PingClient(Node):
    def __init__(self, config: RunConfig) -> None:
        super().__init__("netbench_ping_client")
        self.config = config
        qos = qos_profile(config.qos)
        self.publisher = self.create_publisher(BenchmarkPacket, config.topic, qos)
        self.subscription = self.create_subscription(BenchmarkPacket, config.echo_topic, self._on_pong, qos)
        self.payload = packet_payload(config.payload_size)
        self.timer = None
        self.started_mono_ns: int | None = None
        self.measure_start_ns: int | None = None
        self.measure_end_ns: int | None = None
        self.finished = False
        self.seq = 0
        self.sent_measurement = 0
        self.pending: dict[int, PendingPing] = {}
        self.tracker = SequenceTracker(expected_start_seq=None)
        self.rows: list[dict[str, Any]] = []
        self.rtt_ns: list[int] = []
        self.send_monotonic_ns: list[int] = []
        self.reply_monotonic_ns: list[int] = []
        self.timeout_count = 0

    def start(self) -> None:
        now = monotonic_ns()
        self.started_mono_ns = now
        self.measure_start_ns = now + int(self.config.warmup_s * 1_000_000_000)
        self.measure_end_ns = self.measure_start_ns + int(self.config.duration_s * 1_000_000_000)
        self.timer = self.create_timer(timer_period(self.config.rate_hz), self._on_timer)

    def _on_timer(self) -> None:
        if self.finished:
            return
        now = monotonic_ns()
        assert self.measure_start_ns is not None
        assert self.measure_end_ns is not None
        self._check_timeouts(now)
        if now < self.measure_end_ns:
            warmup = now < self.measure_start_ns
            seq = self.seq
            self.seq += 1
            if not warmup:
                self.sent_measurement += 1
                self.send_monotonic_ns.append(now)
            send_wall = wall_ns()
            packet = BenchmarkPacket()
            packet.seq = seq
            packet.sender_monotonic_ns = now
            packet.sender_wall_ns = send_wall
            packet.session_id = self.config.session_id
            packet.payload_size = self.config.payload_size
            packet.payload = self.payload
            self.pending[seq] = PendingPing(seq, now, send_wall, warmup=warmup)
            self.publisher.publish(packet)
        elif now > self.measure_end_ns + int(self.config.request_timeout_s * 1_000_000_000):
            self.finished = True
            if self.timer is not None:
                self.timer.cancel()

    def _check_timeouts(self, now: int) -> None:
        timeout_ns = int(self.config.request_timeout_s * 1_000_000_000)
        for pending in list(self.pending.values()):
            if pending.warmup or pending.timed_out:
                continue
            if now - pending.sent_monotonic_ns >= timeout_ns:
                pending.timed_out = True
                self.timeout_count += 1
                self.rows.append(
                    {
                        "timestamp": iso_utc_from_wall_ns(),
                        "seq": pending.seq,
                        "send_time_ns": pending.sent_wall_ns,
                        "receive_time_ns": None,
                        "local_receive_monotonic_ns": None,
                        "rtt_ns": None,
                        "payload_size": self.config.payload_size,
                        "reordered": False,
                        "duplicate": False,
                        "lost_gap_detected": False,
                        "gap_size": 0,
                        "timeout": True,
                    }
                )

    def _on_pong(self, packet: BenchmarkPacket) -> None:
        if packet.session_id != self.config.session_id:
            return
        now = monotonic_ns()
        pending = self.pending.get(packet.seq)
        if pending is None or pending.warmup:
            return
        receive_wall = wall_ns()
        event = self.tracker.observe(packet.seq)
        rtt = now - pending.sent_monotonic_ns
        self.rtt_ns.append(rtt)
        self.reply_monotonic_ns.append(now)
        self.rows.append(
            {
                "timestamp": iso_utc_from_wall_ns(receive_wall),
                "seq": packet.seq,
                "send_time_ns": pending.sent_wall_ns,
                "receive_time_ns": receive_wall,
                "local_receive_monotonic_ns": now,
                "rtt_ns": rtt,
                "payload_size": packet.payload_size,
                "reordered": event.out_of_order,
                "duplicate": event.duplicate,
                "lost_gap_detected": event.lost_gap_detected,
                "gap_size": event.gap_size,
                "timeout": False,
            }
        )

    def wait_for_server(self, timeout_s: float, stop: ShutdownFlag) -> float | None:
        start = monotonic_ns()
        while rclpy.ok() and not stop.requested:
            has_sub = self.count_subscribers(self.config.topic) > 0
            has_pub = self.count_publishers(self.config.echo_topic) > 0
            if has_sub and has_pub:
                return (monotonic_ns() - start) / NS_PER_MS
            if (monotonic_ns() - start) / 1_000_000_000 > timeout_s:
                return None
            rclpy.spin_once(self, timeout_sec=0.05)
        return None


def run(config: RunConfig) -> int:
    apply_domain_id(config.domain_id)
    rclpy.init()
    node = PingClient(config)
    artifacts = ArtifactManager(config, record_topics=[config.topic, config.echo_topic])
    monitor = SystemMonitor(interface=config.nic) if config.sample_system else None
    stop = ShutdownFlag()
    stop.install()
    started_wall = iso_utc_from_wall_ns()
    discovery_time_ms: float | None = None
    try:
        artifacts.write_metadata()
        artifacts.start_optional_recorders()
        discovery_time_ms = node.wait_for_server(config.discovery_timeout_s, stop)
        node.start()
        last_sample = 0
        while rclpy.ok() and not stop.requested and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.05)
            if monitor is not None and monotonic_ns() - last_sample >= 1_000_000_000:
                monitor.sample()
                last_sample = monotonic_ns()
    finally:
        ended_wall = iso_utc_from_wall_ns()
        artifacts.stop_optional_recorders()
        summary = base_summary(config, started_wall, ended_wall)
        received = node.tracker.unique_received_count
        loss_count = max(0, node.sent_measurement - received)
        rtt = ns_latency_summary(node.rtt_ns)
        rtt["valid"] = bool(node.rtt_ns)
        rtt["reason"] = "ok" if node.rtt_ns else "no_rtt_samples"
        summary.update(
            {
                "sent_messages": node.sent_measurement,
                "received_messages": len([row for row in node.rows if not row["timeout"]]),
                "unique_received_messages": received,
                "application_level_loss_count": loss_count,
                "application_level_loss_rate": safe_ratio(loss_count, node.sent_measurement),
                "duplicate_count": node.tracker.duplicate_count,
                "out_of_order_count": node.tracker.out_of_order_count,
                "throughput_messages_per_sec": rate(received, config.duration_s),
                "throughput_bytes_per_sec": rate(received * config.payload_size, config.duration_s),
                "achieved_request_rate": rate(node.sent_measurement, config.duration_s),
                "RTT": rtt,
                "one_way_latency": empty_latency_summary(False, "not_applicable_for_ping"),
                "inter_arrival_jitter_ms": jitter_ms_from_timestamps(node.reply_monotonic_ns),
                "publish_period_jitter_ms": jitter_ms_from_timestamps(node.send_monotonic_ns),
                "receiver_gap_events": node.tracker.receiver_gap_events,
                "timeout_count": node.timeout_count,
                "timeout_rate": safe_ratio(node.timeout_count, node.sent_measurement),
                "discovery_time_ms": discovery_time_ms,
                "connection_ready_time_ms": discovery_time_ms,
            }
        )
        if monitor is not None:
            summary.update(monitor.summary("sender"))
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
        args_list = ["--mode", "ping", "--role", "client", *args_list]
    config = config_from_args(build_parser().parse_args(args_list))
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
