# Friday flight operator sheet — 25 September 2026

**Canonical #50 procedure.** Execute in order on the authoritative Pi with the qualified pilot and spotter. A failed gate stops aircraft work; retain every attempt and log. H01/H02/H03 are complete. #64 is closed: VGA is retained, HD rejected for promotion, FHD excluded. #32 follows the physical #50 controller decision.

## 0. Frozen revision and configuration

Frozen flight-stack base: `56771a09ab52eb2289e25fe94ec1ebb18fad5d45` (`22-09-26: bound visual packet receipt time`). Any later handoff commit may change documentation only; verify its full SHA against `origin/main` and inspect the commits after this base before aircraft work. Require a clean tracked tree. Every #50 launch uses `--res vga` (camera 640x480); YOLOv8s Hailo inference stays 640x640. Keep the frozen ByteTrack, TIM-MARS, model and controller parameters. No pull, install, rebuild, retune, HD/FHD trial, `--record-raw`, or scientific gate change at the field. Logs belong under `ros2_ws/log/`; root `log/` and `hailort.log` must be absent.

## 1. People, site and equipment

Pilot with immediate RC/manual takeover authority and spotter/observer present; charged aircraft/GCS/Pi batteries, RC and failsafe checked; safe site, weather, geofence and flight permissions confirmed. Physically connect camera, Hailo and Pixhawk. Confirm storage above the recording threshold, current clocks, and ability to retrieve the exact native Pixhawk DataFlash `.bin`. The pilot owns arming, modes, abort and aircraft motion. Ground gates use a disarmed, stationary aircraft.

## 2. Mac/GCS and Pi shell

Join `ISR Aero.Next GCS` on the Mac, then `ssh francisco@192.168.8.174`. On the Pi:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
git --no-pager log -1 --oneline
git rev-parse HEAD
git rev-parse origin/main
git status --short
df -h . /dev/shm
```

Require the final handoff SHA at HEAD and origin/main, a clean tracked tree and adequate free space. Repeat this shell setup in each new Pi terminal, especially after a network reconnect.

## 3. Field network — hard prerequisite

**Unresolved as of 22 September:** `THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION=""` and no saved profile name clearly identifies the approved AERONEXT local router. At IST, obtain the explicitly approved SSID, exact NetworkManager connection-profile name, credentials through the authorised operator, and expected fallback IP/default route. Provision the credentials in NetworkManager and set only that approved profile name in `/etc/default/thesis-host-health`; never put secrets in the repo or evidence. The `ISR Aero.Next GCS Rescue` profile is management-only, not a field fallback. Do not proceed to aircraft operation until the primary-available, primary-unavailable approved-fallback, and neither-available fail-closed transitions have been safely tested with Pixhawk connected and aircraft disarmed.

Connect/power Pixhawk Ethernet, intentionally enter field mode, reconnect over field Wi-Fi if SSH drops:

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

Require mode `pixhawk`; primary `ISR Aero.Next GCS` first when available; Pi Wi-Fi `192.168.8.174/24`; `pixhawk-apm` on eth0 `192.168.144.183/24`; Pixhawk `192.168.144.14` reachable; Wi-Fi owns the default route; **no eth0 default route**; Tailscale inactive. During approved-fallback testing, record its actual profile/address/default route. A failed route/profile/state check blocks aircraft operation. Do not substitute an unapproved profile.

## 4. Static preflight

```bash
tools/flight/field_preflight_check.sh
```

This is read-only and fail-closed, not a physical PASS. Resolve every failure; separately check camera/Hailo connections, battery, RC, geofence and DataFlash access with the pilot.

## 5. Passive MAVROS and recorder gate

Aircraft disarmed/stationary; no controller or setpoint publisher:

```bash
tools/flight/field_preflight_check.sh --passive-live-gate
```

This runs a bounded `--res vga --field-record --no-control` ground recording. Require connected MAVROS, disarmed state, BODY_NED readback, zero command publishers, retained topics, finalized structured MCAP and MJPEG visual, and observed-zero recorder transport loss. Keep failed evidence and stop if any check fails.

## 6. Manual moving-UAV TIM-MARS evidence

Optional supplemental #50 physical-person evidence once network/passive gates pass; it is **not** a substitute for the required controller/flight comparison. Pilot owns motion, controller disabled. Perform if safe and useful to document viewpoint, range, crossing and loss/return without control:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=manual_dynamic_tim_vga
./tools/start_live_stack.sh --res vga --field-record --no-control --tag "$TAG"
```

In terminal B use the exact displayed RUN_ID (never `latest`):

```bash
read -r -p "RUN_ID: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario manual_dynamic_tim
```

Select the intended physical person in Terminal A using `ids` then `target <id>`; record the visible person and exact ID with the target-selection commands in §11. Pilot may perform hover, lateral/range/yaw change, crossing, safe brief loss/return. Record `trial_end`, then normal `stop` and §15–17 verification. Retain any abort.

## 7. Compute-only controller ground gate

Aircraft disarmed/stationary; no MAVROS command mirror:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_compute_vga
./tools/start_live_stack.sh --res vga --field-record --tag "$TAG"
```

Select and record the intended physical person. In terminal B (source ROS overlay):

```bash
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /control_ref/diagnostics
```

Require centred target near-zero yaw; left `yaw_z < 0`; right `yaw_z > 0`; farther/smaller `vx > 0`; nearer/larger `vx < 0`; stale/lost/invalid **zero**. Stop normally and retain the bag. Before any aircraft trial, perform one
complete non-held-out rehearsal: use §15 to verify finalized MCAP, visual,
operator events, command/diagnostic pairing, timing and run provenance; check
that the intended physical person can be annotated and that authority and
commands can be attributed through a distractor/identity transition. Review
resource/cadence evidence from the exact run. Missing reconstruction evidence
blocks the next gate. Any sign or freshness ambiguity blocks flight.

## 8. Restrained/props-off MAVROS command-path gate

Qualified pilot and FCU observer present; props removed or aircraft safely restrained; **do not arm**. Keep this run recording through §9:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_process_loss_vga
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

Terminal B, copy the exact RUN_ID and record the trial:

```bash
read -r -p "RUN_ID: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_process_loss
timeout 20s ros2 topic echo /control_ref/cmd_vel
timeout 20s ros2 topic echo /mavros/setpoint_velocity/cmd_vel
timeout 20s ros2 topic echo /mavros/setpoint_raw/target_local
timeout 12s ros2 topic echo /mavros/state --once
```

Verify expected controller→MAVROS mirror, `BODY_NED` frame, physical signs, zero on stale/lost, expected FCU/GCS state, and no unexpected arming or mode change. An apparent setpoint alone does not prove aircraft response.

## 9. Mandatory exact controller process-loss test

Before any aircraft motion, while §8 MCAP is still recording, establish and observe a **non-zero** reference. Pilot and FCU observer are ready to take over. In terminal B, inspect exact launcher and its **single child** before signalling; stop if missing or ambiguous. This is deliberate only for the disarmed restrained/props-off gate:

```bash
stop_exact_controller() {
    local run_dir launch_pid exe_pid confirm
    run_dir="ros2_ws/log/live_stack/$RUN_ID"
    test -f "$run_dir/pids.txt" || { echo "Run PID file missing" >&2; return 1; }
    launch_pid="$(awk '$2=="control" {print $1}' "$run_dir/pids.txt")"
    test "$(printf '%s\n' "$launch_pid" | sed '/^$/d' | wc -l)" -eq 1 || { echo "Control launcher PID missing or ambiguous" >&2; return 1; }
    exe_pid="$(pgrep -P "$launch_pid" -f control_ref_node || true)"
    test "$(printf '%s\n' "$exe_pid" | sed '/^$/d' | wc -l)" -eq 1 || { echo "Control executable PID ambiguous" >&2; return 1; }
    ps -p "$launch_pid","$exe_pid" -o pid,ppid,args || return 1
    read -r -p "Confirm exact controller child PID $exe_pid and non-zero reference; type YES to kill: " confirm
    test "$confirm" = YES || { echo "Process-loss test cancelled" >&2; return 1; }
    date --iso-8601=ns | tee "$run_dir/controller_process_loss.txt"
    kill -KILL "$exe_pid" || return 1
    date --iso-8601=ns | tee -a "$run_dir/controller_process_loss.txt"
}
stop_exact_controller
python3 tools/live/operator_event.py unexpected_behavior --run-id "$RUN_ID" --description "deliberate exact controller process loss during non-zero reference" --severity concern
python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" --trigger controller_process_loss --from-mode GUIDED --to-mode LOITER
```

Use the **actual** FCU modes in the event command; edit the example values before running. Never kill by broad process-name matching. Observe and timestamp `/control_ref/cmd_vel`, `/mavros/setpoint_velocity/cmd_vel`, `/mavros/setpoint_raw/target_local`, `/mavros/state`, FCU/GCS response and pilot takeover. A killed node cannot publish a graceful final zero. Require documented fail-closed FCU response and effective pilot takeover. Stale non-zero authority or ambiguous FCU response **blocks flight**. Record `trial_end --end-reason controller_process_loss_test` and a rejected/accepted `trial_verdict` with the observed reason **before** normal `stop`, so the event log is archived. If unsafe, use §14 abort events and stop aircraft work.

## 10. Pilot go/no-go

Explicitly confirm: network fallback and routes passed; static and passive gates passed; compute-only signs/freshness passed; restrained BODY_NED/mirror/FCU state passed; exact process-loss fail-closed response and takeover documented; RC takeover and failsafe work; PreArm messages understood; geofence/site/weather/batteries/spotter ready; camera and Hailo healthy; recorder/storage/visual healthy; physical command direction correct; pilot authorizes low-risk baseline first. **Any failure means no flight.**

## 11. Baseline first flight and target selection

Only after §10. Pilot controls arm/mode and initial safety. This first baseline is a safety/recording rehearsal; it may also become a matched pair only if its route, target, loss opportunity and 10.0 s horizon were predeclared before launch and eligibility later holds.

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=flight1_baseline_vga
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

Terminal B:

```bash
read -r -p "RUN_ID: " RUN_ID; export RUN_ID
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario first_baseline
```

In Terminal A inspect `ids`, select `target <id>`; then in B immediately record the human intent and requested ID (do not infer physical correctness from TIM `LOCKED`):

```bash
read -r -p "Visible intended person: " PERSON
read -r -p "Selected track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Pilot exercises conservative following and safe loss→hover/zero. Any wrong-person command or unexpected motion triggers §14 immediate takeover/abort. Before normal `stop`, write `trial_end` and `trial_verdict` (§15); then verify §15–16. Review the baseline with the pilot before any candidate run.

## 12. Predeclared matched baseline vs candidate campaign

Aim for **three eligible matched pairs** of the same physical target and comparable route/loss/return opportunity. Declare and record **before each pair**: physical target, route, safe loss opportunity, fixed **10.0 s** observation horizon. Use the pair number and condition in `TAG`, `--scenario` and `--trial-id`. Preferred order:

| Pair | First | Second |
| --- | --- | --- |
| 1 | `pair1_baseline` | `pair1_candidate` |
| 2 | `pair2_candidate` | `pair2_baseline` |
| 3 | `pair3_baseline` | `pair3_candidate` |

For each run set a **new** RUN_ID, set TAG to its table value, then use exactly one launch:

```bash
# Baseline: LOST -> hover/zero
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=pair1_baseline
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

For the separate candidate run (bounded yaw only and zero translation on LOST):

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=pair1_candidate
./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

Change TAG for pairs 2 and 3 per table. Never start the second run until the first is stopped, retained and reviewed. Terminal B after each launch (copy RUN_ID/TAG):

```bash
read -r -p "RUN_ID: " RUN_ID; export RUN_ID
read -r -p "TAG (pairN_condition): " TAG; export TAG
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario "$TAG" --note "target=... route=... loss=... horizon=10.0s"
```

For the candidate run, use this **instead of** the baseline event:

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario "$TAG" --recovery-enabled --note "target=... route=... loss=... horizon=10.0s"
```

Record `target_selected` as in §11 for **every** run. Eligibility: at least **3.0 s visible trusted LOCKED control before loss**, safe observable loss, comparable return opportunity in both conditions. Stopped, aborted or ineligible attempts stay retained and marked with reasons; replace a pair only with another predeclared pair. Right-censor if the correct target does not return within 10.0 s; record elapsed observation and end reason. Physical-person annotation after flight determines correct reacquisition and wrong-person command duration.

Candidate can be retained only with ≥3 eligible pairs, earlier **correct physical-target** reacquisition than baseline in ≥2, no later reacquisition or worse censoring in the remaining pair, **zero** wrong-person non-zero command duration, **zero** stale/invalid non-zero command, **zero** translation in recovery, no added unsafe motion or unacceptable saturation, and no added takeover. Otherwise retain baseline hover/zero; candidate remains unpromoted. This is descriptive evidence, not statistical superiority. Do not redesign the controller at the field.

## 13–14. Immediate takeover and abort

Pilot takes manual authority immediately for wrong-person non-zero command, unexpected motion, failed RC takeover, stale/invalid non-zero authority, unexpected arm/mode change, unsafe saturation, unresolved BODY_NED/sign, unsafe/ambiguous process-loss response, or evidence failure preventing reconstruction. Record **actual** modes/trigger/reason while preserving the run:

```bash
python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" --trigger wrong_person_command --from-mode GUIDED --to-mode LOITER
python3 tools/live/operator_event.py unexpected_behavior --run-id "$RUN_ID" --description "describe observed motion or authority" --severity critical
python3 tools/live/operator_event.py abort --run-id "$RUN_ID" --abort-class safety --reason "describe exact reason"
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason pilot_abort
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict rejected --integrity-reason "describe safety or evidence failure"
```

The listed modes are examples; use actual modes. Valid abort classes: `safety|geofence|behaviour|equipment|weather|communications|other`. Do not continue to candidate after an unsafe baseline. A failed run is evidence and must never be deleted.

## 15. Normal stop and package checks — each run

Before typing `stop` in Terminal A, write the actual end reason and §16 verdict in B so the append-only event log is archived:

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field observations eligible; postflight package and physical annotation pending"
```

An accepted **field** verdict does not certify final evidence; reject immediately if an observed safety/eligibility/integrity failure exists. Type `stop` in A; wait for recorder finalization. Build the exact path from the displayed RUN_ID and TAG:

```bash
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
test -d "$BAG" || { echo "Exact bag missing: $BAG" >&2; exit 1; }
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
```

For a controller run also execute:

```bash
python3 tools/analysis/summarize_control_diagnostics.py "$BAG"
```

Preserve finalized MCAP/`metadata.yaml`, `run_metadata.json`, `flight_metadata.txt`, `target_authority_events.jsonl`, integrity/transport/package status, archive manifest, recorder finalization/logs, dashboard/TIM/control/operator logs, 640x480 MJPEG `visual_<RUN_ID>.mkv` and visual status. For controller runs inspect controller command/diagnostics, MAVROS mirror/FCU echo, state/pose/velocity and saturation. If verification fails, keep all files and mark the trial rejected; reconcile the archived event verdict rather than silently counting it.

## 16. Exact Pixhawk DataFlash and final verdict

For **each controller trial**, human-select the exact native DataFlash `.bin` belonging to that RUN_ID using timestamps/FCU records; never select “latest” automatically:

```bash
read -r -p "Exact DataFlash .bin path: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

For a post-stop integrity correction, retain an explicit separate postflight decision next to the bag. The run-log archiver refuses overwrite; do not silently change its archived event log or manifest. Do not edit or erase prior events. Record accepted/rejected and concrete integrity reason. Final scientific acceptance also needs physical-person annotation, actual FCU response and the DataFlash match. Never represent pending annotation as passed.

## 17. End of day

After each run's package checks and, for controller trials, exact DataFlash archival (§16), back up every retained bag, including failed/aborted attempts. On the **Mac**, while it can still SSH to the Pi field address, use that attempt's actual RUN_ID/TAG (repeat for every attempt):

```bash
export RUN_ID="<exact RUN_ID>" TAG="<exact TAG>"
printf -v RUN_NAME "%s__video__%s" "$RUN_ID" "$TAG"
mkdir -p "$HOME/Developer/Thesis/Friday-Flight-Backup/live_camera/$RUN_NAME"
rsync -a "francisco@192.168.8.174:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" \
  "$HOME/Developer/Thesis/Friday-Flight-Backup/live_camera/$RUN_NAME/"
rsync -anc --itemize-changes "francisco@192.168.8.174:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" \
  "$HOME/Developer/Thesis/Friday-Flight-Backup/live_camera/$RUN_NAME/"
```

The final dry-run must print no changed files; investigate any output or rsync error. `-a` preserves the visual file mtime used in timing provenance; `-c` checks content on the second pass. Keep originals on the Pi and confirm the copied manifest, MCAP, visual, events and archived exact DataFlash are present. The Mac destination is outside both repositories. Then return to unattended networking only after Pixhawk work ends:

```bash
sudo tools/host/set_pi_network_mode.sh unattended
sudo tools/host/set_pi_network_mode.sh status
git status --short
git status --short --ignored
test ! -e log
test ! -e hailort.log
```

Investigate any runtime noise; keep build/runtime logs in `ros2_ws/log/`. Leave #50 open until physical evidence and controller decision are reviewed. Final #32 mounted 60 s warm-up + 20-minute active run waits for that decision.
