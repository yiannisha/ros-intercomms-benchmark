"""Single CLI entry point for all benchmark roles."""

from __future__ import annotations

import argparse

from ros2_netbench.nodes.common import add_common_arguments, config_from_args
from ros2_netbench.nodes import (
    ping_client,
    ping_server,
    service_client,
    service_server,
    stream_receiver,
    stream_sender,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a ROS 2 network benchmark role and write result artifacts."
    )
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    config = config_from_args(build_parser().parse_args(argv))
    if config.mode == "stream" and config.role == "sender":
        return stream_sender.run(config)
    if config.mode == "stream" and config.role == "receiver":
        return stream_receiver.run(config)
    if config.mode == "ping" and config.role == "client":
        return ping_client.run(config)
    if config.mode == "ping" and config.role == "server":
        return ping_server.run(config)
    if config.mode == "service" and config.role == "client":
        return service_client.run(config)
    if config.mode == "service" and config.role == "server":
        return service_server.run(config)
    raise ValueError(f"Unsupported mode/role combination: {config.mode}/{config.role}")


if __name__ == "__main__":
    raise SystemExit(main())
