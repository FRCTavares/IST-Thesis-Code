"""Host system metric readers for dashboard telemetry.

These helpers read Linux proc/sysfs values used by the dashboard bridge. They
are intentionally independent from ROS so they can be tested or reused without
starting a node.
"""

from __future__ import annotations


class SystemMetricsReader:
    """Read host CPU, memory, and temperature metrics for live dashboard status."""

    def __init__(self) -> None:
        self._last_cpu_total: int | None = None
        self._last_cpu_idle: int | None = None

    def read_cpu_percent(self) -> float | None:
        """Return CPU usage percent from /proc/stat, or None until two samples exist."""
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                line = f.readline().strip()
        except Exception:
            return None

        parts = line.split()
        if len(parts) < 5 or parts[0] != "cpu":
            return None

        try:
            values = [int(v) for v in parts[1:]]
        except Exception:
            return None

        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)

        if self._last_cpu_total is None or self._last_cpu_idle is None:
            self._last_cpu_total = total
            self._last_cpu_idle = idle
            return None

        delta_total = total - self._last_cpu_total
        delta_idle = idle - self._last_cpu_idle

        self._last_cpu_total = total
        self._last_cpu_idle = idle

        if delta_total <= 0:
            return None

        usage = 100.0 * (1.0 - (float(delta_idle) / float(delta_total)))
        return max(0.0, min(100.0, usage))

    def read_memory_metrics(self) -> tuple[float | None, float | None]:
        """Return memory usage percent and used MiB from /proc/meminfo."""
        mem_total_kb = None
        mem_available_kb = None
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_available_kb = int(line.split()[1])
                    if mem_total_kb is not None and mem_available_kb is not None:
                        break
        except Exception:
            return None, None

        if mem_total_kb is None or mem_available_kb is None or mem_total_kb <= 0:
            return None, None

        mem_used_kb = max(0, mem_total_kb - mem_available_kb)
        mem_percent = 100.0 * float(mem_used_kb) / float(mem_total_kb)
        mem_used_mb = float(mem_used_kb) / 1024.0
        return mem_percent, mem_used_mb

    def read_cpu_temp_c(self) -> float | None:
        """Return CPU temperature in Celsius from common Linux thermal paths."""
        candidates = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
        ]

        for path in candidates:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                value = float(raw)
                if value > 1000.0:
                    value = value / 1000.0
                if value > 0.0:
                    return value
            except Exception:
                continue

        return None
