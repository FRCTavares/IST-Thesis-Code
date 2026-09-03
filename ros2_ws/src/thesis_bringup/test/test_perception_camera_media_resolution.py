from thesis_bringup.perception.perception_camera_node import PerceptionCameraNode


def test_detect_tevs_entity_from_current_media_graph():
    graph = """
- entity 1: csi2 (8 pads, 8 links, 0 routes)
             type V4L2 subdev subtype Unknown flags 0
        <- "tevs 10-0048":0 [ENABLED,IMMUTABLE]

- entity 16: tevs 10-0048 (1 pad, 1 link, 0 routes)
             type V4L2 subdev subtype Sensor flags 0
             device node name /dev/v4l-subdev2
"""
    assert (
        PerceptionCameraNode._detect_tevs_entity_from_media_graph(graph)
        == "tevs 10-0048"
    )


def test_detect_tevs_entity_supports_alternate_i2c_address():
    graph = """
- entity 16: tevs 11-0048 (1 pad, 1 link, 0 routes)
             type V4L2 subdev subtype Sensor flags 0
"""
    assert (
        PerceptionCameraNode._detect_tevs_entity_from_media_graph(graph)
        == "tevs 11-0048"
    )


def test_detect_tevs_entity_ignores_link_reference():
    graph = """
        <- "tevs 10-0048":0 [ENABLED,IMMUTABLE]
- entity 18: rp1-cfe-csi2_ch0 (1 pad, 1 link)
"""
    assert PerceptionCameraNode._detect_tevs_entity_from_media_graph(graph) is None


def test_detect_tevs_entity_returns_none_without_tevs_entity():
    graph = """
- entity 1: csi2 (8 pads, 8 links, 0 routes)
- entity 18: rp1-cfe-csi2_ch0 (1 pad, 1 link)
"""
    assert PerceptionCameraNode._detect_tevs_entity_from_media_graph(graph) is None
