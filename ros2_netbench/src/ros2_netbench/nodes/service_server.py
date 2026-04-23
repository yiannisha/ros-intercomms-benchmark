"""ROS 2 service latency benchmark server."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import rclpy
from rclpy.node import Node

from ros2_netbench_interfaces.srv import BenchmarkService

from ros2_netbench.nodes.common import (
    ArtifactManager,
    RunConfig,
    ShutdownFlag,
    add_common_arguments,
    base_summary,
    config_from_args,
)
from ros2_netbench.nodes.sys_monitor import SystemMonitor
from ros2_netbench.utils.clocks import NS_PER_MS, iso_utc_from_wall_ns, monotonic_ns, wall_ns
from ros2_netbench.utils.network import apply_domain_id
from ros2_netbench.utils.qos import qos_profile
from ros2_netbench.utils.stats import rate


class ServiceServer(Node):
    def __init__(self, config: RunConfig) -> None:
        super().__init__("netbench_service_server")
        self.config = config
        self.service = self.create_service(
            BenchmarkService,
            config.service,
            self._on_request,
            qos_profile=qos_profile(config.qos),
        )
        self.active_session_id: int | None = None if config.session_id == 0 else config.session_id
        self.first_request_mono_ns: int | None = None
        self.end_ns: int | None = None
        self.finished = False
        self.received = 0
        self.replied = 0
        self.rows: list[dict[str, Any]] = []

    def _on_request(
        self,
        request: BenchmarkService.Request,
        response: BenchmarkService.Response,
    ) -> BenchmarkService.Response:
        packet = request.packet
        now = monotonic_ns()
        if self.active_session_id is None:
            self.active_session_id = packet.session_id
        if packet.session_id != self.active_session_id:
            response.ok = False
            response.error = "session_id_mismatch"
            return response
        if self.first_request_mono_ns is None:
            self.first_request_mono_ns = now
            total = self.config.warmup_s + self.config.duration_s + self.config.request_timeout_s
            self.end_ns = now + int(total * 1_000_000_000)
        self.received += 1
        response.packet = packet
        response.ok = True
        response.error = ""
        self.replied += 1
        receive_wall_ns = wall_ns()
        self.rows.append(
            {
                "timestamp": iso_utc_from_wall_ns(receive_wall_ns),
                "seq": packet.seq,
                "send_time_ns": packet.sender_wall_ns,
                "receive_time_ns": receive_wall_ns,
                "local_receive_monotonic_ns": now,
                "rtt_ns": None,
                "payload_size": packet.payload_size,
                "reordered": False,
                "duplicate": False,
                "lost_gap_detected": False,
                "gap_size": 0,
                "timeout": False,
            }
        )
        return response

    def maybe_finish_after_deadline(self) -> None:
        if self.end_ns is not None and monotonic_ns() > self.end_ns:
            self.finished = True


def run(config: RunConfig) -> int:
    apply_domain_id(config.domain_id)
    rclpy.init()
    node = ServiceServer(config)
    artifacts = ArtifactManager(config, record_topics=[])
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
            if discovery_time_ms is None and node.count_clients(config.service) > 0:
                discovery_time_ms = (monotonic_ns() - discovery_start_ns) / NS_PER_MS
            if node.first_request_mono_ns is None:
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
        summary.update(
            {
                "active_session_id": node.active_session_id,
                "sent_messages": node.replied,
                "received_messages": node.received,
                "application_level_loss_count": 0,
                "application_level_loss_rate": 0.0,
                "duplicate_count": 0,
                "out_of_order_count": 0,
                "throughput_messages_per_sec": rate(node.replied, config.duration_s),
                "throughput_bytes_per_sec": rate(node.replied * config.payload_size, config.duration_s),
                "achieved_request_rate": None,
                "RTT": {"valid": False, "reason": "computed_by_service_client"},
                "one_way_latency": {"valid": False, "reason": "not_applicable_for_service_server"},
                "inter_arrival_jitter_ms": None,
                "publish_period_jitter_ms": None,
                "receiver_gap_events": None,
                "timeout_count": 0 if node.first_request_mono_ns is not None else 1,
                "discovery_time_ms": discovery_time_ms,
                "connection_ready_time_ms": (
                    (node.first_request_mono_ns - discovery_start_ns) / NS_PER_MS
                    if node.first_request_mono_ns is not None
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
        args_list = ["--mode", "service", "--role", "server", *args_list]
    config = config_from_args(build_parser().parse_args(args_list))
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
