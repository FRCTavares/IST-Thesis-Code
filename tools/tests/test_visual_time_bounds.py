"""Conservative offline bounds never certify physical-person attribution."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "bound_visual_mcap_time", ROOT / "tools/analysis/bound_visual_mcap_time.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_nonzero_first_pts_and_dropped_frames_remain_ordered_and_uncertain():
    start = module.parse_utc_ns("2026-09-22T16:26:07.733086669Z")
    pts = module.parse_pts_ns("1.000000\n1.040000\n1.240000\n1.280000\n")
    result = module.calculate_bounds(start, start + 700_000_000, pts)
    assert result["observed_min_positive_pts_tick_ns"] == 40_000_000
    assert result["max_pts_gap_s"] == pytest.approx(0.2)
    assert result["rows"][0][1] == 1_000_000_000
    assert result["rows"][2][2] >= result["rows"][0][2]
    assert result["source_capture_time_resolved"] is False
    assert result["physical_person_command_attribution"] == "unresolved"


def test_missing_or_corrupt_clock_and_pts_fail_closed():
    for value in ("", "2026-09-22T16:26:07", "not-a-date"):
        with pytest.raises(ValueError):
            module.parse_utc_ns(value)
    for value in ("NaN", "-0.1", "bad"):
        with pytest.raises(ValueError):
            module.parse_pts_ns(value)
    with pytest.raises(ValueError, match="nondecreasing"):
        module.calculate_bounds(100, 1_000_000_000, [20, 10])
    with pytest.raises(ValueError, match="conflict"):
        module.calculate_bounds(1_000_000_000, 1_100_000_000, [0, 40_000_000, 1_000_000_000])


def test_packet_bound_is_not_a_source_capture_or_safe_command_classification():
    start = module.parse_utc_ns("2026-09-22T16:26:07Z")
    bounds = module.calculate_bounds(
        start, start + 900_000_000, [0, 40_000_000, 200_000_000]
    )
    assert bounds["first_packet_window_s"] > 0
    assert bounds["source_capture_time_resolved"] is False
    assert bounds["physical_person_command_attribution"] == "unresolved"
    # Even a command in the receipt window must not be silently made safe.
    cmd_ns = start + 250_000_000
    assert bounds["rows"][0][2] <= cmd_ns <= bounds["rows"][0][3]


def test_inspection_rejects_corrupt_metadata_and_changed_mtime(tmp_path):
    bag = tmp_path / "bag"
    bag.mkdir()
    visual = bag / "visual_run1.mkv"
    visual.write_bytes(b"fake")
    (bag / "run_metadata.json").write_text("not json")
    (bag / "visual_evidence_status.json").write_text("{}")
    with pytest.raises(json.JSONDecodeError):
        module.inspect(bag, "run1")
    (bag / "run_metadata.json").write_text(json.dumps({
        "run_id": "run1",
        "visual": {"file": str(visual), "started_at_utc": "2026-09-22T16:26:07Z",
                   "timestamp_basis": "ffmpeg input wallclock"},
    }))
    (bag / "visual_evidence_status.json").write_text(json.dumps({
        "run_id": "run1", "passed": True,
        "file_mtime_ns": visual.stat().st_mtime_ns - 1,
        "timestamps": {"packet_count": 2},
    }))
    with pytest.raises(ValueError, match="mtime changed"):
        module.inspect(bag, "run1")



def test_inspection_accepts_matching_verified_file_but_not_other_timebase(tmp_path, monkeypatch):
    bag = tmp_path / "bag"
    bag.mkdir()
    visual = bag / "visual_run1.mkv"
    visual.write_bytes(b"fake")
    start_ns = visual.stat().st_mtime_ns - 1_000_000_000
    # The helper's UTC parser is exercised separately; use a whole-second
    # launch safely before the file's finalized mtime.
    from datetime import datetime, timezone
    start = datetime.fromtimestamp(start_ns // 1_000_000_000, timezone.utc)
    (bag / "run_metadata.json").write_text(json.dumps({
        "run_id": "run1",
        "visual": {"file": str(visual),
                   "started_at_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "timestamp_basis": "ffmpeg input wallclock"},
    }))
    (bag / "visual_evidence_status.json").write_text(json.dumps({
        "run_id": "run1", "passed": True,
        "file_mtime_ns": visual.stat().st_mtime_ns,
        "timestamps": {"packet_count": 3},
    }))
    def fake_probe(command, **kwargs):
        if "stream=r_frame_rate,time_base" in command:
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"streams": [{"r_frame_rate": "25/1"}]}), ""
            )
        return subprocess.CompletedProcess(command, 0, "0.100000\n0.140000\n0.340000\n", "")
    monkeypatch.setattr(module.subprocess, "run", fake_probe)
    result, rows = module.inspect(bag, "run1")
    assert result["source_capture_time_resolved"] is False
    assert result["physical_person_command_attribution"] == "unresolved"
    assert len(rows) == 3
    def wrong_timebase(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"streams": [{"r_frame_rate": "30/1"}]}), ""
        )
    monkeypatch.setattr(module.subprocess, "run", wrong_timebase)
    with pytest.raises(ValueError, match="unreviewed visual nominal timebase"):
        module.inspect(bag, "run1")
