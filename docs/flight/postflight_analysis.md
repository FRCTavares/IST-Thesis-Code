# #50 post-flight evidence-to-results workflow

Use after each Friday run, then across the matched pairs. This is an analysis
checklist, not a new flight procedure or a change to the frozen #50 promotion
criteria. The canonical field sheet remains `docs/flight/README.md`.

## 1. Resolve and preserve each exact attempt

From recorded RUN_ID and TAG, never a `latest` link:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
read -r -p "Exact RUN_ID: " RUN_ID; export RUN_ID
read -r -p "Exact TAG: " TAG; export TAG
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
test -d "$BAG" || { echo "Exact bag missing" >&2; exit 1; }
```

Inventory `run_metadata.json`, `flight_metadata.txt`, finalized MCAP and
`metadata.yaml`, `visual_<RUN_ID>.mkv`, `visual_evidence_status.json`,
`target_authority_events.jsonl`, `run_logs/operator_events.jsonl`,
`run_logs/archive_manifest.json`, control/MAVROS topics and exact DataFlash.
Reconcile RUN_ID, TAG, condition and recovery flag across metadata, launcher
command and `trial_start`; disagreement rejects the attempt. Keep failed,
aborted and ineligible runs in the inventory.

## 2. Runtime/transport and FCU evidence

```bash
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
python3 tools/analysis/summarize_control_diagnostics.py "$BAG" --out "$BAG/control_diagnostics_summary.json"
```

Omit `--control-trial` and the diagnostics command for no-control attempts.
If DataFlash was not yet archived, a pending postflight result is expected;
archive only the human-selected exact `.bin` via
`tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"`,
then rerun verification. Preserve the source and manifest. Check MCAP
finalization, observed-zero transport, visual decode, command/diagnostic and
controller/MAVROS pairing, FCU echo/state/pose/velocity and DataFlash time
range. A command is not an aircraft response.

## 3. Physical-person reference and time alignment

The field MCAP intentionally has **no image topic**. The separate 640x480
MJPEG visual has about 10 fps and Matroska PTS relative to its first frame
from ffmpeg input wallclock. `run_metadata.json.visual.started_at_utc` is the
recorder-launch time, **not** an exact first-frame acquisition timestamp.
The existing physical-v2 evaluator is for source-timestamped image/reference
bags; do not run it on a field video as if its frame timestamps were identical
to ROS source-image timestamps.

Start from the unpopulated
`docs/results/live/templates/p050_visual_alignment.json` and retain a
physical-person annotation and explicit alignment record for each scientific
trial: original video/frame or PTS, intended physical person,
presence/occlusion/out-of-FOV state, distractors, target loss and correct
return, reproducible visual-to-MCAP anchors, alignment method, estimated
uncertainty, annotator and review. Tie operator `target_selected` to the
dashboard selection transaction in `target_authority_events.jsonl`; a
requested track ID is not physical truth. Preserve visible ambiguous
intervals as unresolved; do not assign false precision to a 10 fps visual or
count TIM-MARS LOCKED as correct physical-person identity. If alignment or
image coverage cannot distinguish a wrong-person command, the safety result
is **unresolved and candidate promotion is blocked**.

## 4. Controller-facing durations and pair eligibility

Reconstruct the complete command timeline from `/control_ref/cmd_vel` and
`/control_ref/diagnostics`, cross-check
`/mavros/setpoint_velocity/cmd_vel`, `/mavros/setpoint_raw/target_local`,
MAVROS state and native DataFlash. Use physical annotation to classify command
intervals as correct target, wrong person, lost/hover, absent, or unresolved.
Report non-zero wrong-person, stale/invalid non-zero and candidate recovery
translation durations explicitly; keep command values separate from observed
aircraft motion. Record saturation, pilot abort/takeover, process-loss and
recorder failure. Do not invent a zero when a stream or attribution is absent.

For each attempt record visible trusted LOCKED control before loss (must be
>=3.0 s), safe observable loss, the pair's predeclared target/route/loss
opportunity, and comparable return opportunity. Record each 10.0 s horizon,
correct physical-person return time or right-censor at the horizon, plus the
observation actually completed. Keep rejected/ineligible/aborted attempts with
their reasons; only eligible matched baseline/candidate pairs enter the
descriptive comparison. The pair order is 1 baseline→candidate, 2
candidate→baseline, 3 baseline→candidate unless a documented safe deviation
was declared before outcomes were seen.

## 5. Decision and thesis outputs

Fill `docs/results/live/templates/p050_matched_pairs.md` only from reviewed
per-run records. Retain a machine-readable companion with RUN_ID, TAG, exact
bag path, Git SHA, annotation/alignment/DataFlash paths and hashes, eligibility,
censoring, per-pair comparison and every safety flag. All cells stay
`PENDING_PHYSICAL_EVIDENCE` until supported. Candidate promotion requires
all frozen conditions in `docs/flight/README.md`: at least three eligible
pairs, earlier correct reacquisition in at least two, no later/worse censoring
in the remaining pair, zero wrong-person/stale non-zero command and recovery
translation, and no added unsafe motion, unacceptable saturation or takeover.
Otherwise retain baseline and state why candidate was unpromoted. This is
descriptive evidence, not statistical superiority.

After #50's controller decision, execute #32 using
`docs/issues/p032-final-mounted-runbook.md`; only then freeze #39 claims.
