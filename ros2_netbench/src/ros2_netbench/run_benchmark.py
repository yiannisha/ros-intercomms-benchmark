"""CLI entry point for the ROS 2 pub/sub stream benchmark."""

from __future__ import annotations

import argparse

import sys

from ros2_netbench.nodes.common import add_common_arguments, config_from_args, remove_ros_arguments
from ros2_netbench.nodes import stream_receiver, stream_sender


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a ROS 2 DDS pub/sub stream benchmark role and write result artifacts."
    )
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = remove_ros_arguments(list(sys.argv[1:] if argv is None else argv))
    config = config_from_args(build_parser().parse_args(args_list))
    if config.mode == "stream" and config.role == "sender":
        return stream_sender.run(config)
    if config.mode == "stream" and config.role == "receiver":
        return stream_receiver.run(config)
    raise ValueError(f"Unsupported mode/role combination: {config.mode}/{config.role}")


if __name__ == "__main__":
    raise SystemExit(main())
