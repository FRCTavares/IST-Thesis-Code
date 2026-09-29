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

Issue #125 must reconcile the validation image and annotation frame domains
rather than silently assuming those counts are identical. The training split is
admissible but still has to be acquired and verified before the final freeze.

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

The only executable benchmark step allowed before freeze is:

    thesis_env/bin/python tools/issues/p125/audit_visdrone_selected_person_corpus.py \
      --split val \
      --out artifacts/reports/p125_gt_only/visdrone_val_gt_only_audit.json

After the official train split is acquired and verified, run the same command
with `--split train`.

The audit:

- reads source images and official GT annotations only;
- reconciles image frames against annotation frames per sequence;
- inventories pedestrian identities, target heights, occlusion, truncation and
  annotation gaps;
- generates deterministic **candidate** episodes from GT-only rules;
- never reads detections, tracker output, Target-ReID output, TIM-MARS output or
  previous performance reports.

Generated audit JSON belongs under ignored `artifacts/reports/` until the
freeze decision is reviewed.

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
