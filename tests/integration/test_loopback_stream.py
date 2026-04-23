from __future__ import annotations

import importlib.util
import importlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

import pytest


pytestmark = pytest.mark.integration


def _skip_without_ros() -> None:
    if importlib.util.find_spec("rclpy") is None:
        pytest.skip("rclpy is not available")
    if importlib.util.find_spec("ros2_netbench_interfaces") is None:
        pytest.skip("ros2_netbench_interfaces is not available")
    try:
        msg_module = importlib.import_module("ros2_netbench_interfaces.msg")
    except ImportError:
        pytest.skip("ros2_netbench_interfaces.msg is not importable")
    if not hasattr(msg_module, "BenchmarkPacket"):
        pytest.skip("generated BenchmarkPacket message is not available; build and source the workspace")


def test_loopback_stream_sender_receiver(tmp_path: Path):
    _skip_without_ros()
    domain_id = random.randint(100, 200)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "ros2_netbench" / "src") + os.pathsep + env.get(
        "PYTHONPATH",
        "",
    )

    receiver = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "ros2_netbench.nodes.stream_receiver",
            "--domain-id",
            str(domain_id),
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "receiver",
            "--duration",
            "1.0",
            "--warmup",
            "0.2",
            "--rate-hz",
            "20",
            "--payload-size",
            "128",
            "--discovery-timeout",
            "5",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.5)
    sender = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "ros2_netbench.nodes.stream_sender",
            "--domain-id",
            str(domain_id),
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "sender",
            "--duration",
            "1.0",
            "--warmup",
            "0.2",
            "--rate-hz",
            "20",
            "--payload-size",
            "128",
            "--discovery-timeout",
            "5",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        sender_out, sender_err = sender.communicate(timeout=15)
        receiver_out, receiver_err = receiver.communicate(timeout=15)
    finally:
        for proc in (sender, receiver):
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

    assert sender.returncode == 0, sender_out + sender_err
    assert receiver.returncode == 0, receiver_out + receiver_err
    summary = json.loads((tmp_path / "receiver" / "summary.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "stream"
    assert summary["role"] == "receiver"
    assert summary["received_messages"] > 0
    assert (tmp_path / "receiver" / "raw_samples.csv").exists()
