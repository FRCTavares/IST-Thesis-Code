# Integrated camera plus Hailo result

Date: 2026-06-16

## Purpose

Evaluate whether the real-time bottleneck was caused by the full-rate ROS colour image transport path before inference.

## Integrated architecture tested

    TEVS camera
    -> perception_camera_node
    -> Hailo direct backend
    -> /detections
    -> /timing

The integrated node keeps the colour frame inside the perception process and does not publish full-rate /camera/image_raw.

## Test configuration

    capture = 640x480
    inference input = 640x640
    encoding inside node = bgr8
    backend = hailo_direct
    target FPS = 30
    tracker = not running
    target memory = not running
    camera_capture_node = not running
    perception_pipeline_node = not running

## Measured output

Nodes:

    /perception_camera_node

Detection rate:

    /detections = 30.000 Hz stable
    min gap = about 0.031 s
    max gap = about 0.035 s
    std dev = about 0.00085 s

Timing sample:

    ros_wait_ms = 0.08
    pre_ms = 2.29
    resize_ms = 1.45
    color_ms = 0.82
    infer_ms = 6.28
    post_ms = 0.08
    det_pub_ms = 0.33
    e2e_det_ms = 9.68
    loop_ms = 9.67
    pub_dt_ms = 32.74

CPU and thermal:

    perception_camera_node CPU = about 79.5 percent
    temperature = 58.7 C
    throttled = 0x0

## Comparison with modular ROS image path

Previous modular path:

    camera_capture_node
    -> /camera/image_raw bgr8
    -> perception_pipeline_node
    -> Hailo
    -> /detections

Measured modular performance:

    /camera/image_raw = about 26.4 Hz
    /detections = about 26.9 Hz
    e2e_det_ms = about 13.68 ms
    loop_ms = about 13.38 ms
    camera_capture_node CPU = about 105 percent
    perception_pipeline_node CPU = about 64 percent

Integrated path:

    /detections = 30.0 Hz stable
    e2e_det_ms = about 9.68 ms
    loop_ms = about 9.67 ms
    one integrated node CPU = about 79.5 percent

## Conclusion

The bottleneck was the full-rate Python ROS 2 bgr8 image transport before inference, not the TEVS camera and not Hailo.

The integrated camera plus Hailo node is the preferred real-time architecture for the thesis. The modular /camera/image_raw path should remain a debug and visualisation path only.
