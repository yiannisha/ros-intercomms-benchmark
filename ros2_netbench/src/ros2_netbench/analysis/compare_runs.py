"""Generate a simple markdown comparison table for benchmark runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from ros2_netbench.analysis.summarize_run import summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    rows = [summarize(Path(run_dir)) for run_dir in args.run_dirs]
    lines = [
        "| run | mode | role | sent | received | loss rate | timeouts | rtt p95 ms | one-way p95 ms | msg/s |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {run_dir} | {mode} | {role} | {sent} | {received} | {loss_rate} | "
            "{timeout_count} | {rtt_p95_ms} | {one_way_p95_ms} | {throughput_mps} |".format(
                **row
            )
        )
    output = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
