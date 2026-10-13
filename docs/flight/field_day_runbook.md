# Field day runbook

Last reviewed: 2026-10-13

Operator sheet for a field day with the TIM-MARS stack. Follow only this file.
**STOP on failure or ambiguity. Keep every attempt. Never `--record-raw` on the
aircraft. The pilot owns arming, modes, motion and takeover.**

Two terminals on the Pi: **A** runs the live stack, **B** records operator
events and runs checks.

## 1. Ready

Bring: pilot and spotter; aircraft, Pixhawk, Pi, Hailo and camera; GCS and RC;
charged batteries; Ethernet cable; a laptop; a safe site, geofence and weather;
DataFlash access.

Connect from the laptop (field address: the Pi's address on the GCS network, see
`tools/mac/thesis_field_connect.sh`), then on the Pi:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
git rev-parse HEAD
git status --short
df -h . /dev/shm
```

PASS: the revision is the intended one, the tree is clean, storage is OK.

## 2. Network

Pixhawk connected, aircraft disarmed.

```bash
sudo tools/host/set_pi_network_mode.sh pixhawk
sudo tools/host/set_pi_network_mode.sh status
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show eth0
ip route show default
ping -c 3 -W 1 192.168.144.14
systemctl is-active tailscaled
```

PASS: approved Wi-Fi is the default route; `pixhawk-apm` is on `eth0` with no
default route; the Pixhawk answers; Tailscale is inactive. Details and recovery:
`docs/debug/UNATTENDED_PI_OPERATION.md`.

## 3. Static and passive checks

Aircraft disarmed and stationary.

```bash
tools/flight/field_preflight_check.sh
tools/flight/field_preflight_check.sh --passive-live-gate
```

PASS: both.

## 4. Compute-only ground run

Checks signs and freshness with no MAVROS control.

Terminal A:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_compute_vga
./tools/start_live_stack.sh --res vga --field-record --tag "$TAG"
```

Terminal B:

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_compute_vga
```

Terminal A: `ids`, then `target <id>`. Terminal B:

```bash
read -r -p "Person: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /control_ref/diagnostics
```

PASS: centred target gives about zero yaw; target left gives yaw < 0; right gives
yaw > 0; far gives vx > 0; near gives vx < 0; LOST, stale or invalid gives zero.

Before `stop`:

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "compute-only signs/freshness passed"
```

Then `stop` in Terminal A, and:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --ground-qualification
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
python3 tools/analysis/summarize_control_diagnostics.py "$BAG"
```

`--ground-qualification` requires complete runtime evidence but lets the
ground-only package stay explicitly pending for DataFlash and physical
annotation. It only applies to the fixed ground tags (`ground_compute_vga`,
`ground_process_loss_vga`) and never relaxes verification of flight runs.

## 5. Restrained control and process-loss test

Props off or restrained. **Do not arm.**

Terminal A:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_process_loss_vga
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

Terminal B:

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_process_loss
```

Select and record the target as in section 4, then:

```bash
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /mavros/setpoint_velocity/cmd_vel
timeout 20s ros2 topic echo /mavros/setpoint_raw/target_local
```

PASS: the MAVROS mirror, BODY_NED frame and signs are correct; LOST gives zero;
the FCU is disarmed in the expected mode.

With a visible non-zero reference, kill the controller to prove fail-closed
behaviour:

```bash
tools/flight/kill_exact_controller_for_gate.sh "$RUN_ID"
```

The pilot takes over. Record the actual modes:

```bash
python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" --trigger controller_process_loss --from-mode ACTUAL_FROM --to-mode ACTUAL_TO
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason controller_process_loss_test
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "fail-closed response and takeover observed"
```

Then `stop` in Terminal A, and:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial --ground-qualification
```

PASS: fail-closed FCU response and effective takeover. STOP otherwise.

## 6. Pilot GO

GO only if sections 1-5 pass and RC/failsafe, PreArm, batteries, site, weather,
geofence, camera/Hailo and recorder are healthy. **No airborne run starts before
Pilot GO.**

## 7. A recorded flight run

Terminal A:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=<short_run_name>
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

Terminal B, before the run (DataFlash contract: `LOG_DISARMED=0`,
`LOG_FILE_DSRMROT=1`, `LOG_BACKEND_TYPE=1` - do not fly if the values differ):

```bash
read -r -p "RUN_ID: " RUN_ID; export RUN_ID
export TAG=<short_run_name>
export DATAFLASH_DIR="ros2_ws/log/dataflash/${RUN_ID}__${TAG}"
mkdir -p "$DATAFLASH_DIR"
ros2 param get /mavros/param LOG_DISARMED
ros2 param get /mavros/param LOG_FILE_DSRMROT
ros2 param get /mavros/param LOG_BACKEND_TYPE
python3 tools/live/retrieve_pixhawk_dataflash.py catalogue --output "$DATAFLASH_DIR/before.json"
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario <scenario> --note "<target and route>"
```

Terminal A: `ids`, then `target <id>`. Terminal B:

```bash
read -r -p "Person: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --trial-id "$TAG" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

The pilot directs all motion. Take over for a wrong-person or stale non-zero
command, unexpected motion or mode, unsafe saturation, or evidence failure.

To mark a repeated scenario inside the run use
`operator_event.py opportunity_start|opportunity_end` (`--opportunity-id`,
`--scenario`, `--outcome completed|right_censored|aborted|invalid`). Run
`python3 tools/live/operator_event.py --help` for every event type.

### Abort block

```bash
read -r -p "Abort reason: " ACTUAL_REASON
python3 tools/live/operator_event.py abort --run-id "$RUN_ID" --trial-id "$TAG" --abort-class safety --reason "$ACTUAL_REASON"
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --trial-id "$TAG" --end-reason pilot_abort
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --trial-id "$TAG" --verdict rejected --integrity-reason "$ACTUAL_REASON"
```

Then `stop` normally and **keep the run**. Do not invent a missing
`opportunity_end` afterwards.

## 8. Finish every run

Terminal B, for nominal completion (after an abort use the abort block instead):

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --trial-id "$TAG" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --trial-id "$TAG" --verdict accepted --integrity-reason "field run complete; evidence review pending"
export DATAFLASH_DIR="ros2_ws/log/dataflash/${RUN_ID}__${TAG}"
python3 tools/live/retrieve_pixhawk_dataflash.py catalogue --output "$DATAFLASH_DIR/after.json"
python3 tools/live/retrieve_pixhawk_dataflash.py compare --before "$DATAFLASH_DIR/before.json" --after "$DATAFLASH_DIR/after.json" --output "$DATAFLASH_DIR/association.json"
```

The comparison must report exactly one new log (`status=unique_new_log`). If it
reports none or several, keep the run and do not guess a log ID.

Then `stop` in Terminal A and verify the exact run:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
```

`stop` also stops the MAVROS instance the stack owned, so restart MAVROS only to
download the DataFlash log. Keep the aircraft landed, disarmed and on the
validated field network. Read the associated log ID and size from
`association.json`:

```bash
read -r LOG_ID LOG_SIZE < <(python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["selected"]; print(s["id"], s["size"])' "$DATAFLASH_DIR/association.json")
```

Start MAVROS with the same FCU contract and require `connected: true` and
`armed: false` before downloading:

```bash
setsid ros2 launch mavros apm.launch fcu_url:="udp://:14550@" tgt_system:="10" tgt_component:="1" \
  > "$DATAFLASH_DIR/mavros_download.log" 2>&1 &
MAVROS_PID=$!
timeout 2s ros2 topic echo /mavros/state --once      # repeat until connected + disarmed
DATAFLASH="$DATAFLASH_DIR/log_${LOG_ID}.bin"
python3 tools/live/retrieve_pixhawk_dataflash.py download --log-id "$LOG_ID" --expected-size "$LOG_SIZE" --output "$DATAFLASH"
kill -TERM -- "-$MAVROS_PID" 2>/dev/null || true
```

Only after a successful download:

```bash
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH" --provenance-dir "$DATAFLASH_DIR"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

Keep every failed, aborted or ineligible run. What the retained package must
contain: `retained_evidence_package.md`.

## 9. Back up and exit

On the laptop, after every run:

```bash
export RUN_ID="<exact>" TAG="<exact>" PI_FIELD_HOST="<pi field address>"
printf -v RUN_NAME "%s__video__%s" "$RUN_ID" "$TAG"
DEST="$HOME/field-backups/$RUN_NAME"; mkdir -p "$DEST"
rsync -a "francisco@$PI_FIELD_HOST:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" "$DEST/"
rsync -anc --itemize-changes "francisco@$PI_FIELD_HOST:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" "$DEST/"
```

The second `rsync` must print nothing. Then on the Pi:

```bash
sudo tools/host/set_pi_network_mode.sh unattended
sudo tools/host/set_pi_network_mode.sh status
git status --short
test ! -e log
test ! -e hailort.log
```
