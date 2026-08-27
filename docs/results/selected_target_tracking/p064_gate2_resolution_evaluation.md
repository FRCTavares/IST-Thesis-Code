# Issue #64 Gate-2 controlled appearance-resolution result

Status: controlled R3 comparison complete; no material native-HD identity benefit
was observed. Representative airborne target-scale validation remains pending.

Date: 27 August 2026

## Frozen question and decision rule

Gate 2 compares native 1280x720 appearance pixels against a deterministic
640x360 INTER_AREA complete-frame downsample from the same native-HD frames.
Hailo detections, ByteTrack candidates, exact timestamps, scene, FOV, physical
reference, selected target, CPU MARS model, and canonical TIM-MARS parameters
are fixed. Detector inference remains 640x640.

Before either output was inspected, native HD was required to pass both:

- no increase beyond 1e-6 s in wrong-person duration;
- no increase beyond 1e-6 s in target-absent-with-output duration.

Subject to that safety gate, material benefit required either a >=5 percentage
point correct-target increase or lost/suppressed reduction over target-present
duration, or correct reacquisition within 1.0 s after the predeclared hard
exit/re-entry event without a safety regression.

## Input provenance

| Item | Value |
| --- | --- |
| Repository base at replay | `6e7512a3c8d326642d1653dd7dff42d57ebbb3cd`; exact-window replay extension committed with this result |
| Source bag | `bags/source_video/2026-08-27__16-34-50__source__p064_gate2_hd_master_r3__image_raw_detections` |
| Source MCAP SHA-256 | `5580e25f4fef27d3d01c47cfd1e176c56b43449831b62285b6eae2a33aaed34b` |
| Source geometry | native 1280x720; Hailo inference fixed at 640x640 |
| Evaluation window | `[3.000000000, 30.900267443] s` relative to source-header origin `1787844897072285865 ns` |
| First physical frame | `3.033175097 s`; the preceding 33.175097 ms is an honest reference gap |
| Retained frames | 837 exact image/detection timestamp pairs |
| Candidate digest | `23e7388edd50e341ef325efef30de45a70cb59701bfab9d1a726f868edfd32d9` |
| Tracker semantic digest | `68b7b81d39d3445effcb50de43f768d613235bd20c0047c4194566fc1627276d` |
| Canonical TIM config SHA-256 | `e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931` |
| CPU MARS model SHA-256 | `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1` |

Both deterministic replays use initial selected transport ID 2, the same
inclusive absolute processing window
`[1787844900072285865, 1787844927972553308] ns`, master-coordinate geometry
1280x720, and the complete frozen candidate-stream digest guard. Only the
appearance-image bag changes.

## Human physical reference

Corrected CVAT export:

`artifacts/reports/p064_gate2_hd_master_r3_cvat/completed/p064_gate2_hd_master_r3_completed_cvat_images_1_1_corrected_20260827.zip`

- export SHA-256:
  `d8a85c0b2dfbf84c1cb6c0bd693eb03d84782bb623c584c3d021603a684a53ff`;
- CVAT for images 1.1, 837 images, 1280x720;
- exactly one `target` and one `phys_d001` box on every frame 0--836;
- zero missing/duplicate roles, unsupported labels, invalid coordinates, or
  frame/name/dimension mismatches;
- target: laptop-carrying person;
- distractor: striped-shirt woman.

Canonical frozen-v2 reference:

`docs/data/physical_target_references/p064_gate2_hd_master_r3.json`

SHA-256:
`814a5fed32b296da4f50e090979f7bdf0b748a95658afdc309a7c4dd666a93f4`.

It contains 837 per-frame `present_scored` / `distractors_complete` samples,
complete coverage for both roles, exact manifest timestamps, and the final
right-boundary anchor. The reference covers 27.867092346 s; the initial
33.175097 ms remains `reference_gap`.

The human target associates to initial ByteTrack ID 2 on all 78 frames where
ID 2 exists, with median IoU 0.914. ID 1 instead associates to `phys_d001` on
828 frames, with median distractor IoU 0.863. Later target track fragments
include IDs 3, 6, 7, and 11. These numeric IDs are transport evidence only and
never define physical identity.

## Frozen replay outputs

| Condition | Appearance provenance | Output MCAP SHA-256 | Generated semantic SHA-256 |
| --- | --- | --- | --- |
| native HD | 1280x720 same-size; stream `b0ad9f693544660fe40f95f9261b89878823337f406817f5b724cca45a8aa5c8` | `12e4eccbb4b3c7776c09a63625001b35a3c1bffda2f07435c27b7b55610f056d` | `d1642ff9fd29021f103ed3ffd2347b635c013573ec19df318fb04056fb95fef7` |
| low-resolution control | 640x360 deterministic INTER_AREA downsample; stream `2c71b4ddba2a280d312c17407041f4b8228f3ce0fb8ea728041f6983ca53176d` | `7a239589a813671e8f4e124fc144fee47435220c35066d4c39dcb9b2059fdff5` | `26caabd8793ed6fa43aa70ac2f4f0abc37e311c80a26e48bd0b4e4c81359822a` |

The generated semantic digests differ because appearance diagnostics/internal
state differ, but the controller-facing target output and physical-reference
duration buckets are identical.

## Controller-facing physical-reference result

Target-present denominator for both conditions: 27.867092346 s.

| Metric | native 1280x720 | control 640x360 | native minus control |
| --- | ---: | ---: | ---: |
| correct target | 2.700000 s | 2.700000 s | 0.000000 s |
| wrong person | 0.000000 s | 0.000000 s | 0.000000 s |
| lost/suppressed | 25.167092 s | 25.167092 s | 0.000000 s |
| absent with output | 0.000000 s | 0.000000 s | 0.000000 s |
| correct fraction | 9.688847% | 9.688847% | 0.000 pp |
| lost/suppressed fraction | 90.311153% | 90.311153% | 0.000 pp |

Both reconciliations pass with zero residual. Localization is secondary and is
also identical: duration-weighted IoU 0.914257 over 2.700 s of correctly
attributed output.

The human target reaches the right image boundary at 23.999843003 s and is back
inside on the next retained frame at 24.033190 s. Both conditions' last valid
controller output occurs at 5.699873996 s; neither produces a valid output
after the exit/re-entry. Therefore neither condition reacquires within 1.0 s.

## Frozen materiality decision

- Safety gate, wrong-person regression: PASS; difference 0.000000 s.
- Safety gate, absent-with-output regression: PASS; difference 0.000000 s.
- Criterion A, >=5 percentage point aggregate improvement: FAIL; difference
  0.000 percentage points.
- Criterion B, correct reacquisition within 1.0 s: FAIL for both conditions.

**Controlled R3 material native-HD benefit: NO.**

Native 1280x720 appearance pixels did not change controller-facing identity
robustness relative to the exact-frame 640x360 control under identical
detector/tracker evidence in this sequence.

## Target-scale distribution and external validity

All 837 human target-present boxes were measured in native source pixels.

| Statistic | min | p10 | p25 | median | p75 | p90 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| target height (px) | 534.64 | 535.06 | 540.29 | 549.72 | 553.41 | 558.89 | 561.11 |
| height / image height | 74.26% | 74.31% | 75.04% | 76.35% | 76.86% | 77.62% | 77.93% |
| bbox area / image area | 10.14% | 10.90% | 14.17% | 15.40% | 16.02% | 17.35% | 18.55% |

The intended operating floor is approximately 20 px target height, whereas the
smallest R3 target is 534.64 px. R3 therefore does not represent the smaller
bounding-box distribution expected near the approximately 10 m airborne
following regime. No empirical normal target height at 10 m is invented here.

The negative controlled result cannot establish that extra source resolution
would also be ineffective for substantially smaller flight-view targets.
Conversely, it provides no evidence that HD will help at those scales.

## Stage-B and Issue #64 status

Additional repeated HD Stage-B runtime characterization is not justified by
this controlled result because native HD delivered no material identity
benefit. Stage A's existing live-feasibility result remains authoritative.

Issue #64 remains open for one final within-scope external-validity item:
native-HD representative drone-POV / flight-geometry validation at realistic
target scale, keeping detector inference fixed at 640x640 and preserving exact
timing/provenance. This is not perfectionism: the issue explicitly requires a
distant/small-target case, and R3's minimum target height is 534.64 px. The
planned field validation next week blocks a general source-resolution
recommendation, but it does not rewrite the controlled R3 finding.

No canonical TIM-MARS parameters, detector behavior, tracker behavior, or
thresholds changed.
