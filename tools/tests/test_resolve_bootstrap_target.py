"""Focused tests for physical-reference bootstrap time alignment."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_PATH = REPO_ROOT / "tools/analysis/resolve_bootstrap_target.py"


def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "resolve_bootstrap_target", RESOLVER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RESOLVER = load_resolver()


def stamp(time_ns: int):
    return SimpleNamespace(
        sec=time_ns // 1_000_000_000,
        nanosec=time_ns % 1_000_000_000,
    )


def image(time_ns: int):
    return SimpleNamespace(header=SimpleNamespace(stamp=stamp(time_ns)))


def tracks(time_ns: int, track_id: int | None, box=(10.0, 10.0, 20.0, 20.0)):
    values = []
    if track_id is not None:
        x1, y1, x2, y2 = box
        values.append(
            SimpleNamespace(
                id=track_id,
                cx=(x1 + x2) / 2.0,
                cy=(y1 + y2) / 2.0,
                w=x2 - x1,
                h=y2 - y1,
            )
        )
    return SimpleNamespace(src_stamp_ns=time_ns, tracks=values)


class FakeReader:
    def __init__(self, messages):
        self.messages = list(messages)
        self.index = 0

    def open(self, *_args):
        return None

    def get_all_topics_and_types(self):
        return [
            SimpleNamespace(name="/camera/image_raw", type="sensor_msgs/msg/Image"),
            SimpleNamespace(name="/tracks", type="thesis_msgs/msg/Track2DArray"),
        ]

    def has_next(self):
        return self.index < len(self.messages)

    def read_next(self):
        value = self.messages[self.index]
        self.index += 1
        return value


def install_fake_bag(monkeypatch, messages):
    monkeypatch.setattr(RESOLVER, "SequentialReader", lambda: FakeReader(messages))
    monkeypatch.setattr(RESOLVER, "deserialize_message", lambda raw, _cls: raw)
    monkeypatch.setattr(RESOLVER, "get_message", lambda _name: object)


def write_reference(
    tmp_path: Path,
    reference_t_s: float,
    additional_times_s=(),
) -> Path:
    path = tmp_path / "reference.json"
    path.write_text(
        json.dumps(
            {
                "provenance": {"source_image_topic": "/camera/image_raw"},
                "samples": [
                    {
                        "t_s": value,
                        "identity_state": "present_scored",
                        "target_bbox_xyxy": [10.0, 10.0, 20.0, 20.0],
                    }
                    for value in (reference_t_s, *additional_times_s)
                ],
            }
        )
    )
    return path


def test_pre_reference_tracks_do_not_consume_bytetrack_budget(tmp_path, monkeypatch):
    origin = 10_000_000_000
    messages = [
        ("/tracks", tracks(origin + 1_000_000_000, 99), origin + 1),
        ("/camera/image_raw", image(origin), origin + 2),
        ("/tracks", tracks(origin + 2_000_000_000, 98), origin + 3),
        ("/tracks", tracks(origin + 3_000_000_000, 7), origin + 4),
    ]
    install_fake_bag(monkeypatch, messages)

    result = RESOLVER.resolve(
        tmp_path / "bag",
        write_reference(tmp_path, 3.0),
        "/tracks",
        min_iou=0.5,
        max_lag_frames=1,
    )

    assert result["ok"] is True
    assert result["resolved_track_id"] == 7
    assert result["bootstrap_frame_index"] == 0
    assert result["track_frames_skipped_before_reference"] == 2
    assert result["per_frame_best"][0]["track_time_from_reference_origin_s"] == 3.0


def test_deepsort_budget_starts_at_reference_instant(tmp_path, monkeypatch):
    origin = 10_000_000_000
    messages = [
        ("/tracks", tracks(origin - 2, None), origin - 2),
        ("/tracks", tracks(origin - 1, None), origin - 1),
        ("/camera/image_raw", image(origin), origin),
        ("/tracks", tracks(origin, None), origin),
        ("/tracks", tracks(origin + 1, None), origin + 1),
        ("/tracks", tracks(origin + 2, 3), origin + 2),
    ]
    install_fake_bag(monkeypatch, messages)

    result = RESOLVER.resolve(
        tmp_path / "bag",
        write_reference(tmp_path, 0.0, (0.000000001, 0.000000002)),
        "/tracks",
        min_iou=0.5,
        max_lag_frames=3,
    )

    assert result["ok"] is True
    assert result["resolved_track_id"] == 3
    assert result["bootstrap_frame_index"] == 2
    assert result["track_frames_skipped_before_reference"] == 2
    assert result["frames_inspected"] == 3


def test_exact_required_frame_wins_over_earlier_threshold_matches(
    tmp_path, monkeypatch
):
    origin = 10_000_000_000
    messages = [
        ("/camera/image_raw", image(origin), origin),
        ("/tracks", tracks(origin, 3), origin),
        ("/tracks", tracks(origin + 1_000_000_000, 3), origin + 1),
        ("/tracks", tracks(origin + 2_000_000_000, 3), origin + 2),
    ]
    install_fake_bag(monkeypatch, messages)

    result = RESOLVER.resolve(
        tmp_path / "bag",
        write_reference(tmp_path, 0.0, (1.0, 2.0)),
        "/tracks",
        min_iou=0.5,
        max_lag_frames=3,
        required_frame_index=2,
    )

    assert result["ok"] is True
    assert result["bootstrap_frame_index"] == 2
    assert result["required_bootstrap_frame_index"] == 2
    assert [frame["best_track_id"] for frame in result["per_frame_best"]] == [
        3,
        3,
        3,
    ]
