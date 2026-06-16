# Live camera transport bottleneck check

Date: 2026-06-16

## Test setup

Hardware:
- Raspberry Pi 5
- TEVS-AR0234 CSI camera
- Hailo AI HAT+

Runtime:
- ROS 2 Jazzy
- camera_capture_node
- perception_pipeline_node
- Hailo direct backend

Detection-only launch:
- capture: 640x480
- publish: 640x480
- image encoding: bgr8
- Hailo input: 640x640
- tracker disabled
- target memory disabled
- dashboard disabled
- web video disabled

## Key measurements

Colour ROS image transport:

    /camera/image_raw about 26.4 Hz
    encoding=bgr8
    resolution=640x480

Detector output:

    /detections about 26.9 Hz

Timing sample:

    pre_ms = 3.56 ms
    resize_ms = 1.75 ms
    color_ms = 1.76 ms
    infer_ms = 8.14 ms
    post_ms = 0.08 ms
    e2e_det_ms = 13.68 ms
    loop_ms = 13.38 ms
    pub_dt_ms = 34.73 ms

CPU and thermal:

    camera_capture_node CPU about 105 percent
    perception_pipeline_node CPU about 64 percent
    temperature about 61.5 C
    throttled = 0x0

## Conclusion

The Hailo detector is not the limiting stage. Inference takes about 8 ms and the full detection loop is about 14 ms, which is well below the 33.3 ms frame period for 30 FPS.

The limiting stage is the full-colour ROS image transport path before inference:

    TEVS camera
    -> OpenCV BGR frame
    -> Python ROS 2 sensor_msgs/Image bgr8
    -> DDS
    -> perception node

Diagnostic tests showed:

    mono8 640x480, 307 KB/frame -> about 30 Hz
    bgr8 640x480, 922 KB/frame -> about 26 Hz

An experimental UYVY path through OpenCV was attempted, but OpenCV still returned BGR frames with shape (480, 640, 3) even when native capture was requested. Therefore UYVY transport through the current OpenCV path is not useful.

## Engineering decision

The best real-time architecture is to keep the colour frame inside the perception process and publish only compact semantic outputs:

    camera/perception process
    -> Hailo inference
    -> /detections
    -> /timing

The full-colour /camera/image_raw topic should remain a debug and visualisation path, not the critical inference path.
