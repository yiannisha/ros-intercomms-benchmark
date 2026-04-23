"""Print a compact summary for one or more result directories."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ros2_netbench.utils.csv_json import read_json


def summarize(path: Path) -> dict[str, Any]:
    summary = read_json(path / "summary.json")
    return {
        "run_dir": str(path),
        "mode": summary.get("mode"),
        "role": summary.get("role"),
        "sent": summary.get("sent_messages"),
        "received": summary.get("received_messages"),
        "loss_rate": summary.get("application_level_loss_rate"),
        "timeout_count": summary.get("timeout_count"),
        "rtt_p95_ms": (summary.get("RTT") or {}).get("p95"),
        "one_way_p95_ms": (summary.get("one_way_latency") or {}).get("p95"),
        "throughput_mps": summary.get("throughput_messages_per_sec"),
        "throughput_Bps": summary.get("throughput_bytes_per_sec"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+")
    args = parser.parse_args(argv)
    for run_dir in args.run_dirs:
        item = summarize(Path(run_dir))
        print(
            "{run_dir}: mode={mode} role={role} sent={sent} received={received} "
            "loss_rate={loss_rate} timeouts={timeout_count} rtt_p95_ms={rtt_p95_ms} "
            "one_way_p95_ms={one_way_p95_ms} throughput_mps={throughput_mps}".format(**item)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
