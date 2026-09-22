"""Contracts for frozen #64 runtime collection and fail-closed summaries."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "tools/start_live_stack.sh").read_text()
RUNNER = (ROOT / "tools/experiments/run_p064_cell.py").read_text()
SHELL = (ROOT / "tools/experiments/run_p064_cell.sh").read_text()


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load(ROOT / "tools/live/validate_live_run_metadata.py", "p064_validator")
summary = load(ROOT / "tools/experiments/summarize_p064_matrix.py", "p064_summary")


def provenance(topic: dict) -> dict:
    return {
        "schema_version": 1, "run_id": "run1", "recorded_at_utc": "2026-09-22T12:00:00Z",
        "bag": {"recorded_topics": ["/detections"]},
        "invocation": {"command": "start_live_stack.sh --no-control"},
        "git": {"commit": "0" * 40, "dirty": False}, "hardware_software": {},
        "hashes": {}, "resolved_parameters": {"tracker_node": {"tracker_type": "bytetrack"}},
        "topic_qos_inventory": {"/detections": topic}, "target": {}, "runtime_switch_history": [],
    }


def test_positive_publisher_required_for_strict_visual_provenance():
    for entry in ({"publisher_count": 0}, {"error": "Unknown topic"},
                  {"publisher_count": None}):
        errors, _ = validator.validate(provenance(entry), strict_topic_inventory=True)
        assert errors
    errors, _ = validator.validate(provenance({"publisher_count": 1}),
                                   strict_topic_inventory=True)
    assert not errors


def test_raw_topics_exclude_tim_only_streams():
    block = LAUNCHER.split("VIDEO_BAG_TOPICS=(", 1)[1].split("# Controller outputs", 1)[0]
    mars = block.split('if [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then', 1)[1].split("fi", 1)[0]
    assert "/timing_target" in mars
    assert "/target_memory_mars/status" in mars
    assert block.count("/timing_target") == 1
    assert 'tracker_reid_model=$REID_MODEL_PATH' in LAUNCHER


def test_runner_freezes_matrix_and_no_control():
    assert len(summary.CELLS) == 8
    assert [summary.CELLS[i][:3] for i in range(1, 9)] == [
        ("vga", "bytetrack", "mars"), ("vga", "bytetrack", "off"),
        ("vga", "deepsort", "off"), ("vga", "bytetrack", "mars"),
        ("hd", "bytetrack", "mars"), ("hd", "bytetrack", "off"),
        ("hd", "deepsort", "off"), ("hd", "bytetrack", "mars"),
    ]
    assert '"--record-structured-visual", "--no-control"' in RUNNER
    assert 'duration = 240 if not smoke' in RUNNER
    assert 'warmup = 60 if not smoke' in RUNNER
    assert '"detector,tracker,tim" if' in RUNNER
    assert '"detector,tracker"' in RUNNER
    assert "--field-record" not in RUNNER
    assert "--control-mavros" not in RUNNER
    assert "source /opt/ros/jazzy/setup.bash" in SHELL


def test_missing_evidence_cannot_pass(tmp_path):
    result = summary.summarize(5, "2026-09-22__14-00-00", tmp_path / "missing_bag",
                               tmp_path / "missing_run", operator_target_id=3)
    assert result["classification"] == "invalid"
    assert result["reasons"]


def test_matrix_does_not_infer_decision_from_incomplete_cells(tmp_path):
    (tmp_path / "bags/live_camera").mkdir(parents=True)
    result = summary.matrix(tmp_path)
    assert result["matrix_complete"] is False
    assert result["hd_runtime_qualified"] is None
    assert result["decision"] == "pending_matrix"


def test_hd_tim_frozen_gate_boundaries(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    from types import SimpleNamespace

    bag = tmp_path / "bag"
    run = tmp_path / "run"
    (run / "p032_resources").mkdir(parents=True)
    bag.mkdir()
    start = 1_700_000_000_000_000_000
    end = start + 240_000_000_000
    active = start + 60_000_000_000
    topics = list(summary.STREAMS) + ["/target_memory_mars", "/timing_target",
                                      "/target_memory_mars/status"]
    stamps = {topic: [active + i * 1_000_000_000 // 15 for i in range(2700)]
              for topic in topics}
    statuses = [{"appearance_candidates": 1, "appearance_image_age_ms": 20.0,
                 "appearance_skip_reason": "stale_image" if i < 270 else "ok",
                 "tim_mars_processing_ms": 20.0, "appearance_backend_calls": 1,
                 "appearance_backend_valid": 1} for i in range(2700)]
    messages = {
        "/timing": [(ns, SimpleNamespace(e2e_det_ms=50)) for ns in stamps["/timing"]],
        "/timing_tracker": [(ns, SimpleNamespace(track_ms=10)) for ns in stamps["/timing_tracker"]],
        "/timing_target": [(ns, SimpleNamespace(e2e_validated_target_ms=200)) for ns in stamps["/timing_target"]],
        "/target_memory_mars/status": [(ns, SimpleNamespace(data=json.dumps(row)))
                                        for ns, row in zip(stamps["/target_memory_mars/status"], statuses)],
    }
    resources = {
        "measurement_window": {"analysis_start_monotonic_ns": 100_000_000_000_000},
        "integrity": {"architecture_has_complete_samples": True,
                      "live_resource_roots_present_throughout_window": True,
                      "resource_records_have_known_sample_schema": True,
                      "hardware_records_have_known_sample_schema": True,
                      "steady_state_resource_samples_present": True,
                      "steady_state_hardware_samples_present": True},
        "architecture_total": {"missing_requested_groups": [],
                               "cpu_percent": {"steady_state": {"mean": 300}},
                               "rss_kib": {"steady_state": {"mean": 1_000_000}}},
        "hardware": {"temperature_c": {"steady_state": {"maximum": 65}},
                     "arm_frequency_hz": {"steady_state": {"mean": 2400000000}},
                     "mem_available_kib": {"steady_state": {"minimum": 6000000,
                                                          "maximum": 6100000}},
                     "throttling": {"steady_state": {"nonzero_count": 0}},
                     "samples_with_errors": {"steady_state": 0}},
    }
    monkeypatch.setattr(summary, "resource_window", lambda _: (start, end, resources))
    def samples(_):
        messages["/target_memory_mars/status"] = [
            (ns, SimpleNamespace(data=json.dumps(row)))
            for ns, row in zip(stamps["/target_memory_mars/status"], statuses)
        ]
        return stamps, messages
    monkeypatch.setattr(summary, "bag_samples", samples)
    def write(name, value):
        (bag / name).write_text(json.dumps(value))
    write("evidence_package_status.json", {"runtime_status": "complete_runtime_evidence",
                                           "provenance_validation": {"passed": True}})
    write("recorder_transport_status.json", {"quality_status": "observed_zero"})
    write("visual_evidence_status.json", {"passed": True, "duration_s": 250})
    write("bag_integrity.json", {"passed": True})
    write("per_topic_quality.json", {"checks_passed": True,
                                     "topics": {topic: {"timestamp_monotonic": True} for topic in topics}})
    (bag / "timing_full_horizon.md").write_text("full horizon\n")
    visual_start = datetime.fromtimestamp((start - 5_000_000_000) / 1e9, timezone.utc).isoformat()
    write("run_metadata.json", {"run_id": "run1", "scenario_tag": summary.CELLS[5][3],
        "visual": {"file": str(bag / "visual_run1.mkv"), "started_at_utc": visual_start},
        "bag": {"recorded_topics": topics},
        "topic_qos_inventory": {topic: {"publisher_count": 1} for topic in topics},
        "resolved_parameters": {"perception_camera_node": {"width": "1280", "height": "720"}},
        "invocation": {"command": "start_live_stack.sh --no-control"}})
    (bag / "target_authority_events.jsonl").write_text(json.dumps({
        "authority_state": "selection_requested", "requested_target_id": 3,
        "monotonic_ns": 99_999_999_999_999}) + "\n")
    (run / "p032_resources/provenance.json").write_text(json.dumps({
        "architecture_groups": ["detector", "tracker", "tim"]}))
    (run / "p064_collection_status.json").write_text(json.dumps({
        "formal": True, "cell": 5, "run_id": "run1", "tag": summary.CELLS[5][3],
        "launcher_ready": True, "launcher_finalized": True, "sampler_returncode": 0,
        "operator_target_id": 3, "physical_target_description": "person in blue jacket",
        "analysis_returncodes": {"per_topic": 0, "full_horizon_timing": 0,
                                 "transport": 0, "provenance": 0, "package": 0}}))
    passed = summary.summarize(5, "run1", bag, run, operator_target_id=3)
    assert passed["classification"] == "pass", passed["reasons"]
    assert passed["metrics"]["stale_appearance_fraction"] == .1
    collection = json.loads((run / "p064_collection_status.json").read_text())
    collection["sampler_returncode"] = 1
    (run / "p064_collection_status.json").write_text(json.dumps(collection))
    incomplete = summary.summarize(5, "run1", bag, run, operator_target_id=3)
    assert incomplete["classification"] == "invalid"
    collection["sampler_returncode"] = 0
    (run / "p064_collection_status.json").write_text(json.dumps(collection))
    statuses[270]["appearance_skip_reason"] = "stale_image"
    failed = summary.summarize(5, "run1", bag, run, operator_target_id=3)
    assert failed["classification"] == "fail"
    assert "stale appearance fraction above 10 percent" in failed["reasons"]
    statuses[270]["appearance_skip_reason"] = "ok"
    messages["/timing_target"][0] = (stamps["/timing_target"][0],
                                    SimpleNamespace(e2e_validated_target_ms=201))
    for i, ns in enumerate(stamps["/timing_target"]):
        messages["/timing_target"][i] = (ns, SimpleNamespace(e2e_validated_target_ms=201))
    failed = summary.summarize(5, "run1", bag, run, operator_target_id=3)
    assert failed["classification"] == "fail"
    assert "validated-target p95 above 200 ms" in failed["reasons"]
