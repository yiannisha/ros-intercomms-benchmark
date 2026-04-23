"""QoS parsing for ROS 2 benchmark nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rclpy.duration import Duration
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    LivelinessPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


@dataclass(slots=True)
class QosConfig:
    reliability: str = "reliable"
    history: str = "keep_last"
    depth: int = 10
    durability: str = "volatile"
    deadline_ms: float | None = None
    liveliness: str = "system_default"

    def as_dict(self) -> dict[str, Any]:
        return {
            "reliability": self.reliability,
            "history": self.history,
            "depth": self.depth,
            "durability": self.durability,
            "deadline_ms": self.deadline_ms,
            "liveliness": self.liveliness,
        }


def _choice(value: str, mapping: dict[str, Any], field: str) -> Any:
    normalized = value.lower()
    if normalized not in mapping:
        valid = ", ".join(sorted(mapping))
        raise ValueError(f"Invalid {field} '{value}'. Expected one of: {valid}")
    return mapping[normalized]


def qos_profile(config: QosConfig) -> QoSProfile:
    if config.depth < 1:
        raise ValueError("QoS depth must be >= 1")

    profile = QoSProfile(
        history=_choice(
            config.history,
            {"keep_last": HistoryPolicy.KEEP_LAST},
            "history",
        ),
        depth=config.depth,
        reliability=_choice(
            config.reliability,
            {
                "reliable": ReliabilityPolicy.RELIABLE,
                "best_effort": ReliabilityPolicy.BEST_EFFORT,
            },
            "reliability",
        ),
        durability=_choice(
            config.durability,
            {
                "volatile": DurabilityPolicy.VOLATILE,
                "transient_local": DurabilityPolicy.TRANSIENT_LOCAL,
            },
            "durability",
        ),
        liveliness=_choice(
            config.liveliness,
            {
                "system_default": LivelinessPolicy.SYSTEM_DEFAULT,
                "automatic": LivelinessPolicy.AUTOMATIC,
                "manual_by_topic": LivelinessPolicy.MANUAL_BY_TOPIC,
            },
            "liveliness",
        ),
    )
    if config.deadline_ms is not None:
        if config.deadline_ms < 0:
            raise ValueError("deadline_ms must be non-negative")
        profile.deadline = Duration(seconds=config.deadline_ms / 1000.0)
    return profile


def add_qos_arguments(parser: Any) -> None:
    parser.add_argument("--reliability", choices=["reliable", "best_effort"], default="reliable")
    parser.add_argument("--history", choices=["keep_last"], default="keep_last")
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--durability", choices=["volatile", "transient_local"], default="volatile")
    parser.add_argument("--deadline-ms", type=float, default=None)
    parser.add_argument(
        "--liveliness",
        choices=["system_default", "automatic", "manual_by_topic"],
        default="system_default",
    )


def qos_config_from_args(args: Any) -> QosConfig:
    return QosConfig(
        reliability=args.reliability,
        history=args.history,
        depth=args.depth,
        durability=args.durability,
        deadline_ms=args.deadline_ms,
        liveliness=args.liveliness,
    )
