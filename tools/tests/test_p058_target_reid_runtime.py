"""Tests for the Issue #58 deterministic Target-ReID runtime adapter."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
BASELINE_PATH = ANALYSIS_DIR / "p058_target_reid_baseline.py"
RUNTIME_PATH = ANALYSIS_DIR / "p058_target_reid_runtime.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load_module("p058_target_reid_baseline", BASELINE_PATH)
MODULE = load_module("p058_target_reid_runtime", RUNTIME_PATH)


class FakeMars:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def encode(self, image, boxes):
        result = self.outputs[self.calls]
        self.calls += 1
        assert len(result) == len(boxes)
        return result


def stamp(ns):
    return SimpleNamespace(
        sec=ns // 1_000_000_000,
        nanosec=ns % 1_000_000_000,
    )


def track(track_id, cx=100.0, cy=100.0, w=40.0, h=80.0):
    return SimpleNamespace(
        id=track_id,
        cx=cx,
        cy=cy,
        w=w,
        h=h,
        score=0.9,
    )


def tracks_message(ns, tracks):
    return SimpleNamespace(
        header=SimpleNamespace(stamp=stamp(ns)),
        src_stamp_ns=0,
        tracks=list(tracks),
    )


def runtime(fake_mars, *, threshold=0.7, max_image_age_ms=250.0):
    return MODULE.TargetReIdRuntime(
        model_path="unused.pb",
        selected_track_id=1,
        threshold=threshold,
        image_width=640.0,
        image_height=640.0,
        max_image_age_ms=max_image_age_ms,
        mars_backend=fake_mars,
    )


def image():
    return np.zeros((640, 640, 3), dtype=np.uint8)


def test_first_valid_selected_embedding_bootstraps_anchor_but_does_not_publish():
    rt = runtime(
        FakeMars([
            [
                np.asarray([1.0, 0.0], dtype=np.float32),
                np.asarray([0.0, 1.0], dtype=np.float32),
            ]
        ])
    )

    rt.add_image(1_000_000_000, image())

    result = rt.process_tracks(
        tracks_message(
            1_000_000_000,
            (track(1), track(2)),
        )
    )

    assert result.anchor_ready
    assert not result.decision.published


def test_after_bootstrap_tracker_id_has_no_identity_authority():
    rt = runtime(
        FakeMars([
            [
                np.asarray([1.0, 0.0], dtype=np.float32),
                np.asarray([0.0, 1.0], dtype=np.float32),
            ],
            [
                np.asarray([0.6, 0.8], dtype=np.float32),
                np.asarray([1.0, 0.0], dtype=np.float32),
            ],
        ]),
        threshold=0.5,
    )

    rt.add_image(1_000_000_000, image())
    rt.process_tracks(
        tracks_message(
            1_000_000_000,
            (track(1), track(2)),
        )
    )

    rt.add_image(1_100_000_000, image())
    result = rt.process_tracks(
        tracks_message(
            1_100_000_000,
            (track(1), track(99)),
        )
    )

    assert result.decision.published
    assert result.decision.selected_candidate is not None
    assert result.decision.selected_candidate.track_id == 99


def test_below_threshold_returns_lost():
    rt = runtime(
        FakeMars([
            [np.asarray([1.0, 0.0], dtype=np.float32)],
            [np.asarray([0.6, 0.8], dtype=np.float32)],
        ]),
        threshold=0.7,
    )

    rt.add_image(1_000_000_000, image())
    rt.process_tracks(
        tracks_message(
            1_000_000_000,
            (track(1),),
        )
    )

    rt.add_image(1_100_000_000, image())
    result = rt.process_tracks(
        tracks_message(
            1_100_000_000,
            (track(7),),
        )
    )

    assert not result.decision.published
    assert result.decision.similarity == pytest.approx(0.6)


def test_too_old_image_returns_lost_without_encoding():
    mars = FakeMars([])
    rt = runtime(
        mars,
        max_image_age_ms=250.0,
    )

    rt.add_image(1_000_000_000, image())

    result = rt.process_tracks(
        tracks_message(
            1_300_000_001,
            (track(1),),
        )
    )

    assert not result.anchor_ready
    assert not result.decision.published
    assert mars.calls == 0


def test_latest_nonfuture_image_is_selected():
    rt = runtime(
        FakeMars([
            [np.asarray([1.0, 0.0], dtype=np.float32)]
        ])
    )

    rt.add_image(1_000_000_000, image())
    rt.add_image(1_090_000_000, image())
    rt.add_image(1_110_000_000, image())

    result = rt.process_tracks(
        tracks_message(
            1_100_000_000,
            (track(1),),
        )
    )

    assert result.selected_image_timestamp_ns == 1_090_000_000
    assert result.image_age_ms == pytest.approx(10.0)


def test_anchor_waits_for_selected_track_valid_embedding():
    rt = runtime(
        FakeMars([
            [
                None,
                np.asarray([1.0, 0.0], dtype=np.float32),
            ],
            [
                np.asarray([1.0, 0.0], dtype=np.float32),
                np.asarray([0.0, 1.0], dtype=np.float32),
            ],
        ])
    )

    rt.add_image(1_000_000_000, image())
    first = rt.process_tracks(
        tracks_message(
            1_000_000_000,
            (track(1), track(2)),
        )
    )

    assert not first.anchor_ready

    rt.add_image(1_100_000_000, image())
    second = rt.process_tracks(
        tracks_message(
            1_100_000_000,
            (track(1), track(2)),
        )
    )

    assert second.anchor_ready
    assert not second.decision.published


def test_pixel_bbox_conversion_matches_tracker_geometry():
    rt = runtime(
        FakeMars([
            [np.asarray([1.0, 0.0], dtype=np.float32)]
        ])
    )

    bbox = rt._track_bbox_xyxy(
        track(
            1,
            cx=100.0,
            cy=150.0,
            w=40.0,
            h=80.0,
        )
    )

    assert bbox == pytest.approx(
        (80.0, 110.0, 120.0, 190.0)
    )
