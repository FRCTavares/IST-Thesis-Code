"""Issue #50/#74: deterministic retained-bag integrity check (no ROS)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "tools/live/verify_retained_bag.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_retained_bag", MODULE)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


vrb = _load()


def _make_bag(tmp_path: Path, *, topics: dict[str, int], storage: str = "mcap",
              storage_files: list[str] | None = None, nonempty: bool = True,
              write_metadata: bool = True) -> Path:
    bag = tmp_path / "run__video"
    bag.mkdir()
    files = storage_files if storage_files is not None else ["run__video_0.mcap"]
    for name in files:
        (bag / name).write_bytes(b"x" * (4096 if nonempty else 0))
    if write_metadata:
        info = {
            "rosbag2_bagfile_information": {
                "version": 9,
                "storage_identifier": storage,
                "duration": {"nanoseconds": 12_000_000_000},
                "starting_time": {"nanoseconds_since_epoch": 1_700_000_000_000_000_000},
                "message_count": sum(topics.values()),
                "relative_file_paths": files,
                "topics_with_message_count": [
                    {
                        "topic_metadata": {
                            "name": name,
                            "type": "std_msgs/msg/String",
                            "serialization_format": "cdr",
                        },
                        "message_count": count,
                    }
                    for name, count in topics.items()
                ],
            }
        }
        import yaml

        (bag / "metadata.yaml").write_text(yaml.safe_dump(info), encoding="utf-8")
    return bag


CONTROL_TOPICS = {
    "/camera/dashboard": 900,
    "/detections": 900,
    "/tracks": 900,
    "/target_memory_mars": 850,
    "/target_memory_mars/status": 850,
    "/control_ref/cmd_vel": 600,
    "/control_ref/diagnostics": 600,
    "/mavros/state": 60,
    "/mavros/imu/data_raw": 3000,
    "/mavros/setpoint_raw/target_local": 0,
    "/mavros/statustext/recv": 0,
}


# E. pass
def test_pass_on_well_formed_control_bag(tmp_path):
    bag = _make_bag(tmp_path, topics=CONTROL_TOPICS)
    passed, report = vrb.verify_bag(
        bag_dir=bag,
        required_topics=["/control_ref/cmd_vel", "/control_ref/diagnostics",
                         "/mavros/state", "/mavros/setpoint_raw/target_local",
                         "/mavros/statustext/recv"],
        require_nonzero=["/control_ref/cmd_vel", "/control_ref/diagnostics",
                         "/mavros/state", "/mavros/imu/data_raw"],
        expected_storage="mcap",
        run_ros2_bag_info=False,
    )
    assert passed is True
    assert report["passed"] is True
    assert report["storage_identifier"] == "mcap"
    assert report["total_bytes"] > 0
    # setpoint_raw / statustext are present but empty -- that is allowed
    assert "/mavros/setpoint_raw/target_local" not in report["missing_topics"]
    assert report["failed_nonzero_topics"] == []


# F. missing metadata -> fail, nothing deleted
def test_missing_metadata_fails_without_touching_files(tmp_path):
    bag = _make_bag(tmp_path, topics=CONTROL_TOPICS, write_metadata=False)
    before = sorted(p.name for p in bag.iterdir())
    passed, report = vrb.verify_bag(
        bag_dir=bag, required_topics=[], require_nonzero=[],
        expected_storage="mcap", run_ros2_bag_info=False,
    )
    assert passed is False
    assert any("metadata.yaml" in e for e in report["errors"])
    assert sorted(p.name for p in bag.iterdir()) == before


# G. required topic missing -> explicit failure
def test_required_topic_missing_is_explicit(tmp_path):
    topics = dict(CONTROL_TOPICS)
    topics.pop("/control_ref/diagnostics")
    bag = _make_bag(tmp_path, topics=topics)
    passed, report = vrb.verify_bag(
        bag_dir=bag,
        required_topics=["/control_ref/diagnostics"],
        require_nonzero=[],
        expected_storage="mcap",
        run_ros2_bag_info=False,
    )
    assert passed is False
    assert report["missing_topics"] == ["/control_ref/diagnostics"]
    assert any("/control_ref/diagnostics" in e for e in report["errors"])


def test_required_nonzero_topic_empty_fails(tmp_path):
    topics = dict(CONTROL_TOPICS)
    topics["/control_ref/cmd_vel"] = 0
    bag = _make_bag(tmp_path, topics=topics)
    passed, report = vrb.verify_bag(
        bag_dir=bag, required_topics=["/control_ref/cmd_vel"],
        require_nonzero=["/control_ref/cmd_vel"],
        expected_storage="mcap", run_ros2_bag_info=False,
    )
    assert passed is False
    assert report["failed_nonzero_topics"] == ["/control_ref/cmd_vel"]


def test_empty_storage_file_fails(tmp_path):
    bag = _make_bag(tmp_path, topics=CONTROL_TOPICS, nonempty=False)
    passed, report = vrb.verify_bag(
        bag_dir=bag, required_topics=[], require_nonzero=[],
        expected_storage="mcap", run_ros2_bag_info=False,
    )
    assert passed is False
    assert any("non-empty storage" in e for e in report["errors"])


def test_wrong_storage_identifier_fails(tmp_path):
    bag = _make_bag(tmp_path, topics=CONTROL_TOPICS, storage="sqlite3",
                    storage_files=["run__video_0.db3"])
    passed, report = vrb.verify_bag(
        bag_dir=bag, required_topics=[], require_nonzero=[],
        expected_storage="mcap", run_ros2_bag_info=False,
    )
    assert passed is False
    assert any("storage identifier" in e for e in report["errors"])


# I. a non-control (dataset / perception-only) bag is not forced to have
# control or MAVROS topics
def test_perception_only_bag_not_forced_to_have_control_topics(tmp_path):
    bag = _make_bag(
        tmp_path,
        topics={"/camera/image_raw": 900, "/detections": 900, "/tracks": 900},
    )
    passed, report = vrb.verify_bag(
        bag_dir=bag,
        required_topics=["/camera/image_raw", "/detections", "/tracks"],
        require_nonzero=["/camera/image_raw"],
        expected_storage="mcap",
        run_ros2_bag_info=False,
    )
    assert passed is True


def test_cli_writes_report_and_returns_exit_code(tmp_path):
    import subprocess
    import sys

    bag = _make_bag(tmp_path, topics=CONTROL_TOPICS)
    out = tmp_path / "bag_integrity.json"
    result = subprocess.run(
        [sys.executable, str(MODULE), "--bag-dir", str(bag),
         "--require-topic", "/control_ref/diagnostics",
         "--require-nonzero", "/control_ref/cmd_vel",
         "--no-ros2-bag-info", "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    report = json.loads(out.read_text())
    assert report["passed"] is True
