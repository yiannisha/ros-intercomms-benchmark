"""Pub/sub stream benchmark sender."""

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
    packet_payload,
    remove_ros_arguments,
    timer_period,
)
from ros2_netbench.nodes.sys_monitor import SystemMonitor
from ros2_netbench.utils.clocks import NS_PER_MS, iso_utc_from_wall_ns, monotonic_ns, wall_ns
from ros2_netbench.utils.network import apply_domain_id
from ros2_netbench.utils.qos import qos_profile
from ros2_netbench.utils.stats import jitter_ms_from_timestamps, rate


class StreamSender(Node):
    def __init__(self, config: RunConfig) -> None:
        super().__init__("netbench_stream_sender")
        self.config = config
        self.publisher = self.create_publisher(
            BenchmarkPacket,
            config.topic,
            qos_profile(config.qos),
        )
        self.payload = packet_payload(config.payload_size)
        self.timer = None
        self.started_mono_ns: int | None = None
        self.measure_start_ns: int | None = None
        self.measure_end_ns: int | None = None
        self.finished = False
        self.seq = 0
        self.sent_rows: list[dict[str, Any]] = []
        self.send_monotonic_ns: list[int] = []

    def start(self) -> None:
        now = monotonic_ns()
        self.started_mono_ns = now
        self.measure_start_ns = now + int(self.config.warmup_s * 1_000_000_000)
        self.measure_end_ns = self.measure_start_ns + int(self.config.duration_s * 1_000_000_000)
        self.timer = self.create_timer(timer_period(self.config.rate_hz), self._on_timer)

    def _on_timer(self) -> None:
        if self.finished:
            return
        now_mono = monotonic_ns()
        assert self.measure_start_ns is not None
        assert self.measure_end_ns is not None
        if now_mono >= self.measure_end_ns:
            self.finished = True
            if self.timer is not None:
                self.timer.cancel()
            return

        in_measurement = now_mono >= self.measure_start_ns
        seq = self.seq
        self.seq += 1

        send_wall_ns = wall_ns()
        packet = BenchmarkPacket()
        packet.seq = seq
        packet.sender_monotonic_ns = now_mono
        packet.sender_wall_ns = send_wall_ns
        packet.session_id = self.config.session_id
        packet.payload_size = self.config.payload_size
        packet.payload = self.payload
        self.publisher.publish(packet)

        if in_measurement:
            self.send_monotonic_ns.append(now_mono)
            self.sent_rows.append(
                {
                    "timestamp": iso_utc_from_wall_ns(send_wall_ns),
                    "seq": seq,
                    "send_time_ns": send_wall_ns,
                    "receive_time_ns": None,
                    "local_receive_monotonic_ns": None,
                    "rtt_ns": None,
                    "payload_size": self.config.payload_size,
                    "reordered": False,
                    "duplicate": False,
                    "lost_gap_detected": False,
                    "gap_size": 0,
                    "timeout": False,
                }
            )

    def wait_for_subscription(self, timeout_s: float, stop: ShutdownFlag) -> float | None:
        start = monotonic_ns()
        while rclpy.ok() and not stop.requested:
            if self.count_subscribers(self.config.topic) > 0:
                return (monotonic_ns() - start) / NS_PER_MS
            if (monotonic_ns() - start) / 1_000_000_000 > timeout_s:
                return None
            rclpy.spin_once(self, timeout_sec=0.05)
        return None


def run(config: RunConfig) -> int:
    apply_domain_id(config.domain_id)
    rclpy.init()
    node = StreamSender(config)
    artifacts = ArtifactManager(config, record_topics=[config.topic])
    monitor = SystemMonitor(interface=config.nic) if config.sample_system else None
    stop = ShutdownFlag()
    stop.install()
    started_wall = iso_utc_from_wall_ns()
    discovery_time_ms: float | None = None
    try:
        artifacts.write_metadata()
        artifacts.start_optional_recorders()
        discovery_time_ms = node.wait_for_subscription(config.discovery_timeout_s, stop)
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
        sent = len(node.sent_rows)
        summary.update(
            {
                "sent_messages": sent,
                "received_messages": None,
                "application_level_loss_count": None,
                "application_level_loss_rate": None,
                "duplicate_count": 0,
                "out_of_order_count": 0,
                "throughput_messages_per_sec": rate(sent, config.duration_s),
                "throughput_bytes_per_sec": rate(sent * config.payload_size, config.duration_s),
                "RTT": {"valid": False, "reason": "not_applicable_for_stream_sender"},
                "one_way_latency": {"valid": False, "reason": "computed_by_receiver"},
                "inter_arrival_jitter_ms": None,
                "publish_period_jitter_ms": jitter_ms_from_timestamps(node.send_monotonic_ns),
                "receiver_gap_events": None,
                "timeout_count": 0,
                "discovery_time_ms": discovery_time_ms,
                "connection_ready_time_ms": discovery_time_ms,
            }
        )
        if monitor is not None:
            summary.update(monitor.summary("sender"))
            artifacts.write_system_samples(monitor.rows())
        artifacts.write_raw_samples(node.sent_rows)
        artifacts.write_summary(summary)
        node.destroy_node()
        rclpy.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = remove_ros_arguments(list(sys.argv[1:] if argv is None else argv))
    if "--mode" not in args_list:
        args_list = ["--mode", "stream", "--role", "sender", *args_list]
    config = config_from_args(build_parser().parse_args(args_list))
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
