#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

import rclpy
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import rosbag2_py

from thesis_bringup.target_memory import (
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
)


def read_tracks(bag_path: Path):
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id=""),
        rosbag2_py.ConverterOptions("", ""),
    )

    topic_types = {
        t.name: t.type
        for t in reader.get_all_topics_and_types()
    }
    msg_type = get_message(topic_types["/tracks"])

    rows = []
    first_t = None

    while reader.has_next():
        topic, raw, t_ns = reader.read_next()
        if topic != "/tracks":
            continue

        if first_t is None:
            first_t = int(t_ns)

        msg = deserialize_message(raw, msg_type)
        t = (int(t_ns) - first_t) / 1e9

        tracks = []
        for tr in msg.tracks:
            cx = float(tr.cx)
            cy = float(tr.cy)
            w = float(tr.w)
            h = float(tr.h)
            tracks.append({
                "id": int(tr.id),
                "cx": cx,
                "cy": cy,
                "w": w,
                "h": h,
                "score": float(tr.score),
            })

        rows.append({
            "t": t,
            "frame_id": int(msg.frame_id),
            "tracks": tracks,
        })

    return rows


def to_candidate(track: dict[str, Any]) -> CandidateTrack:
    cx = track["cx"]
    cy = track["cy"]
    w = track["w"]
    h = track["h"]
    bbox = (
        cx - 0.5 * w,
        cy - 0.5 * h,
        cx + 0.5 * w,
        cy + 0.5 * h,
    )
    return CandidateTrack(
        track_id=int(track["id"]),
        bbox=bbox,
        score=float(track["score"]),
    )


def inject_fault(
    rows,
    selected_id: int,
    new_id: int,
    gap_start_s: float,
    gap_duration_s: float,
):
    gap_end_s = gap_start_s + gap_duration_s
    injected = []

    for row in rows:
        t = row["t"]
        out_tracks = []

        for tr in row["tracks"]:
            tr = dict(tr)

            if tr["id"] == selected_id:
                if gap_start_s <= t < gap_end_s:
                    continue

                if t >= gap_end_s:
                    tr["id"] = new_id

            out_tracks.append(tr)

        injected.append({
            "t": t,
            "frame_id": row["frame_id"],
            "tracks": out_tracks,
        })

    return injected


def run_raw_selector(rows, selected_id: int):
    out = []
    for row in rows:
        found = None
        for tr in row["tracks"]:
            if tr["id"] == selected_id:
                found = tr
                break

        out.append({
            "t": row["t"],
            "valid": found is not None,
            "id": selected_id if found is not None else 0,
        })
    return out


def run_tim(rows, selected_id: int):
    cfg = TargetMemoryConfig(
        image_width=640.0,
        image_height=640.0,
        accept_score_locked=0.52,
        accept_score_lost=0.60,
        ambiguity_margin=0.07,
        max_uncertain_frames=6,
        max_lost_frames=30,
        min_candidate_score=0.10,
    )
    tim = TargetIdentityMemory(cfg)

    out = []
    selected = False

    for row in rows:
        candidates = [to_candidate(tr) for tr in row["tracks"]]

        if not selected:
            first = next((c for c in candidates if c.track_id == selected_id), None)
            if first is not None:
                result = tim.select(first)
                selected = True
            else:
                result = tim.update([])
        else:
            result = tim.update(candidates)

        best = result.best_score

        out.append({
            "t": row["t"],
            "frame_id": row["frame_id"],
            "state": result.state.value,
            "mode": result.control_mode.value,
            "valid": result.visible and result.target_track_id is not None,
            "id": int(result.target_track_id) if result.visible and result.target_track_id is not None else 0,
            "target_track_id": int(result.target_track_id) if result.target_track_id is not None else 0,
            "quality": float(result.quality),
            "reacquired": bool(result.reacquired),
            "reason": result.reason,
            "frames_since_seen": int(result.frames_since_seen),
            "num_candidates": len(candidates),
            "best_track_id": int(best.track_id) if best is not None else 0,
            "best_total": float(best.total) if best is not None else float("nan"),
            "best_iou": float(best.iou) if best is not None else float("nan"),
            "best_distance": float(best.distance) if best is not None else float("nan"),
            "best_scale": float(best.scale) if best is not None else float("nan"),
            "best_confidence": float(best.confidence) if best is not None else float("nan"),
            "best_id_bonus": float(best.id_bonus) if best is not None else float("nan"),
            "best_ambiguous": bool(best.ambiguous) if best is not None else False,
        })

    return out


def first_reacq_after(tim_rows, t0: float):
    for r in tim_rows:
        if r["t"] >= t0 and r["state"] == "REACQUIRED":
            return r
    return None


def write_summary(path: Path, bag: Path, raw, tim, selected_id, new_id, gap_start, gap_duration):
    post = [r for r in tim if r["t"] >= gap_start]
    raw_post = [r for r in raw if r["t"] >= gap_start]

    raw_valid = sum(1 for r in raw_post if r["valid"])
    tim_valid = sum(1 for r in post if r["valid"])

    reacq = first_reacq_after(tim, gap_start + gap_duration)

    lines = []
    lines.append("# TIM-V0 Deterministic Fault-Injection Evaluation")
    lines.append("")
    lines.append(f"- Bag: `{bag}`")
    lines.append(f"- Selected ID before fault: {selected_id}")
    lines.append(f"- Injected replacement ID after fault: {new_id}")
    lines.append(f"- Gap start: {gap_start:.2f} s")
    lines.append(f"- Gap duration: {gap_duration:.2f} s")
    lines.append("")
    lines.append("## Post-fault validity")
    lines.append("")
    lines.append(f"- Raw ID selector valid samples after fault start: {raw_valid}/{len(raw_post)}")
    lines.append(f"- TIM-V0 valid samples after fault start: {tim_valid}/{len(post)}")
    lines.append("")
    lines.append("## Reacquisition")
    lines.append("")
    if reacq is None:
        lines.append("- TIM did not emit REACQUIRED after the injected ID switch.")
    else:
        dt = reacq["t"] - (gap_start + gap_duration)
        lines.append(f"- TIM reacquired at t={reacq['t']:.2f} s")
        lines.append(f"- Time after reappearance: {dt:.2f} s")
        lines.append(f"- Reacquired ID: {reacq['id']}")
        lines.append(f"- Quality: {reacq['quality']:.3f}")
        lines.append(f"- Reason: {reacq['reason']}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "The raw selector follows only the original selected track ID. "
        "After the injected ID switch, it cannot recover because the selected ID no longer exists. "
        "TIM-V0 uses target memory and geometric consistency, so it can reacquire the same physical target under the new tracker ID."
    )

    path.write_text("\n".join(lines))


def plot(raw, tim, out_path: Path):
    plt.figure(figsize=(12, 4))
    plt.step([r["t"] for r in raw], [1 if r["valid"] else 0 for r in raw], where="post", label="raw selected ID")
    plt.step([r["t"] for r in tim], [1 if r["valid"] else 0 for r in tim], where="post", label="TIM-V0")
    plt.yticks([0, 1], ["invalid", "valid"])
    plt.xlabel("time [s]")
    plt.ylabel("validity")
    plt.title("Raw ID selector vs TIM-V0 under injected ID switch")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_state(tim, out_path: Path):
    order = {
        "NO_TARGET": 0,
        "LOCKED": 1,
        "UNCERTAIN": 2,
        "LOST": 3,
        "REACQUIRED": 4,
    }
    plt.figure(figsize=(12, 4))
    plt.step([r["t"] for r in tim], [order.get(r["state"], -1) for r in tim], where="post")
    plt.yticks(list(order.values()), list(order.keys()))
    plt.xlabel("time [s]")
    plt.ylabel("TIM state")
    plt.title("TIM-V0 state under injected ID switch")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--selected-id", type=int, default=1)
    parser.add_argument("--new-id", type=int, default=3)
    parser.add_argument("--gap-start-s", type=float, default=15.0)
    parser.add_argument("--gap-duration-s", type=float, default=2.0)
    parser.add_argument("--out-root", type=Path, default=Path("reports/tim_v0_fault_injection"))
    args = parser.parse_args()

    bag = args.bag.resolve()
    out_dir = args.out_root / bag.name
    out_dir.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    try:
        rows = read_tracks(bag)
    finally:
        if rclpy.ok():
            rclpy.shutdown()

    injected = inject_fault(
        rows,
        selected_id=args.selected_id,
        new_id=args.new_id,
        gap_start_s=args.gap_start_s,
        gap_duration_s=args.gap_duration_s,
    )

    raw = run_raw_selector(injected, selected_id=args.selected_id)
    tim = run_tim(injected, selected_id=args.selected_id)

    write_summary(
        out_dir / "summary.md",
        bag,
        raw,
        tim,
        args.selected_id,
        args.new_id,
        args.gap_start_s,
        args.gap_duration_s,
    )
    plot(raw, tim, out_dir / "raw_vs_tim_fault_validity.png")
    plot_state(tim, out_dir / "tim_fault_state_timeline.png")

    print(f"[ok] wrote {out_dir}")
    print(f"[ok] summary: {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
