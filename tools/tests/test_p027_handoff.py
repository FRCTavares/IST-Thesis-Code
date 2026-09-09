"""Synthetic Stage-7 source/annotation handoff; never runs an architecture."""
import copy
import json
from pathlib import Path
import sys

import pytest
import yaml

import test_validate_tim_evaluation_split as V
import test_p058_final_architecture_comparison as R
import test_cvat_physical_reference as CTEST

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/analysis"))
sys.path.insert(0, str(ROOT / "tools/experiments"))
import p027_handoff as H
import finalize_p027_heldout_entry as F


def ready_fixture(root, entry_id):
    source = root / "bags/source" / entry_id / "exact_capture"
    source.mkdir(parents=True)
    (source / "source_0.mcap").write_bytes(b"synthetic source bytes; no serialized algorithm output")
    info = {"storage_identifier": "mcap", "relative_file_paths": ["source_0.mcap"],
            "topics_with_message_count": [
                {"topic_metadata": {"name": name}, "message_count": 3}
                for name in ("/camera/image_raw", "/detections")]}
    (source / "metadata.yaml").write_text(yaml.safe_dump({"rosbag2_bagfile_information": info}))
    (source / "run_metadata.json").write_text(json.dumps(
        {"git": {"commit": "a" * 40, "dirty": False}}))
    relative_source = source.relative_to(root).as_posix()
    reference = json.loads((ROOT / "tools/analysis/templates/physical_target_reference_v2_template.json").read_text())
    reference["provenance"].update(
        sequence_id=entry_id, source_bag_path=relative_source,
        source_bag_name=source.name, evaluation_window={"start_s": 0.0, "end_s": 0.09})
    sample = copy.deepcopy(reference["samples"][1])
    sample.update(t_s=0.0, interpolate_from_previous=False)
    end = copy.deepcopy(sample)
    end.update(t_s=0.09, interpolate_from_previous=True)
    reference["samples"] = [sample, end]
    annotation = root / f"{entry_id}.json"
    annotation.write_text(json.dumps(reference))
    manifest = CTEST.manifest()
    manifest.update(sequence_id=entry_id, source_bag_path=relative_source, source_bag_name=source.name)
    manifest["source_bag_provenance"]["metadata_yaml_sha256"] = H.sha256_file(source / "metadata.yaml")
    frame_manifest = root / f"{entry_id}_frames.json"
    frame_manifest.write_text(json.dumps(manifest))
    entry = {
        "id": entry_id, "status": "ready", "scenario": "synthetic only",
        "expected_source_path": "planning/unused",
        "planned_physical_v2_reference_path": "planning/unused.json",
        "source_path": relative_source, "annotation_path": annotation.name,
        "annotation_sha256": H.sha256_file(annotation),
        "selected_target_id": 0, "people_group": "anonymous_A",
        "clothing_group": "outfit_A", "overlap_record": "Explicit synthetic overlap record.",
        "historical_exposure": "Synthetic only; no algorithm exposure.",
        "files": H.source_inventory(root, relative_source),
    }
    return entry, frame_manifest


def stage7(root):
    split = V.manifest(root, final_ready=False)
    split["split_id"] = H.ACTIVE_SPLIT_ID
    entries = [ready_fixture(root, entry_id)[0]
               for entry_id in F.SCENARIOS.values()]
    split["sets"]["final_held_out"] = entries
    contract_path = V.bind_final_comparison_contract(root, split)
    return split, json.loads(contract_path.read_text())


def test_validator_and_runner_share_actual_frozen_authorities(tmp_path, monkeypatch):
    split, contract = stage7(tmp_path)
    monkeypatch.setattr(R.RUN, "REPO_ROOT", tmp_path)
    assert V.validate(split, tmp_path, verify_hashes=True, require_final_ready=True) == []
    sequences = R.RUN.final_sequences(contract, split, None)
    for entry, sequence in zip(split["sets"]["final_held_out"], sequences):
        assert sequence["source_path"] == entry["source_path"]
        assert sequence["physical_reference"] == entry["annotation_path"]
        assert sequence["physical_reference_sha256"] == entry["annotation_sha256"]
        assert sequence["source_files"] == entry["files"]
        R.RUN.verify_sequence_inputs(sequence)


@pytest.mark.parametrize("field", ["source", "annotation"])
def test_tampering_after_validation_fails_both_consumers(tmp_path, monkeypatch, field):
    split, contract = stage7(tmp_path)
    monkeypatch.setattr(R.RUN, "REPO_ROOT", tmp_path)
    assert V.validate(split, tmp_path, verify_hashes=True) == []
    entry = split["sets"]["final_held_out"][0]
    sequence = R.RUN.final_sequences(contract, split, None)[0]
    path = tmp_path / (entry["source_path"] + "/source_0.mcap" if field == "source" else entry["annotation_path"])
    data = path.read_bytes()
    # Same-size changes prove hash verification rather than only size checks.
    path.write_bytes(data.replace(b"synthetic", b"SYNTHETIC", 1) if field == "source"
                     else data.replace(b"black_shirt", b"white_shirt", 1))
    assert path.read_bytes() != data
    assert V.validate(split, tmp_path, verify_hashes=True)
    with pytest.raises(SystemExit):
        R.RUN.verify_sequence_inputs(sequence)
    if field == "annotation":
        # Re-resolution must retain the old expected hash, not bless new bytes.
        resolved = R.RUN.final_sequences(contract, split, None)[0]
        assert resolved["physical_reference_sha256"] == entry["annotation_sha256"]
        with pytest.raises(SystemExit):
            R.RUN.verify_sequence_inputs(resolved)


@pytest.mark.parametrize("field", ["source_path", "annotation_path", "annotation_sha256",
                                  *H.METADATA_FIELDS, "selected_target_id", "files"])
def test_ready_metadata_missing_fails_closed(tmp_path, field):
    split, _ = stage7(tmp_path)
    del split["sets"]["final_held_out"][0][field]
    assert V.validate(split, tmp_path, verify_hashes=True)


@pytest.mark.parametrize("change", ["add", "omit", "redirect", "duplicate"])
def test_source_inventory_cannot_miss_or_redirect_payload(tmp_path, change):
    entry, _ = ready_fixture(tmp_path, F.SCENARIOS["h01"])
    if change == "add":
        (tmp_path / entry["source_path"] / "extra.mcap").write_bytes(b"extra")
    elif change == "omit":
        entry["files"] = entry["files"][:-1]
    elif change == "duplicate":
        entry["files"].append(entry["files"][0])
    else:
        entry["source_path"] = "bags/source"
    with pytest.raises(ValueError):
        H.validate_ready_entry(entry, tmp_path, verify_hashes=True)


def proposal_fixture(tmp_path):
    ready, manifest = ready_fixture(tmp_path, F.SCENARIOS["h01"])
    pending = copy.deepcopy(ready)
    for key in ("source_path", "annotation_path", "annotation_sha256", "selected_target_id"):
        pending.pop(key)
    pending.update(status="reserved_pending_capture", files=[])
    split = {"split_id": H.ACTIVE_SPLIT_ID, "sets": {"final_held_out": [pending]}}
    kwargs = dict(root=tmp_path, scenario="h01", source_path=ready["source_path"],
                  annotation_path=ready["annotation_path"], frame_manifest=manifest.name,
                  metadata={key: ready[key] for key in H.METADATA_FIELDS})
    return split, kwargs


def test_proposal_is_non_mutating_and_requires_no_algorithm_output(tmp_path):
    split, kwargs = proposal_fixture(tmp_path)
    before = copy.deepcopy(split)
    candidate, entry = F.propose(split, **kwargs)
    assert split == before
    assert candidate["sets"]["final_held_out"][0] == entry
    assert entry["status"] == "ready"
    assert entry["selected_target_id"] == 0
    assert entry["expected_source_path"] == before["sets"]["final_held_out"][0]["expected_source_path"]
    H.validate_ready_entry(entry, tmp_path, verify_hashes=True)


def test_refinalization_refused(tmp_path):
    split, kwargs = proposal_fixture(tmp_path)
    candidate, _ = F.propose(split, **kwargs)
    with pytest.raises(ValueError, match="pending"):
        F.propose(candidate, **kwargs)


@pytest.mark.parametrize("field,value", [
    ("people_group", "pending_capture"), ("overlap_record", ""),
    ("selected_target_id", 1), ("selected_target_id", False),
])
def test_placeholder_and_tracker_identity_refused(tmp_path, field, value):
    entry, _ = ready_fixture(tmp_path, F.SCENARIOS["h01"])
    entry[field] = value
    with pytest.raises(ValueError):
        H.validate_ready_entry(entry, tmp_path, verify_hashes=True)


def test_manifest_from_another_source_refused(tmp_path):
    split, kwargs = proposal_fixture(tmp_path)
    path = tmp_path / kwargs["frame_manifest"]
    manifest = json.loads(path.read_text())
    manifest["source_bag_path"] = "bags/another_source"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="source differs"):
        F.propose(split, **kwargs)


def test_pending_stage7_still_valid(tmp_path):
    split = V.manifest(tmp_path, final_ready=False)
    split["split_id"] = H.ACTIVE_SPLIT_ID
    assert V.validate(split, tmp_path, verify_hashes=True) == []
    assert V.validate(split, tmp_path, require_final_ready=True)


def test_proposal_cli_refuses_existing_output_without_mutation(tmp_path, monkeypatch):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "evidence"
    sentinel.write_bytes(b"preserve")
    monkeypatch.setattr(sys, "argv", ["finalize", "--scenario", "h01",
        "--source-path", "unused", "--annotation-path", "unused",
        "--frame-manifest", "unused", "--metadata", "unused",
        "--output-dir", str(output), "--confirm-human-reviewed"])
    with pytest.raises(SystemExit):
        F.main()
    assert sentinel.read_bytes() == b"preserve"


def test_proposal_cli_validates_candidate_and_emits_only_review_files(tmp_path, monkeypatch):
    split, _ = stage7(tmp_path)
    ready = split["sets"]["final_held_out"][0]
    metadata_path = tmp_path / "operator_metadata.json"
    metadata_path.write_text(json.dumps({key: ready[key] for key in H.METADATA_FIELDS}))
    actual_source, actual_annotation = ready["source_path"], ready["annotation_path"]
    ready.update(status="reserved_pending_capture", files=[])
    for key in ("source_path", "annotation_path", "annotation_sha256", "selected_target_id"):
        ready.pop(key)
    split_path = tmp_path / "split.json"
    split_path.write_text(json.dumps(split, indent=2) + "\n")
    before = split_path.read_bytes()
    output = tmp_path / "proposal"
    monkeypatch.setattr(F, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["finalize", "--scenario", "h01",
        "--split", str(split_path), "--source-path", actual_source,
        "--annotation-path", actual_annotation,
        "--frame-manifest", F.SCENARIOS["h01"] + "_frames.json",
        "--metadata", str(metadata_path), "--output-dir", str(output),
        "--confirm-human-reviewed"])
    F.main()
    assert split_path.read_bytes() == before
    candidate = json.loads((output / "split.proposed.json").read_text())
    assert V.validate(candidate, tmp_path, verify_hashes=True, require_final_ready=True) == []
    assert set(path.name for path in output.iterdir()) == {
        "split.patch", "ready-entry.json", "split.proposed.json", "proposal-provenance.json"}
    patch = (output / "split.patch").read_text()
    assert "--- a/split.json" in patch and "+++ b/split.json" in patch
    # Exercise the emitted patch in a synthetic repository only.
    import subprocess
    subprocess.run(["git", "apply", "--check", str(output / "split.patch")],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "apply", str(output / "split.patch")], cwd=tmp_path, check=True)
    assert json.loads(split_path.read_text()) == candidate


@pytest.mark.parametrize("scenario", ["h01", "h02", "h03"])
def test_blank_cvat_templates_require_human_fields(tmp_path, scenario):
    path = ROOT / f"docs/data/preparation/p027/{scenario}_cvat_preparation.json"
    template = json.loads(path.read_text())
    assert template["sequence_id"] == F.SCENARIOS[scenario]
    assert "samples" not in template and "semantic_intervals" not in template
    assert "selected_target_id" not in template
    with pytest.raises(ValueError):
        CTEST.C.preparation_config(path)
    template.update(source_bag_path="bags/source/synthetic", annotator="human",
                    selected_physical_target_label="anonymous_target",
                    coordinate_convention_evidence="synthetic source inspection")
    filled = tmp_path / "preparation.json"
    filled.write_text(json.dumps(template))
    CTEST.C.preparation_config(filled)


def test_source_with_algorithm_topics_is_refused_without_reading_payload(tmp_path):
    entry, _ = ready_fixture(tmp_path, F.SCENARIOS["h01"])
    path = tmp_path / entry["source_path"] / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data["rosbag2_bagfile_information"]["topics_with_message_count"].append(
        {"topic_metadata": {"name": "/target_memory_mars/status"}, "message_count": 1})
    path.write_text(yaml.safe_dump(data))
    entry["files"] = H.source_inventory(tmp_path, entry["source_path"])
    with pytest.raises(ValueError, match="only non-empty"):
        H.validate_ready_entry(entry, tmp_path, verify_hashes=True)
