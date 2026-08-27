# Issue #64 — 1920x1080 Capture

## 1. Preflight

    cd /home/francisco/Desktop/Thesis-Code || return 1

    export GIT_PAGER=cat
    export PAGER=cat
    export COLCON_LOG_PATH="$PWD/ros2_ws/log/colcon"
    export HAILORT_LOGGER_PATH="$PWD/ros2_ws/log/hailort"

    git status --branch --short
    git rev-parse HEAD
    df -h /
    ls -l /dev/video0 /dev/hailo0
    ls -l /dev/media* 2>/dev/null

Prefer at least 100 GiB free.

## 2. Check 1920x1080 before recording

Start:

    ./tools/start_live_stack.sh --res fhd --camera-publish-image-raw --camera-preflight-stream-probe-on --no-control --no-tracker --no-dashboard --no-web-video

If the launcher falls back to 640x480, type `stop` and fix the camera before
recording.

In a second terminal:

    cd /home/francisco/Desktop/Thesis-Code || return 1
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=42

    timeout 8s ros2 topic echo /camera/image_raw --once
    timeout 12s ros2 topic hz /camera/image_raw

Confirm:

- width = 1920
- height = 1080
- timestamps are positive

Check detector size:

    ros2 param dump /perception_camera_node 2>/dev/null | rg -n 'width:|height:|img_w:|img_h:|publish_image_raw'

Required:

- camera = 1920x1080
- detector = 640x640

Then type `stop` in the first terminal.

## 3. Controlled ground master

Primary Issue #64 recording:

    cd /home/francisco/Desktop/Thesis-Code || return 1

    export COLCON_LOG_PATH="$PWD/ros2_ws/log/colcon"
    export HAILORT_LOGGER_PATH="$PWD/ros2_ws/log/hailort"
    export RECORDING_MIN_FREE_GIB=100

    ./tools/start_live_stack.sh --res fhd --record-dataset --no-control --tag p064_highres_ground_master

Record about 60-90 seconds.

Include:

- target + distractor separated;
- crossing;
- partial occlusion;
- target moving farther away;
- target exit;
- 5-8 s absence if practical;
- target re-entry.

Prefer 2-3 short attempts.

Finish with:

    stop

## 4. Verify ground recording

    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    LATEST_DATASET_BAG="$(ls -1dt bags/datasets/* | head -1)"

    echo "$LATEST_DATASET_BAG"
    du -sh "$LATEST_DATASET_BAG"
    ros2 bag info "$LATEST_DATASET_BAG"

Required topics:

- `/camera/image_raw`
- `/detections`
- `/tracks`
- `/target_memory_mars`
- `/target_memory_mars/status`
- timing topics

Verify actual raw resolution:

    thesis_env/bin/python - "$LATEST_DATASET_BAG" <<'PYBAG'
    import sys
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    bag = sys.argv[1]

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=bag, storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )

    types = {x.name: x.type for x in reader.get_all_topics_and_types()}
    msg_type = get_message(types["/camera/image_raw"])

    count = 0
    dims = set()
    positive = 0

    while reader.has_next():
        topic, payload, bag_ns = reader.read_next()
        if topic != "/camera/image_raw":
            continue

        msg = deserialize_message(payload, msg_type)
        count += 1
        dims.add((int(msg.width), int(msg.height)))

        stamp = (
            int(msg.header.stamp.sec) * 1_000_000_000
            + int(msg.header.stamp.nanosec)
        )
        if stamp > 0:
            positive += 1

    print("frames:", count)
    print("dimensions:", sorted(dims))
    print("positive_header_stamps:", positive)

    if dims != {(1920, 1080)}:
        raise SystemExit("FAIL: raw bag is not pure 1920x1080")

    print("PASS: genuine 1920x1080 master")
    PYBAG

If this fails, re-record before leaving the field.

## 5. UAV / flight master

For the UAV-motion run:

    cd /home/francisco/Desktop/Thesis-Code || return 1

    export COLCON_LOG_PATH="$PWD/ros2_ws/log/colcon"
    export HAILORT_LOGGER_PATH="$PWD/ros2_ws/log/hailort"
    export RAW_RECORDING_MIN_FREE_GIB=100

    ./tools/start_live_stack.sh --res fhd --field-record --record-raw --tag p064_highres_uav_master

Do not add `--control-mavros`.

Follow:

    docs/flight/P023_FLIGHT_READINESS.md

Finish with:

    stop

## 6. Verify flight bags

    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    LATEST_LIVE_BAG="$(ls -1dt bags/live_camera/* | rg -v '__image_raw$' | head -1)"
    LATEST_RAW_BAG="$(ls -1dt bags/live_camera/*__image_raw | head -1)"
    LATEST_MAVROS_BAG="$(ls -1dt bags/mavros/* | head -1)"

    echo "LIVE: $LATEST_LIVE_BAG"
    ros2 bag info "$LATEST_LIVE_BAG"

    echo "RAW: $LATEST_RAW_BAG"
    ros2 bag info "$LATEST_RAW_BAG"

    echo "MAVROS: $LATEST_MAVROS_BAG"
    ros2 bag info "$LATEST_MAVROS_BAG"

The raw bag must contain genuine 1920x1080 `/camera/image_raw`.

## Final rule

Do not leave the field without at least one verified 1920x1080 master.

Keep all recordings until reviewed and never power off before `stop` finishes.
