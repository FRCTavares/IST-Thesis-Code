"""Regression tests for the post-access physical-v2 source-time correction."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT
    / "tools"
    / "analysis"
    / "evaluate_physical_target_bbox_v2_source_time_repair.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "evaluate_physical_target_bbox_v2_source_time_repair",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _stamp(ns: int):
    return SimpleNamespace(
        sec=ns // 1_000_000_000,
        nanosec=ns % 1_000_000_000,
    )


def _message(
    *,
    src_stamp_ns: int = 0,
    header_ns: int = 0,
):
    return SimpleNamespace(
        src_stamp_ns=src_stamp_ns,
        header=SimpleNamespace(
            stamp=_stamp(header_ns),
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_output_timestamp_prefers_src_stamp_ns():
    message = _message(
        src_stamp_ns=123,
        header_ns=456,
    )

    assert MODULE.output_message_time_ns(
        message,
        789,
    ) == (123, "src_stamp_ns")


def test_output_timestamp_falls_back_to_positive_header():
    message = _message(
        src_stamp_ns=0,
        header_ns=456,
    )

    assert MODULE.output_message_time_ns(
        message,
        789,
    ) == (456, "header.stamp")


def test_output_timestamp_falls_back_to_bag_record():
    message = _message(
        src_stamp_ns=0,
        header_ns=0,
    )

    assert MODULE.output_message_time_ns(
        message,
        789,
    ) == (789, "bag_record_timestamp")


def test_source_image_timestamp_uses_header_not_src_stamp():
    message = _message(
        src_stamp_ns=111,
        header_ns=222,
    )

    assert MODULE.source_image_time_ns(
        message,
        333,
    ) == (222, "header.stamp")


def test_source_image_timestamp_falls_back_to_bag_record():
    message = _message(
        src_stamp_ns=111,
        header_ns=0,
    )

    assert MODULE.source_image_time_ns(
        message,
        333,
    ) == (333, "bag_record_timestamp")


def test_h01_known_origin_semantics():
    record_ns = 1789486281311251797
    header_ns = 1789486281308955860

    message = _message(
        header_ns=header_ns,
    )

    resolved, clock = MODULE.source_image_time_ns(
        message,
        record_ns,
    )

    assert resolved == 1789486281308955860
    assert clock == "header.stamp"
    assert record_ns - resolved == 2295937


def test_repair_delegates_scoring_to_frozen_v2_core():
    source = inspect.getsource(MODULE.main)

    assert (
        "pbe2.evaluate_physical_target_bbox_v2"
        in source
    )
    assert (
        Path(MODULE.pbe2.__file__).resolve()
        == (
            REPO_ROOT
            / "tools"
            / "analysis"
            / "physical_target_bbox_evaluation_v2.py"
        ).resolve()
    )


def test_frozen_v2_files_remain_byte_identical():
    expected = {
        "physical_target_reference_v2.py":
            "6299542c5ae3f4f21bb313112f8375774ed2685ccf0cb164bd56848c34094c96",
        "physical_target_bbox_evaluation_v2.py":
            "4e80edc4a574d0eaf9fadbcf5c085513afe2ba40758cb25bbaeb866400fdbcfd",
        "evaluate_physical_target_bbox_v2.py":
            "ab6012a3cf912c1a9c35be3487101c55d646c8a00d3bb47670ab20785076a631",
    }

    analysis = REPO_ROOT / "tools" / "analysis"

    for filename, digest in expected.items():
        assert _sha256(analysis / filename) == digest
