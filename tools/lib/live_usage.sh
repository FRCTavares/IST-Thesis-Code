#!/usr/bin/env bash

print_resolution_presets() {
    cat <<'EOF'
Available resolution presets:
    vga      640x480
    hd       1280x720
    fhd      1920x1080

Custom format:
    WIDTHxHEIGHT (example: 1024x576)
EOF
}

print_advanced_usage() {
    cat <<'EOF'
Usage: start_live_stack.sh [options]

Starts the live camera + inference + optional tracking/control/dashboard stack.
All ROS runtime logs are forced under ros2_ws/log/runtime for this run.

Options:
    --perception-mode <single-process>
                                                                            Perception path selection. Only single-process is supported.
    -v, --verbose                     Enable verbose startup/status logs (default: warnings/errors only)
    --tracker <sort|ocsort|bytetrack|deepsort>  Tracker backend (default: ocsort)
    --tracker-profile-off               Disable tracker profiling instrumentation
    --tracker-gc-probe-off              Disable tracker GC probe instrumentation (lower overhead)
    --tracker-gc-probe-on               Enable tracker GC probe instrumentation
    --tracker-profile-log-every <N>     Log tracker profile every N frames (default: 30)
    --tracker-profile-serialize-every <N>
                                                                            Serialize sample every N frames (default: 0 disabled)
    --tracker-iou-threshold <F>         SORT/OCSORT IoU threshold (default: 0.18)
    --tracker-max-age <N>               SORT/OCSORT max track age (default: 4)
    --tracker-min-hits <N>              SORT/OCSORT min hits before confirm (default: 3)
    --tracker-centre-gate <F>           SORT/OCSORT centre gating pixels (default: 200)
    --tracks-off                        Disable /tracks publishing from tracker
    --tracks-require-subscribers        Publish /tracks only when subscribers are present (default)
    --tracks-ignore-subscribers         Publish /tracks regardless of subscriber count
    --tracker-timing-off                Disable /timing_tracker publishing (default)
    --tracker-timing-on                 Enable /timing_tracker publishing
    --timing-off                        Disable /timing publishing from inference client
    --resolution <preset|WIDTHxHEIGHT>  Quick camera capture resolution selector
    --list-resolutions                  Print resolution presets and exit
    --camera-width <N>                  Camera capture width (default: 1280)
    --camera-height <N>                 Camera capture height (default: 720)
    --camera-publish-width <N>          /camera/image_raw width (default: camera-width)
    --camera-publish-height <N>         /camera/image_raw height (default: camera-height)
    --camera-publish-resize-mode <resize|letterbox>
                                                                            /camera/image_raw reshape mode (default: letterbox)
    --camera-publish-encoding <bgr8|rgb8>
                                                                            /camera/image_raw encoding (default: bgr8)
    --camera-fps <N>                    Camera publish fps (default: 30)
    --dashboard-fps <N>                 Dashboard image publish fps (default: 30)
    --camera-no-flip                    Disable camera frame flip
    --camera-rate-controls-off          Disable sensor FPS/exposure rate control writes
    --camera-rate-controls-on           Enable sensor FPS/exposure rate control writes
    --camera-trigger-control-off        Disable sensor trigger_mode control write (default)
    --camera-trigger-control-on         Enable sensor trigger_mode control write
    --camera-preflight-stream-probe-off Disable active preflight stream probe (default)
    --camera-preflight-stream-probe-on  Enable active preflight stream probe
    --camera-sensor-max-fps <N>         Sensor max_fps control (default: 30)
    --camera-ae-upper <N>               Sensor ae_exposure_upper control (default: 8333)
    --camera-ae-max <N>                 Sensor ae_exposure_max control (default: 33333)
    --camera-exposure-mode <0|1|2>      Sensor exposure mode (0=manual, 1=auto, 2=agc; default: 1)
    --camera-manual-exposure <N>        Sensor manual exposure when mode=0 (default: 8333)
    --infer-queue-size <N>              Inference queue size (legacy client + single-process ingress, default: 1)
    --infer-workers <N>                 Legacy client workers / single-process preprocess workers (default: 2)
    --infer-timeout-ms <N>              Inference request timeout ms (default: 300)
    --infer-retries <N>                 Inference retries after timeout/error (default: 0)
    --infer-print-every <N>             Inference periodic stats interval (default: 240)
    --infer-timeout-log-every <N>       Inference timeout log interval (default: 20)
    --perception-image-qos-depth <N>    Perception image subscription depth (single-process default: 2)
    --perception-hailo-queue-buffers <N>
                                                                            Hailo Gst queue max-size-buffers (single-process default: 6)
    --perception-inference-backend <name>
                                                                            Inference backend (single-process default: hailo_direct)
    --perception-async-max-inflight <N>  Experimental request for in-flight calls (single-process owner path enforces 1)
    --perception-hailo-videoconvert-off  Disable pre-hailonet videoconvert stage (single-process)
    --perception-hailo-videoconvert-on   Enable pre-hailonet videoconvert stage (single-process default)
    --perception-gc-off                 Disable Python cyclic GC in perception node
    --perception-gc-on                  Enable Python cyclic GC in perception node (default)
    --perception-no-stub-fallback       Fail fast if Hailo backend initialization fails (default)
    --perception-allow-stub-fallback    Allow stub fallback when Hailo backend initialization fails
    --target-memory <off|hsv|mars|both>
                                          Select TIM mode, default: hsv
    --target-memory-appearance         Enable TIM-MARS appearance extraction
    --target-memory-appearance-image-topic <topic>
                                          Image topic for TIM appearance, default: /camera/dashboard
    --target-memory-appearance-min-bbox-height <px>
                                          Minimum bbox height for appearance crops, default: 30.0
    --target-memory-appearance-max-image-age-ms <ms>
                                          Maximum latest-image age for HSV appearance features, default: 250.0
    --target-memory-mars-image-topic <topic>
                                          Image topic for TIM-MARS, default: /camera/dashboard
    --target-memory-mars-model-path <path>
                                          MARS-small128 .pb path
    --target-memory-mars-batch-size <N>
                                          TIM-MARS ReID batch size, default: 32
    --target-memory-mars-appearance-weight <F>
                                          TIM-MARS appearance weight, default: 0.12
    --target-memory-mars-min-similarity <F>
                                          TIM-MARS minimum appearance similarity, default: 0.35
    --no-dashboard                      Disable dashboard bridge
    --no-tracker                        Do not start tracker node
    --no-target                         Deprecated alias; target selection is now handled by dashboard bridge API
    --no-control                        Do not start control_ref_node
    --control-mavros                    Enable MAVROS mirroring in control_ref_node
    --control-stale-timeout-s <N>       Control stale target timeout seconds (default: 0.80)
    --no-web-video                      Do not start web_video_server
    --record-video                      Record dashboard video + perception/tracking/target/timing/control topics
    --no-record-video                   Disable video bag recording
    --record-dataset                    Record raw camera imagery + perception/TIM telemetry for offline replay
    --no-record-dataset                 Disable dataset bag recording
    --bag-tag <NAME>                    Add a safe tag to the bag folder name
    --bag-out-root <PATH>               Override bag output root, default: $THESIS_ROOT/artifacts/bags/live_camera
    --record-mavros                     Add lightweight MAVROS state/control topics to video bag
    --no-record-mavros                  Do not add MAVROS topics to video bag
    --rosbag                            Deprecated alias for --record-video
    Runtime prompt commands:
    status          Print tracked process IDs
    ids             Print currently visible track IDs from /tracks
    target <id>     Select a track ID as the active target through /api/target
    clear-target    Clear the selected target
    clear           Clear terminal
    stop            Stop the live stack
    -h, --help                          Show this help message
EOF
}

print_usage() {
    cat <<'EOF'
Usage: start_live_stack.sh [options]

Day-to-day options:
    --profile <daily|safe-camera|performance>
                                      Startup preset (default: daily)
    --perception-mode <single-process>
                                      Perception path selection. Only single-process is supported.
    --resolution <preset|WIDTHxHEIGHT>
                                      Quick camera capture resolution selector
    --list-resolutions                 Print available resolution presets and exit
    --camera-width <N>                Camera capture width (default: profile value)
    --camera-height <N>               Camera capture height (default: profile value)
    --camera-rate-controls-off        Disable sensor FPS/exposure control writes
    --camera-rate-controls-on         Enable sensor FPS/exposure control writes (less robust)
    --camera-trigger-control-on       Enable sensor trigger_mode control write (less robust)
    --camera-preflight-stream-probe-on
                                      Actively stream-test /dev/video0 before ROS startup
    --perception-inference-backend <name>
                                      Perception backend (default: hailo_direct)
    --no-tracker                      Do not start tracker node
    --target-memory <off|hsv|mars|both>
                                      Select TIM mode, default: hsv
    --target-memory-appearance        Enable TIM-MARS appearance extraction
    --no-target                       Deprecated alias; target selection is now handled by dashboard bridge API
    --no-control                      Do not start control_ref_node
    --no-dashboard                    Disable dashboard bridge
    --no-web-video                    Do not start web_video_server
    --record-video                    Record dashboard video + perception/tracking/target/timing/control topics
    --record-dataset                  Record raw camera imagery + perception/TIM telemetry for offline replay
    --no-record-dataset               Disable dataset bag recording
    --bag-tag <NAME>                  Add a safe tag to the bag folder name
    --record-mavros                   Add lightweight MAVROS state/control topics
    --rosbag                          Deprecated alias for --record-video
    Runtime prompt commands:
    status          Print tracked process IDs
    ids             Print currently visible track IDs from /tracks
    target <id>     Select a track ID as the active target through /api/target
    clear-target    Clear the selected target
    clear           Clear terminal
    stop            Stop the live stack
    -v, --verbose                     Enable verbose startup/status logs
    -h, --help                        Show this concise help
    --help-advanced                   Show full advanced argument list

Notes:
    - Script preflights the media graph and avoids active V4L2 stream probing by default.
    - Use --camera-preflight-stream-probe-on for a stronger but more invasive stream probe.
    - Available resolution presets:
      vga=640x480, hd=1280x720, fhd=1920x1080
EOF
}
