"""Shared node configuration and artifact helpers."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import secrets
import signal
from typing import Any

from ros2_netbench import __version__
from ros2_netbench.utils.clocks import iso_utc_from_wall_ns, wall_ns
from ros2_netbench.utils.csv_json import ensure_dir, write_csv, write_json
from ros2_netbench.utils.network import ManagedProcess, command_available
from ros2_netbench.utils.qos import QosConfig, add_qos_arguments, qos_config_from_args


DISCOVERY_ENV_KEYS = (
    "ROS_DOMAIN_ID",
    "RMW_IMPLEMENTATION",
    "ROS_DISCOVERY_SERVER",
    "FASTRTPS_DEFAULT_PROFILES_FILE",
    "FASTDDS_DEFAULT_PROFILES_FILE",
    "CYCLONEDDS_URI",
)


@dataclass(slots=True)
class RunConfig:
    mode: str
    role: str
    run_id: str
    output_dir: Path
    payload_size: int
    rate_hz: float
    duration_s: float
    warmup_s: float
    session_id: int
    domain_id: int | None
    topic: str
    echo_topic: str
    service: str
    qos: QosConfig
    clock_sync: str
    max_clock_offset_ms: float
    clock_offset_ms: float | None
    sample_system: bool
    nic: str | None
    bag: bool
    trace: bool
    request_timeout_s: float
    discovery_timeout_s: float

    def metadata(self) -> dict[str, Any]:
        return {
            "tool": "ros2_netbench",
            "version": __version__,
            "mode": self.mode,
            "role": self.role,
            "run_id": self.run_id,
            "created_at": iso_utc_from_wall_ns(),
            "payload_size": self.payload_size,
            "rate_hz": self.rate_hz,
            "duration_s": self.duration_s,
            "warmup_s": self.warmup_s,
            "session_id": self.session_id,
            "domain_id": self.domain_id,
            "topic": self.topic,
            "echo_topic": self.echo_topic,
            "service": self.service,
            "qos": self.qos.as_dict(),
            "clock_sync": {
                "mode": self.clock_sync,
                "max_clock_offset_ms": self.max_clock_offset_ms,
                "clock_offset_ms": self.clock_offset_ms,
            },
            "sample_system": self.sample_system,
            "nic": self.nic,
            "bag": self.bag,
            "trace": self.trace,
            "request_timeout_s": self.request_timeout_s,
            "discovery_timeout_s": self.discovery_timeout_s,
            "environment": {
                key: os.environ.get(key)
                for key in DISCOVERY_ENV_KEYS
                if os.environ.get(key) is not None
            },
        }


class ShutdownFlag:
    def __init__(self) -> None:
        self.requested = False

    def install(self) -> None:
        def _handle(_signum: int, _frame: Any) -> None:
            self.requested = True

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)


class ArtifactManager:
    def __init__(self, config: RunConfig, record_topics: list[str] | None = None) -> None:
        self.config = config
        self.record_topics = record_topics or []
        self.run_dir = ensure_dir(config.output_dir / config.run_id)
        self._bag_process: ManagedProcess | None = None
        self._trace_process: ManagedProcess | None = None

    def write_metadata(self) -> None:
        write_json(self.run_dir / "run_metadata.json", self.config.metadata())

    def start_optional_recorders(self) -> None:
        if self.config.bag:
            if not command_available("ros2"):
                raise RuntimeError("--bag requested but 'ros2' command is not available")
            bag_dir = self.run_dir / "rosbag"
            if self.record_topics:
                argv = ["ros2", "bag", "record", "-o", str(bag_dir), *self.record_topics]
            else:
                argv = ["ros2", "bag", "record", "-a", "-o", str(bag_dir)]
            self._bag_process = ManagedProcess(argv)
            self._bag_process.start()
        if self.config.trace:
            if not command_available("ros2"):
                raise RuntimeError("--trace requested but 'ros2' command is not available")
            trace_dir = self.run_dir / "trace"
            argv = ["ros2", "trace", "-s", str(trace_dir)]
            self._trace_process = ManagedProcess(argv)
            self._trace_process.start()

    def stop_optional_recorders(self) -> None:
        if self._bag_process is not None:
            self._bag_process.stop()
        if self._trace_process is not None:
            self._trace_process.stop()

    def write_summary(self, summary: dict[str, Any]) -> None:
        path = self.run_dir / "summary.json"
        write_json(path, summary)
        fields = [
            f"{summary.get('mode')}/{summary.get('role')}",
            f"sent={summary.get('sent_messages')}",
            f"received={summary.get('received_messages')}",
            f"timeouts={summary.get('timeout_count')}",
            f"summary={path}",
        ]
        print("[ros2_netbench] " + " ".join(fields), flush=True)

    def write_raw_samples(self, rows: list[dict[str, Any]]) -> None:
        fields = [
            "timestamp",
            "seq",
            "send_time_ns",
            "receive_time_ns",
            "local_receive_monotonic_ns",
            "rtt_ns",
            "payload_size",
            "reordered",
            "duplicate",
            "lost_gap_detected",
            "gap_size",
            "timeout",
        ]
        write_csv(self.run_dir / "raw_samples.csv", fields, rows)

    def write_system_samples(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        write_csv(
            self.run_dir / "system_stats.csv",
            ["timestamp", "monotonic_ns", "cpu_percent", "memory_mb", "nic_tx_bps", "nic_rx_bps"],
            rows,
        )


def new_run_id(mode: str, role: str) -> str:
    stamp = iso_utc_from_wall_ns(wall_ns()).replace(":", "").replace("+0000", "Z")
    suffix = secrets.token_hex(3)
    return f"{stamp}_{mode}_{role}_{suffix}"


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["stream", "ping", "service"], required=True)
    parser.add_argument(
        "--role",
        choices=["sender", "receiver", "client", "server"],
        required=True,
        help="stream uses sender/receiver; ping and service use client/server",
    )
    parser.add_argument("--payload-size", type=int, default=1024)
    parser.add_argument("--rate-hz", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--session-id", type=int, default=None)
    parser.add_argument("--domain-id", type=int, default=None)
    parser.add_argument("--topic", default="/netbench/stream")
    parser.add_argument("--echo-topic", default="/netbench/pong")
    parser.add_argument("--service", default="/netbench/service")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--clock-sync",
        choices=["unknown", "ok", "offset"],
        default="unknown",
        help="Controls whether one-way latency is reported as valid.",
    )
    parser.add_argument("--max-clock-offset-ms", type=float, default=1.0)
    parser.add_argument("--clock-offset-ms", type=float, default=None)
    parser.add_argument("--sample-system", action="store_true")
    parser.add_argument("--nic", default=None, help="Linux network interface to sample, e.g. eth0")
    parser.add_argument("--bag", action="store_true", help="Record benchmark topics with rosbag2")
    parser.add_argument("--trace", action="store_true", help="Start ros2 tracing if installed")
    parser.add_argument("--request-timeout", type=float, default=1.0)
    parser.add_argument("--discovery-timeout", type=float, default=10.0)
    add_qos_arguments(parser)


def remove_ros_arguments(args: list[str]) -> list[str]:
    from rclpy.utilities import remove_ros_args

    return remove_ros_args(args=args)


def config_from_args(args: argparse.Namespace) -> RunConfig:
    if args.payload_size < 0:
        raise ValueError("--payload-size must be >= 0")
    if args.payload_size > 4_294_967_295:
        raise ValueError("--payload-size must fit uint32")
    if args.rate_hz <= 0:
        raise ValueError("--rate-hz must be > 0")
    if args.duration <= 0:
        raise ValueError("--duration must be > 0")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0")
    if args.request_timeout <= 0:
        raise ValueError("--request-timeout must be > 0")
    if args.discovery_timeout <= 0:
        raise ValueError("--discovery-timeout must be > 0")
    if args.clock_sync == "offset" and args.clock_offset_ms is None:
        raise ValueError("--clock-sync offset requires --clock-offset-ms")
    if args.mode == "stream" and args.role not in {"sender", "receiver"}:
        raise ValueError("stream mode requires role sender or receiver")
    if args.mode in {"ping", "service"} and args.role not in {"client", "server"}:
        raise ValueError(f"{args.mode} mode requires role client or server")

    session_id = args.session_id
    if session_id is None:
        session_id = 0 if args.role in {"receiver", "server"} else secrets.randbits(63)
    run_id = args.run_id or new_run_id(args.mode, args.role)
    return RunConfig(
        mode=args.mode,
        role=args.role,
        run_id=run_id,
        output_dir=Path(args.output_dir),
        payload_size=args.payload_size,
        rate_hz=args.rate_hz,
        duration_s=args.duration,
        warmup_s=args.warmup,
        session_id=session_id,
        domain_id=args.domain_id,
        topic=args.topic,
        echo_topic=args.echo_topic,
        service=args.service,
        qos=qos_config_from_args(args),
        clock_sync=args.clock_sync,
        max_clock_offset_ms=args.max_clock_offset_ms,
        clock_offset_ms=args.clock_offset_ms,
        sample_system=args.sample_system,
        nic=args.nic,
        bag=args.bag,
        trace=args.trace,
        request_timeout_s=args.request_timeout,
        discovery_timeout_s=args.discovery_timeout,
    )


def one_way_latency_valid(config: RunConfig) -> tuple[bool, str]:
    if config.clock_sync == "ok":
        return True, "operator_marked_clock_sync_ok"
    if config.clock_sync == "offset":
        assert config.clock_offset_ms is not None
        if abs(config.clock_offset_ms) <= config.max_clock_offset_ms:
            return True, "clock_offset_within_threshold"
        return False, "clock_offset_exceeds_threshold"
    return False, "clock_sync_unknown"


def base_summary(config: RunConfig, started_wall: str, ended_wall: str) -> dict[str, Any]:
    return {
        "mode": config.mode,
        "role": config.role,
        "run_id": config.run_id,
        "session_id": config.session_id,
        "experiment_start_timestamp": started_wall,
        "experiment_end_timestamp": ended_wall,
        "payload_size": config.payload_size,
        "rate_hz": config.rate_hz,
        "duration_s": config.duration_s,
        "warmup_s": config.warmup_s,
        "qos": config.qos.as_dict(),
        "discovery_time_ms": None,
        "connection_ready_time_ms": None,
        "sender_cpu_percent": None,
        "receiver_cpu_percent": None,
        "sender_memory_mb": None,
        "receiver_memory_mb": None,
        "sender_nic_tx_bps": None,
        "receiver_nic_rx_bps": None,
        "sender_nic_rx_bps": None,
        "receiver_nic_tx_bps": None,
    }


def empty_latency_summary(valid: bool = False, reason: str = "unavailable") -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
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


def timer_period(rate_hz: float) -> float:
    return 1.0 / rate_hz


def packet_payload(size: int) -> bytes:
    return bytes(size)


def dataclass_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
