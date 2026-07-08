# Pixhawk 6X Ethernet MAVROS IMU Integration Result

Date: 2026-06-02
Platform: Raspberry Pi 5
Flight controller: Pixhawk 6X
Firmware: ArduPilot / ArduCopter V4.6.3
Connection: Ethernet MAVLink UDP
ROS version: ROS 2 Jazzy
MAVROS target: system 9, component 1

---

## 1. Objective

The objective of this test was to receive IMU data from the Pixhawk 6X flight controller in ROS 2 on the Raspberry Pi through an Ethernet connection.

The required success condition was:

    ros2 topic hz /mavros/imu/data_raw

publishing a stable IMU stream.

---

## 2. Network Setup

The Raspberry Pi and Pixhawk 6X were connected directly through Ethernet.

The active Ubuntu wired profile used for this setup was:

    pixhawk-apm

The MAVLink traffic was received by the Raspberry Pi on UDP port:

    14550

The Pixhawk was detected by MAVROS as:

    system ID: 9
    component ID: 1

This was visible in the MAVROS log:

    link[1000] detected remote address 9.1
    MAVROS UAS via /uas9 started. MY ID 9.191, TARGET ID 9.1

---

## 3. Working MAVROS Launch Command

The working MAVROS launch command was:

    source /opt/ros/jazzy/setup.bash
    export ROS_DOMAIN_ID=42

    ros2 launch mavros apm.launch \
      fcu_url:=udp://:14550@ \
      tgt_system:=9 \
      tgt_component:=1

The target system and component were required because the Pixhawk was not using the default MAVLink target 1.1. It was using 9.1.

Without explicitly setting this, MAVROS could detect packets but did not correctly connect to the flight controller.

---

## 4. MAVROS Connection Evidence

The successful MAVROS connection was confirmed by:

    ros2 topic echo /mavros/state --once

Expected result:

    connected: true
    mode: STABILIZE

The MAVROS terminal also showed:

    CON: Got HEARTBEAT, connected. FCU: ArduPilot
    FCU: ArduCopter V4.6.3
    FCU: Pixhawk6X-bdshot

This confirmed that ROS 2 was connected to the Pixhawk through MAVROS.

---

## 5. IMU Stream Issue

Initially, MAVROS connected successfully, but the IMU topic did not publish data.

The topic existed:

    /mavros/imu/data_raw

but this command did not produce a rate:

    ros2 topic hz /mavros/imu/data_raw

The reason was that ArduPilot was not yet streaming the required MAVLink IMU messages on this Ethernet link.

---

## 6. Required Stream Request

After MAVROS was running, the following service call was required:

    source /opt/ros/jazzy/setup.bash
    export ROS_DOMAIN_ID=42

    ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
      "{stream_id: 0, message_rate: 50, on_off: true}"

This enabled the required MAVLink data stream.

After this request, the MAVROS terminal showed:

    IMU: Raw IMU message used.

This confirmed that MAVROS started receiving RAW_IMU messages from the Pixhawk.

---

## 7. Final IMU Result

The final IMU topic was:

    /mavros/imu/data_raw

The measured ROS 2 topic rate was approximately:

    50 Hz

Example output:

    average rate: 49.993
    average rate: 50.042
    average rate: 49.997
    average rate: 50.016
    average rate: 50.014

This confirms that the Pixhawk 6X IMU data was successfully received in ROS 2 over Ethernet.

---

## 8. Working Helper Scripts

Two helper scripts were created.

### 8.1 Start MAVROS

File:

    tools/pixhawk_mavros/start_pixhawk_mavros.sh

Content:

    #!/usr/bin/env bash
    set -eo pipefail

    source /opt/ros/jazzy/setup.bash

    set -u
    export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

    ros2 launch mavros apm.launch \
      fcu_url:=udp://:14550@ \
      tgt_system:=9 \
      tgt_component:=1

Usage:

    ./start_pixhawk_mavros.sh

This terminal must remain open.

### 8.2 Request MAVLink Streams

File:

    tools/pixhawk_mavros/request_pixhawk_streams.sh

Content:

    #!/usr/bin/env bash
    set -eo pipefail

    source /opt/ros/jazzy/setup.bash

    set -u
    export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

    ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
      "{stream_id: 0, message_rate: 50, on_off: true}"

Usage:

    ./request_pixhawk_streams.sh

This must be run after MAVROS has started.

---

## 9. Reproduction Procedure

Use two terminals.

### Terminal 1

    cd ~/Desktop/Thesis-Code/tools/pixhawk_mavros
    ./start_pixhawk_mavros.sh

Wait until MAVROS reports:

    CON: Got HEARTBEAT, connected. FCU: ArduPilot

### Terminal 2

    cd ~/Desktop/Thesis-Code/tools/pixhawk_mavros
    ./request_pixhawk_streams.sh
    ros2 topic hz /mavros/imu/data_raw

Expected result:

    average rate: approximately 50 Hz

---

## 10. Important Notes

The warning below is unrelated to the IMU-to-ROS 2 integration:

    PreArm: RC not found

It is an ArduPilot pre-arm condition and does not prevent MAVROS from receiving IMU data.

The warning below is also unrelated to the IMU test:

    GP: No GPS fix

The warning below can appear if ros2 topic hz is started before the IMU stream request takes effect:

    topic [/mavros/imu/data_raw] does not appear to be published yet

It is not fatal if the topic later starts publishing.

The stream-rate request may need to be repeated after restarting MAVROS or rebooting the Pixhawk/Pi.

---

## 11. Final Status

The integration is working.

Confirmed:

- Ethernet MAVLink transport works.
- MAVROS connects to ArduPilot.
- Correct MAVLink target is 9.1.
- MAVROS IMU plugin receives RAW_IMU.
- ROS 2 publishes /mavros/imu/data_raw.
- Measured rate is approximately 50 Hz.

This setup is now ready to be integrated into the thesis live stack as the MAVROS/flight-controller telemetry input.
