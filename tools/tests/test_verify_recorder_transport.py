"""Recorder transport loss is retained separately from MCAP integrity."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "tools/live/verify_recorder_transport.py"
spec = importlib.util.spec_from_file_location("verify_recorder_transport", MODULE)
vrt = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(vrt)


def _log(path: Path, count: int | None, *, stopped: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "[INFO] [1.0] [rosbag2_recorder]: Recording stopped\n" if stopped else ""
    if count is not None:
        text += (
            "[WARN] [1.1] [rosbag2_recorder]: "
            f"Number of messages lost on the transport layer: {count}\n"
        )
    path.write_text(text, encoding="utf-8")


def test_explicit_zero_is_observed_zero(tmp_path):
    bag = tmp_path / "video"
    _log(bag / "run_logs/rosbag.log", 0)
    report = vrt.verify_transport(bag)
    assert report["quality_status"] == "observed_zero"
    assert report["runtime_evidence_acceptable"] is True
    assert report["recorders"]["main"]["reported_transport_loss_count"] == 0


def test_nonzero_counts_preserve_recorder_identity_and_scope(tmp_path):
    bag = tmp_path / "video"
    raw = tmp_path / "video__image_raw"
    _log(bag / "run_logs/rosbag.log", 2186)
    _log(raw / "run_logs/raw_image_bag.log", 3073)
    report = vrt.verify_transport(bag, raw)
    assert report["quality_status"] == "observed_nonzero"
    assert report["runtime_evidence_acceptable"] is False
    assert report["recorders"]["main"]["scope"] == "multi_topic_aggregate"
    assert report["recorders"]["main"]["reported_transport_loss_count"] == 2186
    assert report["recorders"]["raw_image"]["scope"] == "single_topic_camera_image_raw"
    assert report["recorders"]["raw_image"]["reported_transport_loss_count"] == 3073
    assert "loss_fraction" not in json.dumps(report)
    assert "/camera/dashboard" not in json.dumps(report)


def test_missing_log_is_unavailable_not_zero(tmp_path):
    report = vrt.verify_transport(tmp_path / "video")
    item = report["recorders"]["main"]
    assert item["status"] == "unavailable"
    assert item["log_present"] is False
    assert item["reported_transport_loss_count"] is None


def test_missing_diagnostic_and_partial_log_are_unavailable(tmp_path):
    bag = tmp_path / "video"
    path = bag / "run_logs/rosbag.log"
    _log(path, None)
    assert vrt.verify_transport(bag)["recorders"]["main"]["status"] == "unavailable"
    _log(path, 7, stopped=False)
    assert vrt.verify_transport(bag)["recorders"]["main"]["status"] == "unavailable"


def test_malformed_or_duplicate_diagnostic_is_unavailable(tmp_path):
    bag = tmp_path / "video"
    path = bag / "run_logs/rosbag.log"
    _log(path, 7)
    path.write_text(path.read_text().replace(": 7", ": unknown"))
    assert vrt.verify_transport(bag)["recorders"]["main"]["parse_ok"] is False
    _log(path, 7)
    path.write_text(path.read_text() + path.read_text().splitlines()[-1] + "\n")
    assert vrt.verify_transport(bag)["recorders"]["main"]["status"] == "unavailable"
