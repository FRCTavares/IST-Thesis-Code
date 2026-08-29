"""Focused contract tests for common image+detection bag construction."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest
SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "build_common_input_bag.py"
SPEC = importlib.util.spec_from_file_location("build_common_input_bag", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
def test_common_input_sorts_exact_pairs_deterministically():
    pairs = MODULE.validate_common_input_records([(20, b"image-20"), (10, b"image-10")], [(10, b"detection-10"), (20, b"detection-20")])
    assert pairs == [(10, b"image-10", b"detection-10"), (20, b"image-20", b"detection-20")]
def test_common_input_rejects_count_mismatch():
    with pytest.raises(RuntimeError, match="counts differ"):
        MODULE.validate_common_input_records([(10, b"image")], [])
def test_common_input_rejects_duplicate_source_timestamp():
    with pytest.raises(RuntimeError, match="Duplicate source image"):
        MODULE.validate_common_input_records([(10, b"first"), (10, b"second")], [(10, b"detection"), (20, b"other")])
def test_common_input_rejects_missing_timestamp_peer():
    with pytest.raises(RuntimeError, match="do not match exactly"):
        MODULE.validate_common_input_records([(10, b"image"), (20, b"image2")], [(10, b"detection"), (30, b"detection2")])
def test_common_input_rejects_nonpositive_timestamp():
    with pytest.raises(RuntimeError, match="non-positive"):
        MODULE.validate_common_input_records([(0, b"image")], [(0, b"detection")])
