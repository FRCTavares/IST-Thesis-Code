#!/usr/bin/env python3
"""Measure Issue #32 deterministic-replay algorithm compute cost.

This is the "replay_algorithmic_cost" measurement mode defined in
docs/data/runtime_characterization/p032_runtime_characterization_v1.yaml.
It orchestrates the already-validated, unmodified deterministic replay
runners (tools/experiments/run_deterministic_tracker_replay.py and
tools/experiments/run_deterministic_tim_replay.py) as subprocesses and
records their whole-process resource usage (wall time, user/system CPU,
peak RSS) via POSIX child rusage accounting.

Each invocation of this script measures exactly one stage
("tracker" or "tim") of exactly one architecture on exactly one sequence,
so resource.getrusage(RUSAGE_CHILDREN) starts at zero for the one child it
measures and its ru_maxrss is unambiguous.

This is deterministic, non-real-time, batch replay: there is no ROS
executor scheduling or playback pacing. It is valid for algorithm
CPU-service-time, peak memory, and fair architecture-to-architecture
comparison under identical detection input. It is NOT valid for real-time
latency, cadence, jitter, or backlog claims -- those come from the
"live_sustained" measurement mode instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA = "p032_replay_cost_v1"

TRACKER_REPLAY_SCRIPT = (
    REPO_ROOT / "tools" / "experiments" / "run_deterministic_tracker_replay.py"
)
TIM_REPLAY_SCRIPT = (
    REPO_ROOT / "tools" / "experiments" / "run_deterministic_tim_replay.py"
)
APPEARANCE_BUDGET_SCRIPT = (
    REPO_ROOT / "tools" / "analysis" / "analyse_p032_appearance_budget.py"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def find_by_id(entries: list[dict[str, Any]], entry_id: str, kind: str) -> dict[str, Any]:
    for entry in entries:
        if entry["id"] == entry_id:
            return entry
    raise SystemExit(f"ERROR: unknown {kind} id {entry_id!r} in manifest.")


def run_measured(command: list[str], *, cwd: Path, log_path: Path) -> dict[str, Any]:
    """Run one child process and return its wall time + rusage."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()

    with log_path.open("w", encoding="utf-8") as log_file:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    wall_s = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)

    if result.returncode != 0:
        raise SystemExit(
            f"ERROR: command failed (exit {result.returncode}): "
            f"{' '.join(command)}. See {log_path}."
        )

    return {
        "command": command,
        "wall_s": wall_s,
        "user_cpu_s": after.ru_utime - before.ru_utime,
        "sys_cpu_s": after.ru_stime - before.ru_stime,
        "peak_rss_kib": int(after.ru_maxrss),
        "log_path": str(log_path),
    }


def measure_tracker_stage(
    manifest: dict[str, Any],
    architecture: dict[str, Any],
    sequence: dict[str, Any],
    output_dir: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    source_bag_dir = REPO_ROOT / sequence["source_path"]
    source_bag_file = source_bag_dir / sequence["source_bag_file"]

    if not source_bag_dir.is_dir():
        raise SystemExit(f"ERROR: source bag directory missing: {source_bag_dir}")

    if not source_bag_file.is_file():
        raise SystemExit(f"ERROR: source bag file missing: {source_bag_file}")

    observed_source_sha256 = sha256_file(source_bag_file)
    expected_source_sha256 = sequence["source_sha256"]

    if observed_source_sha256 != expected_source_sha256:
        raise SystemExit(
            "ERROR: source bag hash mismatch. expected="
            f"{expected_source_sha256} observed={observed_source_sha256}. "
            "Refusing to measure against an unverified source bag."
        )

    tracker_config = REPO_ROOT / architecture["tracker_config"]
    observed_config_sha256 = sha256_file(tracker_config)
    expected_config_sha256 = architecture["tracker_config_sha256"]

    if observed_config_sha256 != expected_config_sha256:
        raise SystemExit(
            "ERROR: tracker config hash mismatch. expected="
            f"{expected_config_sha256} observed={observed_config_sha256}. "
            "Refusing to measure against a drifted config."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    tracks_bag = output_dir / "tracks.bag"

    if tracks_bag.exists() and overwrite:
        import shutil

        shutil.rmtree(tracks_bag)

    command = [
        sys.executable,
        str(TRACKER_REPLAY_SCRIPT),
        str(source_bag_dir),
        str(tracks_bag),
        "--config",
        str(tracker_config),
        "--selection-mode",
        "fixed_id",
        "--selected-track-id",
        str(sequence["selected_target_id"]),
    ]

    if architecture.get("requires_model"):
        mars_model = REPO_ROOT / manifest["frozen_boundary"]["mars_model_path"]
        command += ["--model", str(mars_model)]

    result = run_measured(
        command,
        cwd=REPO_ROOT,
        log_path=output_dir / "tracker_replay.log",
    )

    freeze_metadata_path = tracks_bag / "tracker_freeze_metadata.json"

    if not freeze_metadata_path.is_file():
        raise SystemExit(
            f"ERROR: expected provenance file missing: {freeze_metadata_path}"
        )

    freeze_metadata = json.loads(freeze_metadata_path.read_text(encoding="utf-8"))
    frame_count = int(freeze_metadata["counts"]["detection_messages_processed"])

    if frame_count <= 0:
        raise SystemExit("ERROR: replay processed zero detection frames.")

    total_cpu_s = result["user_cpu_s"] + result["sys_cpu_s"]

    record = {
        "schema": SCHEMA,
        "stage": "tracker",
        "measurement_mode": "replay_algorithmic_cost",
        "architecture_id": architecture["id"],
        "sequence_id": sequence["id"],
        "frame_count": frame_count,
        "wall_s": result["wall_s"],
        "user_cpu_s": result["user_cpu_s"],
        "sys_cpu_s": result["sys_cpu_s"],
        "total_cpu_s": total_cpu_s,
        "peak_rss_kib": result["peak_rss_kib"],
        "mean_cpu_ms_per_frame": (total_cpu_s * 1000.0) / frame_count,
        "command": result["command"],
        "provenance": {
            "git_commit": freeze_metadata["repository"]["commit"],
            "git_branch": freeze_metadata["repository"]["branch"],
            "git_status_short": freeze_metadata["repository"]["status_short"],
            "source_bag": str(source_bag_file),
            "source_sha256": observed_source_sha256,
            "tracker_config": str(tracker_config),
            "tracker_config_sha256": observed_config_sha256,
            "tracks_bag": str(tracks_bag),
        },
    }

    output_path = output_dir / "replay_cost_tracker.json"
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return record


def measure_tim_stage(
    manifest: dict[str, Any],
    architecture: dict[str, Any],
    sequence: dict[str, Any],
    output_dir: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    if not architecture.get("tim_enabled"):
        raise SystemExit(
            f"ERROR: architecture {architecture['id']!r} does not enable TIM; "
            "the tim stage does not apply."
        )

    tracks_bag = output_dir / "tracks.bag"

    if not tracks_bag.is_dir():
        raise SystemExit(
            f"ERROR: tracks bag missing; run the tracker stage first: {tracks_bag}"
        )

    tim_config = REPO_ROOT / manifest["frozen_boundary"]["canonical_tim_mars_config"]
    observed_tim_sha256 = sha256_file(tim_config)
    expected_tim_sha256 = manifest["frozen_boundary"]["canonical_tim_mars_config_sha256"]

    if observed_tim_sha256 != expected_tim_sha256:
        raise SystemExit(
            "ERROR: TIM-MARS config hash mismatch. expected="
            f"{expected_tim_sha256} observed={observed_tim_sha256}. "
            "Refusing to measure against a drifted config."
        )

    mars_model = REPO_ROOT / manifest["frozen_boundary"]["mars_model_path"]
    observed_model_sha256 = sha256_file(mars_model)
    expected_model_sha256 = manifest["frozen_boundary"]["mars_model_sha256"]

    if observed_model_sha256 != expected_model_sha256:
        raise SystemExit(
            "ERROR: MARS model hash mismatch. expected="
            f"{expected_model_sha256} observed={observed_model_sha256}. "
            "Refusing to measure against a drifted model."
        )

    tim_bag = output_dir / "tim.bag"

    if tim_bag.exists() and overwrite:
        import shutil

        shutil.rmtree(tim_bag)

    command = [
        sys.executable,
        str(TIM_REPLAY_SCRIPT),
        str(tracks_bag),
        str(tim_bag),
        "--config",
        str(tim_config),
        "--model",
        str(mars_model),
        "--selected-track-id",
        str(sequence["selected_target_id"]),
    ]

    result = run_measured(
        command,
        cwd=REPO_ROOT,
        log_path=output_dir / "tim_replay.log",
    )

    appearance_json = output_dir / "appearance_workload.json"
    appearance_markdown = output_dir / "appearance_workload.md"

    appearance_command = [
        sys.executable,
        str(APPEARANCE_BUDGET_SCRIPT),
        str(tim_bag),
        "--topic",
        "/target_memory_mars/status",
        "--run-name",
        f"{architecture['id']}_{sequence['id']}",
        "--git-commit",
        _git_commit(),
        "--json-out",
        str(appearance_json),
        "--markdown-out",
        str(appearance_markdown),
        "--measurement-mode",
        "replay_algorithmic_cost",
    ]

    subprocess.run(
        appearance_command,
        cwd=str(REPO_ROOT),
        check=True,
        stdout=(output_dir / "appearance_budget.log").open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    total_cpu_s = result["user_cpu_s"] + result["sys_cpu_s"]

    record = {
        "schema": SCHEMA,
        "stage": "tim",
        "measurement_mode": "replay_algorithmic_cost",
        "architecture_id": architecture["id"],
        "sequence_id": sequence["id"],
        "wall_s": result["wall_s"],
        "user_cpu_s": result["user_cpu_s"],
        "sys_cpu_s": result["sys_cpu_s"],
        "total_cpu_s": total_cpu_s,
        "peak_rss_kib": result["peak_rss_kib"],
        "command": result["command"],
        "appearance_budget_json": str(appearance_json),
        "appearance_budget_markdown": str(appearance_markdown),
        "provenance": {
            "git_commit": _git_commit(),
            "tim_config": str(tim_config),
            "tim_config_sha256": observed_tim_sha256,
            "mars_model": str(mars_model),
            "mars_model_sha256": observed_model_sha256,
            "tracks_bag": str(tracks_bag),
            "tim_bag": str(tim_bag),
        },
    }

    output_path = output_dir / "replay_cost_tim.json"
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return record


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--architecture-id", required=True)
    parser.add_argument("--sequence-id", required=True)
    parser.add_argument("--stage", required=True, choices=["tracker", "tim"])
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)

    architecture = find_by_id(
        manifest["architectures"], args.architecture_id, "architecture"
    )
    sequence = find_by_id(manifest["sequences"], args.sequence_id, "sequence")

    if args.stage == "tracker":
        measure_tracker_stage(
            manifest,
            architecture,
            sequence,
            args.output_dir,
            overwrite=args.overwrite,
        )
    else:
        measure_tim_stage(
            manifest,
            architecture,
            sequence,
            args.output_dir,
            overwrite=args.overwrite,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
