"""Presentation contracts for the raw-versus-TIM comparison renderer."""

import importlib.util
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools/bag/render_tim_comparison_video.py"

SPEC = importlib.util.spec_from_file_location("tim_comparison_video", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RENDERER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RENDERER
SPEC.loader.exec_module(RENDERER)


def test_annotation_reference_is_white_and_visibly_dashed():
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    RENDERER.draw_dashed_rectangle(image, (10, 10, 100, 100))

    top_edge = image[10, 10:101]
    bright = np.all(top_edge >= 200, axis=1)
    assert bright.any()
    assert (~bright).any()


def test_header_text_is_scaled_to_stay_inside_panel():
    image = np.zeros((108, 960, 3), dtype=np.uint8)
    text = "May hard re-entry | TIM-MARS [/target_memory_mars] | ByteTrack"

    scale = RENDERER.put_text_fit(
        image, text, (16, 30), 928, 0.72, RENDERER.WHITE, 2, 0.52
    )
    width = RENDERER.cv2.getTextSize(
        text, RENDERER.cv2.FONT_HERSHEY_SIMPLEX, scale, 2
    )[0][0]

    assert width <= 928
    assert image[:, 16:944].any()


def test_header_is_above_and_does_not_cover_camera_pixels():
    camera = np.zeros((540, 960, 3), dtype=np.uint8)
    camera[0, :] = (12, 34, 56)
    camera[-1, :] = (78, 90, 123)

    panel = RENDERER.draw_panel(
        camera,
        "Seq01 | RAW [/target] | ByteTrack",
        "LOST",
        RENDERER.YELLOW,
        2.0,
        0,
        0,
        None,
        None,
        "clean_visible",
        0.0,
    )

    assert panel.shape == (652, 960, 3)
    assert np.array_equal(panel[RENDERER.HEADER_HEIGHT :], camera)


def test_letterbox_preserves_full_four_by_three_frame():
    camera = np.full((480, 640, 3), 127, dtype=np.uint8)
    viewport, scale, pad_x, pad_y = RENDERER.letterbox_image(camera, 960, 540)

    assert viewport.shape == (540, 960, 3)
    assert scale == 1.125
    assert (pad_x, pad_y) == (120, 0)
    assert np.all(viewport[:, :120] == 0)
    assert np.all(viewport[:, 120:840] == 127)


def test_seq01_legacy_inference_box_uses_independent_xy_scaling():
    recorded = (
        283.5250644683838,
        104.52411651611328,
        319.49172019958496,
        225.7096176147461,
    )

    mapped = RENDERER.map_box(
        recorded,
        img_w=640,
        img_h=480,
        source_pixels=False,
    )

    assert mapped == (284, 78, 319, 169)


def test_versioned_source_pixel_box_is_not_scaled_twice():
    message = SimpleNamespace(
        header=SimpleNamespace(
            frame_id=(
                "tim_mars_source_pixels_resize_v1;frame=7;"
                "source=640x480;inference=640x640;"
                "scale=1,1.33333333;pad=0,0"
            )
        )
    )

    assert RENDERER.track_boxes_are_source_pixels(message)
    assert RENDERER.map_box(
        (100.0, 50.0, 200.0, 150.0),
        img_w=640,
        img_h=480,
        source_pixels=True,
    ) == (100, 50, 200, 150)


def test_target_absence_has_no_reference_box():
    annotation = RENDERER.Ann(
        start_s=0.0,
        end_s=1.0,
        target_label="CORRECT_TARGET",
        target_visible=False,
        correct_id=53,
        event_type="target_absent",
    )

    status, _, reference_id, bucket = RENDERER.classify(annotation, 53)
    assert status == "ANNOTATION: TARGET ABSENT"
    assert reference_id == 0
    assert bucket == "grey"
    assert RENDERER.status_for_display(status) == "TARGET ABSENT"


def test_latest_sample_exposes_age_for_freshness_gate():
    events = [(0.1, 1), (0.5, 7), (1.0, 9)]
    index, sample_time, value = RENDERER.latest_sample_at(events, 0, 0.8)

    assert index == 1
    assert sample_time == 0.5
    assert value == 7
    assert 0.8 - sample_time < 1.0


def test_pair_uses_one_bag_and_first_image_header_as_common_origin():
    source = inspect.getsource(RENDERER.render_pair)
    assert "t0_ns = first_header_for_topic(bag, selected_image_topic)" in source
    assert source.count('"bag": bag') == 1
    assert 'output_topic="/target"' in source
    assert 'output_topic="/target_memory_mars"' in source


def test_cli_requires_explicit_evidence_and_labels():
    parser = RENDERER.build_parser()
    args = parser.parse_args(
        [
            "--bag",
            "bag",
            "--annotation",
            "annotation.csv",
            "--sequence-label",
            "Seq03",
            "--tracker-label",
            "OC-SORT",
            "--output",
            "comparison.mp4",
        ]
    )

    assert args.bag == Path("bag")
    assert args.output == Path("comparison.mp4")
    assert args.max_output_age_s == 1.0


def test_panel_defaults_use_native_aspect_at_fixed_readable_width():
    namespace = RENDERER.panel_namespace()
    assert namespace.output_width == 960
    assert namespace.header_height == RENDERER.HEADER_HEIGHT
    assert not hasattr(namespace, "output_size")
