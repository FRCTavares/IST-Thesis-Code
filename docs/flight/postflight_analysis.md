# #50 post-flight evidence-to-results workflow

Use after each Friday run, then across the matched pairs. This is an analysis
checklist, not a new flight procedure or a change to the frozen #50 promotion
criteria. The canonical field sheet remains `docs/flight/field_day_runbook.md`.

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

The field MCAP intentionally has **no image topic**. Rosbag receipt times
are Pi system-clock epoch nanoseconds; camera and controller message headers
also use the live ROS system clock (no simulated time). Operator events retain
UTC plus monotonic samples, with a clock pair at `trial_start`.

The separate MJPEG/MKV receives dashboard frames over HTTP. ffmpeg stamps
input packets from its **system wall clock** and rebases the Matroska packet
PTS to the first input packet; the saved `creation_time` and
`run_metadata.json.visual.started_at_utc` are the **pre-launch** UTC value,
not first-frame UTC. The camera-origin header timestamp is lost at the HTTP
video boundary. The actual rate is variable: the retained VGA #64 file has
2,143 packets over 285.72 s (7.50 fps) and a 1.0 s maximum packet gap;
the protocol-deviation HD file has 905 over 282.16 s (3.21 fps) and a
2.8 s gap. The stream's nominal 25 fps is not its measured rate. Use each
packet PTS, never frame index divided by requested or nominal fps.

After the normal package check, compute **conditional ffmpeg packet-receipt**
windows for the exact run (once; do not overwrite an existing result):

```bash
python3 tools/analysis/bound_visual_mcap_time.py --bag-dir "$BAG" --run-id "$RUN_ID" --json-out "$BAG/visual_packet_receipt_bounds.json" --csv-out "$BAG/visual_packet_receipt_bounds.csv"
```

The helper requires a passed visual verifier, matching RUN_ID, intact
finalized-file mtime, nondecreasing packet PTS/count, and the reviewed nominal
25-Hz MJPEG timebase. Let `L` be ffmpeg pre-launch UTC, `F` the finalized
file mtime, `p_i` a packet PTS, `p_0` the first, `p_N` the last, and `q`
the larger of one nominal 25-Hz input tick (40 ms) and the observed minimum
positive PTS increment. Under continuous system wall time,
authentic original mtime, and this ffmpeg timestamp contract, packet `i`
reached ffmpeg in the conservative UTC interval
`[max(L, L + p_i - p_0 - q), F - (p_N - p_0) + (p_i - p_0) + 2q]`.
The first packet is bounded by `[L, F - (p_N - p_0) + q]`.
The extra ticks cover rebasing/quantization; they are not camera-to-recorder
latency estimates. The older #64 VGA run gives a conditional first-packet
window of 0.380 s and a maximum per-packet window of 0.460 s using its
current filesystem mtime. Its old visual status did **not** pin that mtime,
so this demonstration is diagnostic rather than certified provenance.
New runs retain the finalized mtime in `visual_evidence_status.json` and
the helper refuses an altered copy. Check operator-event wall/monotonic
pairs for clock discontinuities; an unresolved clock jump invalidates the
conditional bound.

**Packet receipt is not camera capture.** The dashboard image keeps its
camera source stamp inside ROS, but neither that stamp nor a per-frame identity
is carried into the MKV or field MCAP. The capture-to-HTTP/ffmpeg delay has
no measured upper bound in the current evidence. Therefore the packet-receipt
CSV alone cannot align physical-person identity to controller commands or
prove zero wrong-person non-zero duration. The physical-v2 evaluator requires
source-timestamped image/reference bags; do not feed it this video as though
its PTS were source timestamps.

Start from `docs/results/live/templates/p050_visual_alignment.json`.
For each scientific attempt, retain original packet PTS, intended physical
person, presence/occlusion/out-of-FOV and distractor intervals, independently
reviewed cross-modal anchors if available, their method and uncertainty,
annotator, and every visual coverage gap. Tie operator `target_selected` to
the dashboard selection transaction; tracker ID and TIM-MARS LOCKED are not
physical truth. An annotation interval maps to command time only through
a separately justified **source-capture** interval. Expand interval endpoints
by its uncertainty; missing packets and uncovered transitions remain
unresolved. If any possible wrong-person interval overlaps a non-zero
command, report unresolved or wrong-person duration as supported, **never
zero by default**. Candidate promotion remains blocked unless every relevant
non-zero command can be attributed with adequate physical-person coverage.

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
all frozen conditions in `docs/flight/field_day_runbook.md`: at least three eligible
pairs, earlier correct reacquisition in at least two, no later/worse censoring
in the remaining pair, zero wrong-person/stale non-zero command and recovery
translation, and no added unsafe motion, unacceptable saturation or takeover.
Otherwise retain baseline and state why candidate was unpromoted. This is
descriptive evidence, not statistical superiority.

After #50's controller decision, execute #32 using
`docs/issues/p032-final-mounted-runbook.md`; only then freeze #39 claims.
