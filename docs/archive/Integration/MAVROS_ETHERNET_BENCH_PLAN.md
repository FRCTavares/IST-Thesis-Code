# MAVROS Ethernet Bench Plan

Date: 2026-05-06

Goal: verify Pixhawk Ethernet/MAVLink connectivity and record one passive bench bag with flight-state telemetry plus TIM-V0 topics.

---

## 1. Information needed from Afonso

- Pixhawk Ethernet IP:
- Companion computer IP/subnet:
- MAVLink protocol: UDP or TCP
- MAVLink local port:
- MAVLink remote port:
- Whether Pixhawk pushes MAVLink to the companion or waits for connection:
- ArduPilot NET/SERIAL configuration:
- Expected stream rate:
- Safety notes:

---

## 2. Network checks

Commands to run once the Pixhawk is connected:

    ip addr
    ip route
    ping <pixhawk_ip>

Expected:

- Pi has an IP on the same subnet as the Pixhawk.
- Pixhawk responds to ping, if ICMP is enabled.
- No route conflict prevents reaching the Pixhawk.

---

## 3. MAVROS startup candidate commands

UDP candidate:

    ros2 launch mavros apm.launch fcu_url:=udp://:<local_port>@<pixhawk_ip>:<remote_port>

TCP candidate:

    ros2 launch mavros apm.launch fcu_url:=tcp://<pixhawk_ip>:<remote_port>

Exact command depends on Afonso's answer.

---

## 4. Topics to verify

Minimum topics:

- /mavros/state
- /mavros/imu/data
- /mavros/local_position/pose
- /mavros/local_position/velocity_local

Optional topics:

- /mavros/global_position/global
- /mavros/global_position/local
- /mavros/battery
- /mavros/extended_state

Verification commands:

    ros2 topic list | rg '/mavros'
    ros2 topic echo /mavros/state --once
    ros2 topic hz /mavros/imu/data

---

## 5. Passive bench bag

Record perception/TIM plus MAVROS context:

    ros2 bag record -s mcap \
      /target_memory \
      /target_memory/status \
      /tracks \
      /timing \
      /timing_tracker \
      /mavros/state \
      /mavros/imu/data \
      /mavros/local_position/pose \
      /mavros/local_position/velocity_local

No control commands should be sent during the first bench test.

---

## 6. Success criteria

- MAVROS starts without connection errors.
- /mavros/state publishes.
- /mavros/imu/data publishes at a stable rate.
- A short bench bag records both MAVROS and TIM-V0 topics.
- No arming, mode changes, or setpoint control are attempted.

---

## 7. Notes to fill after Afonso replies

Pixhawk Ethernet IP:

Companion computer IP/subnet:

Final MAVROS command:

Bench bag name:

Observed MAVROS topics:

Problems found:

