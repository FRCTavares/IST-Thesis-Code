# Friday #50 — operator sheet
**Canonical #50 procedure.** 25 September 2026. Follow only this file.
H01/H02/H03 are complete. #64 is closed: VGA is retained.
STOP on failure. Keep every attempt. Never `--record-raw`.
Pilot owns arming, modes, motion and takeover.
## Ready
Bring: pilot + spotter; aircraft/Pixhawk/Pi/Hailo/camera; GCS/RC; batteries;
Ethernet; Mac; safe site/geofence/weather; DataFlash access.
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
## Compute-only
A:
```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_compute_vga
./tools/start_live_stack.sh --res vga --field-record --tag "$TAG"
```
B:
```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_compute_vga
```
A: `ids`, `target <id>`. B:
```bash
read -r -p "Person: " PERSON; read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /control_ref/diagnostics
```
PASS: centre≈0 yaw; left<0; right>0; far vx>0; near vx<0;
LOST/stale/invalid=zero.
Before `stop`:
```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "compute-only signs/freshness passed"
```
Then `stop`:
```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG"
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
python3 tools/analysis/summarize_control_diagnostics.py "$BAG"
```
STOP on ambiguity.
## Restrained control + process loss
Props off/restrained. **Do not arm.**
A:
```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_process_loss_vga
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```
B:
```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_process_loss
```
Select/record target as above, then:
```bash
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /mavros/setpoint_velocity/cmd_vel
timeout 20s ros2 topic echo /mavros/setpoint_raw/target_local
```
PASS: mirror/BODY_NED/signs correct; LOST=zero; FCU disarmed/expected mode.
With visible non-zero reference:
```bash
tools/flight/kill_exact_controller_for_gate.sh "$RUN_ID"
```
Pilot takes over. Record actual modes:
```bash
python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" --trigger controller_process_loss --from-mode ACTUAL_FROM --to-mode ACTUAL_TO
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason controller_process_loss_test
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "fail-closed response and takeover observed"
```
Then `stop`:
```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
```
PASS: fail-closed FCU response + effective takeover. STOP otherwise.
## Pilot GO
GO only if all above pass plus RC/failsafe, PreArm, batteries, site/weather,
geofence, camera/Hailo and recorder healthy.

**No airborne run starts before Pilot GO.**

Final comparison airborne order:

1. Flight 1 — Baseline A (`bcb_baseline_a`)
2. Flight 2 — Candidate (`bcb_candidate`)
3. Flight 3 — Baseline B (`bcb_baseline_b`)

Remember: `B -> C -> B`.

The manual-RC dynamic TIM-MARS flight was already completed on 25 September
2026 and is retained as supporting/commissioning evidence. It is **not repeated**
as part of the final physical comparison.

---

## COMPLETED 25 SEPTEMBER — MANUAL RC / DYNAMIC TIM-MARS

**Do not repeat for the final B-C-B comparison.**

Retained run: `2026-09-25__10-29-29`, tag
`dynamic_uav_tim_manual_r1`.

Purpose: supporting moving-UAV TIM-MARS observation with pilot-owned motion and
controller disabled. The retained run had healthy runtime/visual/transport
evidence, but predates the final opportunity-event contract and therefore is
not one of the three final controller-comparison flights.

The commands below are retained as the historical procedure used for that run.

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

---

## COMPARISON RULES — FLIGHTS 1–3

Match O1/O2/O3 target, route, loss and return pattern across all three flights.
Each opportunity requires >=3 s trusted visible control before safe loss and
a comparable return. Evaluation horizon: 10 s.

TAKE OVER for wrong-person/stale non-zero command, unexpected motion/mode,
unsafe saturation, or evidence failure. No candidate after an unsafe baseline.

### ABORT BLOCK — USE WHEN NEEDED

Terminal B:

```bash
read -r -p "Abort reason: " ACTUAL_REASON
python3 tools/live/operator_event.py abort --run-id "$RUN_ID" --trial-id "$TAG" --abort-class safety --reason "$ACTUAL_REASON"
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --trial-id "$TAG" --end-reason pilot_abort
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --trial-id "$TAG" --verdict rejected --integrity-reason "$ACTUAL_REASON"
```

Then `stop` normally and KEEP the run.

If the abort occurs during an opportunity, do **not** invent the missing
`opportunity_end` afterward. The strict verifier accepts the retained event
sequence as an aborted coherent prefix; the run remains retained evidence but
does not count as a complete B-C-B comparison flight.

---

## FINAL PHYSICAL COMPARISON — THREE-FLIGHT B–C–B

This supersedes the earlier six-flight `B C | C B | B C` plan.

The final scientific field comparison uses at most three planned flights in one
session:

| Flight | Role | Condition | Tag |
|---|---|---|---|
| 1 | Baseline A | recovery disabled | `bcb_baseline_a` |
| 2 | Candidate | bounded yaw-only recovery enabled | `bcb_candidate` |
| 3 | Baseline B | recovery disabled | `bcb_baseline_b` |

The three flights use the same frozen normal-follow controller:

- `yaw_kp = 0.60`
- `max_yaw_z = 0.20 rad/s`
- `max_delta_yaw_z = 0.03`
- `invert_yaw = true`

The candidate changes only the already-frozen LOST recovery policy:

- `recovery_yaw_rate = 0.10 rad/s`
- `recovery_max_duration_s = 1.0 s`
- `recovery_max_integrated_yaw_rad = 0.10 rad`
- translation remains prohibited during recovery.

Do not retune between Flights 1–3. Any controller/recovery parameter change
ends this comparison and requires a new frozen comparison sequence.

### Three predeclared loss opportunities per flight

Each flight contains three repeated loss/return opportunities. They are repeated
observations inside one flight, **not three independent flights**.

- **O1 — right loss:** selected person traverses slowly toward camera-right,
  exits view, then returns from the same side.
- **O2 — left loss:** selected person traverses slowly toward camera-left,
  exits view, then returns from the same side.
- **O3 — distractor + loss:** distractor crosses near the selected person;
  after separation, the selected person continues laterally out of view and
  returns separated from the distractor.

For every O1/O2/O3:

1. selected person must have at least `3.0 s` of trusted visible LOCKED control
   immediately before the induced loss;
2. loss must be safe and observable;
3. observation horizon is `10.0 s`;
4. record correct-person return/reacquisition or right-censor at `10.0 s`;
5. after the opportunity, re-establish separated trusted following for at least
   `3.0 s` before beginning the next opportunity.

Use the same target, route geometry, loss direction and return pattern for the
corresponding O1/O2/O3 across all three flights as closely as practical.

Any wrong-person authority, unexpected aircraft motion, stale non-zero command,
unsafe saturation, pilot takeover, recorder/evidence failure or other safety
concern triggers the existing abort block. KEEP the run.

---

## FLIGHT 1 — BASELINE A

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=bcb_baseline_a
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=bcb_baseline_a
read -r -p "Trial note — target/route: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario bcb_three_opportunity --note "$NOTE opportunities=O1-right,O2-left,O3-distractor-loss; horizon_each=10.0s"
```

Terminal A:

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
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --trial-id "$TAG" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Terminal B: timestamp each predeclared opportunity immediately before it
starts and immediately after it ends. The pilot directs all aircraft motion.
For O1:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O1 --scenario right_loss
```

Perform O1 right-side loss and return. Then:

```bash
read -r -p "O1 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O1 --outcome "$OUTCOME"
```

For O2:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O2 --scenario left_loss
```

Perform O2 left-side loss and return. Then:

```bash
read -r -p "O2 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O2 --outcome "$OUTCOME"
```

For O3:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O3 --scenario distractor_loss
```

Perform O3 distractor crossing, selected-person loss and return. Then:

```bash
read -r -p "O3 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O3 --outcome "$OUTCOME"
```

Record the observed outcome, including censoring or invalidity. Here,
`completed` means that the prescribed opportunity was completed; it does not
assert successful correct-person reacquisition. Derive actual reacquisition
timing and identity correctness from retained ROS/video evidence. Follow
`Finish every run`.


---

## FLIGHT 2 — CANDIDATE

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=bcb_candidate
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=bcb_candidate
read -r -p "Trial note — target/route: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario bcb_three_opportunity --recovery-enabled --note "$NOTE opportunities=O1-right,O2-left,O3-distractor-loss; horizon_each=10.0s"
```

Terminal A:

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
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --trial-id "$TAG" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Terminal B: timestamp each predeclared opportunity immediately before it
starts and immediately after it ends. The pilot directs all aircraft motion.
For O1:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O1 --scenario right_loss
```

Perform O1 right-side loss and return. Then:

```bash
read -r -p "O1 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O1 --outcome "$OUTCOME"
```

For O2:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O2 --scenario left_loss
```

Perform O2 left-side loss and return. Then:

```bash
read -r -p "O2 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O2 --outcome "$OUTCOME"
```

For O3:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O3 --scenario distractor_loss
```

Perform O3 distractor crossing, selected-person loss and return. Then:

```bash
read -r -p "O3 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O3 --outcome "$OUTCOME"
```

Record the observed outcome, including censoring or invalidity. Here,
`completed` means that the prescribed opportunity was completed; it does not
assert successful correct-person reacquisition. Derive actual reacquisition
timing and identity correctness from retained ROS/video evidence. Follow
`Finish every run`.


---

## FLIGHT 3 — BASELINE B

### Terminal A — START

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=bcb_baseline_b
echo "$RUN_ID"
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

### Terminal B — START + TARGET EVENT

```bash
read -r -p "RUN_ID: " RUN_ID
export RUN_ID
export TAG=bcb_baseline_b
read -r -p "Trial note — target/route: " NOTE
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario bcb_three_opportunity --note "$NOTE opportunities=O1-right,O2-left,O3-distractor-loss; horizon_each=10.0s"
```

Terminal A:

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
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --trial-id "$TAG" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Terminal B: timestamp each predeclared opportunity immediately before it
starts and immediately after it ends. The pilot directs all aircraft motion.
For O1:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O1 --scenario right_loss
```

Perform O1 right-side loss and return. Then:

```bash
read -r -p "O1 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O1 --outcome "$OUTCOME"
```

For O2:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O2 --scenario left_loss
```

Perform O2 left-side loss and return. Then:

```bash
read -r -p "O2 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O2 --outcome "$OUTCOME"
```

For O3:

```bash
python3 tools/live/operator_event.py opportunity_start --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O3 --scenario distractor_loss
```

Perform O3 distractor crossing, selected-person loss and return. Then:

```bash
read -r -p "O3 outcome (completed/right_censored/aborted/invalid): " OUTCOME
python3 tools/live/operator_event.py opportunity_end --run-id "$RUN_ID" --trial-id "$TAG" --opportunity-id O3 --outcome "$OUTCOME"
```

Record the observed outcome, including censoring or invalidity. Here,
`completed` means that the prescribed opportunity was completed; it does not
assert successful correct-person reacquisition. Derive actual reacquisition
timing and identity correctness from retained ROS/video evidence. Follow
`Finish every run`.


## Finish every run

For nominal completion, Terminal B after O3. For an abort, use the abort block
instead and then continue at `stop`:

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --trial-id "$TAG" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --trial-id "$TAG" --verdict accepted --integrity-reason "field run complete; final annotation and evidence review pending"
```

Then `stop` at Terminal A's `live-stack>` prompt:

```text
stop
```

After stop finalizes the recorders, verify and archive the exact run:

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
read -r -p "Exact DataFlash .bin: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events --expect-bcb-opportunities "$TAG"
```

The recorded provisional verdict never overrides later evidence review. Retain
failed, aborted, censored and ineligible runs.

KEEP every failed, aborted, or ineligible run.

## Decision

An opportunity triplet O1/O2/O3 is eligible only when the corresponding
opportunity is eligible and physically attributable in Baseline A, Candidate,
and Baseline B.

A controller-policy promotion decision requires at least **two eligible
opportunity triplets**.

Candidate recovery is promoted only if all safety/integrity conditions pass and:

- with three eligible triplets, Candidate reacquires the correct person earlier
  than **both** baseline flights in at least two triplets and is no worse than
  either baseline in the remaining triplet;
- with only two eligible triplets, Candidate must reacquire earlier than both
  baselines in both;
- wrong-person non-zero command duration is zero;
- stale/invalid non-zero command duration is zero;
- recovery translation duration is zero;
- Candidate adds no unsafe motion, unacceptable saturation or pilot takeover.

Otherwise retain the baseline hover-on-loss policy and report the comparison as
inconclusive or non-promoting, as supported by the evidence.

The three within-flight opportunities are repeated descriptive observations,
not independent flight replicates. Do not claim statistical superiority.

No field retuning.

## Backup + exit
Mac, every run:
```bash
export RUN_ID="<exact>" TAG="<exact>" PI_FIELD_HOST="192.168.8.174"
printf -v RUN_NAME "%s__video__%s" "$RUN_ID" "$TAG"
DEST="$HOME/Developer/Thesis/evidence/field/2026-09-25/$RUN_NAME"; mkdir -p "$DEST"
rsync -a "francisco@$PI_FIELD_HOST:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" "$DEST/"
rsync -anc --itemize-changes "francisco@$PI_FIELD_HOST:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" "$DEST/"
```
Second rsync: no output. Use validated fallback Pi address if needed.
```bash
sudo tools/host/set_pi_network_mode.sh unattended
sudo tools/host/set_pi_network_mode.sh status
git status --short
test ! -e log
test ! -e hailort.log
```
Then `docs/issues/p032-final-mounted-runbook.md` with retained #50 policy.
