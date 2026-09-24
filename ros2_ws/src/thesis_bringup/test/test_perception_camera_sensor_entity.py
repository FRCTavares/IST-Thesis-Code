"""Regression tests for integrated-camera TEVS entity detection."""

from thesis_bringup.perception.perception_camera_node import (
    _extract_tevs_sensor_entity,
)


def test_extracts_unquoted_media_ctl_tevs_entity():
    topology = """
Device topology
- entity 1: csi2 (8 pads, 8 links, 0 routes)
- entity 16: tevs 10-0048 (1 pad, 1 link, 0 routes)
             type V4L2 subdev subtype Sensor flags 0
             device node name /dev/v4l-subdev2
- entity 18: rp1-cfe-csi2_ch0 (1 pad, 1 link)
"""
    assert _extract_tevs_sensor_entity(topology) == "tevs 10-0048"


def test_prefers_first_tevs_entity():
    topology = """
- entity 16: tevs 10-0048 (1 pad, 1 link, 0 routes)
- entity 17: tevs 11-0048 (1 pad, 1 link, 0 routes)
"""
    assert _extract_tevs_sensor_entity(topology) == "tevs 10-0048"


def test_returns_none_without_tevs_entity():
    topology = """
- entity 1: csi2 (8 pads, 8 links, 0 routes)
- entity 18: rp1-cfe-csi2_ch0 (1 pad, 1 link)
"""
    assert _extract_tevs_sensor_entity(topology) is None
