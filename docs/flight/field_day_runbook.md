# #50 / #74 field-day runbook (copy-paste)

The compact go/no-go checklist is `docs/flight/README.md`; this is the
step-by-step command reference so nothing depends on memory. Aircraft
operation is still gated by every check in that sheet. **The baseline command
never enables candidate recovery.** The 14 September no-MAVROS structured-bag plus separate-MJPEG development runs reached observed_zero transport loss at near-30 Hz structured cadence with roughly 10 fps visual evidence. The exact MAVROS-inclusive profile still requires a representative safe field-ground run with a visible target before aircraft evidence is accepted. Do not add paired raw: full-stack tests lost 52–68% of inferred source frames. The source-only H01/H02/H03 procedure is unchanged.

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

## 1. Offline repository precheck

No field step requires internet, a Git pull, or Tailscale.

```bash
cd /home/francisco/Desktop/Thesis-Code || exit 1
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
set +u
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
git --no-pager log -1 --oneline
git status --short
df -h "$PWD" "$PWD/bags"
python3 tools/analysis/validate_tim_evaluation_split.py   docs/data/splits/tim_mars_split_v4.json --verify-hashes
bash tools/start_live_stack.sh --help |   rg 'field-record|record-structured-visual|control-mavros|no-control'
```

## 2. GCS-only field network and hardware check

Use `ssh francisco@192.168.8.174` from the Mac after joining
`ISR Aero.Next GCS`. The complete expected-address, Rescue, and reconnect
procedure is section 2 of `docs/flight/README.md`.

```bash
sudo tools/host/set_pi_network_mode.sh pixhawk
sudo tools/host/set_pi_network_mode.sh status
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show eth0
ip route show default
ip route show default dev eth0
ping -c 3 -W 1 192.168.144.14
systemctl is-active tailscaled
ls -l /dev/video0 /dev/media0 /dev/hailo0
hailortcli scan
```

Field state requires GCS Wi-Fi, `pixhawk-apm` with no Ethernet default
route, reachable Pixhawk, and inactive Tailscale. MAVROS is launcher-owned; do
not start a separate instance.

## 2A. Passive MAVROS recording-capacity ground gate

Before aircraft evidence, perform the exact disarmed, stationary, visible-person
gate from section 4 of `docs/flight/README.md`:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=capacity_ground_r1
echo "RUN_ID=$RUN_ID"
./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"
```

This is structured non-image MCAP plus separate MJPEG and passive MAVROS.
Require connected/armed-false telemetry, visible target/distractor evidence,
graceful finalization, and `observed_zero` transport loss before flight.

## 2B. Required moving-platform TIM-MARS trial

Before treating the later closed-loop flights as representative UAV evidence,
capture one manual-pilot moving-platform TIM-MARS trial.

This trial is **not** a closed-loop controller test:

- pilot owns all aircraft motion;
- TIM-MARS/tracker may run;
- MAVROS may record telemetry;
- `--no-control` is mandatory so `control_ref_node` does not run;
- `--control-mavros` must remain absent;
- H01/H02/H03 remain untouched.

Detailed choreography and acceptance criteria:

`docs/flight/P050_DYNAMIC_UAV_TIM_TRIAL.md`

Choose the run id:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=dynamic_uav_tim_manual_r1
    echo "RUN_ID=$RUN_ID"

Start retained evidence capture:

    ./tools/start_live_stack.sh \
        --field-record \
        --no-control \
        --tag "$TAG"

Required motion includes lateral translation, range/scale change, yaw/viewpoint
change, simultaneous target + UAV motion, a distractor interaction, and—when
safe—a brief visibility-loss/recovery event from a changed UAV viewpoint.

After this trial is safely stopped and its evidence package retained, continue
with the controller trials below.

Decide the closed-loop trial condition and run id before recording:

```bash
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"     # deterministic; reused everywhere
echo "$RUN_ID"
```

## 3. Start a controller trial

Baseline, only after every physical gate in the canonical sheet passes:

```bash
export TAG=flight1_baseline
./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"
```

Candidate, only when the #50/#74 recovery promotion is explicitly intended:

```bash
export TAG=flight4_yaw_recovery_candidate
./tools/start_live_stack.sh --field-record --control-mavros   --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

The launcher prints the run id and refuses an existing non-empty bag path.

## 4. Operator events from Terminal B

Set the exact run id printed by Terminal A:

```bash
read -r -p "RUN_ID printed by Terminal A: " RUN_ID; export RUN_ID
```

Baseline start:

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition baseline --scenario following
```

Candidate start:

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID"   --condition candidate --scenario yaw_recovery --recovery-enabled
```

After `ids` and `target <id>` at the live prompt:

```bash
read -r -p "Visible person description: " PERSON
read -r -p "Track ID: " TRACK_ID
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID"   --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Use only supported event names. Exact loss/crossing scenarios and safety-event
commands are in section 8 of `docs/flight/README.md`.

## 5. Controlled stop

For a nominally completed trial, record `trial_end` **before** stopping the stack so it is present when `stop_stack` archives `operator_events.jsonl`:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

Then, at the `live-stack>` prompt type `stop` (or Ctrl-C once). The stack then, in order:

1. finalizes the separate visual recorder while its local HTTP source remains available;
2. stops the application nodes first — the controller emits its final
   safe-zero and shutdown diagnostic while the recorders are still running;
3. waits `STOP_APP_SETTLE_S` (2 s) so the last messages are recorded;
4. sends SIGINT to the structured recorder and waits up to `RECORDER_FINALIZE_GRACE_S`
   (10 s) for recorder exit after flushing/finalizing, escalating to SIGTERM
   then SIGKILL only if needed; the subsequent integrity check requires
   finalized `metadata.yaml` and non-empty MCAP storage (and it says whether finalization was graceful);
5. archives `run_logs/` (`control.log`, `dashboard_bridge.log`,
   `target_memory_mars.log`, `operator_events.jsonl`, `recorder_finalize_outcome.txt`,
   `archive_manifest.json`) and `target_authority_events.jsonl` next to the bag;
6. writes `bag_integrity.json` plus `visual_evidence_status.json`, `recorder_transport_status.json` and `evidence_package_status.json` beside the bag
   and prints **`EVIDENCE PACKAGE INCOMPLETE`** if anything is missing.

```bash
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"; export BAG
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID"   --field-record --expect-visual --expect-operator-events
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
```

## 6. Before disconnecting the Pixhawk

Retrieve the exact native ArduPilot DataFlash file with Mission Planner,
MAVProxy, QGC, or a wired SD-card copy. Never select a file by assuming the
latest one belongs to this trial.

```bash
read -r -p "Exact DataFlash .bin path: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID"   --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG"   --run-id "$RUN_ID" --control-trial --field-record   --expect-visual --expect-operator-events
```

Real-hardware DataFlash retrieval remains verification-pending; the archive
helper only validates the explicitly supplied file. After Pixhawk disconnect:

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
