#!/usr/bin/env python3
"""Run and finalize one frozen, operator-controlled #64 runtime cell."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import urllib.request

from summarize_p064_matrix import CELLS, ROOT


def read_lines(process: subprocess.Popen[str], log: Path, lines: queue.Queue[str]) -> None:
    with log.open("w", encoding="utf-8") as stream:
        assert process.stdout is not None
        for line in process.stdout:
            stream.write(line)
            stream.flush()
            print(line, end="", flush=True)
            lines.put(line)


def start_stack(cell: int, run_id: str, tag: str, *, smoke: bool) -> tuple[subprocess.Popen[str], Path]:
    resolution, tracker, memory, _ = CELLS[cell]
    run_dir = ROOT / "ros2_ws/log/live_stack" / run_id
    bag = ROOT / "bags/live_camera" / f"{run_id}__video__{tag}"
    if run_dir.exists() or bag.exists():
        raise ValueError("run ID already has a log or evidence directory")
    run_dir.mkdir(parents=True)
    command = [str(ROOT / "tools/start_live_stack.sh"), "--res", resolution,
               "--tracker", tracker, "--mem", memory,
               "--record-structured-visual", "--no-control", "--tag", tag]
    env = dict(os.environ, RUN_ID=run_id)
    print(f"Cell {cell}: {resolution.upper()} | {tracker} | memory={memory} | control=off")
    print(f"RUN_ID={run_id} TAG={tag}")
    print("Command:", " ".join(command))
    if smoke:
        print("NON-SCIENTIFIC ENGINEERING SMOKE")
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    return process, run_dir


def wait_ready(process: subprocess.Popen[str], lines: queue.Queue[str], run_id: str) -> bool:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=.25)
            if f"[ok] run id: {run_id}" in line:
                return True
        except queue.Empty:
            if process.poll() is not None:
                return False
    return False


def choose_target() -> tuple[int, str]:
    while True:
        subprocess.run([sys.executable, str(ROOT / "tools/live/print_track_ids.py"),
                        "--timeout", "4.0"], check=False)
        choice = input("Select the physical person's track ID (Enter refreshes IDs): ").strip()
        if not choice:
            continue
        if not choice.isdecimal() or int(choice) <= 0:
            print("Enter a positive displayed track ID.")
            continue
        target_id = int(choice)
        payload = json.dumps({"target": target_id}).encode()
        request = urllib.request.Request("http://127.0.0.1:8090/api/target", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"target selection returned HTTP {response.status}")
        description = input("Brief physical description of the selected person: ").strip()
        if not description:
            raise ValueError("physical target description is required")
        print(f"Selected track ID {target_id}. Keep the physical person and motion comparable.")
        return target_id, description


def run_command(command: list[str], *, log: Path | None = None) -> int:
    print("[analysis]", " ".join(command), flush=True)
    if log is None:
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    with log.open("w", encoding="utf-8") as output:
        return subprocess.run(command, cwd=ROOT, stdout=output,
                              stderr=subprocess.STDOUT, check=False).returncode


def finalize(process: subprocess.Popen[str]) -> bool:
    if process.poll() is None and process.stdin is not None:
        try:
            process.stdin.write("stop\n")
            process.stdin.flush()
        except BrokenPipeError:
            pass
    try:
        return process.wait(timeout=90) == 0
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell", type=int, choices=CELLS)
    parser.add_argument("--engineering-smoke", type=int, metavar="SECONDS",
                        help="bounded tooling run; never formal evidence")
    args = parser.parse_args()
    cell = args.cell
    smoke = args.engineering_smoke is not None
    if smoke and not 10 <= args.engineering_smoke <= 60:
        parser.error("engineering smoke duration must be 10-60 seconds")
    if not smoke:
        dirty = subprocess.check_output(["git", "status", "--short", "--untracked-files=no"],
                                        cwd=ROOT, text=True).strip()
        if dirty:
            parser.error("tracked repository changes must be committed before a formal cell")
        for prior in range(1, cell):
            prior_tag = CELLS[prior][3]
            records = sorted((ROOT / "bags/live_camera").glob(f"*__video__{prior_tag}/p064_cell_result.json"))
            if not any((json.loads(path.read_text()).get("classification") in ("pass", "fail"))
                       for path in records):
                parser.error(f"formal Cell {prior} has no valid result; preserve order or repeat it")
    run_id = datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    tag = CELLS[cell][3] if not smoke else f"p064_runner_engineering_smoke_c{cell}"
    bag = ROOT / "bags/live_camera" / f"{run_id}__video__{tag}"
    process, run_dir = start_stack(cell, run_id, tag, smoke=smoke)
    lines: queue.Queue[str] = queue.Queue()
    thread = threading.Thread(target=read_lines, args=(process, run_dir / "p064_launcher.log", lines), daemon=True)
    thread.start()
    ready = wait_ready(process, lines, run_id)
    selected: int | None = None
    target_description: str | None = None
    sampler_rc: int | None = None
    if ready:
        try:
            if CELLS[cell][2] == "mars" and not smoke:
                selected, target_description = choose_target()
            groups = "detector,tracker,tim" if CELLS[cell][2] == "mars" else "detector,tracker"
            duration = 240 if not smoke else args.engineering_smoke
            warmup = 60 if not smoke else 0
            sampler = subprocess.Popen([sys.executable, str(ROOT / "tools/experiments/measure_p032_live_resources.py"),
                "--run-dir", str(run_dir), "--architecture-groups", groups,
                "--duration-s", str(duration), "--warm-up-s", str(warmup)], cwd=ROOT)
            while sampler.poll() is None:
                if process.poll() is not None:
                    sampler.terminate()
                    break
                time.sleep(.5)
            sampler_rc = sampler.wait()
        except (EOFError, KeyboardInterrupt, OSError, ValueError) as exc:
            print(f"[error] cell setup or measurement interrupted: {exc}", file=sys.stderr)
    else:
        print("[error] live stack did not reach ready state", file=sys.stderr)
    stopped = finalize(process)
    thread.join(timeout=5)
    if not stopped:
        print("[error] live stack did not finalize normally", file=sys.stderr)
    analysis_results: dict[str, int] = {}
    if bag.is_dir():
        required = ["/camera/fps", "/detections", "/tracks", "/target", "/timing", "/timing_tracker"]
        if CELLS[cell][2] == "mars":
            required += ["/target_memory_mars", "/target_memory_mars/status", "/timing_target"]
        command = [sys.executable, str(ROOT / "tools/live/assess_bag_topics.py"), str(bag),
                   "--out", str(bag / "per_topic_quality.json")]
        for topic in required:
            command += ["--require-topic", topic, "--require-nonzero", topic]
        analysis_results["per_topic"] = run_command(command, log=run_dir / "p064_topic_assessment.log")
        analysis_results["full_horizon_timing"] = run_command([sys.executable, str(ROOT / "tools/analysis/analyse_bag_timing.py"), str(bag),
                     "--out", str(bag / "timing_full_horizon.md"),
                     "--figdir", str(bag / "timing_figures"), "--gap-ms", "500"],
                    log=run_dir / "p064_timing_analysis.log")
        analysis_results["transport"] = run_command([sys.executable, str(ROOT / "tools/live/verify_recorder_transport.py"),
                     "--bag-dir", str(bag)])
        analysis_results["provenance"] = run_command([sys.executable, str(ROOT / "tools/live/validate_live_run_metadata.py"),
                     str(bag / "run_metadata.json"), "--strict-topic-inventory"])
        analysis_results["package"] = run_command([sys.executable, str(ROOT / "tools/live/verify_evidence_package.py"),
                     "--bag-dir", str(bag), "--run-id", run_id, "--expect-visual",
                     "--runtime-only"])
    collection = {"schema": "p064_collection_status_v1", "cell": cell,
                  "run_id": run_id, "tag": tag, "formal": not smoke,
                  "launcher_ready": ready, "sampler_returncode": sampler_rc,
                  "launcher_finalized": stopped, "analysis_returncodes": analysis_results,
                  "operator_target_id": selected,
                  "physical_target_description": target_description}
    collection_text = json.dumps(collection, indent=2, sort_keys=True) + "\n"
    (run_dir / "p064_collection_status.json").write_text(collection_text)
    if bag.is_dir():
        (bag / "p064_collection_status.json").write_text(collection_text)
    if smoke:
        result = {"run_id": run_id, "tag": tag, "classification": "non_scientific_smoke",
                  "launcher_ready": ready, "sampler_returncode": sampler_rc,
                  "launcher_finalized": stopped, "bag_dir": str(bag)}
        (run_dir / "p064_smoke_result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if ready and stopped and sampler_rc == 0 else 1
    command = [sys.executable, str(ROOT / "tools/experiments/summarize_p064_matrix.py"),
               "--cell", str(cell), "--run-id", run_id]
    if selected is not None:
        command += ["--operator-target-id", str(selected)]
    rc = run_command(command)
    run_command([sys.executable, str(ROOT / "tools/experiments/summarize_p064_matrix.py"), "--matrix"])
    return 0 if ready and stopped and sampler_rc == 0 and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
