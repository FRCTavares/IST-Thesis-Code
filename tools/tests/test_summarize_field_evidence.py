from __future__ import annotations

import json
from pathlib import Path

from tools.live.summarize_field_evidence import summarize


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _package(tmp_path: Path, *, loss: int = 0) -> Path:
    bag = tmp_path / "bag"
    bag.mkdir()
    _write(bag / "bag_integrity.json", {
        "passed": True,
        "storage_identifier": "mcap",
        "duration_ns": 10_000_000_000,
        "total_bytes": 1234,
        "topic_message_counts": {"/detections": 300, "/tracks": 300},
    })
    _write(bag / "recorder_transport_status.json", {
        "quality_status": "observed_zero" if loss == 0 else "observed_nonzero",
        "recorders": {"main": {
            "reported_transport_loss_count": loss,
            "parse_ok": True,
        }},
    })
    _write(bag / "visual_evidence_status.json", {
        "passed": True,
        "recorder_alive_at_stop": True,
        "finalization": "graceful",
        "codec": "mjpeg",
        "width": 640,
        "height": 480,
        "measured_fps": 10.0,
        "decoded_frames": 100,
    })
    _write(bag / "evidence_package_status.json", {
        "runtime_status": "complete_runtime_evidence",
        "pending": ["pending_pixhawk_dataflash"],
        "problems": [],
    })
    return bag


def test_zero_loss_structured_visual_package_passes(tmp_path: Path) -> None:
    ok, lines = summarize(_package(tmp_path))
    assert ok is True
    assert "/detections: count=300 retained_hz=30.000" in lines
    assert lines[-1] == "runtime_evidence_acceptable: True"


def test_nonzero_transport_loss_fails(tmp_path: Path) -> None:
    ok, lines = summarize(_package(tmp_path, loss=1))
    assert ok is False
    assert lines[-1] == "runtime_evidence_acceptable: False"


def test_structured_image_topic_fails(tmp_path: Path) -> None:
    bag = _package(tmp_path)
    integrity_path = bag / "bag_integrity.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    integrity["topic_message_counts"]["/camera/dashboard"] = 100
    _write(integrity_path, integrity)

    ok, lines = summarize(bag)
    assert ok is False
    assert any("unexpected_structured_image_topics" in line for line in lines)
