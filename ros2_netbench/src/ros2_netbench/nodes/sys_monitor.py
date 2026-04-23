"""Low-overhead Linux process and NIC sampler."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time

from ros2_netbench.utils.clocks import iso_utc_from_wall_ns, monotonic_ns
from ros2_netbench.utils.stats import summary_stats


CLK_TCK = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")


@dataclass(slots=True)
class SystemSample:
    timestamp: str
    monotonic_ns: int
    cpu_percent: float | None
    memory_mb: float | None
    nic_tx_bps: float | None
    nic_rx_bps: float | None

    def as_row(self) -> dict[str, float | int | str | None]:
        return {
            "timestamp": self.timestamp,
            "monotonic_ns": self.monotonic_ns,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "nic_tx_bps": self.nic_tx_bps,
            "nic_rx_bps": self.nic_rx_bps,
        }


class SystemMonitor:
    """Sample current process CPU/RSS and optionally one network interface."""

    def __init__(self, interface: str | None = None, pid: int | None = None) -> None:
        self.interface = interface
        self.pid = pid or os.getpid()
        self.samples: list[SystemSample] = []
        self._last_process_cpu_s: float | None = None
        self._last_wall_s: float | None = None
        self._last_nic: tuple[int, int] | None = None

    def sample(self) -> SystemSample:
        now_wall = time.monotonic()
        now_mono_ns = monotonic_ns()
        proc_cpu_s = self._read_process_cpu_seconds()
        memory_mb = self._read_process_memory_mb()

        cpu_percent = None
        if self._last_process_cpu_s is not None and self._last_wall_s is not None:
            elapsed = now_wall - self._last_wall_s
            if elapsed > 0:
                cpu_percent = ((proc_cpu_s - self._last_process_cpu_s) / elapsed) * 100.0
        self._last_process_cpu_s = proc_cpu_s
        self._last_wall_s = now_wall

        nic_tx_bps = None
        nic_rx_bps = None
        nic = self._read_nic_bytes()
        if nic is not None and self._last_nic is not None and len(self.samples) > 0:
            previous_rx, previous_tx = self._last_nic
            elapsed = (now_mono_ns - self.samples[-1].monotonic_ns) / 1_000_000_000
            if elapsed > 0:
                nic_rx_bps = ((nic[0] - previous_rx) * 8.0) / elapsed
                nic_tx_bps = ((nic[1] - previous_tx) * 8.0) / elapsed
        if nic is not None:
            self._last_nic = nic

        sample = SystemSample(
            timestamp=iso_utc_from_wall_ns(),
            monotonic_ns=now_mono_ns,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            nic_tx_bps=nic_tx_bps,
            nic_rx_bps=nic_rx_bps,
        )
        self.samples.append(sample)
        return sample

    def summary(self, prefix: str) -> dict[str, float | None]:
        cpu_values = [s.cpu_percent for s in self.samples if s.cpu_percent is not None]
        mem_values = [s.memory_mb for s in self.samples if s.memory_mb is not None]
        tx_values = [s.nic_tx_bps for s in self.samples if s.nic_tx_bps is not None]
        rx_values = [s.nic_rx_bps for s in self.samples if s.nic_rx_bps is not None]
        return {
            f"{prefix}_cpu_percent": summary_stats(cpu_values)["mean"],
            f"{prefix}_memory_mb": summary_stats(mem_values)["max"],
            f"{prefix}_nic_tx_bps": summary_stats(tx_values)["mean"],
            f"{prefix}_nic_rx_bps": summary_stats(rx_values)["mean"],
        }

    def rows(self) -> list[dict[str, float | int | str | None]]:
        return [sample.as_row() for sample in self.samples]

    def _read_process_cpu_seconds(self) -> float:
        stat = Path(f"/proc/{self.pid}/stat").read_text(encoding="utf-8")
        right = stat.rsplit(")", maxsplit=1)[1].split()
        utime = int(right[11])
        stime = int(right[12])
        return (utime + stime) / CLK_TCK

    def _read_process_memory_mb(self) -> float | None:
        try:
            statm = Path(f"/proc/{self.pid}/statm").read_text(encoding="utf-8").split()
        except FileNotFoundError:
            return None
        if len(statm) < 2:
            return None
        rss_pages = int(statm[1])
        return (rss_pages * PAGE_SIZE) / (1024.0 * 1024.0)

    def _read_nic_bytes(self) -> tuple[int, int] | None:
        if not self.interface:
            return None
        try:
            lines = Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return None
        prefix = f"{self.interface}:"
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith(prefix):
                continue
            parts = stripped.split(":", maxsplit=1)[1].split()
            if len(parts) < 16:
                return None
            rx_bytes = int(parts[0])
            tx_bytes = int(parts[8])
            return rx_bytes, tx_bytes
        return None
