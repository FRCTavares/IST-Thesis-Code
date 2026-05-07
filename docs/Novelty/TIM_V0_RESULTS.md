# TIM-V0 Results: Selected-Target Memory

Date: 2026-05-05  
Project: RGB-only selected-target perception for micro-UAV following  
Status: V0 implementation and initial validation complete

---

## 1. Objective

TIM-V0 is a lightweight selected-target memory layer placed above detector and tracker outputs.

The objective is not generic multi-object tracking. The objective is to maintain one operator-selected person as a reliable target state for downstream UAV control under noisy detections, short occlusions, missed frames, and tracker ID reassignment.

The baseline `/target` logic follows a raw tracker ID. If the selected tracker ID disappears, the baseline target becomes invalid. TIM-V0 instead keeps a memory of the selected physical target and tries to recover it using geometric and temporal consistency.

---

## 2. Scope of TIM-V0

TIM-V0 uses only lightweight geometric and temporal cues:

- IoU consistency
- centre-distance consistency
- scale consistency
- confidence
- same-ID bonus
- ambiguity rejection
- hysteresis through explicit target states

TIM-V0 does **not** use:

- learned appearance embeddings
- re-identification networks
- ROI re-detection
- detector retraining
- global multi-object identity optimisation
- any future-frame information

This keeps V0 suitable for onboard use on the Raspberry Pi 5 and allows the cost of the target-memory layer to be measured independently from detector and tracker cost.

---

## 3. Position in the Live Stack

TIM-V0 runs after the tracker and before any control-valid target output is consumed.

```text
/camera/image_raw
    -> perception_pipeline_node
    -> /detections
    -> tracker_node
    -> /tracks
    -> target_memory_node
    -> /target_memory
    -> /target_memory/status
```

The existing dashboard-selected target remains available as:

```text
/target
```

This allows direct comparison between:

```text
/target          raw selected-ID baseline
/target_memory   TIM-V0 selected-target memory output
```

---

## 4. ROS Integration

TIM-V0 is implemented in:

```text
ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py
ros2_ws/src/thesis_bringup/thesis_bringup/nodes/target_memory_node.py
```

Synthetic tests are implemented in:

```text
ros2_ws/src/thesis_bringup/test/test_target_memory_synthetic.py
```

Analysis scripts are implemented in:

```text
tools/analysis/analyse_tim_v0_bag.py
tools/analysis/evaluate_tim_v0_fault_injection.py
tools/analysis/evaluate_tim_v0_fault_injection_batch.py
```

Live comparison helper:

```text
tools/live/watch_tim_vs_target.py
```

---

## 5. Live-Stack Flags

TIM-V0 is enabled by default in the live stack.

Default operation:

```bash
./tools/start_live_stack.sh --profile daily
```

Disable TIM-V0 for raw baseline runs:

```bash
./tools/start_live_stack.sh --profile daily --no-target-memory
```

Explicitly enable TIM-V0:

```bash
./tools/start_live_stack.sh --profile daily --target-memory
```

When video recording is enabled, TIM topics are recorded by default if TIM is enabled:

```bash
./tools/start_live_stack.sh --profile daily --record-video --bag-tag <tag>
```

Recorded TIM topics:

```text
/target_memory
/target_memory/status
```

When `--no-target-memory` is used, TIM topics are omitted from the video bag while the normal timing and control topics remain recorded.

---

## 6. Target Selection Semantics

The operator still selects a target through the existing dashboard bridge path:

```text
target <id>
```

Internally, this updates `/target`.

TIM-V0 mirrors positive raw `/target` IDs and initialises memory from the corresponding track in `/tracks`.

Important rule:

```text
operator command > target memory > raw tracker ID
```

A positive raw `/target` ID can initialise or reinitialise TIM. A raw `/target` ID of zero is not automatically treated as an operator clear, because it can also mean the selected tracker ID is temporarily invisible. Explicit TIM clearing remains available through:

```text
/target_memory/clear
```

---

## 7. State Machine

TIM-V0 uses five states:

```text
NO_TARGET
LOCKED
UNCERTAIN
LOST
REACQUIRED
```

### State meanings

| State | Meaning |
|---|---|
| `NO_TARGET` | No operator-selected target has been initialised. |
| `LOCKED` | Target is visible and confidently matched. |
| `UNCERTAIN` | Target memory exists, but current evidence is weak or missing for a short period. |
| `LOST` | Target has been absent or weak for long enough that normal control must stop. |
| `REACQUIRED` | A candidate has been accepted after uncertainty or loss and should be confirmed. |

---

## 8. Control Validity Policy

TIM-V0 exposes a control-relevant mode through `/target_memory/status`:

```text
NO_CONTROL
NORMAL
YAW_ONLY
HOVER
CONFIRM
```

Mapping:

| TIM state | Control mode | Intended behaviour |
|---|---|---|
| `NO_TARGET` | `NO_CONTROL` | Do not command target following. |
| `LOCKED` | `NORMAL` | Normal target-relative control may be used. |
| `UNCERTAIN` | `YAW_ONLY` | Use reduced control authority, typically yaw-only or slow response. |
| `LOST` | `HOVER` | Stop target-following commands and hold/hover. |
| `REACQUIRED` | `CONFIRM` | Candidate reacquired, confirm before full trust if needed. |

The topic `/target_memory` is conservative and intended to be safe for controller-style consumers. If TIM does not currently consider the target visible and control-valid, `/target_memory` publishes an empty target state:

```text
id = 0
cx = 0
cy = 0
w = 0
h = 0
score = 0
quality = 0
```

Detailed memory state, reasons, and scores remain available in:

```text
/target_memory/status
```

---

## 9. Candidate Score

For each candidate track `j`, TIM-V0 computes a lightweight matching score:

```text
S_j = w_iou S_iou
    + w_dist S_dist
    + w_scale S_scale
    + w_conf S_conf
    + w_id S_id
    - w_amb S_amb
```

The selected candidate is accepted only if:

```text
S_j >= state-dependent threshold
```

and the match is not ambiguous.

Current thresholds:

```text
accept_score_locked = 0.52
accept_score_lost   = 0.60
ambiguity_margin    = 0.07
```

The higher lost-state threshold is intentional. TIM-V0 is conservative after target loss to avoid reacquiring the wrong person.

---

## 10. Default Configuration

Current V0 defaults:

```text
image_width             = 640
image_height            = 640
accept_score_locked     = 0.52
accept_score_lost       = 0.60
ambiguity_margin        = 0.07
max_uncertain_frames    = 6
max_lost_frames         = 30
min_candidate_score     = 0.10
tracks_are_normalized   = false
zero_id_when_not_visible = true
mirror_raw_target_selection = true
```

These values are not final thesis-tuned constants yet. They are the working V0 configuration used for the first integration and fault-injection evaluations.

---

## 11. Validation Completed

### 11.1 Unit tests

Synthetic logic tests passed:

```text
12 passed
```

The tests cover:

- target selection
- same-ID lock maintenance
- ID-switch recovery
- short missing periods
- transition to lost
- reacquisition after loss
- ambiguity rejection
- rejection of far wrong candidates
- score preference for memory-consistent candidates

### 11.2 Live integration

TIM-V0 was integrated into `tools/start_live_stack.sh`.

Validated behaviours:

- `target_memory_node` starts automatically with the live stack.
- `--target-memory` and `--no-target-memory` flags work.
- TIM mirrors dashboard `/target` selection.
- `/target_memory` and `/target_memory/status` are recorded in bags when TIM is enabled.
- TIM topics are omitted from bags when `--no-target-memory` is used.

---

## 12. Evidence Bags

Main evidence bags used during V0 validation:

```text
2026-05-05__09-55-39__video__tim_v0_occlusion_01
2026-05-05__10-07-32__video__tim_v0_id_switch_02
2026-05-05__14-47-10__video__tim_v0_integrated_smoke_01
2026-05-05__16-11-58__video__tim_flag_smoke_02
```

Interpretation of each:

| Bag | Use |
|---|---|
| `tim_v0_occlusion_01` | Clean short-loss state-machine and latency evidence. |
| `tim_v0_id_switch_02` | Longer loss sequence with `UNCERTAIN`, `LOST`, `REACQUIRED`. |
| `tim_v0_integrated_smoke_01` | Confirms live-stack integration and recording path. |
| `tim_flag_smoke_02` | Confirms TIM flags, recording, and locked-state behaviour after kernel recovery. |

---

## 13. Live Behaviour Observed

Observed state sequences include:

```text
NO_TARGET -> LOCKED
LOCKED -> UNCERTAIN -> REACQUIRED -> LOCKED
LOCKED -> UNCERTAIN -> LOST -> REACQUIRED -> LOCKED
```

These transitions provide more control-relevant information than raw ID-based target selection.

The raw selector only exposes whether the selected tracker ID is currently visible. TIM-V0 exposes whether the selected physical target is locked, uncertain, lost, or reacquired.

---

## 14. Bag-Level Duration Metrics

Duration metrics were added to:

```text
tools/analysis/analyse_tim_v0_bag.py
```

This reports state and control-mode durations instead of only sample counts.

### `tim_v0_occlusion_01`

Post-selection validity:

```text
Raw valid samples after TIM selection: 162/168
TIM valid samples after TIM selection: 162/168
Raw valid duration after TIM selection: 15.362/15.796 s
TIM valid duration after TIM selection: 15.371/15.802 s
```

State durations:

```text
LOCKED      = 15.644 s
UNCERTAIN   = 0.432 s
REACQUIRED  = 0.127 s
NO_TARGET   = 21.735 s
```

Control-mode durations:

```text
NORMAL      = 15.644 s
YAW_ONLY    = 0.432 s
CONFIRM     = 0.127 s
NO_CONTROL  = 21.735 s
```

### `tim_v0_id_switch_02`

Post-selection validity:

```text
Raw valid samples after TIM selection: 90/187
TIM valid samples after TIM selection: 90/187
Raw valid duration after TIM selection: 7.818/16.877 s
TIM valid duration after TIM selection: 7.803/16.880 s
```

State durations:

```text
LOCKED      = 7.795 s
UNCERTAIN   = 1.654 s
LOST        = 7.416 s
REACQUIRED  = 0.084 s
NO_TARGET   = 4.044 s
```

Control-mode durations:

```text
NORMAL      = 7.795 s
YAW_ONLY    = 1.654 s
HOVER       = 7.416 s
CONFIRM     = 0.084 s
NO_CONTROL  = 4.044 s
```

### `tim_flag_smoke_02`

Post-selection validity:

```text
Raw valid samples after TIM selection: 137/137
TIM valid samples after TIM selection: 134/134
Raw valid duration after TIM selection: 12.095/12.095 s
TIM valid duration after TIM selection: 11.849/11.849 s
```

State durations:

```text
LOCKED     = 11.955 s
NO_TARGET  = 51.896 s
```

This bag is mainly an integration smoke test. It is not intended as an occlusion or ID-switch result.

---

## 15. TIM-V0 Latency

TIM-V0 overhead is negligible relative to detector and tracker latency.

Representative measured latencies:

### `tim_v0_occlusion_01`

```text
mean = 0.1174 ms
p50  = 0.0636 ms
p95  = 0.2046 ms
p99  = 0.8148 ms
max  = 6.6742 ms
```

### `tim_v0_id_switch_02`

```text
mean = 0.1772 ms
p50  = 0.0986 ms
p95  = 0.2684 ms
p99  = 3.7459 ms
max  = 5.1569 ms
```

### `tim_flag_smoke_02`

```text
mean = 0.0747 ms
p50  = 0.0420 ms
p95  = 0.1333 ms
p99  = 0.2590 ms
max  = 4.6973 ms
```

Conclusion:

```text
TIM-V0 adds substantially less than 1 ms p95 overhead in the tested runs.
```

---

## 16. Deterministic ID-Switch Fault Injection

A deterministic fault-injection test was added using recorded `/tracks` data.

Implemented scripts:

```text
tools/analysis/evaluate_tim_v0_fault_injection.py
tools/analysis/evaluate_tim_v0_fault_injection_batch.py
```

Fault model:

```text
selected target ID disappears for a configured gap
same target reappears with a replacement track ID
```

This creates a repeatable ID-switch condition and compares:

```text
raw selected-ID baseline
vs
TIM-V0 selected-target memory
```

---

## 17. Single Fault-Injection Result

Using `tim_v0_occlusion_01`:

```text
selected ID before fault = 1
replacement ID after fault = 3
gap start = 28.00 s
gap duration = 2.00 s
```

Result:

```text
Raw ID selector valid samples after fault start: 0/110
TIM-V0 valid samples after fault start: 85/110
TIM reacquired at t = 30.01 s
Time after reappearance = 0.01 s
Reacquired ID = 3
Quality = 0.825
Reason = reacquired_candidate
```

Interpretation:

The raw selector failed because it kept waiting for track ID `1`. TIM-V0 recovered the selected physical target under replacement track ID `3`.

---

## 18. Batch Fault-Injection Result

Batch configuration:

```text
selected ID = 1
replacement ID = 3
gap starts = 24, 26, 28, 30, 32 s
gap durations = 1, 2, 3 s
cases = 15
```

Aggregate result:

```text
Reacquired cases = 13/15
Mean validity gain = 0.635
Max validity gain = 0.882
Min validity gain = 0.000
Mean reacquisition time = 0.400 s
Max reacquisition time = 1.917 s
```

Detailed cases:

| gap start | duration | raw valid | TIM valid | gain | reacquired | reacq ID |
|---:|---:|---:|---:|---:|:---:|---:|
| 24.00 | 1.00 | 0/147 | 125/147 | 0.850 | true | 3 |
| 24.00 | 2.00 | 0/147 | 113/147 | 0.769 | true | 3 |
| 24.00 | 3.00 | 0/147 | 105/147 | 0.714 | true | 3 |
| 26.00 | 1.00 | 0/119 | 105/119 | 0.882 | true | 3 |
| 26.00 | 2.00 | 0/119 | 104/119 | 0.874 | true | 3 |
| 26.00 | 3.00 | 0/119 | 96/119 | 0.807 | true | 3 |
| 28.00 | 1.00 | 0/110 | 96/110 | 0.873 | true | 3 |
| 28.00 | 2.00 | 0/110 | 85/110 | 0.773 | true | 3 |
| 28.00 | 3.00 | 0/110 | 66/110 | 0.600 | true | 3 |
| 30.00 | 1.00 | 0/91 | 66/91 | 0.725 | true | 3 |
| 30.00 | 2.00 | 0/91 | 41/91 | 0.451 | true | 3 |
| 30.00 | 3.00 | 0/91 | 41/91 | 0.451 | true | 3 |
| 32.00 | 1.00 | 0/57 | 43/57 | 0.754 | true | 3 |
| 32.00 | 2.00 | 0/57 | 0/57 | 0.000 | false | 0 |
| 32.00 | 3.00 | 0/57 | 0/57 | 0.000 | false | 0 |

The raw selected-ID baseline failed after all injected ID switches because it continued waiting for the original selected ID.

TIM-V0 reacquired the replacement ID in 13 out of 15 cases.

---

## 19. Failure Analysis

The two failed batch cases occurred at late gaps:

```text
gap start = 32 s, duration = 2 s
gap start = 32 s, duration = 3 s
```

Failure diagnostics:

| gap start | duration | final state | final reason | final quality | final best | max post best |
|---:|---:|---|---|---:|---:|---:|
| 32.00 | 2.00 | `LOST` | `best_below_threshold:0.411<0.600` | 0.000 | 0.411 | 0.420 |
| 32.00 | 3.00 | `LOST` | `best_below_threshold:0.411<0.600` | 0.000 | 0.411 | 0.415 |

Interpretation:

TIM-V0 did not fail due to a runtime or state-machine error. It rejected the candidate because the reacquisition score was below the lost-state threshold:

```text
accept_score_lost = 0.60
best score approximately 0.41 to 0.42
```

This is an expected conservative failure mode. TIM-V0 avoids reacquiring weak candidates after loss, reducing the risk of wrong target reacquisition.

---

## 20. Threshold Sensitivity Analysis

A lost-state threshold sensitivity sweep was added after the initial TIM-V0 fault-injection evaluation.

Script:

- `tools/analysis/sweep_tim_v0_fault_thresholds.py`

Sweep configuration:

- selected ID: `1`
- replacement ID: `3`
- gap starts: `24, 26, 28, 30, 32 s`
- gap durations: `1, 2, 3 s`
- thresholds: `0.35, 0.38, 0.40, 0.42, 0.45, 0.50, 0.60`
- cases per threshold: `15`

Result:

| accept_score_lost | reacquired | mean gain | max gain | min gain | mean reacq time [s] | max reacq time [s] | failed |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.35 | 15/15 | 0.719 | 0.891 | 0.456 | 0.164 | 0.794 | 0 |
| 0.38 | 15/15 | 0.719 | 0.891 | 0.456 | 0.164 | 0.794 | 0 |
| 0.40 | 15/15 | 0.713 | 0.891 | 0.456 | 0.274 | 1.794 | 0 |
| 0.42 | 14/15 | 0.681 | 0.882 | 0.000 | 0.362 | 1.794 | 1 |
| 0.45 | 13/15 | 0.636 | 0.882 | 0.000 | 0.381 | 1.794 | 2 |
| 0.50 | 13/15 | 0.635 | 0.882 | 0.000 | 0.400 | 1.917 | 2 |
| 0.60 | 13/15 | 0.635 | 0.882 | 0.000 | 0.400 | 1.917 | 2 |

Interpretation:

Lowering the lost-state acceptance threshold improves recovery in weak geometric cases. Thresholds at or below `0.40` recovered all 15 injected ID-switch cases. However, this requires accepting weaker geometric evidence after target loss.

The default value `accept_score_lost = 0.60` is therefore not a maximum-recovery setting. It is a conservative safety-oriented setting that rejects weak reacquisition candidates after loss.

This supports the intended TIM-V0 design philosophy: prefer safe rejection over risky reacquisition when evidence is weak.

This sweep should not be interpreted as a full safety proof. It is a deterministic threshold sensitivity analysis. A true wrong-reacquisition metric requires annotated natural multi-person data.

---

## 21. Main Claims Supported by V0

Supported claims:

1. TIM-V0 can run live onboard with negligible compute overhead.
2. TIM-V0 provides explicit target validity states beyond raw tracker ID visibility.
3. TIM-V0 can encode control-relevant states such as `YAW_ONLY`, `HOVER`, and `CONFIRM`.
4. TIM-V0 can recover from deterministic tracker ID reassignment where a raw selected-ID baseline fails.
5. TIM-V0 failure cases are interpretable through score and threshold diagnostics.

Not yet supported:

1. TIM-V0 has not yet proven robust natural ID-switch improvement in a large set of real flight bags.
2. TIM-V0 does not solve long disappearance with weak geometry.
3. TIM-V0 does not solve visually ambiguous identical-person crossings.
4. TIM-V0 does not improve detector recall for tiny or far persons.

---

## 22. Current Limitations

TIM-V0 depends on geometric consistency. It can fail when:

- the target disappears for too long
- the reappearing candidate has low IoU or poor scale consistency
- the target reappears in a substantially different location
- multiple similar candidates create ambiguity
- detector outputs are too unstable or missing
- the tracker produces no candidate near the remembered target

The batch failures show this clearly. In late-gap cases, the best candidate score was only around `0.41`, below the lost-state threshold of `0.60`.

---

## 23. Motivation for TIM-V1

TIM-V1 should add a lightweight appearance cue, but only when needed.

Recommended TIM-V1 direction:

```text
motion + IoU + scale + confidence + target-only appearance cue
```

Appearance should be used only for:

- ambiguous candidates
- recovery after ID switch
- recovery after `UNCERTAIN` or `LOST`

It should not become a full DeepSORT-style always-on ReID system.

The V0 failure cases motivate this directly:

```text
geometric score too weak after loss
appearance could help decide if candidate is still the selected person
```

---

---

## Live UI Validation: TIM-V0 Dashboard Panel

A practical live UI validation run was completed after adding TIM-V0 target-memory telemetry to the dashboard.

Evidence bag:

- `2026-05-06__12-11-17__video__tim_v0_ui_panel_screenshot_01`

The dashboard now exposes:

- TIM state
- control mode
- raw selected target ID
- TIM target ID
- target-memory quality
- TIM latency
- matching reason

The run showed a clear raw-ID failure and TIM recovery case. During the test, the raw selected target became invalid, while TIM-V0 remained locked on the selected physical target under a new tracker ID.

Summary:

| Metric | Raw `/target` | TIM `/target_memory` |
|---|---:|---:|
| Valid samples | 931/1580 | 1375/1546 |
| Post-selection valid samples | 929/1379 | 1374/1377 |
| Post-selection valid duration | 57.069/83.014 s | 82.771/82.950 s |

TIM-V0 recovered approximately `25.702 s` of valid target output compared with the raw selected-ID baseline.

Observed TIM transitions:

- `NO_TARGET -> LOCKED`
- `LOCKED -> UNCERTAIN -> REACQUIRED -> LOCKED`
- `LOCKED -> UNCERTAIN -> REACQUIRED -> LOCKED`

Reacquisition events:

| Time [s] | Reacquired track ID | Quality | Reason |
|---:|---:|---:|---|
| 72.38 | 4 | 0.735 | reacquired_candidate |
| 78.10 | 4 | 0.876 | reacquired_candidate |

Latency:

| Metric | Value |
|---|---:|
| mean | 0.1313 ms |
| p50 | 0.0943 ms |
| p95 | 0.2117 ms |
| p99 | 0.5654 ms |
| max | 6.1227 ms |

Interpretation:

This run confirms that TIM-V0 is not only working in offline fault injection. It is also visible and useful in the live UI. The raw target can become invalid or stale, while TIM-V0 keeps a control-valid selected target through short tracking interruptions and tracker ID reassignment.

## 24. V0 Conclusion

TIM-V0 is a valid baseline novelty layer for selected-target UAV following.

It is:

- lightweight
- live-stack integrated
- recordable
- analysable
- control-aware
- deterministic under synthetic/fault-injection tests
- able to recover from injected ID-switch faults

The strongest result is the deterministic ID-switch batch evaluation:

```text
raw selected-ID baseline: 0 valid samples after injected ID switch in all tested cases
TIM-V0: reacquired in 13/15 cases
mean validity gain: 0.635
mean reacquisition time: 0.400 s
```

TIM-V0 is therefore sufficient as the thesis V0 selected-target memory baseline.

The next stage should be TIM-V1, focused on adding a lightweight target-only appearance cue for ambiguous or low-geometric-score reacquisition cases.

## TIM-V0 Freeze Status

TIM-V0 is frozen as the geometry-only selected-target memory baseline.

Frozen features:

- raw `/target` mirroring
- selected-target memory
- IoU, distance, scale, confidence, same-ID bonus, ambiguity penalty
- explicit states: `NO_TARGET`, `LOCKED`, `UNCERTAIN`, `LOST`, `REACQUIRED`
- conservative `/target_memory` output
- `/target_memory/status` diagnostics
- live-stack flags: `--target-memory`, `--no-target-memory`
- bag recording of TIM topics
- deterministic ID-switch fault injection evaluation

Known limitations:

- no appearance cue
- no wrong-target annotation yet
- no natural multi-person benchmark yet
- weak geometry after long loss can prevent reacquisition

Next stage:
TIM-V1 should add lightweight target-only appearance only for ambiguity and lost-target recovery.

## Evaluation Protocol Upgrade After Supervisor Feedback

After supervisor feedback, TIM-V0 evaluation was extended beyond valid target duration.

The key issue is that valid target duration alone is insufficient. For target-relative UAV control, a valid output is useful only if it corresponds to the selected person. A method that keeps publishing a target can still be unsafe if that target is a distractor.

The evaluation protocol now separates:

- valid and correct target output
- valid but wrong target output
- invalid output while the selected target is visible
- safe invalid output when the selected target is not visible

This makes wrong-target duration a first-class metric.

Added artefacts:

- `docs/Novelty/TIM_EVALUATION_PROTOCOL.md`
- `tools/analysis/templates/target_correctness_annotations_template.csv`
- `tools/analysis/evaluate_tim_target_correctness.py`
- interval-level annotation CSVs under `docs/Novelty/annotations/`

First interval-level result on `2026-05-06__12-11-17__video__tim_v0_ui_panel_screenshot_01`:

| Metric | Raw `/target` | TIM `/target_memory` |
|---|---:|---:|
| correct duration [s] | 57.100 | 82.990 |
| wrong duration [s] | 0.000 | 0.000 |
| lost duration [s] | 25.990 | 0.100 |
| correct ratio | 0.687 | 0.999 |
| wrong ratio | 0.000 | 0.000 |
| lost ratio | 0.313 | 0.001 |

This first result shows that TIM-V0 improves selected-target continuity without introducing wrong-target output in this bag. Future TIM-V0, TIM-V1, and TIM-V2 comparisons should report correct-target duration, wrong-target duration, lost-target duration, and target-absent-but-output-valid duration separately for raw `/target` and TIM `/target_memory`.

This keeps the thesis focus on selected-target identity correctness rather than generic target availability.
