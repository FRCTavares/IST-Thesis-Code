# 22 September 2026 physical evidence sequence

Status updated 22 September 2026: physical access resumed and the operational
#64 source-resolution decision for the remaining aircraft programme is **VGA
640x480**. The predeclared #64 eight-cell matrix is not complete; the
time-constrained HD comparison is documented as a protocol deviation in
`docs/issues/p064-high-resolution-appearance-source.md`. Proceed to #50 using
VGA, then to #32 only after the #50 controller retain/reject decision.

This sheet preserves the original decision rules and historical #64 procedure
below. Use `docs/flight/README.md` for the detailed aircraft operator procedure
and `docs/issues/p1-14-final-runtime-characterization.md` for the final runtime
contract. Stop on a failed physical prerequisite and retain every failed
attempt.

## Common start and frozen boundaries

On the Pi, with complete hardware physically available:

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
    export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
    export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"
    git status --short
    git rev-parse HEAD
    df -h . /dev/shm
    test -s models/hef/yolov8s.hef
    test -s models/reid/mars-small128.pb
    test -s ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml
    sha256sum models/hef/yolov8s.hef models/reid/mars-small128.pb ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml

A failed test or dirty source requires diagnosis before retained collection.
Do not rebuild, pull, retune TIM-MARS, change tracker/model thresholds, change
the detector's 640x640 inference input, alter the H01-H03 held-out record, or
revive FHD. The operational #64 resolution decision is now frozen as VGA for the remaining
aircraft work. Proceed with #50, then #32 only after #50 records the retained
controller policy. The unfinished #64 matrix may be completed later as
supplementary evidence. Record the actual Git SHA, commands, selected physical
person, camera geometry, FCU mode and hash outputs with each retained run. Each
run gets a unique RUN_ID and tag.

## 1. #64: bounded source-resolution decision, aircraft control OFF

Preconditions: mounted TEVS camera and Hailo are healthy; a comparable
person, scene and lighting are available; no aircraft authority. A distractor
is required only for the conditional small/distant identity comparison after
HD passes the runtime matrix. The remotely enumerated camera was not streamed
on 18 September.
Verify native capture and dashboard geometry from the actual run metadata.
Avoid the active camera stream probe and unnecessary mode restarts.

Run four VGA cells, then four HD cells, in this exact order within each block:

| cell | RES | TRACKER | MEMORY | groups |
| --- | --- | --- | --- | --- |
| 1 | vga | bytetrack | mars | detector,tracker,tim |
| 2 | vga | bytetrack | off | detector,tracker |
| 3 | vga | deepsort | off | detector,tracker |
| 4 | vga | bytetrack | mars | detector,tracker,tim |
| 5 | hd | bytetrack | mars | detector,tracker,tim |
| 6 | hd | bytetrack | off | detector,tracker |
| 7 | hd | deepsort | off | detector,tracker |
| 8 | hd | bytetrack | mars | detector,tracker,tim |

The prepared one-command runner implements the same flags, 240 s resource
measurement, 60 s warm-up, normal stack finalization, and evidence checks:

    tools/experiments/run_p064_cell.sh 1

Use cell numbers `2` through `8` for the remaining rows, in order. It prints
the exact RUN_ID, configuration and bag path, refuses an existing run, and
prompts for a physical target track ID and brief description only in TIM
cells. Select the intended person using the displayed track IDs and dashboard;
keep scene and human motion comparable between matched VGA/HD runs. Raw cells
proceed without selection.
The runner retains invalid attempts, writes `p064_cell_result.json` in each
bag or run log directory, and updates `reports/p064_matrix_summary.json` and
`reports/p064_matrix_summary.md`. Its classification is a runtime-evidence
gate, not a human identity judgment. The manual two-terminal procedure below
remains available for diagnosis.

For each cell, set the table values and a unique TAG such as p064_vga_tim_r1.
In terminal A:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=p064_vga_tim_r1
    export RES=vga TRACKER=bytetrack MEMORY=mars
    ./tools/start_live_stack.sh --res "$RES" --tracker "$TRACKER" --mem "$MEMORY" --record-structured-visual --no-control --tag "$TAG"

For TIM cells, select the intended physical person in the live operator
interface; record its description and selected track ID in the run notes.
Do not silently substitute a different person. In terminal B, after healthy
publication, copy the displayed RUN_ID from terminal A:

    export RUN_ID=REPLACE_WITH_DISPLAYED_RUN_ID
    RUN_DIR="$(readlink -f "ros2_ws/log/live_stack/$RUN_ID")"
    if test -f "$RUN_DIR/pids.txt"; then
        python3 tools/experiments/measure_p032_live_resources.py --run-dir "$RUN_DIR" --architecture-groups detector,tracker,tim --duration-s 240 --warm-up-s 60
    else
        echo "Exact live run not found; do not attach the sampler" >&2
    fi

For raw cells replace architecture groups with detector,tracker. In terminal A
type stop only after the sampler finishes; keep launch failures and sampler
failures. Evidence is in ros2_ws/log/live_stack/<RUN_ID>/p032_resources/
(analysis.json, analysis.md, coverage.json, provenance.json and raw samples)
and bags/live_camera/<RUN_ID>__video__<TAG>/ with the structured bag, visual
file and run metadata. Keep exact run paths; never attach to a stale latest
symlink. After each finalized cell, inspect the complete timing horizon and
all-topic gaps; the large gap threshold keeps internal stalls in the timing
sample population rather than silently selecting short active segments:

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
    python3 tools/analysis/analyse_bag_timing.py "$BAG" --out "$BAG/timing_full_horizon.md" --figdir "$BAG/timing_figures" --gap-ms 1260000

The timing tool still labels its target section active-only; use the large
threshold above and inspect per_topic_quality.json plus the sampler's
bounded coverage. Do not accept from a rate or p95 alone. Keep warm-up and
post-warm-up populations separate in the final #64 report.

The predeclared HD runtime gate applies to every valid HD cell: complete
intervals and required roots, no sustained camera/ROS failure or unexplained
thermal throttling, detector/tracker at least 15 Hz, and no steady-state
publication gap of 0.5 s or more. Both HD TIM cells additionally need
validated-target output at least 15 Hz, p95 e2e_validated_target_ms at most
200 ms, and stale appearance-image skips at most 10% of eligible attempts.
Report the matched VGA values and resource increase. Raw tracker cells have
no TIM authority-latency claim. A camera fault can justify a declared repeat
with the failed attempt retained; a gate failure is a result, not a reason to
keep tuning HD.

If HD fails, retain VGA. If HD passes, capture one representative native-HD
small/distant source with a distractor, crossing or occlusion, exit and re-entry.
This capture is no-control development evidence, not a held-out replacement:

    tools/experiments/record_p064_drone_sequence.sh small_distant_r1

The wrapper records native /camera/image_raw and /detections to RAM first and
copies to bags/source_video/<RUN_ID>__source__p064_drone_small_distant_r1__image_raw_detections/.
Check /dev/shm capacity before capture and keep both copies until hashes and
message cadence are verified. Require the predeclared 3.0 s warm-up exclusion,
exact image/detection timestamp pairing in the retained interval, and no
retained gap of 67 ms or more. The physical target and small-scale interval
must be established by human review before TIM output inspection. Freeze one
ByteTrack candidate stream, then compare native 1280x720 appearance with
INTER_AREA 640x360 complete-frame downsampling from the same frames. Use the
existing deterministic tracker/TIM runners and physical-v2 evaluator; retain
their manifests, source/variant/candidate digests, annotation, and both reports.
The exact target ID and evaluation interval are human decisions, not values to
guess in a shell command.

Native HD must not increase wrong-person or absent-with-output duration beyond
1e-6 s reconciliation tolerance. Then require at least 5 percentage points
more correct authority or 5 points less LOST on the target-present denominator,
or a correct hard-exit/re-entry recovery within 1.0 s without safety regression.
If the matched identity test does not meet that rule, retain VGA. Record the
retain/reject decision before #50 and #32; do not promote from short-run
runtime feasibility alone.

## 2. #50: real FCU and closed-loop controller decision

Preconditions: #64 resolution decision recorded; qualified pilot, spotter,
safe site, battery/RC/manual takeover and geofence ready; Pixhawk attached.
No aircraft motion until the passive, compute-only, restrained/props-off,
controller-process-loss, physical direction and pilot gates pass. The Pi had
no FCU connection on 18 September. The installed field-network configuration
still has an empty approved Pixhawk Wi-Fi fallback setting. #50's inherited
fallback gate must be resolved with an explicitly approved profile before
aircraft operation; do not invent a network profile or credentials.

### Approved field-network fallback operator note

Before #50 aircraft operation, bring the **explicitly approved AERONEXT
local-router** network name/SSID, its NetworkManager connection-profile name,
and the expected Pi IPv4 address/default route for that profile. The
authorised operator provisions credentials in NetworkManager on the Pi;
credentials do not belong in this repository or trial metadata. Enter only
the approved **connection-profile name** as
`THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION` in
`/etc/default/thesis-host-health` (the file read by
`tools/host/set_pi_network_mode.sh`). The primary remains
`ISR Aero.Next GCS`; a management-rescue profile is not a field fallback.

With the real FCU connected, validate both primary-available and
primary-unavailable transitions using
`sudo tools/host/set_pi_network_mode.sh pixhawk` and `status`.
Record the active wlan0 connection, default route, `pixhawk-apm` on eth0
without an eth0 default route, inactive Tailscale, Pixhawk ping/MAVROS
connection and the field preflight result. Exercise the fail-closed case
when neither approved field profile can activate, with the aircraft
disarmed; retain the transition log and restore the primary after the test.
Do not expose a password or PSK in retained output. The #64 no-control
camera decision can proceed without this profile; #50 aircraft operation
cannot proceed while this inherited fallback gate is unresolved. Do not
substitute an unapproved Wi-Fi connection.

Follow docs/flight/README.md in order. With Pixhawk Ethernet connected:

    sudo tools/host/set_pi_network_mode.sh pixhawk
    sudo tools/host/set_pi_network_mode.sh status
    ping -c 3 -W 1 192.168.144.14
    tools/flight/field_preflight_check.sh
    tools/flight/field_preflight_check.sh --passive-live-gate

Require approved field Wi-Fi, no Ethernet default route, inactive Tailscale,
connected MAVROS and passing passive recorder. Do not continue on failure.
Run the compute-only ground gate and restrained command-path gate with the
exact commands in docs/flight/README.md, using the retained --res choice.
At the restrained gate, aircraft disarmed and props removed or safely
restrained, confirm a non-zero reference, then deliberately stop the exact
control_ref_node process while MCAP records. Identify the PID from
ros2_ws/log/live_stack/<RUN_ID>/pids.txt and inspect its process tree before
the action; do not kill by a broad name pattern. Record the operator event and
time, /control_ref/cmd_vel, /mavros/setpoint_velocity/cmd_vel,
/mavros/setpoint_raw/target_local, /mavros/state and FCU/ground-station
response. Use the exact tracked run; if the child PID is ambiguous, stop the
test and resolve it before signalling anything:

    stop_exact_controller() {
        local run_dir launch_pid exe_pid
        run_dir="ros2_ws/log/live_stack/$RUN_ID"
        test -f "$run_dir/pids.txt" || { echo "Run PID file missing" >&2; return 1; }
        launch_pid="$(awk '$2=="control" {print $1}' "$run_dir/pids.txt")"
        test -n "$launch_pid" || { echo "Control launcher PID missing" >&2; return 1; }
        exe_pid="$(pgrep -P "$launch_pid" -f control_ref_node || true)"
        test "$(printf '%s\n' "$exe_pid" | sed '/^$/d' | wc -l)" -eq 1 || { echo "Control executable PID ambiguous" >&2; return 1; }
        ps -p "$launch_pid","$exe_pid" -o pid,ppid,args || return 1
        date --iso-8601=ns | tee "$run_dir/controller_process_loss.txt"
        kill -KILL "$exe_pid" || return 1
        date --iso-8601=ns | tee -a "$run_dir/controller_process_loss.txt"
    }
    stop_exact_controller

The pilot and FCU observer must be ready before the kill. Record the
process-loss trial_start/abort or verdict events with the exact RUN_ID. A killed
process cannot publish a graceful final zero. Require
documented fail-closed FCU response and pilot takeover; if stale non-zero
authority persists or response cannot be established, STOP before flight.

For the retained physical comparison, use the baseline command from
docs/flight/README.md first, then the candidate command only after a clean
baseline and pilot go decision:

    ./tools/start_live_stack.sh --res "$RETAINED_RES" --field-record --control-mavros --tag "$TAG"
    ./tools/start_live_stack.sh --res "$RETAINED_RES" --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"

Run approximately three eligible matched pairs of the same target and
controlled loss/re-entry situation, alternating order baseline/candidate,
candidate/baseline, baseline/candidate if conditions allow. Declare each
pair's target, route, loss opportunity and fixed 10.0 s observation
horizon before the pair. Eligibility requires at least 3.0 s of visible
trusted LOCKED control before loss, a safe observable target loss, and a
comparable return opportunity in both conditions. A stopped/aborted/ineligible trial stays in the record;
mark its reason and do not silently count it as a successful recovery.
Right-censor when the target does not return within the declared horizon,
recording both the elapsed observation and why it ended.

For every trial use operator_event.py trial_start, target_selected, trial_end;
on a takeover or abort add operator_takeover/abort and trial_verdict, with
condition baseline or candidate matching the launch. The full syntax is in
docs/flight/README.md and tools/live/operator_event.py --help. Preserve
MCAP, visual recording, target-authority events, operator events, run logs,
provenance, exact DataFlash .bin, failed starts, takeovers and aborted trials.
For each exact RUN_ID/TAG after normal stop:

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events
    python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
    python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
    python3 tools/analysis/summarize_control_diagnostics.py "$BAG"
    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events

Set DATAFLASH to the exact human-identified .bin path, never latest. For a failed or interrupted run, preserve the bag first and run each verifier that can still complete; document the missing artifact rather than fabricate it. Review
command/diagnostic pairing, FCU echo, timestamps, authority state, physical
person, correct/lost/absent durations, wrong-person non-zero command duration,
recovery timing, saturation, and aborts. Any wrong-person non-zero command,
unsafe motion, failed RC takeover, stale authority or unexpected mode/arming
is an immediate pilot abort and blocks promotion. Retain bounded yaw only with at least three eligible matched pairs, correct
physical-target reacquisition earlier than baseline within the 10.0 s
horizon in at least two pairs, no later reacquisition or worse censoring in
the remaining pair, zero wrong-person non-zero command duration, no
stale/invalid non-zero command, no translational command during recovery,
and no additional unsafe motion, saturation or takeover. If any condition
fails or fewer than three eligible pairs are obtained, retain baseline
hover/zero and report the candidate as unpromoted. Report per-pair outcomes
descriptively; this small sample does not establish statistical superiority.
Do not redesign the recovery controller at the site.

## 3. #32: final mounted integrated runtime

Preconditions: #64 source resolution and #50 controller policy are recorded
and retained; Pi, camera, Hailo and FCU are mounted in the final configuration.
Run stationary, disarmed and restrained/props-off with qualified supervision;
this is integrated runtime evidence, not 20 minutes of flight evidence. Use
the retained controller option and same recording/UI load as the final stack.
No run before both decisions.

In terminal A, set RETAINED_RES to vga or hd and set RECOVERY_FLAGS to the
empty array for hover/zero, or to the two candidate flags if that policy was
retained:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=p032_final_mounted
    export RETAINED_RES=vga
    RECOVERY_FLAGS=()
    ./tools/start_live_stack.sh --res "$RETAINED_RES" --field-record --control-mavros "${RECOVERY_FLAGS[@]}" --tag "$TAG"

Only if yaw was retained, first set:

    RECOVERY_FLAGS=(--control-yaw-recovery --acknowledge-yaw-recovery-candidate)

In terminal B, copy the exact displayed RUN_ID and attach once after healthy
publication:

    export RUN_ID=REPLACE_WITH_DISPLAYED_RUN_ID
    RUN_DIR="$(readlink -f "ros2_ws/log/live_stack/$RUN_ID")"
    if test -f "$RUN_DIR/pids.txt"; then
        python3 tools/experiments/measure_p032_live_resources.py --run-dir "$RUN_DIR" --architecture-groups detector,tracker,tim,controller --duration-s 1260 --warm-up-s 60
    else
        echo "Exact live run not found; do not attach the sampler" >&2
    fi

Let the helper finish; stop the stack normally. Retain
ros2_ws/log/live_stack/<RUN_ID>/p032_resources/{provenance.json,coverage.json,
analysis.json,analysis.md,process_trees/,hardware/} and the exact
bags/live_camera/<RUN_ID>__video__p032_final_mounted/ package. Run the same
package, bag-topic and controller-diagnostic checks shown for #50. Also run:

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    python3 tools/analysis/analyse_bag_timing.py "$BAG" --out "$BAG/timing_full_horizon.md" --figdir "$BAG/timing_figures" --gap-ms 1260000
    sha256sum "$BAG"/*.mcap "$BAG"/run_metadata.json "$RUN_DIR"/p032_resources/analysis.json "$RUN_DIR"/p032_resources/provenance.json

Interpret the timing markdown with per_topic_quality.json and coverage.json;
the timing tool's nominal active-only label does not replace bounded-interval
gap/root checks. Hash the MCAP, config, models, manifests and reports; record any unavailable direct
Hailo-utilization or electrical-power measurement as unavailable.

Accept #32 only if all required PID roots and complete bounded sampler
intervals pass integrity, the full interval including stalls is reported,
the final validated-target rate is at least 10 Hz (15 Hz remains desirable),
and p95 camera-to-validated-target processing latency is at most 200 ms.
Report controller command cadence/jitter, latency endpoints, drops/gaps,
selective ReID workload, CPU/RSS, temperature/clocks/throttling,
accelerator contention and raw-image/transport cost. Investigate any
non-zero throttling, root loss, service error or sustained memory decline.
A run below the minimum rate, above the p95 limit, or with incomplete
coverage is failed evidence and cannot support the final onboard claim.
Keep it, diagnose, then repeat only after declaring the reason. Do not
substitute replay or isolated Hailo numbers for this measurement.

After each stage record the decision and retained paths in the relevant issue.
Only after all three stages can #39 freeze final thesis claims.
