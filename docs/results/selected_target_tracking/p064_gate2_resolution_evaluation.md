# Issue #64 Gate-2 controlled appearance-resolution result

Status: corrected controlled R3 comparison accepted; no material
native-HD identity benefit was observed in R3. Issue #64 is paused pending
representative small-target drone-POV validation.

Date: 27 August 2026

## Frozen question, corrected provenance, and accepted result

Gate 2 compares native 1280x720 appearance pixels against a deterministic
640x360 `INTER_AREA` complete-frame downsample from the same native-HD frames.
Scene, FOV, timestamps, Hailo detections, ByteTrack candidates, target identity,
MARS model, TIM-MARS configuration and evaluation window are frozen. Detector
inference remains 640x640.

The R3 master is
`bags/source_video/2026-08-27__16-34-50__source__p064_gate2_hd_master_r3__image_raw_detections`,
MCAP SHA-256
`5580e25f4fef27d3d01c47cfd1e176c56b43449831b62285b6eae2a33aaed34b`.

The corrected deterministic tracker freeze is
`bags/replay/p064_gate2_hd_master_r3__bytetrack_frozen_frameid_fix`.
Its numeric frame IDs are positive and preserve the source versioned
coordinate-contract frame number. Its candidate-stream SHA-256 is
`615ed6abf0083f8cbe86a47257fdc71f4c62c2e16fa314997c57ed34a1a99578`.
Track timestamps, source stamps, IDs and geometry are unchanged relative to
the original freeze; only the invalid numeric `frame_id=0` lifecycle field was
corrected.

The promoted v2 physical reference is
`docs/data/physical_target_references/p064_gate2_hd_master_r3.json`,
SHA-256
`0d9f4148f67b610d5cd012db4d3613f6fc559aec63c2ae705adc50595e8db147`.
Frames 93--96 are human-reviewed `present_reference_unavailable`; 833 frames
remain `present_scored` with `target` and `phys_d001` coverage.

Corrected TIM replays:

- native:
  `bags/replay/p064_gate2_hd_master_r3__tim_native_1280x720_frameid_fix`;
- control:
  `bags/replay/p064_gate2_hd_master_r3__tim_control_640x360_frameid_fix`.

Both consume the same corrected candidate stream. Their generated semantic
digests differ:

- native:
  `9178c9985d96ee42ea3af8934ca462a731ea41b562a9dbe03a3fd2f053d86e7c`;
- control:
  `03532a5a3d0e94703212616c2e9e0d222da2ab2ebcca1fa6e4e227a1c39544ad`.

Thus the appearance-pixel condition genuinely reaches TIM. Despite that, their
v2 physical-target reports are byte-identical.

| Metric | Native 1280x720 | Control 640x360 | Difference |
| --- | ---: | ---: | ---: |
| Correct-target output | 18.600459426 s | 18.600459426 s | 0 s |
| Wrong-person output | 0 s | 0 s | 0 s |
| Lost/suppressed | 9.100239419 s | 9.100239419 s | 0 s |
| Target-absent duration | 0 s | 0 s | 0 s |
| Reference unavailable | 0.133160003 s | 0.133160003 s | 0 s |
| Reference gap | 0.066408595 s | 0.066408595 s | 0 s |
| Total evaluated | 27.900267443 s | 27.900267443 s | 0 s |

The safety gate passes with zero wrong-person regression. The aggregate
resolution-specific benefit is **0 percentage points**, below the frozen
5-percentage-point materiality criterion. Because the complete physical
reports are identical, native HD also provides no resolution-specific
reacquisition advantage over the control.

**Accepted controlled-R3 material native-HD benefit: NO.**

No repeated Stage-B HD runtime characterization is triggered by R3.

## Audit resolution

The originally committed R3 interpretation is superseded, not deleted from
the scientific record. Two defects were found during audit:

1. frames 93--96 had been represented as interpolated `present_scored`
   geometry despite human-confirmed near/full occlusion;
2. deterministic tracker replay parsed only legacy `frame_<n>` identifiers,
   while R3 uses the versioned `;frame=<n>;` contract, producing numeric
   `frame_id=0` and resetting TIM appearance lifecycle state each frame.

The reference state and replay parser were corrected, regression-tested, and
the comparison rerun unchanged. Only the corrected result above is accepted.

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

Repeated HD Stage-B runtime characterization is not justified by R3 because
native HD produced no material controller-facing improvement over the exact
640x360 control. Stage A's live-feasibility evidence remains authoritative.

Issue #64 is **PAUSED — representative drone footage required**.

R3 is not sufficient for a general airborne resolution recommendation because
the target is exceptionally large: 534.64--561.11 px tall, median 549.72 px.
The remaining within-scope item is one native-HD representative drone-POV
sequence containing genuinely smaller targets, at least one distractor and an
identity challenge such as crossing/occlusion plus exit/re-entry.

The representative flight capture may use the established
YOLOv8s + ByteTrack + TIM-MARS live path. This does not alter the controlled R3
experiment, whose detector evidence remains frozen on YOLOv6n.

No canonical TIM-MARS parameters, thresholds, tracker behavior or completed R3
detector evidence are changed.
