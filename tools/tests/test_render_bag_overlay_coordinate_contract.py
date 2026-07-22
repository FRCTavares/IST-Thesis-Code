"""Test source-pixel handling in the saved-overlay renderer."""

from __future__ import annotations

from types import SimpleNamespace

from tools.bag.render_bag_overlay_video import (
    bbox_from_any,
    coordinate_contract_from_message,
    map_overlay_box_to_image,
)


def test_source_pixel_header_exposes_exact_source_dimensions():
    message = SimpleNamespace(
        header=SimpleNamespace(
            frame_id=(
                "tim_mars_source_pixels_resize_v1;frame=7;"
                "source=640x480;inference=640x640;"
                "scale=1,1.33333333;pad=0,0"
            ),
        ),
    )

    contract = coordinate_contract_from_message(message)

    assert contract is not None
    assert contract.source_width == 640
    assert contract.source_height == 480


def test_edge_pixel_box_is_not_misread_as_normalized():
    track = SimpleNamespace(cx=1.0, cy=10.0, w=2.0, h=8.0)

    box = bbox_from_any(
        track,
        640,
        480,
        pixel_coordinates=True,
    )

    assert box == (0, 6, 2, 14)


def test_source_pixel_box_scales_directly_to_saved_image():
    mapped = map_overlay_box_to_image(
        box=(160, 120, 480, 360),
        src_w=640,
        src_h=480,
        img_w=1280,
        img_h=960,
        resize_mode="source",
    )

    assert mapped == (320, 240, 960, 720)
