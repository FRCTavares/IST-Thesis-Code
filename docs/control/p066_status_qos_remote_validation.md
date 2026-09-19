# Controller authority-status QoS remote validation

Date: 19 September 2026
Host: `fcstpi`
Starting repository revision: `2948c95da2a4d46c4794ddaeea473adc118b2cd1`
ROS distribution: ROS 2 Jazzy

## Scope

This validation addresses only ROS 2 transport and controller gating between
`target_memory_mars_node` and `control_ref_node`. No Pixhawk or MAVROS process
was present, aircraft-facing publication remained disabled, and the result is
not physical closed-loop evidence.

## Contract decision

`/target_memory_mars` remains best-effort and volatile. It is a high-rate frame
stream, and the controller independently rejects stale, non-monotonic or
causally mismatched target/status pairs.

`/target_memory_mars/status` is reliable and volatile at both endpoints. Status
contains authority revocation, selection generation, process-session identity
and state transitions. Losing such a sample can delay fail-closed revocation,
whereas its small message size and bounded depth do not justify accepting that
risk. Volatile durability avoids replaying an old authority state to a newly
started controller. Reliable transport does not replace the controller status
freshness gate.

Both nodes obtain these profiles from
`thesis_bringup/authority_qos.py`, preventing the publisher and subscriber
contracts from drifting independently.

## Validation commands

Package build and focused regression suite:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export COLCON_LOG_PATH="$PWD/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$PWD/ros2_ws/log/hailort"
tools/thesis_build.sh --packages-select thesis_bringup
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 -m pytest -q \
  ros2_ws/src/thesis_bringup/test/test_authority_qos_contract.py \
  ros2_ws/src/thesis_bringup/test/test_state_aware_control_policy.py \
  ros2_ws/src/thesis_bringup/test/test_control_ref_safety.py \
  ros2_ws/src/thesis_bringup/test/test_control_ref_state_authority.py \
  ros2_ws/src/thesis_bringup/test/test_control_ref_diagnostics.py \
  ros2_ws/src/thesis_bringup/test/test_live_target_authority.py \
  ros2_ws/src/thesis_bringup/test/test_tim_mars_ros_messages.py \
  ros2_ws/src/thesis_bringup/test/test_target_memory_mars_node_static.py \
  ros2_ws/src/thesis_bringup/test/test_coordinate_time_contract.py
```

The exact actual-node integration wrapper and message driver used on the Pi are
retained under:

```text
ros2_ws/log/p066_status_qos_remote_20260919_v2/commands.sh
ros2_ws/log/p066_status_qos_remote_20260919_v2/driver.py
```

The wrapper used `ROS_DOMAIN_ID=77`, launched the installed TIM-MARS node with
appearance disabled, launched the installed controller with MAVROS and yaw
recovery disabled, recorded `ros2 topic info -v`, and drove fresh selected and
empty track observations through the real ROS interfaces. Disabling appearance
isolated the authority transport; no TIM-MARS scoring or frozen configuration
was changed.

## Results

- package build: passed;
- focused suite: 109 tests passed;
- status publisher: RELIABLE, VOLATILE;
- status subscriber: RELIABLE, VOLATILE;
- target publisher and subscriber: BEST_EFFORT, VOLATILE;
- 15 status samples and 88 controller diagnostic samples observed;
- status states observed: `NO_TARGET`, `LOCKED`, `UNCERTAIN`, `LOST`;
- fresh matched `LOCKED` authority produced `NORMAL_FOLLOW` and a nonzero
  controller reference;
- `LOST` produced zero translation and yaw with recovery disabled;
- expiry of status freshness preserved zero output.

Machine-readable summary and endpoint inventories are retained in the same log
directory as `summary.json`, `status_topic_info.txt`,
`target_topic_info.txt` and `diagnostics_topic_info.txt`.

## Retained failed attempt

The first attempt is retained under
`ros2_ws/log/p066_status_qos_remote_20260919/`. Its one-shot `ros2 topic pub`
process introduced about 1.4 seconds of source age before the track reached the
controller. The controller received the TIM-MARS status but rejected the target
as stale and commanded zero. The second attempt replaced only that CLI input
with an in-process publisher that stamped each observation immediately.

## Limitation

This proves compatible discovery and non-actuating message exchange on the Pi.
It does not validate MAVROS, FCU response, controller-process loss, props-off
signs, pilot takeover, hover, bounded yaw recovery or flight behaviour. Those
remain under Issue #50.
