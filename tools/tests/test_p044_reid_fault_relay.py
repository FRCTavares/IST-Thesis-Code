"""Tests for the experiment-only P044 live ReID fault relay."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceEmbeddingResult,
)


ROOT = Path(__file__).resolve().parents[2]
RELAY_PATH = (
    ROOT
    / "tools"
    / "experiments"
    / "p044_reid_fault_relay.py"
)


def load_module():
    module_name = "p044_reid_fault_relay"
    spec = importlib.util.spec_from_file_location(
        module_name,
        RELAY_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    # Dataclasses with postponed annotations resolve their defining module
    # through sys.modules while the module body is being executed.
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(
            module_name,
            None,
        )
        raise

    return module


def successful_result():
    value = np.ones(
        512,
        dtype=np.float32,
    )
    value /= np.linalg.norm(value)

    return AppearanceEmbeddingResult(
        request_id=17,
        backend_name="repvgg-a0",
        embedding_space="repvgg-a0-person-reid-512d",
        dimension=512,
        started_ns=1_000,
        completed_ns=2_000,
        embedding=value,
        error=None,
    )


def test_fault_configuration_accepts_only_explicit_modes():
    relay = load_module()

    for mode in relay.FAULT_MODES:
        configuration = (
            relay.validate_fault_configuration(
                mode,
                1000.0,
            )
        )

        assert configuration.mode == mode

    with pytest.raises(
        ValueError,
        match="unsupported",
    ):
        relay.validate_fault_configuration(
            "random_drop",
            1000.0,
        )


def test_delay_mode_requires_positive_delay():
    relay = load_module()

    with pytest.raises(
        ValueError,
        match="positive delay",
    ):
        relay.validate_fault_configuration(
            "delay_result",
            0.0,
        )

    assert (
        relay.delay_ns_from_ms(1000.0)
        == 1_000_000_000
    )


def test_injected_failure_preserves_causal_result_contract():
    relay = load_module()
    source = successful_result()

    failure = relay.injected_backend_failure(
        source,
        now_ns=3_000,
    )

    assert failure.request_id == (
        source.request_id
    )
    assert failure.backend_name == (
        source.backend_name
    )
    assert failure.embedding_space == (
        source.embedding_space
    )
    assert failure.dimension == (
        source.dimension
    )
    assert failure.embedding is None
    assert failure.error == (
        relay.INJECTED_FAILURE_REASON
    )
    assert failure.started_ns == 1_000
    assert failure.completed_ns == 3_000


def test_cli_defaults_keep_fault_injection_disabled():
    relay = load_module()
    parser = relay.build_parser()

    args = parser.parse_args(
        [
            "--summary-path",
            "/tmp/p044-relay-summary.json",
        ]
    )

    assert args.mode == "none"
    assert args.delay_ms == 1000.0
    assert args.input_topic == (
        "/appearance/reid/result_raw"
    )
    assert args.output_topic == (
        "/appearance/reid/result"
    )


def test_relay_uses_matching_best_effort_volatile_qos():
    source = RELAY_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "ReliabilityPolicy.BEST_EFFORT"
        in source
    )
    assert (
        "DurabilityPolicy.VOLATILE"
        in source
    )
    assert (
        "HistoryPolicy.KEEP_LAST"
        in source
    )


def test_relay_records_explicit_evidence_boundaries():
    source = RELAY_PATH.read_text(
        encoding="utf-8"
    )

    required = (
        '"experiment_only": True',
        '"production_node_modified": False',
        '"cpu_mars_authoritative": True',
        '"repvgg_observational": True',
        '"target_memory_modified": False',
        '"target_selection_modified": False',
        '"canonical_policy_modified": False',
        "p044_reid_fault_relay_status_v1",
        "p044_reid_fault_relay_summary_v1",
        "delayed_queue_depth",
        "abandoned_delayed",
    )

    for fragment in required:
        assert fragment in source


def test_relay_does_not_import_decision_runtime():
    source = RELAY_PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "target_memory_mars_node",
        "TargetMemoryMARS",
        "PositiveAppearanceMemory",
        "appearance_request_policy",
        "tim_mars_canonical.yaml",
    )

    for fragment in forbidden:
        assert fragment not in source
