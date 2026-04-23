"""Helpers for combining role-local result artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ros2_netbench.utils.csv_json import read_json, write_json


def merge_role_summaries(run_dirs: list[str | Path], output: str | Path) -> dict[str, Any]:
    """Merge multiple role summaries into one JSON document.

    This intentionally does not invent missing peer-side values. It keeps each
    role summary intact so later analysis can compare sender and receiver
    artifacts from machines with different clocks.
    """

    merged: dict[str, Any] = {"roles": []}
    for run_dir in run_dirs:
        path = Path(run_dir)
        summary_path = path / "summary.json"
        metadata_path = path / "run_metadata.json"
        merged["roles"].append(
            {
                "run_dir": str(path),
                "metadata": read_json(metadata_path) if metadata_path.exists() else None,
                "summary": read_json(summary_path) if summary_path.exists() else None,
            }
        )
    write_json(output, merged)
    return merged
