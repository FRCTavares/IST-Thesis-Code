# Issue #125 external benchmark v2

## Purpose

This directory owns the prospective public-dataset protocol for Issue #125.

It is separate from `docs/data/external_benchmark/`, which is frozen Issue #30
evidence and must remain reproducible unchanged.

The new study asks how the unchanged selected-person authority architectures
behave on a broad public UAV corpus. Its planned arms are SORT raw, ByteTrack
raw, OC-SORT raw, DeepSORT raw, simple Target-ReID 0.90 over ByteTrack, and
ByteTrack + canonical TIM-MARS.

## Current status

`visdrone_selected_person_protocol_v1.json` is **draft_not_frozen**.

At this stage only ground-truth/data-contract work is allowed. Architecture
outcome generation is forbidden until the protocol is frozen.

The current Issue #30 source registry already records:

- VisDrone2019-MOT validation as verified;
- archive SHA-256
  `e53571990dfc79229e0a8ae10264bc4fa604a027c44b06e3a097417e4fa55705`;
- 7 sequences and 7 annotation files;
- 2,846 local source images;
- exported sequence cadence as unresolved, so the existing benchmark time
  policy is frame-index only.

The 29 September GT-only Pi audit reconciled the validation frame domain. The
verified archive contains seven sequences and 2,846 images, but the earlier
local extraction omitted the 978-image 4K sequence
`uav0000268_05773_v`. It was restored from that same SHA-256-verified archive.
The seven extracted sequences now have 2,846 image frames and 2,846 annotated
frames, with zero image-only or annotation-only frames.

The draft eligibility rules yield 194 candidate episodes from 225 annotated
pedestrian identities: 23 lack 30 target-present frames after their earliest
eligible selection frame, and 8 have no eligible selection frame. The local
GT-only audit is
`artifacts/reports/p125_gt_only/visdrone_val_gt_only_audit.json` (SHA-256
`f1f1e2f8318f6379aa6fde092807002b2df6bf1f4811fae1600a478d636be09a`).
The training archive was acquired on the Pi from a public mirror after the
official Google Drive link returned a download-limit message. Two independent
mirrors publish the same train SHA-256
`566d08fb53fff4e539f386f5a408ccf17854fd53814dc756bdede2de1dbb4014`;
their validation archive hash also matches the existing independently verified
Issue #30 archive. The downloaded 8,080,572,990-byte train ZIP passed a full
SHA-256 and ZIP integrity check. Its extraction contains 56 sequences, 56
annotation files and 24,201 images.

The train GT-only audit has 24,198 frames with annotation rows. Images 23–25
in `uav0000281_00460_v` have no GT rows; all annotation frames have source
images. Those three frames are explicitly reference-unavailable for
target-present scoring, never evidence of physical target absence. The draft
rules yield 1,361 candidate episodes from 1,822 pedestrian identities (411
lack enough remaining target-present frames and 50 have no eligible selection
frame). The ignored train audit SHA-256 is
`07c5adceee8c877011486f8c5f6856dc7b8bdf20b79e8ed3c653e1b7f65aeb0e`.

The tracked combined `visdrone_gt_only_episode_manifest_v1.json` has 63
sequence source inventories with annotation hashes and frame ranges, 2,047
pedestrian identities and 1,555 draft candidate episodes.
Its SHA-256 is
`34ea378dc1b692a5f62e249a2181daa7d1dde59caf0501187fb3c4b00dcb9941`.
These are GT-only candidates, not frozen benchmark episodes. The protocol
remains **draft_not_frozen** while selection, initialization, evaluator,
model/config hashes and statistical details are finalized before any
architecture outcome access.

## Official VisDrone annotation semantics used by the draft

For VisDrone MOT ground truth:

- class `1` is an individually annotated pedestrian;
- class `2` is a grouped `people` region and is not a single physical-person
  identity;
- truncation `0` means none and `1` means partial truncation (1–50%);
- occlusion `0` means none, `1` partial (1–50%), and `2` heavy (50–100%).

Authority reference:
`https://github.com/VisDrone/VisDrone2018-MOT-toolkit`.

These source semantics describe the annotations only; they are not algorithm
outcomes and may be used during the pre-result audit.

## GT-only audit

The GT-only preparation commands are:

    thesis_env/bin/python tools/issues/p125/audit_visdrone_selected_person_corpus.py \
      --split val \
      --out artifacts/reports/p125_gt_only/visdrone_val_gt_only_audit.json

    thesis_env/bin/python tools/issues/p125/audit_visdrone_selected_person_corpus.py \
      --split train \
      --out artifacts/reports/p125_gt_only/visdrone_train_gt_only_audit.json

    thesis_env/bin/python tools/issues/p125/build_visdrone_gt_only_episode_manifest.py \
      --train-audit artifacts/reports/p125_gt_only/visdrone_train_gt_only_audit.json \
      --val-audit artifacts/reports/p125_gt_only/visdrone_val_gt_only_audit.json \
      --train-archive data/datasets/external/visdrone_mot/_archives/VisDrone2019-MOT-train.zip \
      --val-archive data/datasets/external/visdrone_mot/_archives/VisDrone2019-MOT-val.zip \
      --out docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json

The audit:

- reads source images and official GT annotations only;
- reconciles image frames against annotation frames per sequence;
- inventories pedestrian identities, target heights, occlusion, truncation and
  annotation gaps;
- generates deterministic **candidate** episodes from GT-only rules;
- never reads detections, tracker output, Target-ReID output, TIM-MARS output or
  previous performance reports.

Generated audit JSON belongs under ignored `artifacts/reports/` until the
freeze decision is reviewed. The compact combined candidate manifest is
tracked for review. The manifest builder rejects missing source images,
unreconciled identities, mismatched split rules and duplicate episodes; it
records image frames with no GT rows as reference-unavailable.

## Draft eligibility

The current pre-outcome proposal is:

- VisDrone class `1`;
- valid official GT row;
- first selectable bbox height at least 20 px;
- selection truncation no greater than `1`;
- selection occlusion no greater than `1`;
- at least 30 target-present annotated frames from selection onward;
- at most a 10-frame initialization window.

These are **draft rules**, not final claims. They may be reconciled from the
GT-only corpus audit before outcome access. Once architecture outcomes are
generated, they may no longer be changed to improve results.

## Draft attribution and inference contract

The separate #125 frame classifier uses a 0.30 IoU threshold for any
individually annotated pedestrian and requires the best person's IoU to
exceed the second best by at least 0.10. A valid output with no unique
person match is identity-unresolved. Coverage of at least half the output
box by an ignored or grouped region also makes attribution unresolved.
No valid controller-facing output is LOST/suppressed. Frames without a
target GT row remain outside the four-bucket primary denominator.

Paired TIM-MARS minus ByteTrack effects use the arithmetic mean of
episode-level fractions among ByteTrack-initialisable episodes. The draft
statistics plan uses source sequence as the cluster, 10,000 fixed-seed
cluster-bootstrap replicates, percentile 95% intervals and one two-sided
100,000-draw cluster sign-flip test for wrong-person fraction. Correct-person
availability is a descriptive trade-off effect. The fixed seed is
`12520260930`. The tools have only been tested on synthetic episodes;
architecture results remain inaccessible until the dedicated freeze commit.

The protocol records the exact YOLOv8s, MARS, tracker YAML, TIM-MARS YAML
and relevant runtime-source SHA-256 values. The detector draft uses the
production 640 × 640 direct resize, BGR-to-RGB conversion, `person` label
and 0.35 minimum score. Detector parity and the complete episode evaluator
remain pre-result implementation gates.

## Freeze gate

Before any detector/tracker/TIM aggregate outcome is inspected:

1. acquire and verify train + validation source provenance;
2. reconcile the validation image/annotation count discrepancy;
3. complete the GT-only corpus audit;
4. generate the all-eligible-identity episode manifest;
5. freeze selection/initialization/evaluator rules;
6. record exact model and config SHA-256 values;
7. freeze statistics seed, cluster-bootstrap procedure and primary hypothesis;
8. commit the final protocol with status `frozen`.

A later correctness-only protocol repair must preserve the first generated
output and document the defect, rationale and deterministic rerun. It must not
be used as a tuning route.

## Frozen evidence boundaries

Do not mutate:

- Issue #30 `docs/data/external_benchmark/` frozen manifest/evidence;
- Issue #58 Target-ReID/final-comparison authorities;
- H01-H03 held-out references or outcomes;
- canonical TIM-MARS or tracker parameters because of VisDrone results.
