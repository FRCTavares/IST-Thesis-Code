# Offline field-day command sheet

Last reviewed: 2026-09-14

This is the **only current day-of-flight operator sheet**. It works with no
internet, Tailscale, or institutional ISR connection. Detailed rationale is in
`docs/flight/field_day_runbook.md`; retained-artifact rules are in
`docs/flight/retained_evidence_package.md`.

Never arm, change flight mode, or start physical control without the qualified
pilot and completed gates. Never add `--record-raw` to a full-stack field
command. `--field-record` already enables the supported structured
non-image MCAP, separate 640x480 MJPEG visual, and passive MAVROS telemetry.
`--control-mavros` is the separate aircraft-command mirror.
`--record-structured-visual` is the non-MAVROS development equivalent; do not substitute it for `--field-record` when passive field telemetry is required.
`--field-record` also implies `--record-mavros`; no extra recording flag is needed.

## 1. Connect the Mac to the field GCS

Connect the Mac to Wi-Fi **`ISR Aero.Next GCS`**, then use:

```bash
ssh francisco@192.168.8.174
```

Do not use either historical `100.x` Tailscale address in field mode. If
the Pi is initially on management-only **`ISR Aero.Next GCS Rescue`**, the
same SSH address applies. Rescue grants local SSH only, never Pixhawk, MAVROS,
controller, or flight authority.

In every new Pi shell:

```bash
cd /home/francisco/Desktop/Thesis-Code || exit 1
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
set +u
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
git --no-pager log -1 --oneline
git status --short
```

Do not pull, install, or rebuild at the field.

## 2. Enter and check field network mode

Power/connect Pixhawk Ethernet first. From the Pi shell:

```bash
sudo tools/host/set_pi_network_mode.sh pixhawk
```

The Wi-Fi profile switch may briefly drop SSH. Reconnect with
`ssh francisco@192.168.8.174`, enter the repository again, then run:

```bash
sudo tools/host/set_pi_network_mode.sh status
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show eth0
ip -brief address show wlan0
ip -brief address show eth0
ip route show default
ip route show default dev eth0
ping -c 3 -W 1 192.168.144.14
systemctl is-active tailscaled
```

Require:

- `configured_mode=pixhawk`;
- `wlan0` uses `ISR Aero.Next GCS`, expected Pi address
  `192.168.8.174/24`, and owns the default route;
- `eth0` uses `pixhawk-apm`, expected Pi address
  `192.168.144.183/24`, and reaches Pixhawk `192.168.144.14`;
- `ip route show default dev eth0` prints nothing;
- `tailscaled` prints `inactive`.

If field association fails, the helper fails closed. Wait for Rescue, reconnect
to `192.168.8.174`, and inspect:

```bash
sudo tools/host/set_pi_network_mode.sh status
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
nmcli -f NAME,AUTOCONNECT connection show "ISR Aero.Next GCS"
nmcli -f NAME,AUTOCONNECT connection show "ISR Aero.Next GCS Rescue"
```

Do not launch MAVROS or fly on Rescue. Check Ethernet power/cable, then retry
the explicit `pixhawk` transition. The optional AERONEXT fallback is not
provisioned; do not guess a profile or address.

## 3. Hardware, storage, freeze, and stale-process sanity

```bash
date -Iseconds
df -h "$PWD" "$PWD/bags"
ls -l /dev/video0 /dev/media0 /dev/hailo0
v4l2-ctl -d /dev/video0 --list-formats-ext | sed -n '1,80p'
hailortcli scan
pgrep -af '[s]tart_live_stack.sh|[r]os2 bag record|[r]osbag2_recorder|[m]avros_node|[c]ontrol_ref_node|[f]fmpeg.*visual_'   || echo "no stale live-stack/recorder process"
python3 tools/analysis/validate_tim_evaluation_split.py   docs/data/splits/tim_mars_split_v4.json --verify-hashes
```

Require all three devices, a Hailo device, enough free space, no stale process,
and `final_ready=0/3`.

## 4. Passive MAVROS structured-plus-visual ground capacity gate

This is tomorrow's first retained test. Keep the aircraft disarmed and still.
Use a visible intended person and distractor. Controller and MAVROS command
mirroring are both off.

Terminal A:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=capacity_ground_r1
echo "RUN_ID=$RUN_ID"
./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"
```

`--field-record` performs managed FCU-connect, stream-rate, BODY_NED, and
raw-IMU readiness checks. Do not start a second MAVROS. In Terminal B, SSH over
GCS, enter the repository as in section 1, set the exact RUN_ID printed by
Terminal A, and check passive telemetry:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
timeout 12s ros2 topic echo /mavros/state --once
timeout 12s ros2 topic echo /mavros/imu/data_raw --once
ros2 topic info /mavros/setpoint_velocity/cmd_vel -v
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario passive_mavros_capacity
```

Require `connected: true`, `armed: false`, raw IMU data, and zero
publishers on the MAVROS velocity-command topic. At the `live-stack>`
prompt in Terminal A, use `ids` and `target <id>`. Then record
the physical identity in Terminal B:

```bash
read -r -p "Visible person description: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Run for 60–90 seconds. Before stopping:

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID"   --end-reason ground_capacity_complete
```

Type `stop` once at Terminal A's `live-stack>` prompt. Section
10 must pass before any aircraft trial.

## 5. Manual dynamic-UAV TIM-MARS trial

Only the qualified pilot moves the aircraft. Tracker and TIM-MARS run;
`control_ref_node` is off and there is no thesis command path.

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=dynamic_uav_tim_manual_r1
echo "RUN_ID=$RUN_ID"
./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"
```

In Terminal B, use the exact RUN_ID and supported events:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario dynamic_uav_tim_manual
read -r -p "Visible person description: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Follow `docs/flight/P050_DYNAMIC_UAV_TIM_TRIAL.md`. Record
`trial_end` before typing `stop`. Do not add
`--control-mavros` or `--record-raw`.

## 6. Controller ground gates

First verify controller computation with no aircraft command mirror. Keep the
aircraft disarmed and still:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=controller_compute_ground_r1
echo "RUN_ID=$RUN_ID"
./tools/start_live_stack.sh --field-record --tag "$TAG"
```

In Terminal B, record the compute-only trial before selecting the target:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario controller_compute_ground
read -r -p "Visible person description: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID"   --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

The absence of `--control-mavros` is the safety boundary. After target
selection, observe `/control_ref/cmd_vel`: centred gives
`vx=0`, `yaw_z=0`; left gives `yaw_z<0`, right gives
`yaw_z>0`; smaller/farther gives `vx>0`, larger/nearer gives
`vx<0`; stale/lost gives zeros.

```bash
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /control_ref/diagnostics
```

The real Pixhawk command-path gate is separate. Run it only with the qualified
pilot, propellers removed or the vehicle safely restrained as agreed, RC/manual
takeover confirmed, pre-arm state understood, and direction/sign gate passed:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=controller_command_path_ground_r1
echo "RUN_ID=$RUN_ID"
./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"
```

In Terminal B, record this distinct physical gate:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario controller_command_path_ground
```

The launcher does not arm or change mode. Do not arm during this check. Abort on
a wrong sign, nonzero stale/lost command, unexpected mode/state, or failed
pilot takeover. These physical gates remain pending until performed.

## 7. Closed-loop baseline flight

Use this only after every network, capacity, controller-sign, restrained
command-path, RC/manual takeover, and pilot go/no-go gate above passes:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=flight1_baseline
echo "RUN_ID=$RUN_ID"
./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"
```

In Terminal B:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario following
read -r -p "Visible person description: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

## 8. Other non-held-out physical trials

After the same gates, use a unique run and tag.

Loss/reacquisition, Terminal A:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=flight2_loss_reacquisition
./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"
```

Loss/reacquisition, Terminal B:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario loss_reacquisition
read -r -p "Visible person description: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID"   --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Crossing/distractor, Terminal A:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=flight3_distractor_crossing
./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"
```

Crossing/distractor, Terminal B:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario distractor_crossing
read -r -p "Visible person description: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID"   --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

There are no `loss` or `reacquired` event names. Planned
transitions come from bag/TIM state. Record only observed issues:

```bash
read -r -p "Observed issue: " OBSERVATION
python3 tools/live/operator_event.py unexpected_behavior --run-id "$RUN_ID"   --description "$OBSERVATION" --severity concern
```

Optional bounded-yaw recovery remains experimental. Use only if the existing
#50/#74 promotion decision and all physical gates permit it:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=flight4_yaw_recovery_candidate
./tools/start_live_stack.sh --field-record --control-mavros   --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

Its Terminal B start event must match:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition candidate --scenario yaw_recovery --recovery-enabled
```

For any trial, these are the supported safety/end events:

```bash
python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID"   --trigger pilot_rc
read -r -p "Safety abort reason: " ABORT_REASON
python3 tools/live/operator_event.py abort --run-id "$RUN_ID"   --abort-class safety --reason "$ABORT_REASON"
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID"   --end-reason nominal_complete
```

## 9. H01/H02/H03: separate frozen source-only capture

These are prospective held-out captures. Do not rehearse, open, replay, inspect,
analyse, delete, or modify them. Do not use a full-stack field command. Execute
only the frozen helper when approved held-out capture is actually due:

```bash
tools/experiments/record_p027_heldout_sequence.sh h01
tools/experiments/record_p027_heldout_sequence.sh h02
tools/experiments/record_p027_heldout_sequence.sh h03
```

The helper enforces `/camera/image_raw` plus `/detections`,
640x480 source, YOLOv8s at 640x640 inference, and
tracker/TIM-MARS/controller/dashboard/MAVROS off. See
`docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md`. This audit does not
authorize executing those commands.

## 10. Graceful stop and evidence acceptance

Record `trial_end` before stopping. At `live-stack>`, type
`stop` once (or Ctrl-C once). Let the launcher finalize MJPEG, nodes,
MCAP, logs, transport status, and evidence status. Do not kill recorders.

After the launcher returns, RUN_ID and TAG remain set:

```bash
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"; export BAG
python3 tools/live/verify_evidence_package.py   --bag-dir "$BAG" --run-id "$RUN_ID"   --field-record --expect-visual --expect-operator-events
```

For a controller command-mirroring trial, add `--control-trial`. The
verifier can exit 1 solely because DataFlash and annotation are still pending.
This exact summary distinguishes pending work from runtime failure and prints
every retained topic rate:

```bash
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
```

**Do not accept the flight as retained scientific evidence** if this command
fails: transport must be `observed_zero` with count 0, structured bag
must pass, visual evidence must pass/finalize gracefully, and required
logs/events must be present. There is no acceptable nonzero-loss threshold.
Keep failed evidence; never hide a readable-but-lossy MCAP.

Before disconnecting Pixhawk, retrieve the exact native DataFlash `.bin`,
then archive the explicitly selected file:

```bash
read -r -p "Exact DataFlash .bin path: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py   --bag-dir "$BAG" --run-id "$RUN_ID"   --control-trial --field-record --expect-visual --expect-operator-events
```

## 11. Return to development/unattended mode

After flights stop, recorders finalize, and Pixhawk is disconnected:

```bash
sudo tools/host/set_pi_network_mode.sh unattended
sudo tools/host/set_pi_network_mode.sh status
```

This re-enables Tailscale for later unattended recovery, but field sections
1–10 require only GCS Wi-Fi and direct Pixhawk Ethernet.
