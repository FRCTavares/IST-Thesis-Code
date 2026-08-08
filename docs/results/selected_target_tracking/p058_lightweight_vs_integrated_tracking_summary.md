# Lightweight tracker + TIM-MARS vs. integrated appearance-aware tracking (Issue #58 / P1.13+)

Status: promoted development evidence; not held out; not complete. This is
a **May-only development finding, not a general architecture conclusion**
-- one of four development sequences has complete cross-architecture
evidence, 12/24 cells remain `pending_annotation` (workload prepared, not
annotated: see
[`PENDING_ANNOTATION_QUEUE.md`](p058_lightweight_vs_integrated_tracking_development/PENDING_ANNOTATION_QUEUE.md)),
and the cost axis is blocked on Issue #32.

## Purpose

Determine whether a computationally lightweight, appearance-free tracker
paired with selective TIM-MARS identity validation provides a better
onboard safety-availability-cost trade-off than a heavier tracker that
performs appearance association internally, per
[`docs/issues/p1-13-plus-lightweight-vs-integrated-tracking.md`](../../issues/p1-13-plus-lightweight-vs-integrated-tracking.md).

This does not reopen the rejected one-preset-portability claim from Issue
#43. The canonical ByteTrack + TIM-MARS configuration is not retuned.

## Canonical links

- [Frozen protocol and full engineering record](../../issues/p1-13-plus-lightweight-vs-integrated-tracking.md)
- [Architecture-comparison manifest](../../data/lightweight_vs_integrated_tracking/p058_lightweight_vs_integrated_tracking_v1.yaml)
- [SORT+TIM calibration manifest](../../data/lightweight_vs_integrated_tracking/p058_sort_tim_calibration_v1.yaml)
- [Calibration runner](../../../tools/experiments/run_tim_tracker_calibration.py)
- [Comparison aggregator](../../../tools/analysis/aggregate_lightweight_vs_integrated_report.py)
- [Copied evidence, SHA256SUMS](p058_lightweight_vs_integrated_tracking_development/)
- [Pending annotation queue: 6 replay bags, hashes, quarantine evidence, annotation-session instructions](p058_lightweight_vs_integrated_tracking_development/PENDING_ANNOTATION_QUEUE.md)
- [Annotation validator (fail-closed stale-source-bag guard)](../../../tools/analysis/validate_p058_annotation.py)

## Execution summary

24/24 (architecture x sequence) cells accounted for -- 11 `available`, 12
`pending_annotation`, 1 `no_safe_configuration_found`. Zero silently
missing, zero fabricated.

| Architecture | Role | May | Seq01 | Seq03 | Seq04 |
|---|---|---|---|---|---|
| `bytetrack_raw` | lightweight raw baseline | available | available | available | available |
| `bytetrack_tim` | **intended architecture** | available | available | available | available |
| `sort_raw` | minimal lightweight baseline | available | pending_annotation | pending_annotation | pending_annotation |
| `sort_tim` | minimal lightweight + TIM | **no_safe_configuration_found** | pending_annotation | pending_annotation | pending_annotation |
| `deepsort_raw` | integrated appearance reference | available | pending_annotation | pending_annotation | pending_annotation |
| `deepsort_tim` | diagnostic only | available | pending_annotation | pending_annotation | pending_annotation |

ByteTrack rows are reused directly from Issue #31 (`data_source:
reuse_p031`), not re-executed; `bytetrack_tim`'s May numbers are
byte-identical to #31's canonical baseline cell.

## Two annotation-integrity findings from this session

1. **SORT annotations exist only for May.** No SORT ground truth exists for
   Seq01/Seq03/Seq04. The calibration sweep was scoped to May alone (29
   cells) rather than fabricate or silently skip the gap.
2. **Seq03/Seq04 DeepSORT annotations reference the wrong source bag.**
   `seq04_deepsort.csv`'s first-interval `correct_target_track_id=5` never
   appears in a fresh deterministic replay of the canonical `full_pipeline`
   bag; its `bag_name` field traces to a separate "image_raw"-only capture
   recorded ~2 minutes earlier (`12-59-53` vs the canonical `13-01-36`).
   Confirmed the same for Seq03 (`12-55-58` vs `12-57-48`). Both existing
   files are marked `stale_do_not_use` in the manifest; using them would
   have silently evaluated against the wrong ground truth.

May's SORT/DeepSORT annotations were separately verified to reference the
correct, sole source bag before being trusted (no ambiguity like June's
multiple captures exists for May).

## Results (May hard re-entry -- the only sequence with complete cross-architecture evidence)

| Architecture | Correct [s] | Wrong [s] | Lost [s] |
|---|---:|---:|---:|
| `bytetrack_raw` | 38.283 | 7.927 | 21.490 |
| `bytetrack_tim` | 62.513 | 0.100 | 5.087 |
| `sort_raw` | 29.286 | 0.000 | 37.032 |
| `sort_tim` (closest tested, not promoted) | -- | 15.331 | 6.919 |
| `deepsort_raw` | 18.678 | 32.087 | 17.100 |
| `deepsort_tim` (diagnostic) | 16.178 | 26.734 | 24.953 |

## SORT+TIM calibration result: no configuration passes the safety gate

Raw SORT on May never publishes a wrong-target output (`0.000 s`,
consistent with the historical Issue #43 evidence). All 29 configurations
in the reused Issue #31 dimension grid increase wrong-target duration to
15.3-16.3 s -- even the most conservative setting tested
(`confirmation_time_higher_3`) fails the gate by more than 300x the 0.05 s
tolerance. This is a genuine finding, matching one of the valid conclusions
#58's own text anticipates: *"the minimal tracker does not expose enough
viable candidates, establishing TIM-MARS's lower operational boundary."*
The selector fails closed rather than promoting a losing configuration.

## Scientific interpretation (May only -- do not generalize)

- The intended architecture (ByteTrack + canonical TIM-MARS) is the safest
  and most available system measured: wrong-target falls from a 7.927 s raw
  baseline to 0.100 s while correct-target rises to the highest value of
  any row (62.513 s).
- The minimal pairing (SORT + TIM-MARS) does not clear the safety bar on
  this sequence within the tested calibration grid -- a lower-boundary
  finding, not a defect in the comparison.
- The integrated appearance-aware reference (DeepSORT) is, on this
  sequence, the *least* safe raw tracker measured (32.087 s wrong, more
  than ByteTrack raw's 7.927 s and far more than SORT raw's 0.000 s).
  Layering TIM-MARS on top only partially mitigates this (32.087 to
  26.734 s) while reducing correct-target time -- consistent with
  `deepsort_tim` duplicating appearance-based identity reasoning DeepSORT
  already performs internally, exactly the conflict the issue's own
  architecture-boundary text anticipates.

## Cost evidence

No canonical Issue #32 measurement exists yet for any architecture (Issue
#32 is open; Issue #44 closed with its Hailo ReID path explicitly
observational-only). Replay operation counts and full per-cell provenance
(config/model hashes, commit, repository state) are recorded now in a
schema `docs/data/lightweight_vs_integrated_tracking/p058_lightweight_vs_integrated_tracking_v1.yaml`'s
`cost_evidence_schema` that Issue #32 can join later without rerunning
anything. Latency/CPU/memory/Hailo/thermal/power fields are explicitly
`unavailable_pending_issue_32`, never zero, never omitted.

## Claim boundary

This is single-sequence (May) cross-architecture evidence plus a
four-sequence ByteTrack baseline reused from Issue #31. It supports:

- a narrow, May-specific safety/availability comparison across three
  tracker architectures;
- a genuine "TIM-MARS lower operational boundary" finding for SORT on this
  development set.

It does not support:

- any claim generalized beyond May (Seq01/Seq03/Seq04 remain
  `pending_annotation` for both SORT and DeepSORT);
- a held-out generalization claim (Issue #27, deferred to September 2026);
- an onboard computational-cost claim of any kind (Issue #32, open);
- a claim that DeepSORT is broadly unsafe (single sequence, diagnostic
  framing only, not generalized to StrongSORT/BoT-SORT/Deep-OC-SORT);
- Issue #58 completion (six annotation files pending, cost axis blocked,
  figures not yet generated).

## Provenance preservation

Tracked copies (manifest, calibration lock, aggregate CSV/JSON, this
summary's source tables) with `SHA256SUMS` are in
[`p058_lightweight_vs_integrated_tracking_development/`](p058_lightweight_vs_integrated_tracking_development/).
Generated per-cell reports and replay bags remain git-ignored under
`reports/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/` and
`reports/p058_sort_tim_calibration_6231fdc1_2026_08_08/`, regenerable from
the tracked manifests and scripts against the frozen source bags.

Historical generated files, replay bags, the canonical YAML, and the
existing (now-flagged-stale) annotation CSVs were not edited or moved --
the stale files remain on disk for forensic traceability, only marked
`stale_do_not_use` in the manifest.
