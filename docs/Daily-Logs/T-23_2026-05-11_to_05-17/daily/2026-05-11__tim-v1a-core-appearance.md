# Daily Log - 2026-05-11 - TIM-V1A Core Appearance Cue

## Goal

Resume thesis development and advance from TIM-V0 towards TIM-V1.

## Starting point

Repository was clean at the beginning of the session.

Relevant previous commits:

- 4d1df65 05-09-2026: Add TIM-V1A appearance feature utilities
- 1375ebe 05-09-2026: Prepare TIM field recording and TIM-V1A design

Existing baseline tests passed after disabling ROS pytest plugin autoload.

Command used:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/thesis_bringup/test/test_appearance_memory.py src/thesis_bringup/test/test_target_memory_synthetic.py -q

Result:

    20 passed

## TIM-V1A core appearance cue integrated

Implemented TIM-V1A inside the ROS-free TargetIdentityMemory core.

Changed files:

- ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py
- ros2_ws/src/thesis_bringup/test/test_target_memory_appearance.py

Main changes:

- CandidateTrack now supports optional appearance features.
- CandidateScore now reports appearance similarity and whether appearance was used.
- TargetMemoryConfig now exposes optional TIM-V1A appearance parameters:
  - appearance_enabled
  - appearance_weight
  - appearance_min_similarity
  - appearance_update_alpha
  - appearance_ambiguous_only
- Appearance remains disabled by default, preserving TIM-V0 behaviour.
- Appearance is used only as a gated tie-breaker.
- Appearance cannot rescue geometrically implausible candidates.
- Appearance memory updates only when the state is confirmed as LOCKED.
- Appearance memory freezes during UNCERTAIN, LOST, and REACQUIRED.

## Safety correction

Initial test feedback showed that a strong appearance score could rescue a far-away geometrically implausible candidate.

This was corrected by adding a geometry plausibility gate before applying the appearance bonus.

Interpretation:

- appearance can resolve ambiguous nearby candidates
- appearance cannot make TIM follow a far-away lookalike

## Validation

Command used:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/thesis_bringup/test/test_appearance_memory.py src/thesis_bringup/test/test_target_memory_synthetic.py src/thesis_bringup/test/test_target_memory_appearance.py -q

Result:

    25 passed

Syntax check:

    python3 -m py_compile ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py ros2_ws/src/thesis_bringup/thesis_bringup/appearance_memory.py ros2_ws/src/thesis_bringup/test/test_target_memory_appearance.py

Result:

- passed

## Commit

- 46bbd07 05-11-2026: Integrate TIM-V1A appearance cue

## Interpretation

TIM-V1A core logic is now implemented and unit-tested.

This is not live image integration yet. The ROS wrapper does not yet extract appearance features from camera images.

## Next step

Implement TIM-V1B:

- connect appearance extraction to target_memory_node.py
- subscribe to an image topic only when appearance is enabled
- extract per-track appearance features from the latest image
- keep the feature path disabled by default
- preserve TIM-V0 live behaviour unless explicitly enabled

---

## TIM-V1B ROS wrapper appearance extraction added

Integrated optional image-based appearance extraction into `target_memory_node.py`.

Changed file:

- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/target_memory_node.py

Main changes:

- Added `appearance_enabled` parameter, disabled by default.
- Added optional image subscription only when appearance is enabled.
- Default appearance image topic is `/camera/dashboard`.
- Converts latest image to BGR using `cv_bridge`.
- Extracts HSV upper/lower appearance features for each candidate track.
- Passes extracted features into `CandidateTrack(..., appearance=feature)`.
- Adds appearance diagnostics to `/target_memory/status`.
- Preserves TIM-V0 live behaviour when `appearance_enabled:=false`.

Validation:

- `colcon build --symlink-install --packages-select thesis_bringup`
- `timeout 5s ros2 run thesis_bringup target_memory_node --ros-args -p appearance_enabled:=false`
  - result: node started cleanly, timeout exit code 124
- `timeout 5s ros2 run thesis_bringup target_memory_node --ros-args -p appearance_enabled:=true -p appearance_image_topic:=/camera/dashboard`
  - result: node started cleanly, timeout exit code 124
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/thesis_bringup/test/test_appearance_memory.py src/thesis_bringup/test/test_target_memory_synthetic.py src/thesis_bringup/test/test_target_memory_appearance.py -q`
  - result: 25 passed

Interpretation:

TIM-V1B now connects the ROS wrapper to image-based appearance features while keeping the feature path opt-in. This gives a safe live integration path for TIM-V1 without changing the default live-stack behaviour.

Next step:

Run a live or replay smoke test with `appearance_enabled:=true` and confirm that `/target_memory/status` reports non-zero appearance values when a selected target is visible.

---

## TIM-V1D live-stack appearance flags added

Added live-stack CLI support for TIM-V1B appearance extraction.

Changed files:

- tools/lib/live_defaults.sh
- tools/lib/live_cli.sh
- tools/lib/live_usage.sh
- tools/start_live_stack.sh

New flags:

- `--target-memory-appearance`
- `--no-target-memory-appearance`
- `--target-memory-appearance-image-topic <topic>`
- `--target-memory-appearance-min-bbox-height <px>`
- `--target-memory-appearance-max-image-age-ms <ms>`

Default behaviour:

- TIM remains enabled by default.
- TIM appearance remains disabled by default.
- Normal live-stack behaviour is preserved unless `--target-memory-appearance` is explicitly used.

Validation:

- `./tools/start_live_stack.sh --help`
- `./tools/start_live_stack.sh --help-advanced`
- `bash -n tools/start_live_stack.sh`
- `bash -n tools/lib/live_cli.sh`
- `bash -n tools/lib/live_defaults.sh`
- `bash -n tools/lib/live_usage.sh`

Interpretation:

The live stack can now start TIM with image-based appearance extraction through an explicit opt-in flag, without changing the default runtime path.

---

## TIM-V1D live validation

Started the live stack with TIM appearance enabled:

    ./tools/start_live_stack.sh --profile safe-camera --target-memory --target-memory-appearance --target-memory-appearance-image-topic /camera/dashboard

Startup result:

- Live stack started successfully.
- Capture: 640x480.
- Published perception image: 640x640.
- Detector: single-process Hailo direct backend.
- Tracker: OC-SORT.
- A `/camera/image_raw` readiness warning appeared, but the launcher continued because camera FPS was active.

TIM node validation:

- `target_memory_node` launched successfully.
- `appearance_enabled=True`.
- `appearance_image_topic=/camera/dashboard`.
- `/target_memory/status` published JSON diagnostics with appearance fields.

Observed topic rates:

- `/camera/dashboard`: approximately 12 Hz during the check.
- `/tracks`: approximately 16 Hz during the check.
- `/target_memory/status`: approximately 16 to 17 Hz during the check.

Observed status sample:

- `appearance`: 0.0
- `appearance_used`: false

Interpretation:

The live TIM-V1B path is wired correctly and does not crash. Appearance use may remain false during normal stable tracking because the appearance cue is intentionally gated and mainly used for ambiguity, loss, and reacquisition. Further validation requires a selected target plus an ambiguity or ID-switch scenario.

---

## TIM-V1E deterministic image-derived appearance proof

Added a deterministic test proving that image-derived appearance features can influence TIM matching.

Test added:

- `test_image_derived_appearance_can_change_tim_match_decision`

Scenario:

- Frame 0: operator selects a red target.
- The node helper extracts the red appearance feature from the synthetic image.
- Frame 1: two candidates appear:
  - a geometrically closer blue candidate
  - a shifted red candidate
- TIM uses the image-derived appearance feature and selects the red candidate.

Important observation:

- The first version of the test failed because TIM made the red candidate the best candidate, but still rejected the switch as ambiguous.
- This was correct behaviour.
- The test was adjusted with a smaller `ambiguity_margin` so it isolates the image-derived appearance matching path.

Validation:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/thesis_bringup/test/test_appearance_memory.py src/thesis_bringup/test/test_target_memory_synthetic.py src/thesis_bringup/test/test_target_memory_appearance.py src/thesis_bringup/test/test_target_memory_node_appearance.py -q`
- Result: 31 passed

Interpretation:

TIM-V1 now has deterministic proof that the ROS wrapper can extract appearance from images, pass it into the ROS-free TIM core, and affect candidate association under controlled conditions.

---

## TIM-V1F live appearance diagnostics validated

Ran the live stack with TIM appearance enabled and checked `/target_memory/status`.

Observed diagnostic fields:

- `appearance_enabled`: true
- `appearance_candidates`: 1
- `appearance_features_valid`: 1
- `appearance_image_age_ms`: approximately 34 ms

Interpretation:

The live TIM appearance extraction path is not only launching, it is successfully extracting at least one valid image-derived appearance feature from a live candidate track. This confirms that `/camera/dashboard` images are reaching `target_memory_node`, crop extraction is working, and features are being attached to candidates before TIM matching.

Additional full-length status sample:

    {"appearance_candidates": 1, "appearance_enabled": true, "appearance_features_valid": 1, "appearance_image_age_ms": 4.221505, "appearance_skip_reason": "ok", "best": null, "control_mode": "NO_CONTROL", "frame_id": 1644, "frames_since_seen": 0, "lat_ms": 0.919801, "num_tracks": 1, "quality": 0.0, "reacquired": false, "reason": "no_operator_selected_target", "state": "NO_TARGET", "target_track_id": null, "visible": false}

This confirms live feature extraction before operator target selection. The NO_TARGET state is expected because no track had been selected during the sample.

---

## TIM-V1H bag analysis exports appearance diagnostics

Updated the TIM bag analyser to export TIM-V1 appearance diagnostic fields from `/target_memory/status`.

Added exported fields:

- `appearance_enabled`
- `appearance_candidates`
- `appearance_features_valid`
- `appearance_image_age_ms`
- `appearance_skip_reason`
- `best_appearance`
- `best_appearance_used`

Re-ran analysis on:

    artifacts/bags/live_camera/2026-05-11__10-18-33__video__tim_v1g_target_selected_smoke

Updated report:

    reports/tim_v0/2026-05-11__10-18-33__video__tim_v1g_target_selected_smoke

Bag-level TIM-V1 appearance evidence:

- status rows: 1415
- selected-target status rows: 1273
- rows with valid appearance features: 1412
- rows with `best_appearance_used=true`: 0
- appearance image age mean: 41.62 ms
- appearance image age p95: 122.13 ms

Interpretation:

The recorded target-selected live run confirms that TIM-V1 appearance extraction was active and valid for almost the entire bag. `best_appearance_used=true` remained zero because this was a stable single-person smoke run, not an ambiguity or reacquisition scenario.

---

## TIM bag analysis wording made version-neutral

Updated `tools/analysis/analyse_tim_v0_bag.py` so the generated report title and interpretation no longer describe the analysis as TIM-V0-only.

Reason:

- The analyser now exports TIM-V1 appearance diagnostics.
- The historical output folder remains `reports/tim_v0/` for compatibility.
- The generated report content is now TIM-version neutral.

Validation:

- `python3 -m py_compile tools/analysis/analyse_tim_v0_bag.py`
- Re-ran the analyser on the TIM-V1G target-selected smoke bag.
- Confirmed the generated report title is now `TIM Bag Analysis`.

---

## TIM-V1I controlled occlusion smoke bag

Recorded a short target-selected live run with TIM appearance enabled and a brief disturbance/occlusion.

Command:

    ./tools/start_live_stack.sh --profile safe-camera --target-memory --target-memory-appearance --target-memory-appearance-image-topic /camera/dashboard --record-video --bag-tag tim_v1i_occlusion_smoke

Bag:

    artifacts/bags/live_camera/2026-05-11__10-35-24__video__tim_v1i_occlusion_smoke

Report:

    reports/tim_v0/2026-05-11__10-35-24__video__tim_v1i_occlusion_smoke

Summary:

- Raw /target samples: 1181
- TIM /target_memory samples: 1187
- TIM status samples: 1186
- Post-selection window starts at t=10.54 s
- TIM valid duration after selection: 60.877 / 61.997 s
- LOCKED duration: 60.996 s
- UNCERTAIN duration: 0.458 s
- LOST duration: 0.664 s
- REACQUIRED events: 1
- First UNCERTAIN -> REACQUIRED duration: 1.122 s
- First LOST -> REACQUIRED duration: 0.664 s
- TIM latency mean: 1.142 ms
- TIM latency p95: 4.247 ms
- TIM latency p99: 7.144 ms

Appearance diagnostics:

- status rows: 1186
- selected-target status rows: 1043
- positive /target_memory rows: 1025
- valid appearance feature rows: 948
- appearance_used rows: 0
- appearance image age mean: 42.10 ms
- appearance image age p95: 128.50 ms

Interpretation:

This run provides the first controlled TIM-V1 occlusion/reacquisition evidence. TIM transitioned through UNCERTAIN and LOST during the disturbance, reacquired the target after 0.664 s, and returned to LOCKED. Appearance features were extracted for most of the run, but appearance-assisted matching was not triggered because this scenario did not include a two-person ambiguity.

---

## TIM-V1K appearance diagnostics report added

Added a dedicated TIM-V1 appearance diagnostics report script:

- `tools/analysis/analyse_tim_v1_appearance.py`

The script reads `target_memory_status.csv` generated by the TIM bag analyser and writes an appearance-focused summary to:

- `reports/tim_v1_appearance/<bag_name>/summary.md`

Report contents:

- appearance enabled rows
- selected-target rows
- rows with valid appearance features
- rows with `best_appearance_used=true`
- image age mean/p50/p95/p99
- TIM latency mean/p50/p95/p99
- state counts
- appearance skip reason counts
- appearance-used by state

Ran the report on:

- `2026-05-11__10-18-33__video__tim_v1g_target_selected_smoke`
- `2026-05-11__10-35-24__video__tim_v1i_occlusion_smoke`

TIM-V1I occlusion report result:

- Status rows: 1186
- Appearance enabled rows: 1186
- Selected-target rows: 1043
- Rows with valid appearance features: 948
- Rows with `best_appearance_used=true`: 0
- Image age mean: 42.101 ms
- Image age p50: 27.191 ms
- Image age p95: 128.502 ms
- Image age p99: 189.920 ms
- TIM latency mean: 1.142 ms
- TIM latency p50: 0.919 ms
- TIM latency p95: 4.154 ms
- TIM latency p99: 7.099 ms
- Appearance skip reasons:
  - ok: 1175
  - stale_image: 11

Interpretation:

TIM-V1 now has a dedicated report for appearance extraction behaviour. The occlusion smoke bag confirms that appearance extraction was active and valid for most of the run, with bounded image age and low TIM latency. Appearance-assisted matching was not triggered, which is expected because this was not a two-person ambiguity case.

---

## TIM-V1J two-person ambiguity bag

Recorded a two-person live run with TIM appearance enabled.

Command:

    ./tools/start_live_stack.sh --profile safe-camera --target-memory --target-memory-appearance --target-memory-appearance-image-topic /camera/dashboard --record-video --bag-tag tim_v1j_two_person_ambiguity

Bag:

    artifacts/bags/live_camera/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity

Reports:

    reports/tim_v0/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity
    reports/tim_v1_appearance/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity

General TIM results:

- Raw /target samples: 1193
- TIM /target_memory samples: 1200
- TIM status samples: 1199
- Post-selection window starts at t=5.26 s
- Raw valid duration after selection: 34.484 / 67.880 s
- TIM valid duration after selection: 56.105 / 67.878 s
- LOCKED duration: 55.962 s
- UNCERTAIN duration: 0.616 s
- LOST duration: 11.125 s
- REACQUIRED events: 2
- First UNCERTAIN -> REACQUIRED duration: 1.071 s
- First LOST -> REACQUIRED duration: 0.706 s
- TIM latency mean: 1.315 ms
- TIM latency p95: 4.196 ms
- TIM latency p99: 8.213 ms

Appearance diagnostics:

- Appearance enabled rows: 1199
- Rows with valid appearance features: 1197
- Rows with best_appearance_used=true: 84
- Image age mean: 32.130 ms
- Image age p50: 18.517 ms
- Image age p95: 108.146 ms
- Image age p99: 177.309 ms
- Appearance skip reasons:
  - ok: 1197
  - stale_image: 2
- Appearance-used by state:
  - LOCKED: 2
  - UNCERTAIN: 3
  - LOST: 77
  - REACQUIRED: 2

Multi-person evidence:

- Rows with >=2 tracks: 656
- Rows with >=2 valid appearance features: 595
- Rows with 3 tracks: 45
- Rows with 4 tracks: 3

First appearance-used sample:

- t=39.833 s
- state: UNCERTAIN
- target_track_id: 1
- num_tracks: 1
- appearance_features_valid: 1
- best_track_id: 2
- best_total: 0.491
- best_appearance: 0.440
- reason: best_below_threshold:0.491<0.520

Interpretation:

This is the first real two-person TIM-V1 evidence bag. It confirms that image-derived appearance features were extracted during a multi-person run and that the TIM-V1 appearance cue actively affected association decisions. TIM produced valid target output for substantially longer than raw /target after selection, and reacquired after tracker identity changes. Correctness is not yet proven because this bag still needs manual annotation of correct/wrong/lost target intervals.

---

## TIM-V1N manual target-correctness evaluation

Created first-pass manual correctness annotations for the TIM-V1J two-person ambiguity bag.

Annotation file:

- `docs/annotations/tim_v1j_two_person_ambiguity/target_correctness_annotations.csv`

Manual review notes:

- `docs/annotations/tim_v1j_two_person_ambiguity/manual_review_notes.md`

Evaluator command:

    python3 tools/analysis/evaluate_tim_target_correctness.py artifacts/bags/live_camera/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity --annotations docs/annotations/tim_v1j_two_person_ambiguity/target_correctness_annotations.csv --out-dir reports/target_correctness/tim_v1j_two_person_ambiguity --step-s 0.05

Result:

| Metric | Raw /target | TIM /target_memory |
|---|---:|---:|
| correct duration [s] | 33.350 | 54.670 |
| wrong duration [s] | 0.000 | 0.290 |
| lost duration [s] | 23.670 | 2.060 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 5.600 | 5.600 |
| visible target duration [s] | 57.020 | 57.020 |
| correct ratio | 0.585 | 0.959 |
| wrong ratio | 0.000 | 0.005 |
| lost ratio | 0.415 | 0.036 |

Interpretation:

This is the first manually annotated selected-target correctness result for TIM-V1. On this two-person ambiguity run, TIM improves correct target duration from 33.350 s to 54.670 s and correct ratio from 0.585 to 0.959. TIM reduces lost duration from 23.670 s to 2.060 s. A small wrong-target duration of 0.290 s appears in TIM, corresponding to a wrong ratio of 0.005. This is an important thesis result because it shows a measurable improvement over raw tracker-ID target selection while also exposing the residual risk of brief wrong-target output.

---

## TIM-V1L appearance ablation on the same two-person bag

Replayed the TIM-V1J two-person ambiguity bag twice:

1. appearance disabled
2. appearance enabled

Replay bags:

- `artifacts/bags/eval/tim_v1j_replay_appearance_off`
- `artifacts/bags/eval/tim_v1j_replay_appearance_on`

Correctness results:

| Replay | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|
| Appearance OFF | 0.956 | 0.008 | 0.036 |
| Appearance ON | 0.956 | 0.008 | 0.036 |

Appearance diagnostics:

| Metric | OFF | ON |
|---|---:|---:|
| appearance enabled rows | 0 | 1201 |
| valid appearance rows | 0 | 1170 |
| appearance used rows | 0 | 82 |
| rows with >=2 tracks | 659 | 659 |
| rows with >=2 valid appearance features | 0 | 593 |
| TIM latency p95 | 0.216 ms | 1.984 ms |

Interpretation:

On this bag, the main improvement over raw `/target` comes from selected-target memory itself. Appearance was active and influenced candidate scores in 82 rows, but it did not change the final selected-target correctness metrics compared with appearance disabled. This is an important ablation result because it avoids overclaiming the contribution of appearance. TIM-V1 appearance adds measurable overhead, but the replay p95 latency remains below 2 ms.

---

## TIM-V1M appearance-critical crossing run

Recorded a harder two-person crossing/re-entry scenario designed to stress geometry and give appearance a stronger role.

Command:

    ./tools/start_live_stack.sh --profile safe-camera --target-memory --target-memory-appearance --target-memory-appearance-image-topic /camera/dashboard --record-video --bag-tag tim_v1m_appearance_critical_crossing

Bag:

    artifacts/bags/live_camera/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

Reports:

    reports/tim_v0/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing
    reports/tim_v1_appearance/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

General TIM results:

- Raw /target samples: 1269
- TIM /target_memory samples: 1269
- TIM status samples: 1269
- Post-selection window starts at t=20.40 s
- Raw valid duration after selection: 15.240 / 52.347 s
- TIM valid duration after selection: 15.264 / 52.350 s
- LOCKED duration: 15.315 s
- UNCERTAIN duration: 0.584 s
- LOST duration: 36.502 s
- REACQUIRED events: 1
- First LOST -> REACQUIRED duration: 20.152 s
- TIM latency mean: 1.711 ms
- TIM latency p95: 5.092 ms
- TIM latency p99: 8.859 ms

Appearance diagnostics:

- Appearance enabled rows: 1269
- Rows with valid appearance features: 1262
- Rows with best_appearance_used=true: 541
- Image age mean: 39.384 ms
- Image age p50: 24.507 ms
- Image age p95: 127.396 ms
- Image age p99: 204.796 ms
- Appearance skip reasons:
  - ok: 1262
  - stale_image: 7
- Appearance-used by state:
  - LOST: 533
  - UNCERTAIN: 7
  - REACQUIRED: 1

Multi-person evidence:

- Rows with >=2 tracks: 1154
- Rows with >=2 valid appearance features: 1150
- Rows with 3 tracks: 92

Representative rejected appearance-assisted candidates:

- t=36.355 s, state=LOST, best_track_id=9, best_total=0.560, best_appearance=0.451, reason=best_below_threshold:0.560<0.600
- t=36.386 s, state=LOST, best_track_id=9, best_total=0.570, best_appearance=0.495, reason=best_below_threshold:0.570<0.600

Interpretation:

This harder run successfully produced an appearance-critical ambiguity condition. Appearance was used heavily, but the current conservative LOST-state threshold rejected many candidates even when appearance similarity was moderate. The run shows that TIM-V1 appearance affects candidate scoring, but reacquisition is still dominated by the acceptance policy. This motivates a threshold/reacquisition sweep rather than further appearance plumbing.
