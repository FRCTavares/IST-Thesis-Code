# Friday #50 — operator sheet
**Canonical #50 procedure.** 25 September 2026. Follow only this file.
H01/H02/H03 are complete. #64 is closed: VGA is retained.
STOP on failure. Keep every attempt. Never `--record-raw`.
Pilot owns arming, modes, motion and takeover.
## Ready
Bring: pilot + spotter; aircraft/Pixhawk/Pi/Hailo/camera; GCS/RC; batteries;
Ethernet; Mac; safe site/geofence/weather; DataFlash access.
Mac on ISR:
    ssh francisco@192.168.8.174
Pi:
    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    git rev-parse HEAD origin/main
    git status --short
    df -h . /dev/shm
PASS: HEAD=origin/main, clean, storage OK.
## Network
Before flight validate approved AERONEXT fallback:
ISR → fallback → neither/fail-closed. Pixhawk connected; aircraft disarmed.
    sudo tools/host/set_pi_network_mode.sh pixhawk
    sudo tools/host/set_pi_network_mode.sh status
    nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
    nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show eth0
    ip route show default
    ip route show default dev eth0
    ping -c 3 -W 1 192.168.144.14
    systemctl is-active tailscaled
PASS: approved Wi-Fi default; `pixhawk-apm` eth0; no eth0 default; Pixhawk
reachable; Tailscale inactive.
## Static + passive
Aircraft disarmed/stationary:
    tools/flight/field_preflight_check.sh
    tools/flight/field_preflight_check.sh --passive-live-gate
PASS: both.
## Compute-only
A:
    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_compute_vga
    ./tools/start_live_stack.sh --res vga --field-record --tag "$TAG"
B:
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_compute_vga
A: `ids`, `target <id>`. B:
    read -r -p "Person: " PERSON; read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
    timeout 20s ros2 topic echo /control_ref/cmd_vel
    timeout 20s ros2 topic echo /control_ref/diagnostics
PASS: centre≈0 yaw; left<0; right>0; far vx>0; near vx<0;
LOST/stale/invalid=zero.
Before `stop`:
    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "compute-only signs/freshness passed"
Then `stop`:
    tools/flight/verify_field_run.sh "$RUN_ID" "$TAG"
    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    python3 tools/analysis/summarize_control_diagnostics.py "$BAG"
STOP on ambiguity.
## Restrained control + process loss
Props off/restrained. **Do not arm.**
A:
    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=ground_process_loss_vga
    ./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
B:
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario ground_process_loss
Select/record target as above, then:
    timeout 20s ros2 topic echo /control_ref/cmd_vel
    timeout 20s ros2 topic echo /mavros/setpoint_velocity/cmd_vel
    timeout 20s ros2 topic echo /mavros/setpoint_raw/target_local
PASS: mirror/BODY_NED/signs correct; LOST=zero; FCU disarmed/expected mode.
With visible non-zero reference:
    tools/flight/kill_exact_controller_for_gate.sh "$RUN_ID"
Pilot takes over. Record actual modes:
    python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" --trigger controller_process_loss --from-mode ACTUAL_FROM --to-mode ACTUAL_TO
    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason controller_process_loss_test
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "fail-closed response and takeover observed"
Then `stop`:
    tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
PASS: fail-closed FCU response + effective takeover. STOP otherwise.
## Pilot GO
GO only if all above pass plus RC/failsafe, PreArm, batteries, site/weather,
geofence, camera/Hailo and recorder healthy. First flight = baseline.
## Matched flights
Predeclare each pair: same physical target/route/loss opportunity; 10 s horizon.
| Pair | First | Second |
|---|---|---|
| 1 | baseline | candidate |
| 2 | candidate | baseline |
| 3 | baseline | candidate |
Baseline:
    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=pair1_baseline
    ./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
Candidate:
    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" TAG=pair1_candidate
    ./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
Change TAG for pairs 2/3. B after launch:
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario "$TAG" --note "target=... route=... loss=... horizon=10.0s"
For candidate use instead:
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario "$TAG" --recovery-enabled --note "target=... route=... loss=... horizon=10.0s"
A: `ids`, `target <id>`. B:
    read -r -p "Person: " PERSON; read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
Eligible: ≥3 s trusted visible control before safe loss + comparable return.
TAKE OVER for wrong-person/stale non-zero, unexpected motion/mode, unsafe
saturation or evidence failure. No candidate after unsafe baseline.
Abort:
    python3 tools/live/operator_event.py abort --run-id "$RUN_ID" --abort-class safety --reason "ACTUAL_REASON"
    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason pilot_abort
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict rejected --integrity-reason "ACTUAL_REASON"
## Finish every run
Before `stop`:
    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field eligible; final annotation pending"
Then `stop`; wait for finalization:
    tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    read -r -p "Exact DataFlash .bin: " DATAFLASH
    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
KEEP failed/aborted/ineligible runs.
## Decision
After reviewed physical-person evidence, candidate only with ≥3 eligible pairs;
earlier correct-person reacquisition in ≥2; not worse in remaining pair; zero
wrong-person/stale non-zero; zero recovery translation; no added unsafe
motion/saturation/takeover. Otherwise baseline. No field retuning.
## Backup + exit
Mac, every run:
    export RUN_ID="<exact>" TAG="<exact>" PI_FIELD_HOST="192.168.8.174"
    printf -v RUN_NAME "%s__video__%s" "$RUN_ID" "$TAG"
    DEST="$HOME/Developer/Thesis/evidence/field/2026-09-25/$RUN_NAME"; mkdir -p "$DEST"
    rsync -a "francisco@$PI_FIELD_HOST:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" "$DEST/"
    rsync -anc --itemize-changes "francisco@$PI_FIELD_HOST:/home/francisco/Desktop/Thesis-Code/bags/live_camera/$RUN_NAME/" "$DEST/"
Second rsync: no output. Use validated fallback Pi address if needed.
    sudo tools/host/set_pi_network_mode.sh unattended
    sudo tools/host/set_pi_network_mode.sh status
    git status --short
    test ! -e log
    test ! -e hailort.log
Then `docs/issues/p032-final-mounted-runbook.md` with retained #50 policy.
