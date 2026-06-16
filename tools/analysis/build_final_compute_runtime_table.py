#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


OUT = Path("reports/final_compute_runtime_2026-06-06")


@dataclass
class MethodSpec:
    method: str
    run_log: Path
    time_log: Path
    output_topic: str


METHODS = [
    MethodSpec(
        "Raw ByteTrack",
        OUT / "raw_bytetrack.run.log",
        OUT / "raw_bytetrack.time.txt",
        "/target",
    ),
    MethodSpec(
        "ByteTrack + TIM-MARS",
        OUT / "bytetrack_tim_mars.run.log",
        OUT / "bytetrack_tim_mars.time.txt",
        "/target_memory_mars",
    ),
    MethodSpec(
        "Raw DeepSORT-MARS",
        OUT / "raw_deepsort_mars.run.log",
        OUT / "raw_deepsort_mars.time.txt",
        "/target",
    ),
    MethodSpec(
        "Raw OCSORT",
        OUT / "raw_ocsort.run.log",
        OUT / "raw_ocsort.time.txt",
        "/target",
    ),
    MethodSpec(
        "OCSORT + TIM-MARS",
        OUT / "ocsort_tim_mars.run.log",
        OUT / "ocsort_tim_mars.time.txt",
        "/target_memory_mars",
    ),
]


def extract_eval_bag(run_log: Path) -> str:
    text = run_log.read_text()
    matches = re.findall(r"\[ok\] eval bag: (.+)", text)
    if not matches:
        raise RuntimeError(f"No eval bag found in {run_log}")
    return matches[-1].strip()


def parse_time_log(time_log: Path) -> dict[str, float | str]:
    text = time_log.read_text()

    def grab_float(pattern: str) -> float:
        m = re.search(pattern, text)
        if not m:
            raise RuntimeError(f"Missing pattern {pattern!r} in {time_log}")
        return float(m.group(1))

    def grab_str(pattern: str) -> str:
        m = re.search(pattern, text)
        if not m:
            raise RuntimeError(f"Missing pattern {pattern!r} in {time_log}")
        return m.group(1).strip()

    user_s = grab_float(r"User time \(seconds\):\s*([0-9.]+)")
    sys_s = grab_float(r"System time \(seconds\):\s*([0-9.]+)")
    cpu_percent = grab_float(r"Percent of CPU this job got:\s*([0-9.]+)%")
    wall = grab_str(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*(.+)")
    rss_kb = grab_float(r"Maximum resident set size \(kbytes\):\s*([0-9.]+)")

    return {
        "user_cpu_s": user_s,
        "system_cpu_s": sys_s,
        "cpu_percent": cpu_percent,
        "wall_time": wall,
        "peak_rss_mb": rss_kb / 1024.0,
    }


def parse_bag_info(bag: str) -> dict[str, int]:
    proc = subprocess.run(
        ["ros2", "bag", "info", bag],
        check=True,
        text=True,
        capture_output=True,
    )
    counts: dict[str, int] = {}

    for line in proc.stdout.splitlines():
        m = re.search(r"Topic:\s+(\S+)\s+\|.*?\|\s+Count:\s+(\d+)", line)
        if m:
            counts[m.group(1)] = int(m.group(2))

    return counts


def main() -> None:
    rows = []

    for spec in METHODS:
        bag = extract_eval_bag(spec.run_log)
        time_data = parse_time_log(spec.time_log)
        counts = parse_bag_info(bag)

        output_samples = counts.get(spec.output_topic, 0)
        track_samples = counts.get("/tracks", 0)
        det_samples = counts.get("/detections", 0)
        status_samples = counts.get("/target_memory_mars/status", 0)

        rows.append(
            {
                "method": spec.method,
                "bag": bag,
                "output_topic": spec.output_topic,
                "output_samples": output_samples,
                "track_samples": track_samples,
                "detection_samples": det_samples,
                "tim_status_samples": status_samples,
                **time_data,
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)

    csv_path = OUT / "final_compute_summary.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md_path = OUT / "final_compute_summary.md"
    with md_path.open("w") as f:
        f.write("# Final post-detection compute runtime summary\n\n")
        f.write("Scope: post-detection ROS replay. Hailo inference is excluded. The same source bag replays `/camera/image_raw` and `/detections` for each method.\n\n")
        f.write("| Method | Output topic | Output samples | Tracks | Detections | CPU % | User CPU (s) | System CPU (s) | Wall time | Peak RSS (MB) |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            f.write(
                f"| {r['method']} | `{r['output_topic']}` | {r['output_samples']} | "
                f"{r['track_samples']} | {r['detection_samples']} | "
                f"{r['cpu_percent']:.0f} | {r['user_cpu_s']:.2f} | "
                f"{r['system_cpu_s']:.2f} | {r['wall_time']} | "
                f"{r['peak_rss_mb']:.1f} |\n"
            )

    tex_path = Path("paper_tim_mars/tables/final_compute_runtime.tex")
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    with tex_path.open("w") as f:
        f.write(r"""\begin{table*}[t]
\centering
\caption{Post-detection replay runtime for the final methods. Hailo inference is excluded; the same recorded detections are replayed for each method.}
\label{tab:final_compute_runtime}
\begin{tabular}{lrrrrr}
\toprule
Method & Output samples & Tracks & CPU & User CPU & Peak RSS \\
 &  &  & (\%) & (s) & (MB) \\
\midrule
""")
        for r in rows:
            method = str(r["method"]).replace("+", "$+$")
            f.write(
                f"{method} & {r['output_samples']} & {r['track_samples']} & "
                f"{r['cpu_percent']:.0f} & {r['user_cpu_s']:.2f} & "
                f"{r['peak_rss_mb']:.1f} \\\\\n"
            )
        f.write(r"""\bottomrule
\end{tabular}
\end{table*}
""")

    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {tex_path}")


if __name__ == "__main__":
    main()
