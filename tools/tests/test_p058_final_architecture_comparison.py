"""Contract tests for the frozen Issue #58 final architecture runner.

These bind the runner to the active Stage-7 prospective freeze
(``tim_mars_final_comparison_v3_2026_09_08`` / ``tim_mars_split_v4_2026_09_08``)
and to the current frozen replay/evaluation tooling. No test requires real
H01/H02/H03 held-out data.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = (
    REPO_ROOT
    / "tools/experiments/run_p058_final_architecture_comparison.py"
)
CONTRACT_PATH = (
    REPO_ROOT / "docs/data/splits/tim_mars_final_comparison_v3.json"
)
SPLIT_PATH = REPO_ROOT / "docs/data/splits/tim_mars_split_v4.json"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_p058_final_architecture_comparison",
        RUNNER_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = load_runner()


def contract():
    return json.loads(CONTRACT_PATH.read_text())


def split():
    return json.loads(SPLIT_PATH.read_text())


# --- Active Stage-7 authorities ----------------------------------------------

def test_defaults_bind_to_active_stage7_authorities():
    assert RUN.DEFAULT_CONTRACT == CONTRACT_PATH
    assert RUN.DEFAULT_SPLIT == SPLIT_PATH
    assert contract()["contract_id"] == RUN.ACTIVE_CONTRACT_ID
    assert split()["split_id"] == RUN.ACTIVE_SPLIT_ID
    assert RUN.ACTIVE_CONTRACT_ID == "tim_mars_final_comparison_v3_2026_09_08"
    assert RUN.ACTIVE_SPLIT_ID == "tim_mars_split_v4_2026_09_08"
    assert RUN.ACTIVE_ALGORITHM_FREEZE_COMMIT == (
        "79f11b631688889bf5ffbeb3c16ef543a53f9973"
    )


def test_active_contract_validates_and_returns_architectures():
    architectures = RUN.validate_contract(contract())
    assert tuple(architectures) == RUN.ARCHITECTURE_ORDER


def test_superseded_v2_contract_is_rejected_not_executed():
    stale = copy.deepcopy(contract())
    stale["contract_id"] = "tim_mars_final_comparison_v2_2026_09_05"
    with pytest.raises(SystemExit):
        RUN.validate_contract(stale)


def test_unknown_contract_id_is_rejected():
    stale = copy.deepcopy(contract())
    stale["contract_id"] = "tim_mars_final_comparison_v9_2027_01_01"
    with pytest.raises(SystemExit):
        RUN.validate_contract(stale)


def test_supplied_contract_is_authoritative():
    # The runner operates on the dict it is handed; it never swaps it for a
    # bundled default. Mutating the supplied contract changes the outcome.
    supplied = copy.deepcopy(contract())
    supplied["common_appearance_model"]["model"][
        "path"
    ] = "models/reid/contract-selected-model.pb"
    assert RUN.common_appearance_model_path(supplied) == (
        REPO_ROOT / "models/reid/contract-selected-model.pb"
    )


# --- Frozen scientific invariants -------------------------------------------

def test_primary_architecture_order_is_exactly_frozen_contract():
    architectures = RUN.architecture_map(contract())
    assert tuple(architectures) == RUN.ARCHITECTURE_ORDER
    assert RUN.ARCHITECTURE_ORDER == (
        "bytetrack_raw",
        "target_reid_090",
        "bytetrack_tim_mars",
        "deepsort_raw",
    )


def test_contract_validation_pins_target_reid_threshold():
    broken = copy.deepcopy(contract())
    broken["primary_architectures"][1]["threshold"] = 0.85
    with pytest.raises(ValueError):
        RUN.validate_contract(broken)


def test_contract_validation_pins_tim_all_candidates_policy():
    broken = copy.deepcopy(contract())
    broken["primary_architectures"][2]["tim_mars"][
        "appearance_request_policy"
    ] = "geometry_winner"
    with pytest.raises(ValueError):
        RUN.validate_contract(broken)


def test_contract_validation_pins_canonical_tim_config_hash():
    broken = copy.deepcopy(contract())
    broken["primary_architectures"][2]["tim_mars"]["config"][
        "sha256"
    ] = "0" * 64
    with pytest.raises(SystemExit):
        RUN.validate_contract(broken)


def test_contract_canonical_hash_is_the_stage7_authority():
    tim_cfg = contract()["primary_architectures"][2]["tim_mars"]["config"]
    assert tim_cfg["sha256"] == RUN.ACTIVE_CANONICAL_TIM_CONFIG_SHA256


def test_all_frozen_contract_file_hashes_match_current_tree():
    verified = RUN.verify_contract_files(contract())
    tim_cfg = contract()["primary_architectures"][2]["tim_mars"]["config"]
    # verified value is the live-tree hash; it must equal the contract's own
    # authoritative record (no hard-coded constant in the test).
    assert (
        verified["ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"]
        == tim_cfg["sha256"]
    )
    assert (
        verified["ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml"]
        == contract()["primary_architectures"][0]["tracker"]["config"][
            "sha256"
        ]
    )


# --- v4 held-out entry schema ---------------------------------------------

def test_final_sequences_parses_v4_entry_schema_when_ready(tmp_path):
    synthetic = copy.deepcopy(split())
    reference = tmp_path / "ref.json"
    reference.write_text("{}")

    for entry in synthetic["sets"]["final_held_out"]:
        entry["status"] = "ready"
        # Path("/repo") / "/abs/tmp/ref.json" collapses to the absolute path.
        entry["annotation_path"] = str(reference)
        entry["annotation_sha256"] = hashlib.sha256(reference.read_bytes()).hexdigest()
        entry["source_path"] = entry["expected_source_path"] + "/exact_capture"

    sequences = RUN.final_sequences(contract(), synthetic, None)

    ids = [s["id"] for s in sequences]
    assert ids == list(contract()["held_out_split"]["sequence_ids"])
    for seq in sequences:
        assert seq["evidence_role"] == "final_held_out"
        assert "expected_source_path" not in seq
        assert seq["source_path"].startswith("bags/source/held_out/")
        assert seq["detections_topic"] == "/detections"
        assert seq["image_width"] == RUN.HELDOUT_SOURCE_IMAGE_WIDTH
        assert seq["image_height"] == RUN.HELDOUT_SOURCE_IMAGE_HEIGHT


def test_final_sequences_refuses_reserved_pending_capture():
    # Real v4 split: every held-out entry is reserved_pending_capture.
    with pytest.raises(SystemExit):
        RUN.final_sequences(contract(), split(), None)


def test_final_sequences_ordering_follows_contract():
    synthetic = copy.deepcopy(split())
    synthetic["sets"]["final_held_out"] = list(
        reversed(synthetic["sets"]["final_held_out"])
    )
    with pytest.raises(SystemExit):
        # still refuses (not ready) but must not KeyError on reordering
        RUN.final_sequences(contract(), synthetic, None)


# --- Top-level fail-closed gate (no synthetic H01/H02/H03 outcomes) --------

def test_final_held_out_refuses_before_any_replay(tmp_path, monkeypatch):
    """--set final_held_out must exit non-zero and start no replay while any
    held-out sequence is not ready. Uses a stub split validator so the test is
    hermetic and fast; the real validator's --require-final-ready behaviour is
    covered by tools/tests/test_validate_tim_evaluation_split.py."""
    fake_validator = tmp_path / "fake_split_validator.py"
    fake_validator.write_text(
        "import sys\n"
        "sys.exit(2 if '--require-final-ready' in sys.argv else 0)\n"
    )
    monkeypatch.setattr(RUN, "SPLIT_VALIDATOR", fake_validator)

    synthetic_split = tmp_path / "synthetic_v4_split.json"
    synthetic_split.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "split_id": RUN.ACTIVE_SPLIT_ID,
                "freeze": {
                    "final_comparison_contract": {
                        "contract_id": RUN.ACTIVE_CONTRACT_ID
                    }
                },
                "sets": {
                    "development": [],
                    "legacy_validation": [],
                    "final_held_out": [
                        {"id": sid, "status": "reserved_pending_capture"}
                        for sid in contract()["held_out_split"][
                            "sequence_ids"
                        ]
                    ],
                },
            }
        )
    )

    started = []
    monkeypatch.setattr(
        RUN,
        "run_sequence",
        lambda **kwargs: started.append(kwargs["sequence"]["id"]),
    )
    logged = []
    monkeypatch.setattr(
        RUN,
        "run_logged",
        lambda *a, **k: logged.append(a[0]) or 0,
    )

    out_root = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_p058_final_architecture_comparison.py",
            "--set",
            "final_held_out",
            "--run",
            "--output-dir",
            str(out_root),
        ],
    )

    with pytest.raises(SystemExit):
        RUN.main()

    assert started == []
    assert logged == []
    assert not out_root.exists()


# --- Frozen source-file record verification -------------------------------

def _record_for(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "path": str(path),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def test_verify_frozen_file_records_accepts_matching(tmp_path):
    payload = tmp_path / "h0x_0.mcap"
    payload.write_bytes(b"frozen-held-out-source-payload")
    verified = RUN.verify_frozen_file_records(
        [_record_for(payload)], context="test"
    )
    assert verified[str(payload)] == hashlib.sha256(
        payload.read_bytes()
    ).hexdigest()


def test_verify_frozen_file_records_rejects_wrong_sha(tmp_path):
    payload = tmp_path / "h0x_0.mcap"
    payload.write_bytes(b"frozen-held-out-source-payload")
    record = _record_for(payload)
    record["sha256"] = "0" * 64
    with pytest.raises(SystemExit):
        RUN.verify_frozen_file_records([record], context="test")


def test_verify_frozen_file_records_rejects_wrong_size(tmp_path):
    payload = tmp_path / "h0x_0.mcap"
    payload.write_bytes(b"frozen-held-out-source-payload")
    record = _record_for(payload)
    record["size_bytes"] = record["size_bytes"] + 1
    with pytest.raises(SystemExit):
        RUN.verify_frozen_file_records([record], context="test")


def test_verify_frozen_file_records_rejects_missing_file(tmp_path):
    record = {
        "path": str(tmp_path / "does_not_exist.mcap"),
        "size_bytes": 10,
        "sha256": "0" * 64,
    }
    with pytest.raises(SystemExit):
        RUN.verify_frozen_file_records([record], context="test")


def _heldout_sequence(tmp_path, monkeypatch) -> tuple[dict, Path]:
    tmp_path = Path(tmp_path)
    monkeypatch.setattr(RUN, "REPO_ROOT", tmp_path)
    src_dir = tmp_path / "heldout_src"
    src_dir.mkdir(parents=True)
    payload = src_dir / "h0x_0.mcap"
    payload.write_bytes(b"held-out-frozen-source")
    reference = tmp_path / "h0x_ref.json"
    reference.write_text("{}")
    metadata = src_dir / "metadata.yaml"
    metadata.write_text(__import__("yaml").safe_dump({"rosbag2_bagfile_information": {
        "storage_identifier": "mcap", "relative_file_paths": [payload.name],
        "topics_with_message_count": [
            {"topic_metadata": {"name": name}, "message_count": 1}
            for name in ("/camera/image_raw", "/detections")
        ],
    }}))
    records = [_record_for(path) for path in (payload, metadata)]
    for record in records:
        record["path"] = str(Path(record["path"]).relative_to(tmp_path))
    sequence = {
        "id": "heldout_hx",
        "source_path": str(src_dir.relative_to(tmp_path)),
        "physical_reference": str(reference),
        "physical_reference_sha256": hashlib.sha256(
            reference.read_bytes()
        ).hexdigest(),
        "evidence_role": "final_held_out",
        "source_files": records,
    }
    return sequence, payload


def test_verify_sequence_inputs_accepts_matching_heldout_source_files(
    tmp_path, monkeypatch,
):
    sequence, _ = _heldout_sequence(tmp_path, monkeypatch)
    RUN.verify_sequence_inputs(sequence)  # must not raise


def test_verify_sequence_inputs_rejects_tampered_heldout_source_file(
    tmp_path, monkeypatch,
):
    sequence, _ = _heldout_sequence(tmp_path, monkeypatch)
    sequence["source_files"][0]["sha256"] = "0" * 64
    with pytest.raises(SystemExit):
        RUN.verify_sequence_inputs(sequence)

    sequence, _ = _heldout_sequence(tmp_path / "b", monkeypatch)
    sequence["source_files"][0]["size_bytes"] += 7
    with pytest.raises(SystemExit):
        RUN.verify_sequence_inputs(sequence)

    sequence, payload = _heldout_sequence(tmp_path / "c", monkeypatch)
    payload.unlink()
    with pytest.raises(SystemExit):
        RUN.verify_sequence_inputs(sequence)


def test_verify_contract_files_still_uses_shared_helper():
    # Existing contract verification must keep working through the helper.
    verified = RUN.verify_contract_files(contract())
    assert (
        verified["ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"]
        == contract()["primary_architectures"][2]["tim_mars"]["config"][
            "sha256"
        ]
    )


def test_final_held_out_tampered_source_file_stops_before_run_sequence(
    tmp_path, monkeypatch
):
    """A ready held-out entry whose frozen source payload no longer matches
    its recorded hash must fail closed before any architecture replay."""
    fake_validator = tmp_path / "fake_split_validator.py"
    fake_validator.write_text("import sys\nsys.exit(0)\n")
    monkeypatch.setattr(RUN, "SPLIT_VALIDATOR", fake_validator)

    src_dir = tmp_path / "h01_src"
    src_dir.mkdir()
    payload = src_dir / "h01_0.mcap"
    payload.write_bytes(b"the-real-frozen-source-bytes")
    reference = tmp_path / "h01_ref.json"
    reference.write_text("{}")

    good_record = _record_for(payload)
    tampered_record = dict(good_record, sha256="0" * 64)

    contract_ids = contract()["held_out_split"]["sequence_ids"]
    synthetic_split = tmp_path / "synthetic_v4_split.json"
    synthetic_split.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "split_id": RUN.ACTIVE_SPLIT_ID,
                "freeze": {
                    "final_comparison_contract": {
                        "contract_id": RUN.ACTIVE_CONTRACT_ID
                    }
                },
                "sets": {
                    "development": [],
                    "legacy_validation": [],
                    "final_held_out": [
                        {
                            "id": contract_ids[0],
                            "status": "ready",
                            "source_path": str(src_dir),
                            "annotation_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
                            "annotation_path": str(
                                reference
                            ),
                            "files": [tampered_record],
                        },
                        {"id": contract_ids[1], "status": "ready",
                         "source_path": str(src_dir),
                         "annotation_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
                            "annotation_path": str(reference),
                         "files": [good_record]},
                        {"id": contract_ids[2], "status": "ready",
                         "source_path": str(src_dir),
                         "annotation_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
                            "annotation_path": str(reference),
                         "files": [good_record]},
                    ],
                },
            }
        )
    )

    started = []
    monkeypatch.setattr(
        RUN, "run_sequence",
        lambda **kwargs: started.append(kwargs["sequence"]["id"]),
    )
    logged = []
    monkeypatch.setattr(
        RUN, "run_logged", lambda *a, **k: logged.append(a[0]) or 0
    )

    out_root = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv",
        [
            "run_p058_final_architecture_comparison.py",
            "--set", "final_held_out", "--run",
            "--sequence", contract_ids[0],
            "--output-dir", str(out_root),
        ],
    )

    with pytest.raises(SystemExit):
        RUN.main()

    assert started == []
    assert logged == []
    assert not out_root.exists()


def test_run_split_validator_refuses_real_v4_split_when_not_ready():
    # Real repository validator, real v4 split (final_ready=0/3). Structural
    # validity is not required for this assertion: whether the validator exits
    # non-zero for a structural reason or for the final-ready gate, the runner
    # must refuse.
    with pytest.raises(SystemExit):
        RUN.run_split_validator(SPLIT_PATH, require_final_ready=True)


@pytest.mark.skipif(
    not (
        REPO_ROOT
        / json.loads(SPLIT_PATH.read_text())["sets"]["development"][0][
            "source_path"
        ]
    ).exists(),
    reason="development bags not present in this checkout",
)
def test_run_split_validator_accepts_real_v4_split_structurally():
    # No exception: the split is structurally valid for development use
    # (requires the development bags to be present).
    RUN.run_split_validator(SPLIT_PATH, require_final_ready=False)


def test_split_validator_is_not_delegated_hash_verification(monkeypatch):
    seen = {}

    class _Result:
        returncode = 0

    def fake_run(cmd, check):  # noqa: ARG001
        seen["cmd"] = list(cmd)
        return _Result()

    monkeypatch.setattr(RUN.subprocess, "run", fake_run)
    RUN.run_split_validator(SPLIT_PATH, require_final_ready=True)
    assert "--verify-hashes" not in seen["cmd"]
    assert "--require-final-ready" in seen["cmd"]


# --- Frozen-path guard ----------------------------------------------------

def test_is_documentation_only_classification():
    doc = [
        "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/README.md",
        "ros2_ws/src/thesis_tracker/thesis_tracker/README.md",
        "docs/thing.rst",
        "notes.txt",
        "LICENSE",
        "thesis_tracker/NOTICE",
    ]
    behaviour = [
        "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/target_memory.py",
        "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml",
        "tools/experiments/run_deterministic_tim_replay.py",
        "ros2_ws/src/thesis_tracker/thesis_tracker/bytetrack.py",
        "some/data.json",
    ]
    for path in doc:
        assert RUN._is_documentation_only(path), path
    for path in behaviour:
        assert not RUN._is_documentation_only(path), path


def test_behaviour_bearing_frozen_files_excludes_documentation():
    freeze = contract()["source_code_freeze"]
    files = RUN.behaviour_bearing_frozen_files(
        freeze["commit"],
        [str(p) for p in freeze["required_unchanged_paths"]],
    )
    assert files, "expected a non-empty behaviour-bearing frozen file set"
    assert all(not RUN._is_documentation_only(f) for f in files)
    assert (
        "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml" in files
    )
    assert (
        "tools/analysis/evaluate_physical_target_bbox_v2.py" in files
    )
    # READMEs edited by later repository-structure cleanup must be excluded.
    assert (
        "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/README.md"
        not in files
    )
    assert (
        "ros2_ws/src/thesis_tracker/thesis_tracker/README.md" not in files
    )


def test_frozen_guard_blocks_behaviour_change_allows_readme():
    # A behaviour-bearing frozen file changed -> violation.
    assert RUN.frozen_guard_violations(
        changed_behaviour_files=[
            "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/"
            "target_memory.py"
        ],
        added_paths=[],
        working_tree_status="",
    )
    # A README added under a frozen directory -> no violation.
    assert not RUN.frozen_guard_violations(
        changed_behaviour_files=[],
        added_paths=[
            "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/README.md"
        ],
        working_tree_status="",
    )
    # A new non-documentation file under a frozen directory -> violation.
    assert RUN.frozen_guard_violations(
        changed_behaviour_files=[],
        added_paths=[
            "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/"
            "new_helper.py"
        ],
        working_tree_status="",
    )
    # A dirty working tree under a frozen path -> violation.
    assert RUN.frozen_guard_violations(
        changed_behaviour_files=[],
        added_paths=[],
        working_tree_status=" M ros2_ws/src/thesis_bringup/config/"
        "tim_mars_canonical.yaml",
    )
    # Clean -> no violation.
    assert not RUN.frozen_guard_violations(
        changed_behaviour_files=[],
        added_paths=[],
        working_tree_status="",
    )


def test_verify_frozen_git_paths_passes_on_current_tree():
    # The active contract's frozen paths carry only documentation edits since
    # the algorithm authority, so the behaviour-aware guard must pass.
    summary = RUN.verify_frozen_git_paths(contract())
    assert summary["algorithm_authority_commit"] == (
        RUN.ACTIVE_ALGORITHM_FREEZE_COMMIT
    )
    assert summary["behaviour_bearing_frozen_file_count"] > 0


# --- Pinned replay environment ------------------------------------------

def test_pinned_replay_env_parsed_from_stage7_script():
    pinned = RUN.load_pinned_replay_env()
    assert pinned["TF_DETERMINISTIC_OPS"] == "1"
    assert pinned["TF_NUM_INTRAOP_THREADS"] == "1"
    assert pinned["TF_NUM_INTEROP_THREADS"] == "1"
    assert pinned["OMP_NUM_THREADS"] == "1"
    assert pinned["OPENBLAS_NUM_THREADS"] == "1"
    assert pinned["MKL_NUM_THREADS"] == "1"


def test_pinned_env_passed_only_to_mars_replay_subprocesses(
    tmp_path, monkeypatch
):
    """Every MARS/TensorFlow replay subprocess (Target-ReID, ByteTrack+TIM,
    DeepSORT) receives the pinned environment; the appearance-free ByteTrack
    tracker replay, the bootstrap resolver, and the evaluators do not."""
    recorded: list[tuple[list[str], dict | None]] = []

    def fake_run_logged(command, log_path, env=None):
        recorded.append((list(command), env))
        joined = " ".join(str(c) for c in command)
        # Emulate just enough tool output for run_sequence to proceed.
        if "resolve_bootstrap_target.py" in joined:
            out_idx = command.index("--out") + 1
            frame = 2 if "deepsort" in joined else 0
            track = 7 if "deepsort" in joined else 5
            Path(command[out_idx]).parent.mkdir(parents=True, exist_ok=True)
            Path(command[out_idx]).write_text(
                json.dumps(
                    {
                        "ok": True,
                        "resolved_track_id": track,
                        "bootstrap_frame_index": frame,
                        "bootstrap_iou": 0.9,
                    }
                )
            )
        if "run_deterministic_tim_replay.py" in joined:
            bag = Path(command[3])
            bag.mkdir(parents=True, exist_ok=True)
            (bag / "tim_replay_metadata.json").write_text(
                json.dumps(
                    {"determinism": {"generated_semantic_sha256": "deadbeef"}}
                )
            )
        return 0

    ok_report = {
        "reconciliation": {"ok": True},
        "duration_buckets": {
            "correct_target_output_duration_s": 1.0,
            "wrong_person_output_duration_s": 0.0,
            "identity_unresolved_duration_s": 0.0,
            "lost_or_suppressed_duration_s": 0.0,
        },
        "coverage": {},
        "localisation": {},
    }
    monkeypatch.setattr(RUN, "run_logged", fake_run_logged)
    monkeypatch.setattr(
        RUN, "evaluate_single_topic", lambda **k: dict(ok_report)
    )
    monkeypatch.setattr(RUN, "evaluate_tim", lambda **k: dict(ok_report))
    monkeypatch.setattr(RUN, "tracker_digest", lambda bag: "trackerdigest")
    monkeypatch.setattr(RUN, "bag_payload_hashes", lambda bag: [])
    monkeypatch.setattr(RUN, "prune_generated_payloads", lambda root: [])

    architectures = RUN.validate_contract(contract())
    sequence = {
        "id": "dev_probe",
        "source_path": "docs",  # any existing directory
        "physical_reference": "docs/data/splits/tim_mars_split_v4.json",
        "image_topic": "/camera/image_raw",
        "detections_topic": "/detections",
        "image_width": 640,
        "image_height": 640,
    }
    pinned = RUN.load_pinned_replay_env()

    cells = RUN.run_sequence(
        sequence=sequence,
        architectures=architectures,
        contract=contract(),
        output_root=tmp_path / "out",
        keep_bags=True,
        pinned_env=pinned,
    )

    assert {c["architecture_id"] for c in cells} == set(
        RUN.ARCHITECTURE_ORDER
    )
    for cell in cells:
        if cell["architecture_id"] in {
            "target_reid_090",
            "bytetrack_tim_mars",
            "deepsort_raw",
        }:
            assert cell["pinned_replay_env_applied"] is True

    mars_tools = (
        "run_deterministic_tim_replay.py",
        "run_p058_target_reid_replay.py",
    )
    for command, env in recorded:
        joined = " ".join(str(c) for c in command)
        is_mars = any(tool in joined for tool in mars_tools) or (
            "run_deterministic_tracker_replay.py" in joined
            and "--model" in command
        )
        is_bytetrack_tracker = (
            "run_deterministic_tracker_replay.py" in joined
            and "--model" not in command
        )
        is_support = (
            "resolve_bootstrap_target.py" in joined
        )
        if is_mars:
            assert env is not None and env["TF_DETERMINISTIC_OPS"] == "1", (
                joined
            )
        if is_bytetrack_tracker or is_support:
            assert env is None, joined


# --- Bootstrap semantics ------------------------------------------------

def test_bytetrack_bootstrap_fixed_to_predetermined_initial_frame(tmp_path):
    command = RUN.bootstrap_command(
        Path("/tmp/tracks"),
        Path("/tmp/reference.json"),
        tmp_path / "bootstrap.json",
    )
    assert command[command.index("--min-iou") + 1] == "0.5"
    assert (
        command[command.index("--max-bootstrap-lag-frames") + 1] == "1"
    )


def test_deepsort_bootstrap_uses_predetermined_confirmed_frame(tmp_path):
    command = RUN.bootstrap_command(
        Path("/tmp/tracks"),
        Path("/tmp/reference.json"),
        tmp_path / "bootstrap.json",
        max_bootstrap_lag_frames=3,
    )
    assert (
        command[command.index("--max-bootstrap-lag-frames") + 1] == "3"
    )


def test_bootstrap_predetermined_frame_guard():
    assert RUN.bootstrap_is_at_predetermined_frame(
        {"ok": True, "bootstrap_frame_index": 2}, 2
    )
    assert not RUN.bootstrap_is_at_predetermined_frame(
        {"ok": True, "bootstrap_frame_index": 1}, 2
    )
    assert not RUN.bootstrap_is_at_predetermined_frame(
        {"ok": False, "bootstrap_frame_index": 2}, 2
    )
    assert not RUN.bootstrap_is_at_predetermined_frame(None, 2)


# --- Development-check safety ------------------------------------------

def test_development_check_contains_no_heldout_sequence():
    sequences = RUN.development_sequences(None)
    assert [s["id"] for s in sequences] == [
        "dev_june_seq03",
        "dev_june_seq04",
    ]
    for sequence in sequences:
        assert not sequence["split_membership_id"].startswith("heldout_")
        assert sequence["evidence_role"] == "development_check"


def test_final_pending_ids_is_state_driven():
    synthetic = copy.deepcopy(split())
    for entry in synthetic["sets"]["final_held_out"]:
        entry["status"] = "ready"
    synthetic["sets"]["final_held_out"][1]["status"] = "reserved_pending_capture"
    synthetic["sets"]["final_held_out"][2]["status"] = "annotation_pending"
    assert RUN.final_pending_ids(synthetic) == [
        synthetic["sets"]["final_held_out"][1]["id"],
        synthetic["sets"]["final_held_out"][2]["id"],
    ]


def test_select_ids_preserves_contract_order():
    assert RUN.select_ids(["h01", "h02", "h03"], ["h03", "h01"]) == [
        "h01",
        "h03",
    ]


# --- Payload pruning scope ------------------------------------------

def test_generated_payload_pruning_never_leaves_scope(tmp_path):
    root = tmp_path / "generated_bags"
    inside = root / "cell"
    inside.mkdir(parents=True)
    mcap = inside / "result.mcap"
    sidecar = inside / "provenance.json"
    outside = tmp_path / "source.mcap"
    mcap.write_bytes(b"generated")
    sidecar.write_text("{}")
    outside.write_bytes(b"source")

    removed = RUN.prune_generated_payloads(root)

    assert len(removed) == 1
    assert not mcap.exists()
    assert sidecar.exists()
    assert outside.exists()
