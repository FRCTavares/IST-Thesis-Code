# Reproducing Pixhawk 6X Ethernet MAVROS Connectivity on Raspberry Pi 5

## Purpose

This document explains how to connect a Raspberry Pi 5 to a Pixhawk 6X over
Ethernet and expose Pixhawk telemetry as ROS 2 topics through MAVROS.

The goal is to reproduce the working setup where the Raspberry Pi receives
Pixhawk IMU data on:

    /mavros/imu/data_raw

at approximately:

    50 Hz

This document is standalone: the commands below are enough to reproduce the
connection without using any project-specific helper scripts.

## Tested setup

- Companion computer: Raspberry Pi 5
- Flight controller: Pixhawk 6X
- Firmware: ArduPilot / ArduCopter V4.6.3
- Link type: direct Ethernet
- Middleware: ROS 2 Jazzy
- MAVROS launch file: `mavros apm.launch`
- ROS domain used in my tests: `ROS_DOMAIN_ID=42`
- MAVLink UDP port: `14550`
- MAVLink target system/component detected from Pixhawk:
  - system ID: `9`
  - component ID: `1`

The non-default target IDs were important. In this setup the Pixhawk appeared as
MAVLink target `9.1`, not the usual/default `1.1`.

## 1. Physical connection

Connect the Raspberry Pi 5 and Pixhawk 6X directly with an Ethernet cable.

The tested Ethernet subnet was:

    192.168.144.x

In my captured packets, the relevant traffic was between:

    Pixhawk-side address:       192.168.144.183:14550
    Raspberry Pi-side address:  192.168.144.14:<ephemeral UDP port>

Exact IPs may differ depending on the Pixhawk/network configuration, but the
Raspberry Pi must be on the same Ethernet subnet as the Pixhawk.

## 2. Configure or activate the Ethernet profile on the Raspberry Pi

In my setup, the Ubuntu NetworkManager connection profile was named:

    pixhawk-apm

Activate it with:

    sudo nmcli connection up pixhawk-apm

Check the active IP address:

    ip -brief addr
    ip route

Expected: the Ethernet interface should have an address in the Pixhawk Ethernet
subnet, for example `192.168.144.x`.

If the `pixhawk-apm` profile does not exist on another machine, create or adapt
a wired NetworkManager profile so that the Raspberry Pi Ethernet interface gets
an address on the same subnet as the Pixhawk.

## 3. Check that MAVLink packets are reaching the Raspberry Pi

Before starting MAVROS, confirm that UDP traffic on port `14550` is visible.

Run:

    sudo tcpdump -ni any udp port 14550

Expected: UDP packets between the Pixhawk and the Raspberry Pi.

In my working setup, packets looked like traffic between:

    192.168.144.183.14550
    192.168.144.14.<ephemeral-port>

If there are no packets, fix the Ethernet/IP side first. MAVROS will not connect
until the Raspberry Pi can receive MAVLink traffic.

## 4. Source ROS 2 and set the ROS domain

Run:

    source /opt/ros/jazzy/setup.bash
    export ROS_DOMAIN_ID=42

Use the same `ROS_DOMAIN_ID` in all terminals where you run MAVROS or inspect
ROS topics.

## 5. Start MAVROS

Start MAVROS with the ArduPilot launch file and the Ethernet UDP FCU URL:

    ros2 launch mavros apm.launch \
      fcu_url:=udp://:14550@ \
      tgt_system:=9 \
      tgt_component:=1

Explanation of the important arguments:

- `fcu_url:=udp://:14550@`
  - MAVROS listens for MAVLink over UDP on local port `14550`.
- `tgt_system:=9`
  - The Pixhawk MAVLink system ID used in my setup.
- `tgt_component:=1`
  - The Pixhawk MAVLink component ID used in my setup.

Why this mattered: MAVROS could see packets, but it did not correctly connect
until the target system/component were explicitly set to `9.1`.

Keep this MAVROS terminal open.

## 6. Confirm MAVROS connection

In a second terminal:

    source /opt/ros/jazzy/setup.bash
    export ROS_DOMAIN_ID=42

Check MAVROS state:

    ros2 topic echo /mavros/state --once

Expected output should include:

    connected: true
    armed: false
    mode: STABILIZE

The MAVROS terminal should also show messages similar to:

    CON: Got HEARTBEAT, connected. FCU: ArduPilot
    FCU: ArduCopter V4.6.3
    FCU: Pixhawk6X-bdshot

At this point MAVROS is connected to the Pixhawk.

## 7. Request MAVLink streams

In my setup, MAVROS connected successfully before the IMU stream was publishing
at the expected rate. The fix was to explicitly request MAVLink streams through
the MAVROS stream-rate service.

Run this after MAVROS is connected:

    ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
      "{stream_id: 0, message_rate: 50, on_off: true}"

Expected result: the service call succeeds, and the MAVROS terminal may show:

    IMU: Raw IMU message used.

This step is required to make `/mavros/imu/data_raw` publish reliably at about
50 Hz.

## 8. Verify Pixhawk topics in ROS 2

List MAVROS topics:

    ros2 topic list | grep '^/mavros/'

Important topics that should exist include:

    /mavros/state
    /mavros/imu/data_raw
    /mavros/imu/data
    /mavros/imu/mag
    /mavros/local_position/pose
    /mavros/local_position/velocity_local
    /mavros/global_position/global
    /mavros/global_position/rel_alt
    /mavros/rc/in
    /mavros/rc/out

The exact list can be larger depending on MAVROS plugins.

## 9. Verify IMU data

Check one raw IMU message:

    ros2 topic echo /mavros/imu/data_raw --once

Expected: a `sensor_msgs/msg/Imu` message with angular velocity and linear
acceleration fields.

Example fields from my working setup:

    frame_id: base_link
    angular_velocity:
      x: -0.003
      y: -0.003
      z: 0.002
    linear_acceleration:
      x: -0.2941995
      y: -0.3726527
      z: 9.80665

Then check the rate:

    ros2 topic hz /mavros/imu/data_raw

Expected result:

    average rate: approximately 50 Hz

Measured rates from my working test:

    average rate: 49.910
    average rate: 49.989
    average rate: 49.990
    average rate: 49.968
    average rate: 49.995
    average rate: 49.996
    average rate: 49.998
    average rate: 49.999

This confirms that Pixhawk IMU telemetry is reaching ROS 2 on the Raspberry Pi.

## 10. Optional: record MAVROS topics

To record MAVROS telemetry into a ROS 2 bag:

    ros2 bag record --storage mcap -o mavros_pixhawk_test \
      /mavros/state \
      /mavros/extended_state \
      /mavros/imu/data_raw \
      /mavros/imu/data \
      /mavros/imu/mag \
      /mavros/imu/static_pressure \
      /mavros/imu/temperature_imu \
      /mavros/rc/in \
      /mavros/rc/out \
      /mavros/global_position/global \
      /mavros/global_position/rel_alt \
      /mavros/global_position/local \
      /mavros/local_position/pose \
      /mavros/local_position/velocity_local

## Troubleshooting

### No MAVLink packets on tcpdump

Check:

    sudo tcpdump -ni any udp port 14550

If no packets appear:

- Check the Ethernet cable.
- Check the Raspberry Pi Ethernet IP address.
- Check the Pixhawk Ethernet/MAVLink configuration.
- Confirm the Raspberry Pi and Pixhawk are on the same subnet.

### MAVROS sees packets but does not connect

Use the explicit target:

    tgt_system:=9
    tgt_component:=1

In my setup the Pixhawk was target `9.1`, not `1.1`.

### `/mavros/state` does not show `connected: true`

Check:

    ros2 topic echo /mavros/state --once

If `connected` is false:

- Confirm UDP traffic is present on port `14550`.
- Confirm the MAVROS launch command uses `fcu_url:=udp://:14550@`.
- Confirm the target system/component match the Pixhawk.

### `/mavros/imu/data_raw` exists but does not publish

Request streams:

    ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
      "{stream_id: 0, message_rate: 50, on_off: true}"

Then check again:

    ros2 topic hz /mavros/imu/data_raw

### ROS topics are not visible in another terminal

Use the same ROS domain in every terminal:

    export ROS_DOMAIN_ID=42

Also source ROS 2 in each terminal:

    source /opt/ros/jazzy/setup.bash

## Minimal command sequence

Terminal 1:

    sudo nmcli connection up pixhawk-apm
    source /opt/ros/jazzy/setup.bash
    export ROS_DOMAIN_ID=42

    ros2 launch mavros apm.launch \
      fcu_url:=udp://:14550@ \
      tgt_system:=9 \
      tgt_component:=1

Terminal 2:

    source /opt/ros/jazzy/setup.bash
    export ROS_DOMAIN_ID=42

    ros2 topic echo /mavros/state --once

    ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
      "{stream_id: 0, message_rate: 50, on_off: true}"

    ros2 topic echo /mavros/imu/data_raw --once
    ros2 topic hz /mavros/imu/data_raw

Expected final result:

    /mavros/state shows connected: true
    /mavros/imu/data_raw publishes at approximately 50 Hz

## Evidence from my test

The connection was validated on 2026-06-02. The successful state output showed:

    connected: true
    armed: false
    guided: false
    manual_input: true
    mode: STABILIZE
    system_status: 3

The IMU rate was stable around 50 Hz.

The main setup lesson was that the Pixhawk used MAVLink target `9.1`, and the
MAVLink stream-rate request was required after MAVROS connected.
