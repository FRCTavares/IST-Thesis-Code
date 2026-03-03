#!/usr/bin/env python3
"""
eval_replay_occluded.launch.py

Replay a raw bag, inject synthetic occlusion on /detections -> /detections_occluded,
run tracker + target selector, and record outputs into a new eval bag.

Usage example:
  ros2 launch thesis_bringup eval_replay_occluded.launch.py \
    bag:=/home/francisco/Desktop/Thesis-Code/bags/raw/2026-02-28__slice__smoke2 \
    tracker:=ocsort \
    occl_mode:=periodic_blackout period_s:=3.0 drop_s:=0.5

Notes:
- This launch creates a unique output directory under $THESIS_ROOT/bags/eval/
  using a collision suffix __rN if needed.
- Recorder auto-stops using --max-bag-duration (record_duration_s). Keep using
  `timeout -s SIGINT ...` outside if you prefer your proven recipe.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _pick_eval_outdir(thesis_root: Path, raw_bag: str, tracker: str, tag: str) -> Path:
    base = f"{Path(raw_bag).name}"
    stem = f"{Path(os.popen('date +%F').read().strip())}__eval__{base}__{tracker}__{tag}"
    out = thesis_root / "bags" / "eval" / stem
    if not out.exists():
        return out
    # collision suffix
    n = 1
    while True:
        cand = thesis_root / "bags" / "eval" / f"{stem}__r{n}"
        if not cand.exists():
            return cand
        n += 1


def _make_tag(occl_mode: str, period_s: float, drop_s: float, gate_px: float) -> str:
    # Keep names short but descriptive
    if occl_mode == "periodic_blackout":
        return f"occl_pb_{period_s:g}_{drop_s:g}"
    if occl_mode == "target_centric":
        return f"occl_tc_{period_s:g}_{drop_s:g}_g{gate_px:g}"
    if occl_mode == "fixed_roi":
        return f"occl_roi_{period_s:g}_{drop_s:g}"
    return f"occl_{occl_mode}"


def _launch_setup(context, *args, **kwargs):
    thesis_root = Path(os.environ.get("THESIS_ROOT", str(Path.home() / "Desktop" / "Thesis-Code")))
    raw_bag = LaunchConfiguration("bag").perform(context)
    tracker = LaunchConfiguration("tracker").perform(context)

    occl_mode = LaunchConfiguration("occl_mode").perform(context)
    period_s = float(LaunchConfiguration("period_s").perform(context))
    drop_s = float(LaunchConfiguration("drop_s").perform(context))
    gate_px = float(LaunchConfiguration("gate_px").perform(context))
    target_is_normalised = LaunchConfiguration("target_is_normalised").perform(context).lower() in ("1", "true", "yes")
    img_w = int(LaunchConfiguration("img_w").perform(context))
    img_h = int(LaunchConfiguration("img_h").perform(context))

    roi_str = LaunchConfiguration("roi_xyxy").perform(context)
    roi_str = roi_str.strip().replace("[", "").replace("]", "")
    parts = [p.strip() for p in roi_str.split(",") if p.strip() != ""]
    if len(parts) != 4:
        roi_xyxy = [0.0, 0.0, 0.0, 0.0]
    else:
        roi_xyxy = [float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])]

    record_duration_s = int(float(LaunchConfiguration("record_duration_s").perform(context)))

    tag = _make_tag(occl_mode, period_s, drop_s, gate_px)
    outdir = _pick_eval_outdir(thesis_root, raw_bag, tracker, tag)
    outdir.parent.mkdir(parents=True, exist_ok=True)

    actions: List = []

    actions.append(LogInfo(msg=f"[eval_replay_occluded] THESIS_ROOT={thesis_root}"))
    actions.append(LogInfo(msg=f"[eval_replay_occluded] raw bag: {raw_bag}"))
    actions.append(LogInfo(msg=f"[eval_replay_occluded] tracker: {tracker}"))
    actions.append(LogInfo(msg=f"[eval_replay_occluded] occl_mode={occl_mode} period_s={period_s} drop_s={drop_s} gate_px={gate_px}"))
    actions.append(LogInfo(msg=f"[eval_replay_occluded] recording to: {outdir}"))

    # Occluder node: /detections -> /detections_occluded
    actions.append(
        Node(
            package="thesis_bringup",
            executable="detections_occluder_node",
            name="detections_occluder_node",
            output="screen",
            parameters=[{
                "mode": occl_mode,
                "period_s": period_s,
                "drop_s": drop_s,
                "gate_px": gate_px,
                "target_is_normalised": target_is_normalised,
                "img_w": img_w,
                "img_h": img_h,
                "roi_xyxy": roi_xyxy,
                "debug": False,
            }],
        )
    )

    # Tracker node: remap /detections -> /detections_occluded
    actions.append(
        Node(
            package="thesis_tracker",
            executable="tracker_node",
            name="tracker_node",
            output="screen",
            parameters=[{
                "tracker_type": tracker,
                # Keep min_score consistent via your YAML in thesis_bringup/config, or add here if you want.
            }],
            remappings=[
                ("/detections", "/detections_occluded"),
            ],
        )
    )

    # Target selector (unchanged)
    actions.append(
        Node(
            package="thesis_target_selector",
            executable="target_selector_node",
            name="target_selector_node",
            output="screen",
        )
    )

    # Recorder (eval outputs)
    # Auto-stop after record_duration_s to avoid hanging forever.
    actions.append(
        ExecuteProcess(
            cmd=[
                "ros2", "bag", "record",
                "--storage", "mcap",
                "-o", str(outdir),
                "--max-bag-duration", str(record_duration_s),
                "--topics",
                "/tracks", "/target", "/timing_tracker",
            ],
            output="screen",
        )
    )

    # Player (raw inputs)
    actions.append(
        ExecuteProcess(
            cmd=[
                "ros2", "bag", "play",
                "--rate", "1.0",
                raw_bag,
            ],
            output="screen",
        )
    )

    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            "bag",
            description="Path to raw bag directory (e.g., $THESIS_ROOT/bags/raw/2026-02-28__slice__smoke2)",
        ),
        DeclareLaunchArgument(
            "tracker",
            default_value="ocsort",
            description="Tracker backend: sort | ocsort | bytetrack",
        ),
        DeclareLaunchArgument(
            "occl_mode",
            default_value="periodic_blackout",
            description="Occlusion mode: periodic_blackout | target_centric | fixed_roi",
        ),
        DeclareLaunchArgument("period_s", default_value="3.0", description="Blackout period (s)"),
        DeclareLaunchArgument("drop_s", default_value="0.5", description="Blackout duration inside each period (s)"),
        DeclareLaunchArgument("gate_px", default_value="60.0", description="Target-centric gate radius in pixels"),
        DeclareLaunchArgument("target_is_normalised", default_value="true", description="Whether /target cx,cy are normalised"),
        DeclareLaunchArgument("img_w", default_value="640", description="Image width for normalised -> pixels"),
        DeclareLaunchArgument("img_h", default_value="640", description="Image height for normalised -> pixels"),
        DeclareLaunchArgument(
            "roi_xyxy",
            default_value="0,0,0,0",
            description="ROI for fixed_roi mode: 'x1,y1,x2,y2' (pixels)",
        ),
        DeclareLaunchArgument(
            "record_duration_s",
            default_value="70",
            description="Recorder max duration (s). Keeps runs comparable and prevents hanging.",
        ),
        OpaqueFunction(function=_launch_setup),
    ])