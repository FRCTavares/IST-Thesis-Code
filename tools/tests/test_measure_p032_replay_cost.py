from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "experiments" / "measure_p032_replay_cost.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p032_measure_replay_cost",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_sha256_file_matches_known_hash(tmp_path: Path) -> None:
    module = load_module()

    target = tmp_path / "sample.bin"
    payload = b"issue-32 fixture content"
    target.write_bytes(payload)

    assert module.sha256_file(target) == sha256_bytes(payload)


def test_find_by_id_unknown_architecture_raises() -> None:
    module = load_module()

    with pytest.raises(SystemExit, match="unknown architecture"):
        module.find_by_id([{"id": "bytetrack_raw"}], "made_up_id", "architecture")


def test_find_by_id_unknown_sequence_raises() -> None:
    module = load_module()

    with pytest.raises(SystemExit, match="unknown sequence"):
        module.find_by_id([{"id": "dev_may_hard_reentry"}], "made_up", "sequence")


def test_find_by_id_returns_matching_entry() -> None:
    module = load_module()

    entries = [{"id": "a"}, {"id": "b"}]
    assert module.find_by_id(entries, "b", "architecture") is entries[1]


def _build_source_and_config(tmp_path: Path) -> tuple[Path, Path, str, str]:
    source_dir = tmp_path / "source_bag"
    source_dir.mkdir()
    source_file = source_dir / "source_0.mcap"
    source_bytes = b"fixture source bag bytes"
    source_file.write_bytes(source_bytes)

    config_path = tmp_path / "tracker_config.yaml"
    config_bytes = b"tracker_node:\n  ros__parameters:\n    tracker_type: bytetrack\n"
    config_path.write_bytes(config_bytes)

    return (
        source_dir,
        config_path,
        sha256_bytes(source_bytes),
        sha256_bytes(config_bytes),
    )


def test_measure_tracker_stage_rejects_source_hash_mismatch(
    tmp_path: Path,
) -> None:
    module = load_module()
    module.REPO_ROOT = tmp_path  # relative manifest paths resolve under tmp_path

    source_dir, config_path, source_sha, config_sha = _build_source_and_config(
        tmp_path
    )

    manifest = {"frozen_boundary": {}}
    architecture = {
        "id": "bytetrack_raw",
        "tracker_config": str(config_path.relative_to(tmp_path)),
        "tracker_config_sha256": config_sha,
        "requires_model": False,
    }
    sequence = {
        "id": "dev_may_hard_reentry",
        "source_path": str(source_dir.relative_to(tmp_path)),
        "source_bag_file": "source_0.mcap",
        "source_sha256": "0" * 64,
        "selected_target_id": 1,
    }

    with pytest.raises(SystemExit, match="source bag hash mismatch"):
        module.measure_tracker_stage(
            manifest,
            architecture,
            sequence,
            tmp_path / "out",
            overwrite=True,
        )


def test_measure_tracker_stage_rejects_config_hash_mismatch(
    tmp_path: Path,
) -> None:
    module = load_module()
    module.REPO_ROOT = tmp_path

    source_dir, config_path, source_sha, config_sha = _build_source_and_config(
        tmp_path
    )

    manifest = {"frozen_boundary": {}}
    architecture = {
        "id": "bytetrack_raw",
        "tracker_config": str(config_path.relative_to(tmp_path)),
        "tracker_config_sha256": "0" * 64,
        "requires_model": False,
    }
    sequence = {
        "id": "dev_may_hard_reentry",
        "source_path": str(source_dir.relative_to(tmp_path)),
        "source_bag_file": "source_0.mcap",
        "source_sha256": source_sha,
        "selected_target_id": 1,
    }

    with pytest.raises(SystemExit, match="tracker config hash mismatch"):
        module.measure_tracker_stage(
            manifest,
            architecture,
            sequence,
            tmp_path / "out",
            overwrite=True,
        )


def test_measure_tracker_stage_rejects_missing_source_dir(
    tmp_path: Path,
) -> None:
    module = load_module()
    module.REPO_ROOT = tmp_path

    manifest = {"frozen_boundary": {}}
    architecture = {
        "id": "bytetrack_raw",
        "tracker_config": "does_not_matter.yaml",
        "tracker_config_sha256": "0" * 64,
        "requires_model": False,
    }
    sequence = {
        "id": "dev_may_hard_reentry",
        "source_path": "missing_source_dir",
        "source_bag_file": "source_0.mcap",
        "source_sha256": "0" * 64,
        "selected_target_id": 1,
    }

    with pytest.raises(SystemExit, match="source bag directory missing"):
        module.measure_tracker_stage(
            manifest,
            architecture,
            sequence,
            tmp_path / "out",
            overwrite=True,
        )


def test_measure_tim_stage_rejects_non_tim_architecture(
    tmp_path: Path,
) -> None:
    module = load_module()
    module.REPO_ROOT = tmp_path

    manifest = {"frozen_boundary": {}}
    architecture = {"id": "bytetrack_raw", "tim_enabled": False}
    sequence = {"id": "dev_may_hard_reentry", "selected_target_id": 1}

    with pytest.raises(SystemExit, match="does not enable TIM"):
        module.measure_tim_stage(
            manifest,
            architecture,
            sequence,
            tmp_path / "out",
            overwrite=True,
        )


def test_measure_tim_stage_rejects_missing_tracks_bag(
    tmp_path: Path,
) -> None:
    module = load_module()
    module.REPO_ROOT = tmp_path

    manifest = {"frozen_boundary": {}}
    architecture = {"id": "bytetrack_tim", "tim_enabled": True}
    sequence = {"id": "dev_may_hard_reentry", "selected_target_id": 1}

    output_dir = tmp_path / "out_no_tracks"
    output_dir.mkdir()

    with pytest.raises(SystemExit, match="tracks bag missing"):
        module.measure_tim_stage(
            manifest,
            architecture,
            sequence,
            output_dir,
            overwrite=True,
        )


def test_measure_tim_stage_rejects_tim_config_hash_mismatch(
    tmp_path: Path,
) -> None:
    module = load_module()
    module.REPO_ROOT = tmp_path

    tim_config = tmp_path / "tim_mars_canonical.yaml"
    tim_config.write_bytes(b"tim config fixture")

    mars_model = tmp_path / "mars-small128.pb"
    mars_model.write_bytes(b"model fixture")

    output_dir = tmp_path / "out_with_tracks"
    output_dir.mkdir()
    (output_dir / "tracks.bag").mkdir()

    manifest = {
        "frozen_boundary": {
            "canonical_tim_mars_config": str(
                tim_config.relative_to(tmp_path)
            ),
            "canonical_tim_mars_config_sha256": "0" * 64,
            "mars_model_path": str(mars_model.relative_to(tmp_path)),
            "mars_model_sha256": sha256_bytes(b"model fixture"),
        }
    }
    architecture = {"id": "bytetrack_tim", "tim_enabled": True}
    sequence = {"id": "dev_may_hard_reentry", "selected_target_id": 1}

    with pytest.raises(SystemExit, match="TIM-MARS config hash mismatch"):
        module.measure_tim_stage(
            manifest,
            architecture,
            sequence,
            output_dir,
            overwrite=True,
        )
