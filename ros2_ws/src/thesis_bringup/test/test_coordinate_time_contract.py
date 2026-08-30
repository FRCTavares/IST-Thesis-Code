"""Regression tests for the live source-coordinate and image-time contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from thesis_bringup.dashboard.dashboard_bridge_node import DashboardBridgeNode
from thesis_bringup.perception.perception_pipeline_node import (
    PerceptionPipelineNode,
)
from thesis_bringup.perception.preprocessing import (
    COORDINATE_TRANSFORM_CONTRACT,
    ImageTransform,
)


REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(
    ("source_size", "box"),
    [
        ((640, 480), (0.0, 0.0, 640.0, 480.0)),
        ((640, 480), (1.0, 2.0, 639.0, 479.0)),
        ((1920, 800), (123.0, 45.0, 1900.0, 799.0)),
        ((301, 997), (0.5, 0.5, 300.5, 996.5)),
    ],
)
def test_direct_resize_box_round_trip_stays_within_one_pixel(
    source_size,
    box,
):
    transform = ImageTransform.direct_resize(
        source_width=source_size[0],
        source_height=source_size[1],
        inference_width=640,
        inference_height=640,
    )

    inference_box = transform.source_xyxy_to_inference(box)
    round_trip = transform.inference_xyxy_to_source(inference_box)

    assert np.max(np.abs(np.asarray(round_trip) - np.asarray(box))) <= 1.0
    assert transform.pad_x == 0.0
    assert transform.pad_y == 0.0


def test_inverse_transform_clips_boxes_to_source_edges():
    transform = ImageTransform.direct_resize(640, 480, 640, 640)

    mapped = transform.inference_xyxy_to_source(
        (-20.0, -30.0, 700.0, 710.0),
    )

    assert mapped == (0.0, 0.0, 640.0, 480.0)


def test_detection_publication_maps_inference_box_to_source_pixels():
    transform = ImageTransform.direct_resize(640, 480, 640, 640)
    frame = SimpleNamespace(
        frame_id=17,
        stamp_sec=12,
        stamp_nanosec=34,
        t_cam_msg_seen_ns=123456789,
        transform=transform,
    )
    node = object.__new__(PerceptionPipelineNode)
    node.img_w = 640
    node.img_h = 640
    node.min_score = 0.35
    node.label = "person"

    result = {
        "detections": [
            {
                "x": 0.25,
                "y": 0.25,
                "w": 0.5,
                "h": 0.5,
                "score": 0.9,
                "label": "person",
            },
        ],
    }
    output = PerceptionPipelineNode._build_detection_array(
        node,
        frame,
        result,
    )

    assert len(output.detections) == 1
    detection = output.detections[0]
    assert detection.bbox.center.position.x == pytest.approx(320.0)
    assert detection.bbox.center.position.y == pytest.approx(240.0)
    assert detection.bbox.size_x == pytest.approx(320.0)
    assert detection.bbox.size_y == pytest.approx(240.0)
    assert output.header.frame_id.startswith(
        f"{COORDINATE_TRANSFORM_CONTRACT};frame=17;"
    )
    assert "source=640x480" in output.header.frame_id
    assert "inference=640x640" in output.header.frame_id
    assert "t_cam_msg_seen_ns=123456789" in output.header.frame_id


def test_dashboard_normalizes_source_pixel_boxes_without_second_transform():
    node = object.__new__(DashboardBridgeNode)
    node._camera_ref_w = 640.0
    node._camera_ref_h = 480.0

    normalized = DashboardBridgeNode._map_bbox_to_stream_norm(
        node,
        cx=320.0,
        cy=240.0,
        w=160.0,
        h=120.0,
    )

    assert normalized == pytest.approx((0.5, 0.5, 0.25, 0.25))


def test_live_tim_and_control_use_source_camera_dimensions():
    launcher = (REPO_ROOT / "tools/start_live_stack.sh").read_text(
        encoding="utf-8",
    )

    tim_block = launcher.split("start_ros_bg target_memory_mars", 1)[1]
    tim_block = tim_block.split("sleep 1", 1)[0]
    control_block = launcher.split("start_ros_bg control", 1)[1]
    control_block = control_block.split("sleep 1", 1)[0]

    assert "-p image_width:=${CAMERA_WIDTH}.0" in tim_block
    assert "-p image_height:=${CAMERA_HEIGHT}.0" in tim_block
    assert "-p img_w:=${CAMERA_WIDTH}.0" in control_block
    assert "-p img_h:=${CAMERA_HEIGHT}.0" in control_block


@pytest.mark.parametrize(
    ("source_size", "expected_size"),
    [
        ((1280, 720), (640.0, 360.0)),
        ((1920, 1080), (960.0, 540.0)),
    ],
)
def test_p064_detection_publication_stays_in_high_resolution_source_pixels(
    source_size,
    expected_size,
):
    transform = ImageTransform.direct_resize(
        source_width=source_size[0],
        source_height=source_size[1],
        inference_width=640,
        inference_height=640,
    )
    frame = SimpleNamespace(
        frame_id=64,
        stamp_sec=12,
        stamp_nanosec=34,
        t_cam_msg_seen_ns=987654321,
        transform=transform,
    )
    node = object.__new__(PerceptionPipelineNode)
    node.img_w = 640
    node.img_h = 640
    node.min_score = 0.35
    node.label = "person"
    result = {
        "detections": [
            {
                "x": 0.25,
                "y": 0.25,
                "w": 0.5,
                "h": 0.5,
                "score": 0.9,
                "label": "person",
            },
        ],
    }

    output = PerceptionPipelineNode._build_detection_array(
        node, frame, result
    )
    detection = output.detections[0]

    assert detection.bbox.center.position.x == pytest.approx(
        source_size[0] / 2
    )
    assert detection.bbox.center.position.y == pytest.approx(
        source_size[1] / 2
    )
    assert detection.bbox.size_x == pytest.approx(expected_size[0])
    assert detection.bbox.size_y == pytest.approx(expected_size[1])
    expected_source = (
        f"source={source_size[0]}x{source_size[1]}"
    )
    assert expected_source in output.header.frame_id
    assert "inference=640x640" in output.header.frame_id
    assert "pad=0,0" in output.header.frame_id
    assert "t_cam_msg_seen_ns=987654321" in output.header.frame_id
