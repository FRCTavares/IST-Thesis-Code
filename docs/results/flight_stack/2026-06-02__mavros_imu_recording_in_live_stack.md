# MAVROS IMU Recording Integrated into Live Stack

Date: 2026-06-02

## Objective

Integrate Pixhawk 6X MAVROS telemetry into the thesis live recording path so that outdoor drone bags include IMU data.

## Result

The `--record-mavros` option now starts MAVROS automatically, waits for connection, requests ArduPilot MAVLink streams, verifies `/mavros/imu/data_raw`, and then starts video bag recording.

Working command:

    ./tools/start_live_stack.sh \
      --profile daily \
      --record-video \
      --record-mavros \
      --bag-tag mavros_progress_test_02

## MAVROS Startup Evidence

Observed startup sequence:

    [info] [mavros 00s] --record-mavros enabled: starting MAVROS telemetry
    [ok] [mavros 12s] MAVROS connected
    [ok] [mavros 41s] stream-rate service available
    [info] [mavros 41s] requesting MAVROS streams at 50 Hz
    [ok] [mavros 75s] MAVROS raw IMU stream detected
    [ok] [mavros 75s] MAVROS telemetry setup finished

## Bag Evidence

Recorded bag:

    artifacts/bags/live_camera/2026-06-02__11-28-31__video__mavros_progress_test_02

Recorded MAVROS topic counts:

    /mavros/imu/data              Count: 3458
    /mavros/imu/data_raw          Count: 3454
    /mavros/imu/mag               Count: 3454
    /mavros/imu/static_pressure   Count: 3453
    /mavros/state                 Count: 79

Zero-count topics during this test:

    /mavros/imu/temperature_imu
    /mavros/local_position/pose
    /mavros/local_position/velocity_local

These zero-count topics are not failures for the IMU recording objective. They indicate that the topics were included in the recording list but did not publish messages during this test.

## Conclusion

The live stack can now record Pixhawk 6X IMU data through MAVROS when launched with `--record-mavros`.

This is sufficient for outdoor flight bags requiring synchronised camera, perception, target, timing, control, and IMU telemetry.
