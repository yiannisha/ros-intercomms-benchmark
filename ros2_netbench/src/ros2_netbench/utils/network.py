"""Network and subprocess helpers."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Sequence


def apply_domain_id(domain_id: int | None) -> None:
    """Set ROS_DOMAIN_ID before rclpy initialization."""

    if domain_id is not None:
        if domain_id < 0 or domain_id > 232:
            raise ValueError("ROS domain id must be in the range 0..232")
        os.environ["ROS_DOMAIN_ID"] = str(domain_id)


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


class ManagedProcess:
    """A small wrapper for optional helper processes such as rosbag."""

    def __init__(self, argv: Sequence[str], cwd: Path | None = None) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            self.argv,
            cwd=str(self.cwd) if self.cwd else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def stop(self, timeout_s: float = 5.0) -> None:
        if self.process is None:
            return
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout_s)
