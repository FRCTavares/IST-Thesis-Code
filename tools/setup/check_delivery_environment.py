#!/usr/bin/env python3
# Thesis-Code
# Purpose: Inspect delivery software profiles and retained model hashes without starting ROS or hardware.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by the MIT licence in LICENSE.

"""Inspect software prerequisites without starting runtime nodes or hardware."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = ('numpy', 'scipy', 'cv2', 'yaml', 'rclpy', 'rosbag2_py',
        'rosidl_runtime_py', 'ament_index_python.packages', 'thesis_msgs.msg',
        'thesis_tracker', 'thesis_bringup')
PROFILES = {
    'offline': CORE + ('matplotlib',),
    'live': CORE + ('websockets', 'tensorflow', 'hailo_platform', 'cv_bridge',
                    'vision_msgs.msg', 'geometry_msgs.msg'),
    'field': CORE + ('websockets', 'tensorflow', 'hailo_platform', 'cv_bridge',
                     'vision_msgs.msg', 'geometry_msgs.msg', 'mavros_msgs.srv'),
    'campaign': CORE + ('matplotlib', 'onnxruntime', 'ultralytics'),
}
MODELS = {
    'models/hef/yolov8s.hef':
        '69540ff855740371d229f4caca1ab908635a72fec55fdc1541e73f2fc17ec43b',
    'models/reid/mars-small128.pb':
        'e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1',
}


def inspect(profile: str) -> dict:
    """Return explicit availability failures for one chosen software profile."""
    checks = []
    for name in PROFILES[profile]:
        try:
            module = importlib.import_module(name)
            checks.append({'kind': 'module', 'name': name, 'ok': True,
                           'version': str(getattr(module, '__version__', 'unreported'))})
        except Exception as exc:
            checks.append({'kind': 'module', 'name': name, 'ok': False,
                           'reason': f'{type(exc).__name__}: {exc}'})
    entrypoints = {
        'thesis_tracker': ('tracker_node',),
        'thesis_bringup': ('camera_capture_node', 'perception_camera_node',
                           'perception_pipeline_node', 'video_file_publisher_node',
                           'dashboard_bridge_node', 'control_ref_node',
                           'mavros_imu_monitor_node', 'target_memory_mars_node'),
    }
    try:
        from ament_index_python.packages import get_package_prefix
        for package, names in entrypoints.items():
            prefix = Path(get_package_prefix(package))
            for name in names:
                checks.append({'kind': 'ROS entrypoint', 'name': name,
                               'ok': (prefix / 'lib' / package / name).is_file()})
    except Exception as exc:
        checks.append({'kind': 'ROS entrypoints', 'name': 'workspace installation',
                       'ok': False, 'reason': f'{type(exc).__name__}: {exc}'})
    commands = ['ros2', 'ffmpeg']
    if profile in {'offline', 'campaign'}:
        commands += ['zstd']
    if profile in {'live', 'field'}:
        commands += ['v4l2-ctl']
    for name in commands:
        checks.append({'kind': 'command', 'name': name, 'ok': bool(shutil.which(name))})
    if profile == 'field' and shutil.which('ros2'):
        result = subprocess.run(['ros2', 'pkg', 'prefix', 'mavros'],
                                capture_output=True, text=True, timeout=15, check=False)
        checks.append({'kind': 'ROS package', 'name': 'mavros',
                       'ok': result.returncode == 0, 'reason': result.stderr.strip()})
    if profile in {'live', 'field'}:
        for relative, expected in MODELS.items():
            path = ROOT / relative
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            checks.append({'kind': 'model', 'name': relative, 'ok': actual == expected,
                           'sha256': actual, 'expected_sha256': expected})
    return {
        'schema': 1, 'profile': profile, 'python': platform.python_version(),
        'executable': sys.executable, 'platform': platform.platform(),
        'scope': 'Software availability only; no hardware, flight, data or evidence acceptance.',
        'external_inputs': 'Bags/videos/annotations/caches, campaign-specific models and '
                           'pinned research checkouts must be provided from their run manifests.',
        'checks': checks, 'status': 'PASS' if all(c['ok'] for c in checks) else 'FAIL',
    }


def main() -> int:
    """Print the inspected profile and optionally save its structured record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    report = inspect(args.profile)
    rendered = json.dumps(report, indent=2) + '\n'
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered)
    print(rendered, end='')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
