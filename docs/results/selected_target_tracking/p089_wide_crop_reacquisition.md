# Issue #89 — Wide-crop TIM-MARS reacquisition

## Status

**Software and development evaluation complete at commit `046ff8b3`; exact
live/simple-scene reproduction remains pending before Issue #89 can close.**

Issue #89 was opened after a live Raspberry Pi 5 integration failure observed on
1 September 2026. A clearly visible selected person remained on ByteTrack ID
`142`, with very strong same-ID geometry, but TIM-MARS stayed in `LOST/HOVER`
because the selected crop was rejected from MARS appearance encoding solely as
`aspect_ratio_too_wide`.

The implementation now separates:

- whether a crop may provide current appearance evidence for identity
  comparison; and
- whether that crop is trusted to update reusable positive appearance memory.

A sufficiently large, unclipped wide crop can therefore be encoded for current
comparison/reacquisition while remaining ineligible for cache/gallery/positive
memory updates.

The software change is frozen and development evidence shows no controller-facing
identity regression. The GitHub acceptance criterion requiring improved
availability in the exact live/simple-scene reproduction has not yet been
executed, so this issue remains open and Issue #90 must not begin yet.

## Original live failure

Canonical live stack:

- Raspberry Pi 5;
- YOLOv8s direct/in-process Hailo detector;
- ByteTrack;
- CPU MARS;
- TIM-MARS;
- controller disabled;
- two visible people.

Representative selected-target state:

- tracker ID: `142`;
- `state = LOST`;
- `control_mode = HOVER`;
- `visible = false`;
- `target_track_id = 142`;
- `candidate_track_id = 142`;
- suppression:
  `same_id_reacquisition_reject:no_candidate_appearance`.

Representative geometry remained extremely strong:

- detector confidence approximately `0.88--0.89`;
- total geometry approximately `0.97`;
- centre similarity approximately `0.999`;
- IoU approximately `0.95--0.97`;
- scale similarity approximately `1.0`;
- same-ID bonus `1.0`.

The selected crop was approximately:

- width `480--482 px`;
- height `381--383 px`;
- width/height aspect ratio `1.25--1.27`;
- clipping fraction `0.0`.

Despite being large and unclipped, the old crop-quality contract produced:

- `aspect_ratio_too_wide`;
- `encoding_eligible = false`;
- `memory_update_eligible = false`.

## Code-path root cause

The failure crossed three existing subsystems.

### 1. Crop quality

`thesis_bringup/tim_mars/crop_quality.py` originally added
`aspect_ratio_too_wide` to `encoding_reasons`, then copied all encoding
rejections into `memory_reasons`.

Therefore the canonical
`appearance_crop_max_aspect_ratio = 1.00` simultaneously controlled:

1. whether the crop could be encoded at all; and
2. whether its feature could update trusted positive appearance memory.

### 2. Appearance attachment

`appearance_attachment.py` already had the architecture needed for a safer
split:

- only `encoding_eligible` crops are sent to the appearance backend;
- fresh features may be attached directly to the current `CandidateTrack`;
- reusable appearance cache updates additionally require
  `memory_update_eligible`.

Thus current comparison evidence and trusted reusable memory were already
represented separately downstream.

### 3. LOST same-ID safety gate

`target_memory.py` deliberately rejects LOST/UNCERTAIN same-ID recovery when the
candidate has no current appearance evidence:

`same_id_reacquisition_reject:no_candidate_appearance`

That safety rule is retained unchanged.

The defect was therefore upstream appearance unavailability caused by crop
eligibility, not an overly conservative same-ID hijack gate.

## Implemented contract

Software commit:

`046ff8b3192a756562a807117b80518c3de4302e`

Commit subject:

`04-09-26: fix wide-crop TIM-MARS reacquisition`

The upper aspect-ratio check now contributes only to positive-memory
ineligibility.

A wide crop that still passes the existing comparison-quality requirements for
minimum size, clipping, and minimum aspect ratio may be encoded and used as
current appearance evidence.

The canonical upper aspect-ratio threshold remains a conservative positive-memory
trust gate. A crop exceeding that threshold therefore cannot contaminate the
reusable positive appearance cache/gallery solely because comparison encoding is
now allowed.

No new finite comparison-side maximum aspect-ratio threshold was introduced.
The retained development crop telemetry did not provide evidence for a
scientifically justified replacement cutoff such as `1.5`, `1.75`, or `2.0`.

No geometry-only recovery fallback was introduced.

Same-ID hijack protection remains enabled and unchanged.

## MARS preprocessing audit

The canonical CPU model is:

`models/reid/mars-small128.pb`

SHA-256:

`e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`

Its input is `128 x 64 x 3`, corresponding to width/height aspect ratio `0.5`.

The local shared `MarsSmall128Extractor` crops the supplied bbox and directly
resizes that crop to the fixed model input. It does not currently pad or
letterbox wide crops to a canonical person aspect ratio.

Historical DeepSORT/MARS implementations can canonicalise bbox width before
crop/resize. The local extractor is shared by TIM-MARS, Target-ReID, DeepSORT
and analysis tooling, however, so changing that shared preprocessing under
Issue #89 would alter multiple architecture contracts and historical
comparability.

Issue #89 therefore deliberately does **not** change shared MARS preprocessing.
Any future preprocessing experiment would require explicit cross-architecture
recalibration and evaluation rather than being introduced as a hidden part of
this defect fix.

## Regression coverage

Issue #89 added explicit regression coverage for:

- a large, unclipped wide crop;
- wide comparison eligibility with positive-memory ineligibility;
- fresh appearance attachment without cache update;
- LOST same-ID recovery using wide current appearance;
- a competing distractor during wide-target recovery;
- two-step recovery confirmation;
- prevention of wrong-person identity authority;
- preservation of the no-appearance same-ID rejection path through the
  pre-existing target-memory safety tests.

A deterministic integration probe reproduced the intended state-machine
contract:

1. selected target ID `142` enters `LOST`;
2. wide target ID `142` and distractor ID `77` return;
3. target appearance matches protected target appearance;
4. distractor appearance does not;
5. first update enters confirmation-gated `REACQUIRED`;
6. second update returns to `LOCKED`;
7. target authority remains ID `142`;
8. the wide crop does not update positive reusable memory.

## Validation

Validation completed before the software commit:

- `tools/thesis_build.sh --packages-select thesis_bringup`: PASS;
- thesis_bringup pytest suite: `425 passed, 1 skipped`;
- flake8: PASS;
- `git diff --check`: PASS;
- no root-level `log/` or `hailort.log`.

## Development crop telemetry

The retained development-only crop audit covered Seq01, Seq03 and Seq04.
The May corrected replay could not be opened by the same storage path and was
not used for this crop-record count.

Across the readable retained development bags:

- crop-quality records: `20,299`;
- crops with aspect ratio above `1.0`: `28`;
- all 28 occurred in Seq04;
- Seq01 wide crops: `0`;
- Seq03 wide crops: `0`.

The 28 Seq04 wide records were small/transient non-target candidate boxes in the
retained development sequence. None was a large, unclipped selected/candidate
wide crop matching the 1 September live failure.

This is important: the retained sequences test regression safety, but they do
not reproduce the live availability defect itself.

## Deterministic development replay provenance

The post-fix deterministic replays were generated from frozen #58 ByteTrack
candidate streams with the canonical configuration and MARS model.

Canonical TIM-MARS config SHA-256:

`e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`

### Seq03

Output:

`bags/replay/p089_seq03_wide_crop_046ff8b3_2026_09_04`

Frozen candidate-stream SHA-256:

`60e41fb14822af5a04b781ac08a6a75e7a05382a9bd55629a737a325512582db`

Post-fix generated semantic SHA-256:

`de219d248aed32b14649a7eab29065c0899d86db747456eda3565056e45c7304`

Repository status recorded by replay provenance was clean.

### Seq04

Output:

`bags/replay/p089_seq04_wide_crop_046ff8b3_2026_09_04`

Frozen candidate-stream SHA-256:

`9c514facb5cd946a02800885e8bacb9ea9fb0132d6ceab4c73e7f4a30ce3c3bf`

Post-fix generated semantic SHA-256:

`695ae20a8f630fceec74996a373b45c0620f6a096bd2a81510f5c4d65f6b0942`

Repository status recorded by replay provenance was clean.

## Before/after eligibility semantics

Status diagnostics give the direct crop-policy evidence.

### Seq03

There were no crops above the canonical `1.0` upper aspect-ratio threshold.

Old and new diagnostics are unchanged:

- crop records: `5,437`;
- wide crop records: `0`;
- frame-counter encoding rejected sum: `23`;
- frame-counter encoding eligible sum: `844`;
- frame-counter memory ineligible sum: `896`.

### Seq04

Crop-level behavior changed exactly as intended.

Before:

- crop records: `8,958`;
- wide crop records: `28`;
- wide encoding eligible: `0/28`;
- wide encoding rejected: `28/28`;
- wide memory eligible: `0/28`;
- wide memory ineligible: `28/28`.

After:

- crop records: `8,958`;
- wide crop records: `28`;
- wide encoding eligible: `28/28`;
- wide encoding rejected: `0/28`;
- wide memory eligible: `0/28`;
- wide memory ineligible: `28/28`.

The aggregate per-frame attachment counters change from:

- encoding rejected: `28 -> 0`;
- encoding eligible: `1382 -> 1387`;
- memory ineligible: `2600 -> 2600`.

The aggregate encoding-eligible counter is a per-frame attachment diagnostic,
not a one-to-one count of crop-quality records. The crop-level `28/28` result is
the direct evidence for the changed wide-crop semantic contract.

The number of
`same_id_reacquisition_reject:no_candidate_appearance` status mentions remains
unchanged on these retained sequences:

- Seq03: `4 -> 4`;
- Seq04: `186 -> 186`.

This is expected because these sequences do not contain the large selected-target
wide-crop failure observed live.

## Physical-v2 development safety regression

Identity-independent physical-v2 evaluation was rerun before/after on Seq03 and
Seq04.

Physical references:

- Seq03:
  `docs/data/physical_target_references/seq03_crossing.json`,
  SHA-256
  `9e03fedc8076638bfb300cf131672aef38927252c09ac48174fa79bd2aa17f71`;
- Seq04:
  `docs/data/physical_target_references/seq04_occlusion_no_exit.json`,
  SHA-256
  `a99fb5ea98c3f1442c6a90851235f51d773e509ea7be5e7c058bad8d2a0c886b`.

### Seq03 TIM-MARS

Before and after are byte-identical under the physical-v2 evaluator:

- correct-target output: `22.532686264 s`;
- wrong-person output: `0 s`;
- identity unresolved: `0 s`;
- lost/suppressed: `61.234111519 s`;
- physical-reference gap: `0.100453371 s`.

### Seq04 TIM-MARS

Before and after are byte-identical under the physical-v2 evaluator:

- correct-target output: `35.068442774 s`;
- wrong-person output: `0 s`;
- identity unresolved: `0 s`;
- lost/suppressed: `37.431598998 s`;
- target absent: `13.900030159 s`;
- target absent with output: `0 s`;
- physical-reference gap: `0.100883795 s`.

Therefore the wide-crop eligibility change introduces **zero measured
wrong-person regression** and **zero target-absence publication regression** on
the retained physical-v2 development evidence.

## Event/recovery regression equality

The legacy tracker-ID annotation event/recovery evaluator was also run before
and after solely as a deterministic semantic-regression check.

For both Seq03 and Seq04:

- `duration_metrics`: identical;
- `episode_metrics`: identical;
- `recovery_rows`: identical;
- `status_recovery_metrics`: identical;
- all generated CSV files: byte-identical;
- only report provenance differs between old and new runs.

These tracker-ID-derived wrong-target values are **not** substituted for the
identity-independent physical-v2 safety result. Their role here is to prove
before/after behavioral equality under the existing event/recovery tooling.

Generated development reports are retained locally under:

`reports/p089_wide_crop_046ff8b3_2026_09_04/`

They are generated/ignored evidence rather than tracked repository source.

## Scientific interpretation

The development result is intentionally narrow.

It demonstrates that:

1. the old upper aspect-ratio rule unnecessarily prevented current identity
   comparison;
2. the new rule permits wide comparison evidence;
3. the same wide crops remain excluded from positive reusable memory;
4. same-ID hijack protection was not weakened;
5. no geometry-only authority path was introduced;
6. the retained canonical development sequences show no controller-facing
   physical-v2 safety regression.

It does **not** demonstrate improved reacquisition availability on Seq03 or
Seq04 because neither sequence reproduces the large selected-target wide-crop
failure.

It also does not use held-out H01--H03 evidence. Those sequences remain
untouched and isolated from algorithm development.

## Live reproduction refinement — 4 September 2026

The first live validation after `046ff8b3` confirmed that the original
pre-encoding aspect-ratio defect was removed, but it exposed a second
downstream eligibility conflation.

A narrow, trusted operator selection was established first. Live status showed:

- target tracker ID `33`;
- state `LOCKED`;
- `protected_anchor_available=true`;
- trusted gallery size `4`;
- trusted appearance lineage.

The same tracker ID was then retained while the target adopted a wide pose.
Immediately before the controlled lens-cover loss, the tracker bbox was about
`561.571 x 408.704 px`, or approximately `1.374` width/height.

After the brief loss, TIM-MARS reached `LOST`, and tracker ID `33` returned as
the same candidate ID. The current crop evidence showed:

- aspect ratio about `1.372`;
- clipping fraction `0`;
- `encoding_eligible=true`;
- `memory_update_eligible=false`;
- rejection reason `aspect_ratio_too_wide`;
- current appearance available and evaluated;
- positive similarity `0.8435138464`;
- positive support source `trusted_gallery`.

Therefore the original wide-crop encoding blockage was demonstrably removed in
the reproduced live case. However, reacquisition still did not complete.
The state machine repeatedly emitted
`protected_gallery_reacquisition_reject:untrusted_crop`.

Read-only code inspection identified the exact remaining gate in
`candidate_safety_policy.py`: protected-gallery reacquisition treated
`appearance_memory_update_eligible=false` as a blanket rejection. That policy
therefore still conflated suitability for current identity comparison with
suitability for reusable positive-memory adaptation.

The second Issue #89 software correction is deliberately narrow:

- a crop may bypass this protected-gallery `untrusted_crop` rejection only when
  explicit current `appearance_crop_quality` provenance exists;
- the crop must be encoding-eligible;
- it must remain memory-update-ineligible;
- its complete rejection-reason tuple must be exactly
  `('aspect_ratio_too_wide',)`;
- generic provenance-free `memory_update_eligible=false` observations remain
  rejected;
- overlap/group-contaminated comparison crops remain rejected;
- positive anchor/gallery adaptation still requires memory-update eligibility;
- same-ID hijack protection is unchanged;
- no geometry-only fallback is introduced.

The new contract was added test-first. Before the policy edit, the wide-only
protected-gallery test failed while the two conservative rejection controls
passed. After the policy edit:

- focused protected-gallery contract: `3 passed`;
- focused crop/attachment/appearance/protected-memory set: `74 passed`;
- same-ID/hijack/wide/protected-gallery regression subset: `17 passed`;
- complete `thesis_bringup` test suite: `427 passed, 1 skipped`;
- `tools/thesis_build.sh --packages-select thesis_bringup`: PASS;
- `git diff --check`: PASS;
- no root-level `log/`, `hailort.log`, or `.pytest_cache` was created.

The prior live process loaded the pre-fix Python module, so it cannot serve as
validation of this second correction. A fresh runtime restart from the committed
software state is required.

## Final live acceptance — 4 September 2026

The second software correction was committed as
`64cce622a6eb6bc27faf9b8b9b1de0960e33db47` and loaded into a fresh canonical
live runtime.

Recorded live evidence:

`bags/live_camera/2026-09-04__12-06-50__video__p089_live_wide_crop_acceptance_02`

The run metadata records a clean repository at `64cce622`, YOLOv8s direct
Hailo inference, ByteTrack, TIM-MARS with CPU MARS appearance, and controller
output disabled for the acceptance exercise.

A narrow target was first selected as tracker ID `1`. Before widening, status
showed:

- state `LOCKED`;
- target and candidate tracker ID `1`;
- `visible=true`;
- `protected_anchor_available=true`;
- trusted gallery size `4`;
- trusted appearance lineage;
- narrow crop aspect ratio approximately `0.591`;
- narrow crop both encoding-eligible and memory-update-eligible.

The same ByteTrack ID was then retained while the person widened. Immediately
before the loss exercise, `ids` reported approximately
`431.328 x 395.501 px`, already above the canonical `1.0` width/height
memory-trust threshold.

A 10-second diagnostic then applied a brief controlled lens cover. The final
acceptance summary was:

- status messages: `299`;
- `lost_seen=true`;
- `reacquired_same_id=true`;
- `locked_after_reacquire=true`;
- wide samples: `260`;
- wide comparison-only samples: `260`;
- wide samples with evaluated appearance: `48`;
- wide positive-memory updates: `0`;
- wrong visible authority samples: `0`;
- overall acceptance: `PASS=YES`.

The observed state path included:

- `UNCERTAIN` at approximately `3.191 s`;
- `LOST` at approximately `3.388 s`;
- conservative protected-anchor rejection while appearance agreement was still
  insufficient (`0.316 < 0.750`, later `0.690 < 0.750`);
- transient
  `same_id_reacquisition_reject:no_candidate_appearance` between selective
  appearance evaluations;
- `REACQUIRED` at approximately `4.363 s`, with the existing
  `recovery_persistence_pending: id=1 confirm=1/2` gate;
- `LOCKED`, visible, on the same ID at approximately `4.367 s`.

The final wide same-ID evidence later in the probe showed:

- aspect ratio: `1.1773798505`;
- clipping fraction: `0`;
- `encoding_eligible=true`;
- `memory_update_eligible=false`;
- sole rejection reason: `aspect_ratio_too_wide`;
- current appearance available and evaluated;
- positive similarity: `0.8841875126`;
- positive support source: `trusted_gallery`;
- positive memory updated: `false`.

This directly satisfies the live/simple-scene acceptance requirement that
motivated Issue #89: a large valid wide crop can now supply current appearance
for same-ID LOST recovery without being admitted into reusable positive memory.
The existing appearance and protected-anchor safety gates remain active during
recovery rather than being bypassed.

## Final-commit deterministic development regression

Because the second correction changes the downstream protected-gallery policy,
Seq03 and Seq04 were replayed again from their frozen ByteTrack candidate
streams under final software commit `64cce622`.

Final replay outputs:

- Seq03:
  `bags/replay/p089_seq03_wide_crop_64cce622_2026_09_04`;
- Seq04:
  `bags/replay/p089_seq04_wide_crop_64cce622_2026_09_04`.

Frozen candidate-stream SHA-256 values were reverified exactly:

- Seq03:
  `60e41fb14822af5a04b781ac08a6a75e7a05382a9bd55629a737a325512582db`;
- Seq04:
  `9c514facb5cd946a02800885e8bacb9ea9fb0132d6ceab4c73e7f4a30ce3c3bf`.

The generated semantic digests are also exactly unchanged from the first
post-fix replay:

- Seq03:
  `de219d248aed32b14649a7eab29065c0899d86db747456eda3565056e45c7304`;
- Seq04:
  `695ae20a8f630fceec74996a373b45c0620f6a096bd2a81510f5c4d65f6b0942`.

Final provenance artifacts include:

- Seq03 replay metadata SHA-256:
  `9d361d4744bfc4e413821483b95b828483171a539c8ab83735c068cec2a24c39`;
- Seq03 resolved-runtime SHA-256:
  `fbdcb6897b8dc02bdc4ff6cee99079dc5aa50d3bdee2e3912e49d325649ac2ad`;
- Seq04 replay metadata SHA-256:
  `ca3b0fd2d07047e4765961084f97b058d51ff200c7cf67204ecc2f48b53d1490`;
- Seq04 resolved-runtime SHA-256:
  `53d86b9ca8a515e29009d5a25f69eeb6f5e5440b5abda357ca6b22a6f8d2475b`.

## Final physical-v2 safety gate

Identity-independent physical-v2 evaluation was rerun directly on the final
`64cce622` replay outputs. Generated reports are retained locally under:

`reports/p089_wide_crop_64cce622_2026_09_04/physical_v2/`

Seq03 final TIM-MARS result:

- correct-target output: `22.532686264 s`;
- wrong-person output: `0 s`;
- identity unresolved: `0 s`;
- lost/suppressed: `61.234111519 s`;
- physical-reference gap: `0.100453371 s`;
- reconciliation: PASS.

Seq04 final TIM-MARS result:

- correct-target output: `35.068442774 s`;
- wrong-person output: `0 s`;
- identity unresolved: `0 s`;
- lost/suppressed: `37.431598998 s`;
- target absent: `13.900030159 s`;
- target absent with output: `0 s`;
- physical-reference gap: `0.100883795 s`;
- reconciliation: PASS.

For both sequences, the complete physical-v2 duration-bucket dictionaries are
exactly equal to the pre-second-fix Issue #89 results. The downstream
wide-comparison exception therefore introduces no measured controller-facing
safety regression on the retained development evidence.

## Issue #89 closure assessment

All technical acceptance gates are now satisfied:

1. the original pre-encoding wide-crop root cause is documented and fixed;
2. comparison eligibility is separated from positive-memory eligibility;
3. the downstream protected-gallery conflation is documented and narrowly
   corrected;
4. same-ID hijack protection remains enabled;
5. no geometry-only recovery path was introduced;
6. wide-only, contaminated-crop, same-ID, distractor, and protected-gallery
   regression tests are present;
7. the complete `thesis_bringup` suite records `427 passed, 1 skipped`;
8. the project build helper passes;
9. the fresh live reproduction demonstrates
   `LOST -> REACQUIRED -> LOCKED` on the same wide tracker ID;
10. the wide crop remains positive-memory-ineligible throughout the live
    acceptance;
11. no wrong visible authority was observed live;
12. final Seq03/Seq04 physical-v2 safety metrics retain `0 s` wrong-person
    output, and Seq04 retains `0 s` target-absence-with-output;
13. no prospective H01--H03 outcome was inspected or used.

Issue #89 is therefore technically closure-ready. Issue #90 remains blocked
until this branch is merged and Issue #89 is closed.
