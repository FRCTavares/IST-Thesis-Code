"""Issue #50/#74: explicit ArduPilot DataFlash .bin archival (no FCU)."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "tools/live/archive_pixhawk_dataflash.py"


def _load():
    spec = importlib.util.spec_from_file_location("archive_pixhawk_dataflash", MODULE)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


apd = _load()


def _bag(tmp_path: Path) -> Path:
    bag = tmp_path / "run__video"
    bag.mkdir()
    (bag / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    return bag


# K. explicit .bin copies correctly + hash recorded
def test_explicit_bin_is_copied_with_verified_hash(tmp_path):
    bag = _bag(tmp_path)
    src = tmp_path / "downloads" / "2026-09-10 14-00-00.bin"
    src.parent.mkdir()
    payload = b"DFLOG" + bytes(range(256)) * 40
    src.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()

    code, manifest = apd.archive_dataflash(
        run_id="2026-09-10__14-01-08", bag_dir=bag, source_bin=src
    )
    assert code == 0
    archived = bag / "pixhawk_dataflash" / src.name
    assert archived.read_bytes() == payload
    assert manifest["source"]["sha256"] == expected
    assert manifest["archived"]["sha256"] == expected
    assert manifest["sha256_match"] is True
    assert manifest["hardware_verification"] == "pending"
    assert manifest["retrieval_method"] == "explicit_operator_supplied_file"
    assert manifest["source"]["path"] == str(src)
    # source preserved
    assert src.read_bytes() == payload

    written = json.loads(
        (bag / "pixhawk_dataflash" / "dataflash_manifest.json").read_text()
    )
    assert written["sha256_match"] is True


# L. no overwrite of an existing archived .bin / manifest
def test_refuses_overwrite_without_modifying_anything(tmp_path):
    bag = _bag(tmp_path)
    src = tmp_path / "a.bin"
    src.write_bytes(b"first")
    apd.archive_dataflash(run_id="r1", bag_dir=bag, source_bin=src)

    original = (bag / "pixhawk_dataflash" / "a.bin").read_bytes()
    manifest_before = (bag / "pixhawk_dataflash" / "dataflash_manifest.json").read_text()

    src2 = tmp_path / "a.bin"  # same name, different content
    src2.write_bytes(b"second-and-different")
    code, result = apd.archive_dataflash(run_id="r1", bag_dir=bag, source_bin=src2)
    assert code == 3
    assert "refusing to overwrite" in result["error"]
    assert (bag / "pixhawk_dataflash" / "a.bin").read_bytes() == original
    assert (bag / "pixhawk_dataflash" / "dataflash_manifest.json").read_text() == manifest_before


def test_missing_args_and_bad_paths_fail(tmp_path):
    bag = _bag(tmp_path)
    code, _ = apd.archive_dataflash(run_id="", bag_dir=bag, source_bin=tmp_path / "x.bin")
    assert code == 2
    code, _ = apd.archive_dataflash(
        run_id="r", bag_dir=tmp_path / "nope", source_bin=tmp_path / "x.bin"
    )
    assert code == 2
    (tmp_path / "real.bin").write_bytes(b"x")
    code, _ = apd.archive_dataflash(
        run_id="r", bag_dir=bag, source_bin=tmp_path / "not_a_file"
    )
    assert code == 2


def test_cli_requires_all_three_explicit_args(tmp_path):
    bag = _bag(tmp_path)
    (tmp_path / "f.bin").write_bytes(b"x")
    for args in (
        ["--bag-dir", str(bag), "--source-bin", str(tmp_path / "f.bin")],
        ["--run-id", "r", "--source-bin", str(tmp_path / "f.bin")],
        ["--run-id", "r", "--bag-dir", str(bag)],
    ):
        result = subprocess.run(
            [sys.executable, str(MODULE), *args], capture_output=True, text=True
        )
        assert result.returncode == 2  # argparse: missing required


# M. no "latest" / mtime / directory-scan selection anywhere in the code
def test_helper_never_selects_latest_or_by_mtime():
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    called = set()
    attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attrs.add(node.attr)
        if isinstance(node, ast.Name):
            called.add(node.id)
    for banned in ("getmtime", "getctime", "st_mtime", "st_ctime",
                   "glob", "iglob", "iterdir", "scandir", "listdir", "walk"):
        assert banned not in attrs and banned not in called, (
            f"dataflash helper must not use {banned!r}"
        )
    assert "sorted" not in called
    # it only acts on the explicitly supplied path
    sig = inspect.signature(apd.archive_dataflash)
    assert "source_bin" in sig.parameters
