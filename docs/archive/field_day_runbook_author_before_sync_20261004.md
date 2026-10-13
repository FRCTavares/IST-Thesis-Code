# Friday #50 — operator sheet

## Ready

Mac on ISR:
```bash
ssh francisco@192.168.8.174
```
Pi:
```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
git rev-parse HEAD origin/main
git status --short
df -h . /dev/shm
```
PASS: HEAD=origin/main, clean, storage OK.
## Network
Before flight validate approved AERONEXT fallback:
ISR → fallback → neither/fail-closed. Pixhawk connected; aircraft disarmed.
```bash
sudo tools/host/set_pi_network_mode.sh pixhawk
sudo tools/host/set_pi_network_mode.sh status
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show eth0
ip route show default
ip route show default dev eth0
ping -c 3 -W 1 192.168.144.14
systemctl is-active tailscaled
```
PASS: approved Wi-Fi default; `pixhawk-apm` eth0; no eth0 default; Pixhawk
reachable; Tailscale inactive.
## Static + passive
Aircraft disarmed/stationary:
```bash
tools/flight/field_preflight_check.sh
tools/flight/field_preflight_check.sh --passive-live-gate
```
PASS: both.

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 0 — MANUAL RC / DYNAMIC TIM-MARS DONE

Purpose: pilot owns all motion; controller disabled. Record TIM-MARS under real
moving-UAV imagery. Aim for roughly 90--120 s. Do not fly aggressively.

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=dynamic_uav_tim_manual_r1
echo "$RUN_ID"
./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"
```

At `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

### Terminal B — EVENTS

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario dynamic_uav_tim_manual
read -r -p "Visible person description: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

### PILOT

If safe:

1. stable hover ~10 s;
2. lateral left/right;
3. increase/reduce target distance;
4. change yaw/viewpoint;
5. UAV and target move simultaneously;
6. distractor crosses near target;
7. brief target loss + changed-viewpoint return if safe;
8. stable hover ~10 s.

Pilot judgement overrides the sequence. Controller must remain disabled.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
```

### Terminal A — STOP + VERIFY

At `live-stack>`:

```bash
stop
```

Then:

```bash
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
export BAG
echo "$BAG"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
```

KEEP even if imperfect. Do not retune TIM-MARS from this flight.

----------------------------------------------------------------------------------------------------------------------------------------------------------

## MATCHED-FLIGHT RULES — FLIGHTS 1--6

Same physical target/route/loss opportunity within each pair.
Eligible trial: >=3 s trusted visible control before safe loss + comparable return.
Evaluation horizon: 10 s.

TAKE OVER for wrong-person/stale non-zero command, unexpected motion/mode,
unsafe saturation, or evidence failure. No candidate after an unsafe baseline.

### ABORT BLOCK — USE WHEN NEEDED

Terminal B:

```bash
read -r -p "Abort reason: " ACTUAL_REASON
python3 tools/live/operator_event.py abort --run-id "$RUN_ID" --abort-class safety --reason "$ACTUAL_REASON"
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason pilot_abort
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict rejected --integrity-reason "$ACTUAL_REASON"
```

Then `stop` normally and KEEP the run.

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 1 — PAIR 1 BASELINE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=pair1_baseline
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=pair1_baseline
read -r -p "Trial note — target/route/loss: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario "$TAG" --note "$NOTE horizon=10.0s"
```

Terminal A at `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

Terminal B:

```bash
read -r -p "Person: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Fly pair-1 baseline loss/return. Baseline LOST response = hover/zero.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
```

### Terminal A — STOP + VERIFY + DATAFLASH

At `live-stack>`:

```bash
stop
```

Then:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 2 — PAIR 1 CANDIDATE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=pair1_candidate
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=pair1_candidate
read -r -p "Trial note — target/route/loss: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario "$TAG" --recovery-enabled --note "$NOTE horizon=10.0s"
```

Terminal A at `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

Terminal B:

```bash
read -r -p "Person: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Fly the matched pair-1 loss/return. Candidate recovery remains frozen; no retuning.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
```

### Terminal A — STOP + VERIFY + DATAFLASH

At `live-stack>`:

```bash
stop
```

Then:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 3 — PAIR 2 CANDIDATE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=pair2_candidate
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=pair2_candidate
read -r -p "Trial note — target/route/loss: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario "$TAG" --recovery-enabled --note "$NOTE horizon=10.0s"
```

Terminal A at `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

Terminal B:

```bash
read -r -p "Person: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Fly pair-2 candidate loss/return.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
```

### Terminal A — STOP + VERIFY + DATAFLASH

At `live-stack>`:

```bash
stop
```

Then:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 4 — PAIR 2 BASELINE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=pair2_baseline
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=pair2_baseline
read -r -p "Trial note — target/route/loss: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario "$TAG" --note "$NOTE horizon=10.0s"
```

Terminal A at `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

Terminal B:

```bash
read -r -p "Person: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Fly the matched pair-2 baseline loss/return. Baseline LOST response = hover/zero.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
```

### Terminal A — STOP + VERIFY + DATAFLASH

At `live-stack>`:

```bash
stop
```

Then:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 5 — PAIR 3 BASELINE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=pair3_baseline
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=pair3_baseline
read -r -p "Trial note — target/route/loss: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario "$TAG" --note "$NOTE horizon=10.0s"
```

Terminal A at `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

Terminal B:

```bash
read -r -p "Person: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Fly pair-3 baseline loss/return. Baseline LOST response = hover/zero.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
```

### Terminal A — STOP + VERIFY + DATAFLASH

At `live-stack>`:

```bash
stop
```

Then:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

----------------------------------------------------------------------------------------------------------------------------------------------------------

## FLIGHT 6 — PAIR 3 CANDIDATE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=pair3_candidate
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=pair3_candidate
read -r -p "Trial note — target/route/loss: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario "$TAG" --recovery-enabled --note "$NOTE horizon=10.0s"
```

Terminal A at `live-stack>`:

```bash
ids
```

Then:

```bash
target <id>
```

Terminal B:

```bash
read -r -p "Person: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Fly the matched pair-3 candidate loss/return. Candidate recovery remains frozen.

### Terminal B — FINISH

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
```

### Terminal A — STOP + VERIFY + DATAFLASH

At `live-stack>`:

```bash
stop
```

Then:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```
