# ByteTrack configuration sensitivity for downstream TIM-MARS

## Status

Development-only one-factor-at-a-time (OFAT) screening completed on 7 September
2026. This is a robustness/sensitivity study, not a retuning exercise. The
canonical ByteTrack configuration remains canonical: no configuration in this
matrix was promoted, `ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml`
was not modified, TIM-MARS was not modified, and the Issue #27 frozen
configuration was not modified. The experiment finishes with a recommendation
only.

No H01/H02/H03 held-out sequence, outcome, annotation, or file was inspected,
replayed, created, or used.

## Question

Does changing ByteTrack's activation (`track_thresh`), first-round association
(`match_thresh`), or lost-track lifetime (`track_buffer`) configuration improve
the controller-facing TIM-MARS target result on the development sequences,
compared with the canonical ByteTrack settings, without introducing
wrong-target authority?

Raw tracker improvement alone is not sufficient. The outcome of interest is
whether a tracker configuration change propagates into a safer or more
available authoritative `/target_memory_mars` result.

## Method

### Frozen protocol

- Pre-outcome methodology commit: `14c3ef20755863e7ced3350fe823ccc017277ae3`
  ("07-09-26: freeze ByteTrack TIM sensitivity experiment"). No physical-v2
  outcome for any non-canonical configuration existed or was inspected before
  that commit.
- Manifest: `docs/data/tracker_sensitivity/bytetrack_tim_sensitivity_v1.yaml`
  (sha256 `44b96035330c0eb9690b0e7c5f42c02acb33138a2ded771fbc000eb7ef2f6954`).
- Runner: `tools/experiments/run_bytetrack_tim_sensitivity.py`.
- Run id: `p058b_bytetrack_config_sensitivity_14c3ef20_2026_09_07`.

### Independent variable

The only independent variable is ByteTrack configuration. The canonical
ByteTrack profile
(`ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml`, sha256
`e0e5c7c80a2f2b74cb6640e2ea90d9651c33f193c34365dc0d5a7ac9badaa906`) is:
`track_thresh 0.50`, `match_thresh 0.80`, `track_buffer 30`,
`new_track_thresh 0.60`, `low_thresh 0.10`, `second_match_thresh 0.50`,
`unconfirmed_match_thresh 0.70`, `fuse_scores true`, `min_score 0.20`,
`frame_rate 30`.

First-pass OFAT screen, one canonical step above and below baseline per
dimension, everything else held at canonical:

| config id | changed parameter | value | materialized sha256 |
| --- | --- | --- | --- |
| `canonical_baseline` | -- | -- | `e0e5c7c80a2f` (byte-identical to canonical) |
| `track_thresh_lower_1` | `track_thresh` | 0.40 | `b70053a13f97` |
| `track_thresh_higher_1` | `track_thresh` | 0.60 | `0ad50708516d` |
| `match_thresh_lower_1` | `match_thresh` | 0.70 | `d9921fe64215` |
| `match_thresh_higher_1` | `match_thresh` | 0.90 | `41175638b72b` |
| `track_buffer_lower_1` | `track_buffer` | 15 | `49193a10c4ac` |
| `track_buffer_higher_1` | `track_buffer` | 45 | `956f8f19ccf8` |

`new_track_thresh` is pinned at `0.60` for every configuration, including the
`track_thresh` perturbations. In this backend `new_track_thresh` gates track
birth independently of `track_thresh`, so pinning it isolates the
high/low association split from track birth: the `track_thresh` dimension does
not silently change which detections start new tracks.

### Pipeline (deterministic, offline, in-process)

```
frozen recorded images + detections   (identical across all configs, per sequence)
  -> run_deterministic_tracker_replay.py   (candidate ByteTrack YAML)
  -> /tracks + fixed-ID /target
  -> resolve_bootstrap_target.py            (highest-IoU vs physical-v2 target box, >= 0.5)
  -> run_deterministic_tim_replay.py        (canonical TIM-MARS, sha256 0f2ac3fc..., unchanged)
  -> /target_memory_mars + /target
  -> evaluate_physical_target_bbox_v2.py    (identity-independent physical-v2)
  -> analyse_tracker_target_continuity.py   (raw ByteTrack diagnostics)
  -> analyse_tim_state_occupancy.py         (TIM state occupancy / transitions)
```

No detector inference, Hailo, camera, drone, Pixhawk, MAVROS, controller, or
ROS graph is involved. Detector output is reused from the frozen recorded
detections, so detector variability is eliminated within each sequence. The
deterministic replay tools process bags in-process; there are no ROS
processes or ports to leak.

### Bootstrap target resolution

Historical tracker IDs are not reused, because ByteTrack IDs change across
configurations. For each `(sequence, configuration)` the operator bootstrap
target is resolved spatially: the first generated `/tracks` message whose
best-overlapping track reaches IoU `>= 0.5` against the physical-v2 target box
at the first scored reference sample. The same rule is applied identically to
every cell. A configuration with no qualifying track is recorded as a
bootstrap failure and preserved as a result. There were no bootstrap failures:
all 36 cells bootstrapped the same physical person as the canonical baseline,
with bootstrap IoU `0.947` (May), `0.935` (Seq01), `0.925` (Seq03), `0.891`
(Seq04), and resolved bootstrap tracker IDs `1 / 1 / 1 / 5` respectively,
consistent with the historical selected-target IDs for these sequences.

### Evaluation

`physical_target_bbox_evaluation_v2` (`tim_physical_target_bbox_v2`),
identity-independent and spatial. Both the raw fixed-ID `/target` stream and
the `/target_memory_mars` TIM stream are scored against the same physical
reference in one pass. `evaluate_tim_event_recovery.py` and the tracker-ID
annotation oracles are not used for the cross-configuration headline
evaluation because ByteTrack IDs change; the physical-v2 evaluator is the
authoritative identity-independent measure.

### Precision

Reported deltas are literal evaluator differences. The physical-v2 evaluator
does not define a formal precision floor, but the historical Issue #58 work
adopted a `0.05 s` asymmetric wrong-target tolerance, and duration reallocation
below roughly `0.5 s` on a `60-87 s` window is characterised in this report as
marginal / no meaningful signal rather than an effect. The one exception the
report treats as meaningful below `0.5 s` is a wrong-target-authority increase,
consistent with the asymmetric safety ordering.

### Safety ordering

`correct target > lost/hover > wrong target`. A candidate is not an
improvement merely because it publishes a target longer, reduces lost time, or
holds a tracker ID longer. A configuration that converts lost/suppressed time
into wrong-target authority is a safety regression.

## Development-only data

`docs/data/splits/tim_mars_split_v3.json` (`tim_mars_split_v3_2026_09_05`,
sha256 `34bf5b6f09f8938b23fae7cda18314e3aa06115ed0f966f60b8ca6bda8cfb409`) is
the sole authority. All four sequences are `sets.development` entries with
documented historical tuning exposure. `sets.final_held_out`
(`heldout_h01_exit_reentry`, `heldout_h02_crossing`,
`heldout_h03_occlusion_distractor`) is `reserved_pending_capture` with no
files and was not touched.

| sequence | split entry | role | common input (mcap sha256) | physical-v2 reference (sha256) |
| --- | --- | --- | --- | --- |
| `dev_may_hard_reentry` | `dev_may_hard_reentry` | hard comparison | `bags/source/curated/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw` (`becad555...`) | `dev_may_hard_reentry.json` (`45d620d9...`) |
| `dev_june_seq01` | `dev_june_seq01` | regression / stability gate | `bags/replay/p025_seq01_physical_v2_common_input_2026_08_29` (`abf769b7...`) | `seq01_clean.json` (`c0d7c2a3...`) |
| `dev_june_seq03` | `dev_june_seq03_ocsort` | hard comparison | `bags/replay/p058_seq03_physical_v2_common_input_2026_08_28` (`fe5dc3b0...`) | `seq03_crossing.json` (`9e03fedc...`) |
| `dev_june_seq04` | `dev_june_seq04_ocsort` | hard comparison (physical absence) | `bags/replay/p058_seq04_physical_v2_common_input_2026_08_28` (`cacaba91...`) | `seq04_occlusion_no_exit.json` (`a99fb5ea...`) |

The May common input is the curated development raw source bag itself, passed
directly to `run_deterministic_tracker_replay.py`, which processes its 953
recorded detections in original source order using prior images identically
for every configuration (974 recorded images; 21 image frames have no matching
recorded detection, a pre-existing property of the 2026-05-14 capture). Its
recorded detections retain the May 2026 tim_v1-era detector that generated
them. The three June common inputs are the frozen YOLOv8s detection streams
established for the Issue #25/#58 physical-v2 work, with one-to-one
image/detection header equality (1520, 1931, 2047 frames).

### Canonical baseline reproduction

The canonical baseline was rerun through this harness rather than compared to
any previously published number.

| Sequence | Correct (s) | Wrong (s) | Lost (s) | Absent-with-output (s) | IoU wmean | Cross-check |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `dev_may_hard_reentry` | 63.089844 | 0.132906 | 4.642160 | 0.000000 | 0.838358 | +0.50 s correct vs prior p090/p058 May, from regenerating the ByteTrack candidate stream from the curated raw detections (mandatory here) rather than reusing a pre-frozen `/tracks` stream |
| `dev_june_seq01` | 61.200517 | 0.000000 | 0.000000 | 0.000000 | 0.876941 | exact match to the prior p090 Seq01 baseline `61.200516816` |
| `dev_june_seq03` | 25.067443 | 0.133349 | 58.566005 | 0.000000 | 0.869743 | exact match to the promoted post-#90 p090 Seq03 result `25.067443244` |
| `dev_june_seq04` | 43.469300 | 0.000000 | 29.030742 | 0.000000 | 0.817638 | exact match to the promoted post-#90 p090 Seq04 result `43.469299585` |

Seq01/Seq03/Seq04 reproduce the established pipeline to the digit against the
current canonical TIM-MARS. Every candidate in this study is compared against
this baseline, not against an older report.

## Repeatability

`deterministic: true`. The canonical baseline was rerun twice on each of the
four sequences through this same harness. All 8 repeat checks passed with
**zero mismatches**: every repeat reproduced the primary baseline's tracker
generated-semantic digest, TIM generated-semantic digest, bootstrap tracker
ID, physical-v2 correct/wrong/lost duration buckets, and TIM state-occupancy
fractions exactly. Small parameter differences below are therefore real
behavioural differences, not replay noise.

## Cell accounting

- 7 configurations x 4 development sequences = 28 first-pass cells.
- canonical baseline x 4 sequences x 2 repeats = 8 repeatability cells.
- **36/36 cells completed successfully. 0 bootstrap failures. 0 other failures.**

## First-pass results: TIM-MARS physical-v2 delta vs baseline

Delta correct / delta wrong / delta lost, in seconds.

| config | dev_may_hard_reentry | dev_june_seq01 | dev_june_seq03 | dev_june_seq04 | overall |
| --- | --- | --- | --- | --- | --- |
| `track_thresh_lower_1` (0.40) | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / -0.133 / +0.133 | +0.199 / +0.000 / -0.199 | **neutral** |
| `track_thresh_higher_1` (0.60) | +0.620 / **+0.451** / -1.072 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.365 / +0.000 / -0.365 | **unsafe regression** |
| `match_thresh_lower_1` (0.70) | -0.148 / +0.000 / +0.148 | +0.000 / +0.000 / +0.000 | +0.000 / -0.133 / +0.133 | **-1.034** / +0.000 / +1.034 | **regressed** |
| `match_thresh_higher_1` (0.90) | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | **neutral** |
| `track_buffer_lower_1` (15) | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | **neutral** |
| `track_buffer_higher_1` (45) | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | +0.000 / +0.000 / +0.000 | **neutral** |

Absent-with-output stayed at `0.000 s` for the TIM-MARS stream in **every**
cell, including every Seq04 cell across the `13.9 s` physical target absence.

No candidate is `improved` on any sequence. Every non-zero downstream delta
except the two flagged cells is below `0.5 s` on a `60-87 s` window and is
characterised as marginal / no meaningful signal.

## First-pass results: raw fixed-ID ByteTrack physical-v2

The raw tracker output does change substantially for several candidates. It is
the downstream TIM-MARS result above that does not.

Raw correct / raw wrong / raw lost, in seconds; baseline then candidate.

| config / sequence | raw correct | raw wrong | raw lost | target ID switches |
| --- | --- | --- | --- | --- |
| baseline `dev_may_hard_reentry` | 49.612 | 7.630 | 10.624 | 9 |
| `match_thresh_lower_1` May | 66.178 | **0.033** | 1.653 | 10 |
| `track_thresh_higher_1` May | 66.179 | 0.485 | 1.201 | 8 |
| baseline `dev_june_seq03` | 33.832 | 0.100 | 49.835 | 18 |
| `match_thresh_higher_1` Seq03 | 45.399 | **22.798** | 15.570 | 17 |
| `match_thresh_lower_1` Seq03 | 27.565 | 0.133 | 56.069 | 27 |
| `track_thresh_higher_1` Seq03 | 27.332 | 0.100 | 56.335 | 18 |
| `track_thresh_lower_1` Seq03 | 34.033 | 0.000 | 49.734 | 21 |
| baseline `dev_june_seq04` | 26.567 | 37.501 | 8.432 | 13 |
| `match_thresh_lower_1` Seq04 | 26.567 | **6.534** | 39.399 | 12 |
| `match_thresh_higher_1` Seq04 | 26.567 | 32.301 | 13.632 | 13 |

`track_buffer` at 15 and 45 produced a raw tracker stream that is identical to
the canonical baseline on every sequence, with the single negligible exception
that `track_buffer_lower_1` on Seq04 changed the raw target-visible coverage
from `0.93477` to `0.934188`. On these four sequences a lost tracklet was
either re-associated well within 15 frames or removed and replaced by a fresh
identity, so the 15-versus-45 frame `max_time_lost` difference never changed a
removal decision that mattered to the selected target.

Seq01 is completely flat: raw and TIM streams are `61.200517 / 0 / 0` with
`0` target ID switches, `1` fragment and `1.000` visible coverage for every
configuration.

## First-pass results: TIM-MARS state behaviour

TIM transitions into LOST / into REACQUIRED, from `/target_memory_mars/status`:

| config | May | Seq01 | Seq03 | Seq04 |
| --- | --- | --- | --- | --- |
| baseline | 6 / 7 | 0 / 0 | 3 / 3 | 19 / 20 |
| `track_thresh_lower_1` | 6 / 7 | 0 / 0 | 3 / 3 | 17 / 18 |
| `track_thresh_higher_1` | 4 / 5 | 0 / 0 | 3 / 3 | 17 / 19 |
| `match_thresh_lower_1` | 5 / 6 | 0 / 0 | 3 / 3 | 18 / 19 |
| `match_thresh_higher_1` | 6 / 7 | 0 / 0 | 3 / 3 | 19 / 20 |
| `track_buffer_lower_1` | 6 / 7 | 0 / 0 | 3 / 3 | 19 / 20 |
| `track_buffer_higher_1` | 6 / 7 | 0 / 0 | 3 / 3 | 19 / 20 |

Selection-generation (target-authority) changes are `0` on Seq01, `2-3` on
Seq03, `3` on Seq04 (7 for `match_thresh_lower_1`), and `2-3` on May. State
occupancy is dominated by LOCKED on Seq01 (`1.000`), May (`0.93`) and, at the
opposite end, by LOST on Seq03 (`0.69`); it moves by less than one percentage
point for any candidate on any sequence.

## Per-sequence analysis

### Seq01 clean (regression / stability gate)

Every candidate is byte-identical to the canonical baseline: TIM and raw
`61.200517 / 0 / 0`, `0` target ID switches, `1.000` visible coverage, `0`
state transitions, `100 %` LOCKED occupancy. No tested ByteTrack perturbation
destabilises a healthy sequence, and none provides any improvement on it (the
baseline is already a perfect controller-facing result). Seq01 passes as a
regression gate for every candidate.

### May hard re-entry

The canonical baseline is `63.090 / 0.133 / 4.642` (TIM) over a `67.865 s`
window; the raw fixed-ID tracker is `49.612 / 7.630 / 10.624`, with 9 target
ID switches through the exit / re-entry / ID-switch event.

- `track_thresh_lower_1` (0.40), `match_thresh_higher_1` (0.90),
  `track_buffer_lower_1` (15) and `track_buffer_higher_1` (45) leave both the
  raw tracker stream and the TIM stream unchanged from baseline.
- `match_thresh_lower_1` (0.70) transforms the raw tracker
  (`66.178 / 0.033 / 1.653`: raw wrong-person falls from `7.630 s` to
  `0.033 s`, raw correct rises `16.6 s`). The TIM stream barely moves:
  `-0.148 s` correct, `+0.000 s` wrong, `+0.148 s` lost. Marginal; classified
  neutral.
- `track_thresh_higher_1` (0.60) also transforms the raw tracker
  (`66.179 / 0.485 / 1.201`). Downstream TIM gains `+0.620 s` correct but also
  gains **`+0.451 s` wrong-target authority** (`0.133 s -> 0.584 s`), converting
  `1.072 s` of LOST time into both correct and wrong output. Because a
  wrong-target-authority increase above the `0.05 s` tolerance is the most
  serious regression class in the safety ordering, `track_thresh_higher_1` is
  classified an **unsafe regression** on the strength of this sequence.

### Seq03 crossing

The canonical baseline is `25.067 / 0.133 / 58.566` (TIM) over `83.867 s`; the
raw fixed-ID tracker is `33.832 / 0.100 / 49.835` with 18 target ID switches
through the four-person crossing.

- `match_thresh_higher_1` (0.90) drives the raw fixed-ID tracker to
  **`45.399 / 22.798 / 15.570`**: raw wrong-person output rises from `0.100 s`
  to `22.798 s`, a roughly 228-fold increase and by far the largest raw
  failure observed in the study. The downstream TIM-MARS stream is
  **byte-identical to the canonical baseline** (`25.067 / 0.133 / 58.566`,
  identical LOST occupancy, identical transition counts). TIM-MARS suppresses
  the entire 22.8 s raw wrong-person burst. This is the strongest single piece
  of downstream identity-robustness evidence in the study. It is evidence that
  TIM-MARS is acting as the identity-safety layer, not evidence that
  `match_thresh 0.90` is a good tracker setting: the raw configuration itself
  is clearly worse.
- `match_thresh_lower_1` (0.70) and `track_thresh_lower_1` (0.40) each remove
  the residual `0.133 s` of TIM wrong-target output on this sequence, at the
  cost of `+0.133 s` LOST and zero correct-target change. `0.133 s` is at the
  level of a single reference-gap interval and is not treated as a meaningful
  safety improvement.
- `track_thresh_higher_1` (0.60) and both `track_buffer` settings leave the
  TIM stream unchanged.

### Seq04 occlusion / no exit (physical absence)

The canonical baseline is `43.469 / 0.000 / 29.031` (TIM) over `72.500 s` of
physically scored present time, with `0.000 s` absent-with-output across the
`13.900 s` explicit physical target absence. The raw fixed-ID tracker is
`26.567 / 37.501 / 8.432` with `13.100 s` of raw absent-with-output.

- `match_thresh_lower_1` (0.70) reduces the raw wrong-person duration from
  `37.501 s` to `6.534 s` but the downstream TIM stream **loses `1.034 s` of
  correct-target authority** (`43.469 s -> 42.435 s`), moving it into LOST.
  This is the only meaningful downstream availability change in the study and
  it is a regression, so `match_thresh_lower_1` is classified **regressed**.
- `track_thresh_lower_1` (0.40) and `track_thresh_higher_1` (0.60) each add a
  marginal `+0.199 s` and `+0.365 s` of correct-target output with no
  wrong-target and no absence leakage. Both are below the `0.5 s` threshold and
  are treated as no meaningful signal.
- `match_thresh_higher_1` (0.90), `track_buffer_lower_1` (15) and
  `track_buffer_higher_1` (45) leave the TIM stream unchanged.
- Across every tested configuration, TIM-MARS absent-with-output stayed at
  `0.000 s` through the physical absence. Changing the ByteTrack lost-track
  buffer, in either direction, did not cause TIM-MARS authority to leak during
  the `13.9 s` interval in which the physical target is not present.

## Which parameter had the strongest effect

`track_thresh` is the only ByteTrack parameter in this study with any
downstream TIM-MARS signal, and its effect is small, inconsistent in sign, and
unsafe at the higher setting:

- `track_thresh = 0.60` on May: `+0.451 s` wrong-target authority (unsafe).
- `track_thresh = 0.40` on Seq03: `-0.133 s` wrong-target (marginal).
- `track_thresh` on Seq04: `+0.2` to `+0.37 s` correct (marginal).

`match_thresh` changed the raw tracker most dramatically (up to `22.8 s` of
raw wrong-person on Seq03, and `-31 s` of raw wrong-person on Seq04) but
produced no safe downstream improvement: `match_thresh_higher_1` was neutral
downstream despite a catastrophic raw failure, and `match_thresh_lower_1`
regressed downstream availability on Seq04.

`track_buffer` had **no meaningful downstream effect on any of the four
development sequences**, including the Seq04 physical-absence interval.

## Did tracker changes propagate through TIM-MARS?

Largely, no. Raw fixed-ID ByteTrack output moved by tens of seconds of
correct/wrong reallocation under several candidates (`match_thresh_higher_1` on
Seq03: raw wrong `0.100 s -> 22.798 s`; `match_thresh_lower_1` on May: raw
wrong `7.630 s -> 0.033 s`; `match_thresh_lower_1` on Seq04: raw wrong
`37.501 s -> 6.534 s`), while the authoritative `/target_memory_mars` output
moved by at most `1.034 s` in any cell and by less than `0.5 s` in almost all
of them. On the sequence with the largest raw failure (Seq03,
`match_thresh_higher_1`) the TIM stream was byte-identical to baseline.

The defensible claim is bounded: this holds for these three ByteTrack
parameters, over these one-step ranges, on these four development sequences,
with this frozen TIM-MARS configuration and this deterministic
recorded-detection setup. It is not a claim that ByteTrack configuration is
globally irrelevant.

## Wrong-target safety regressions

One: `track_thresh_higher_1` (0.60) on `dev_may_hard_reentry`, `+0.451 s` of
TIM-MARS wrong-target authority (`0.133 s -> 0.584 s`). No other cell increased
TIM wrong-target output above the `0.05 s` tolerance, and TIM absent-with-output
was `0.000 s` in every cell.

## Second pass

Not performed and not justified. No OFAT direction is convincingly promising:
no candidate is `improved` on any sequence, `track_buffer` does nothing
downstream, `match_thresh` provides no safe downstream gain, and `track_thresh`
is inconsistent and unsafe at 0.60. There is nothing to combine.

## Final classification

| candidate | overall | basis |
| --- | --- | --- |
| `track_thresh_lower_1` (0.40) | **neutral** | only sub-0.5 s downstream effects; no meaningful, consistent improvement |
| `track_thresh_higher_1` (0.60) | **unsafe regression** | May: `+0.451 s` wrong-target TIM authority |
| `match_thresh_lower_1` (0.70) | **regressed** | Seq04: `-1.034 s` correct-target TIM authority |
| `match_thresh_higher_1` (0.90) | **neutral downstream** | ~22.8 s raw wrong-person on Seq03 fully absorbed by TIM-MARS; the raw configuration itself is worse |
| `track_buffer_lower_1` (15) | **neutral** | no meaningful downstream effect on any sequence |
| `track_buffer_higher_1` (45) | **neutral** | no meaningful downstream effect on any sequence |

No candidate is `improved`.

## Recommendation

**NO — development evidence does not justify proposing a change to the
canonical ByteTrack configuration.**

`ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml` is unchanged and no
canonical-configuration change follows from this experiment.

The scientifically useful result is the downstream one: tuning ByteTrack
around its current operating point has little useful effect on the
authoritative TIM-MARS output, and TIM-MARS absorbs even a severe upstream
association failure (Seq03, `match_thresh 0.90`, ~22.8 s of raw wrong-person
output) without a comparable controller-facing failure. TIM-MARS is functioning
as the identity-safety layer rather than inheriting raw tracker identity
behaviour, within the tested parameters, ranges, sequences, frozen TIM-MARS
configuration, and deterministic recorded-detection setup.

## Reproduction

```bash
cd ~/Desktop/Thesis-Code
git checkout 14c3ef20755863e7ced3350fe823ccc017277ae3
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 tools/experiments/run_bytetrack_tim_sensitivity.py --run --repeatability \
  --run-id p058b_bytetrack_config_sensitivity_14c3ef20_2026_09_07
python3 tools/analysis/aggregate_bytetrack_tim_sensitivity.py \
  reports/p058b_bytetrack_config_sensitivity_14c3ef20_2026_09_07
```

## Provenance

- pre-outcome methodology commit: `14c3ef20755863e7ced3350fe823ccc017277ae3`
- manifest sha256: `44b96035330c0eb9690b0e7c5f42c02acb33138a2ded771fbc000eb7ef2f6954`
- canonical ByteTrack config sha256: `e0e5c7c80a2f2b74cb6640e2ea90d9651c33f193c34365dc0d5a7ac9badaa906`
- TIM-MARS config sha256: `0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0`
- MARS model sha256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- split sha256: `34bf5b6f09f8938b23fae7cda18314e3aa06115ed0f966f60b8ca6bda8cfb409`
- cells: 36 completed, 0 bootstrap failures, 0 other failures
- machine-readable evidence:
  `docs/results/selected_target_tracking/p058b_bytetrack_config_sensitivity_development/`
  (`manifest_lock.json`, `run_provenance.json`, `repeatability.json`,
  `classification.json`, `comparison_by_sequence.csv` / `.json`,
  `tim_metrics.csv`, `raw_tracker_metrics.csv`, `cells.csv`, `cells.json`,
  `cell_digests.csv`, `run_console.log`, `SHA256SUMS`)
- The intermediate per-cell replay MCAP bags under
  `bags/replay/p058b_bytetrack_config_sensitivity_14c3ef20_2026_09_07/` were
  removed after evaluation to reclaim disk; the per-cell tracker-freeze and
  TIM-replay metadata, generated-semantic digests, and resolved-runtime
  fingerprints are retained under that path and every cell remains auditable
  and reproducible from commit `14c3ef20`.
