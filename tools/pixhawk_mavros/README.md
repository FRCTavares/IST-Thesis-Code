# Pixhawk 6X Ethernet MAVROS Helpers

This folder contains the Pixhawk 6X Ethernet MAVROS helper scripts and the
recorded setup notes used during thesis field testing.

The scripts are stored inside the thesis repository so the MAVROS/Pixhawk setup
is reproducible from `~/Desktop/Thesis-Code`.

## Hardware and network assumptions

- Raspberry Pi 5 connected directly to Pixhawk 6X over Ethernet.
- Ubuntu NetworkManager wired profile: `pixhawk-apm`.
- MAVLink UDP traffic received on port `14550`.
- ROS 2 distro: Jazzy.
- ROS domain: `ROS_DOMAIN_ID=42`.
- MAVROS target:
  - system: `9`
  - component: `1`

## Start MAVROS

From the repository root:

    cd ~/Desktop/Thesis-Code || exit 1
    tools/pixhawk_mavros/start_pixhawk_mavros.sh

Expected MAVROS log:

    CON: Got HEARTBEAT, connected. FCU: ArduPilot

## Request MAVLink streams

In a second terminal, after MAVROS has connected:

    cd ~/Desktop/Thesis-Code || exit 1
    tools/pixhawk_mavros/request_pixhawk_streams.sh

This requests MAVLink streams at 50 Hz using `/mavros/set_stream_rate`.

## Validate connection

Useful checks:

    ros2 topic echo /mavros/state --once
    ros2 topic hz /mavros/imu/data_raw
    ros2 topic list | rg '/mavros/(state|imu|local_position|global_position|rc)'

Expected state check:

    connected: true

Expected IMU result:

    /mavros/imu/data_raw publishes at approximately 50 Hz.

## Field-stack integration

`tools/start_live_stack.sh` uses these helpers for field/source MAVROS
recording modes. It also activates the `pixhawk-apm` NetworkManager profile
before starting MAVROS.

Relevant modes:

    ./tools/start_live_stack.sh --field-record
    ./tools/start_live_stack.sh --source-record

## Evidence

The original setup report and captured command outputs are kept here:

- `pixhawk6x_ethernet_mavros_imu_result.md`
- `logs/`
