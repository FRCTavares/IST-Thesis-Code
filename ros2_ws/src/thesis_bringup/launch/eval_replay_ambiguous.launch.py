#!/usr/bin/env python3
"""
eval_replay_ambiguous.launch.py

Replay a raw bag, inject synthetic ambiguity on /detections -> /detections_ambiguous,
run tracker + target selector, and record outputs into a new eval bag.

Usage:
  ros2 launch thesis_bringup eval_replay_ambiguous.launch.py \
    bag:=$THESIS_ROOT/artifacts/bags/raw/2026-02-28__slice__smoke2 \
    tracker:=ocsort window_start_s:=5.0 window_len_s:=10.0 swap_y:=false
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _today_str() -> str:
    return os.popen("date +%F").read().strip()


def _pick_eval_outdir(thesis_root: Path, raw_bag: str, tracker: str, tag: str) -> Path:
    base = Path(raw_bag).name
    stem = f"{_today_str()}__eval__{base}__{tracker}__{tag}"
    out = thesis_root / "bags" / "eval" / stem
    if not out.exists():
        return out
    n = 1
    while True:
        cand = thesis_root / "bags" / "eval" / f"{stem}__r{n}"
        if not cand.exists():
            return cand
        n += 1


def _make_tag(window_start_s: float, window_len_s: float, swap_y: bool) -> str:
    sy = "y1" if swap_y else "y0"
    return f"amb_cross_{window_start_s:g}_{window_len_s:g}_{sy}"


def _launch_setup(context, *args, **kwargs):
    thesis_root = Path(os.environ.get("THESIS_ROOT", str(Path.home() / "Desktop" / "Thesis-Code")))

    raw_bag = LaunchConfiguration("bag").perform(context)
    tracker = LaunchConfiguration("tracker").perform(context)

    window_start_s = float(LaunchConfiguration("window_start_s").perform(context))
    window_len_s = float(LaunchConfiguration("window_len_s").perform(context))
    swap_y = LaunchConfiguration("swap_y").perform(context).lower() in ("1", "true", "yes")

    record_duration_s = int(float(LaunchConfiguration("record_duration_s").perform(context)))

    tag = _make_tag(window_start_s, window_len_s, swap_y)
    outdir = _pick_eval_outdir(thesis_root, raw_bag, tracker, tag)
    outdir.parent.mkdir(parents=True, exist_ok=True)

    actions: List = []
    actions.append(LogInfo(msg=f"[eval_replay_ambiguous] THESIS_ROOT={thesis_root}"))
    actions.append(LogInfo(msg=f"[eval_replay_ambiguous] raw bag: {raw_bag}"))
    actions.append(LogInfo(msg=f"[eval_replay_ambiguous] tracker: {tracker}"))
    actions.append(LogInfo(msg=f"[eval_replay_ambiguous] window_start_s={window_start_s} window_len_s={window_len_s} swap_y={swap_y}"))
    actions.append(LogInfo(msg=f"[eval_replay_ambiguous] record_duration_s={record_duration_s}"))
    actions.append(LogInfo(msg=f"[eval_replay_ambiguous] recording to: {outdir}"))

    # Ambiguity node: /detections -> /detections_ambiguous
    actions.append(
        Node(
            package="thesis_bringup",
            executable="detections_ambiguity_node",
            name="detections_ambiguity_node",
            output="screen",
            parameters=[{
                "window_start_s": window_start_s,
                "window_len_s": window_len_s,
                "swap_y": swap_y,
                "debug": False,
            }],
        )
    )

    # Tracker node: consume ambiguous detections
    actions.append(
        Node(
            package="thesis_tracker",
            executable="tracker_node",
            name="tracker_node",
            output="screen",
            parameters=[{
                "tracker_type": tracker,
            }],
            remappings=[
                ("/detections", "/detections_ambiguous"),
            ],
        )
    )

    # Target publisher: user-selected focus from dashboard bridge API.
    # No target is selected by default in this replay flow.
    actions.append(
        Node(
            package="thesis_bringup",
            executable="dashboard_bridge_node",
            name="dashboard_bridge_node",
            output="screen",
            parameters=[{
                "ws_host": "127.0.0.1",
                "ws_port": 0,
                "api_host": "127.0.0.1",
                "api_port": 0,
                "publish_hz": 30.0,
            }],
        )
    )

    # Recorder
    actions.append(
        ExecuteProcess(
            cmd=[
                "ros2", "bag", "record",
                "--storage", "mcap",
                "-o", str(outdir),
                "--max-bag-duration", str(record_duration_s),
                "--topics",
                "/tracks", "/target", "/timing_tracker", "/timing_target",
            ],
            output="screen",
        )
    )

    # Player
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
            description="Path to raw bag directory",
        ),
        DeclareLaunchArgument(
            "tracker",
            default_value="ocsort",
            description="Tracker backend: sort | ocsort | bytetrack",
        ),
        DeclareLaunchArgument("window_start_s", default_value="5.0", description="Start of ambiguity window (s)"),
        DeclareLaunchArgument("window_len_s", default_value="10.0", description="Length of ambiguity window (s)"),
        DeclareLaunchArgument("swap_y", default_value="false", description="Also swap y centres during crossing"),
        DeclareLaunchArgument("record_duration_s", default_value="70", description="Recorder max duration (int seconds)"),
        OpaqueFunction(function=_launch_setup),
    ])
