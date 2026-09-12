# #50 / #74 field-day runbook (copy-paste)

The compact go/no-go checklist is `docs/flight/README.md`; this is the
step-by-step command reference so nothing depends on memory. Aircraft
operation is still gated by every check in that sheet. **The baseline command
never enables candidate recovery.**

## Two mappings from perception state to permitted motion (perception-conditioned motion authority)

The controller law and TIM-MARS identity decisions are unchanged between
conditions; only the mapping from perception state to permitted motion changes.

| Perception state | Baseline | Candidate |
| --- | --- | --- |
| trusted selected person | normal following | normal following |
| LOST/uncertain, no eligible recent trusted evidence | no motion (hover) | no motion (hover) |
| LOST + eligible recent trusted evidence | no motion (hover) | bounded yaw-only recovery (no translation) |

Safety invariant (both): **translational following authority requires current
trusted selected-person perception.**

---

## 1. Before leaving home

```bash
cd ~/Desktop/Thesis-Code || exit 1
export GIT_PAGER=cat PAGER=cat
git checkout main && git pull --ff-only
git status --short                       # must be clean
tools/thesis_build.sh --packages-select thesis_msgs thesis_bringup
source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash
df -h /                                  # >= 40 GiB free for --record-raw
python3 tools/analysis/validate_tim_evaluation_split.py \
    docs/data/splits/tim_mars_split_v4.json --verify-hashes   # final_ready=0/3
sha256sum models/hef/yolov8s.hef models/reid/mars-small128.pb \
    ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml
bash tools/start_live_stack.sh --help | grep -E 'field-record|control-mavros|control-yaw-recovery'
```

## 2. At IST, before flight

```bash
sudo tools/host/set_pi_network_mode.sh pixhawk
sudo tools/host/set_pi_network_mode.sh status
nmcli -t -f ACTIVE,SSID dev wifi         # ISR preferred; approved AERONEXT fallback
ip route                                 # pixhawk-apm present, never default route
systemctl is-active tailscaled           # inactive
ls -l /dev/video0 /dev/media0 /dev/hailo0
ros2 topic echo /mavros/state --once     # after MAVROS is up: connected: true
```

Decide the trial condition and run id before recording:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"     # deterministic; reused everywhere
echo "$RUN_ID"
```

## 3. Start the stack

Baseline:

```bash
./tools/start_live_stack.sh --field-record --record-raw --control-mavros --tag flight1_baseline
```

Candidate (only when the #50 recovery promotion is explicitly intended):

```bash
./tools/start_live_stack.sh --field-record --record-raw --control-mavros \
  --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag flight1_candidate
```

The launcher prints the run id and the matching `operator_event.py trial_start`
command; it also refuses to record into an existing non-empty bag directory.

## 4. During the trial

```bash
# in the live-stack> prompt: ids ; target <id>
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" \
    --condition baseline --scenario following                 # or: --condition candidate --recovery-enabled
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" \
    --track-id <id> --intended-physical-person "person in red"
# as needed:
python3 tools/live/operator_event.py unexpected_behavior --run-id "$RUN_ID" --description "..."
python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" --trigger pilot_rc
python3 tools/live/operator_event.py abort --run-id "$RUN_ID" --abort-class safety --reason "..."
```

## 5. Controlled stop

For a nominally completed trial, record `trial_end` **before** stopping the stack so it is present when `stop_stack` archives `operator_events.jsonl`:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

Then, at the `live-stack>` prompt type `stop` (or Ctrl-C once). The stack then, in order:

1. stops the application nodes first — the controller emits its final
   safe-zero and shutdown diagnostic while the recorders are still running;
2. waits `STOP_APP_SETTLE_S` (2 s) so the last messages are recorded;
3. sends SIGINT to the recorder(s) and waits up to `RECORDER_FINALIZE_GRACE_S`
   (10 s) for recorder exit after flushing/finalizing, escalating to SIGTERM
   then SIGKILL only if needed; the subsequent integrity check requires
   finalized `metadata.yaml` and non-empty MCAP storage (and it says whether finalization was graceful);
4. archives `run_logs/` (`control.log`, `dashboard_bridge.log`,
   `target_memory_mars.log`, `operator_events.jsonl`, `recorder_finalize_outcome.txt`,
   `archive_manifest.json`) and `target_authority_events.jsonl` next to the bag;
5. writes `bag_integrity.json` and `evidence_package_status.json` beside the bag
   and prints **`EVIDENCE PACKAGE INCOMPLETE`** if anything is missing.

```bash
cat "bags/live_camera/${RUN_ID}__video__flight1_baseline/evidence_package_status.json"
```

## 6. Before disconnecting the Pixhawk

Retrieve the native ArduPilot DataFlash `.bin` with the actual field tooling
(Mission Planner / MAVProxy `log download`, QGC, or a wired SD-card copy),
identify the exact file for this trial, then:

```bash
BAG="bags/live_camera/${RUN_ID}__video__flight1_baseline"
python3 tools/live/archive_pixhawk_dataflash.py \
  --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin /path/to/<this-trial>.bin
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" \
  --control-trial --field-record --expect-operator-events
```

> **Real-hardware DataFlash retrieval is verification-pending** — there is no
> Pixhawk to test the download step against. The archive helper is validated
> for an explicitly-supplied file only; do not "select the latest log".

```bash
sudo tools/host/set_pi_network_mode.sh unattended
```

## 7. Later (home)

- physical-v2 annotation of the retained imagery
  (`tim_physical_target_bbox_v2`, see `docs/issues/p1-10-physical-reference-v2-contract.md`);
- the final #50/#74 scientific analysers.

`evidence_package_status.json` reports `pending_postflight_annotation` /
`pending_pixhawk_dataflash` until those exist; a package is never
scientifically final on the Pi-side runtime files alone.
