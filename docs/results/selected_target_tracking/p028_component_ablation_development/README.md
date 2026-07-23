# TIM-MARS seven-row development component ablation

Status: promoted development evidence; not held out

## Purpose

This package promotes the complete seven-row TIM-MARS component-ablation matrix from the generated P0.28 report into tracked thesis documentation.

The package preserves the original generated matrix unchanged and adds a correction-aware interpretation. It does not rerun the experiment, alter the matrix, or replace the later dual-oracle final-row audit.

## Canonical links

- [Ablation definition](../../../data/ablations/tim_mars_component_ablation_v1.yaml)
- [Ablation interpretation](../../../data/ablations/README.md)
- [Frozen evaluation split](../../../data/splits/README.md)
- [Evidence-version boundaries](../../../algorithm/tim_mars_evidence_versions.md)
- [Later corrected dual-oracle audit](../p028_wrong_oracle_audit.md)
- [Copied run provenance](run_provenance.json)
- [Copied ablation lock](ablation_lock.json)
- [Copied aggregate CSV](matrix_aggregate_annotated_id.csv)
- [Copied complete sequence CSV](matrix_all_sequences_annotated_id.csv)
- [Copied aggregate JSON](matrix_aggregate_annotated_id.json)
- [Copied-artifact hashes](SHA256SUMS)

The originating generated report path is `reports/p028_component_ablation_6ec7644a_2026-07-23/`. The copied artifacts in this directory are tracked so the thesis-facing table does not depend solely on an ignored generated report directory.

## Scoring availability

The complete seven-row matrix below uses the retained annotated-ID evaluator. It follows manually reviewed target-ID intervals and can be conservative when the same physical person is fragmented into a new tracker ID.

A complete seven-row spatial matrix was not retained for this run. Spatial and annotated-ID results are both available only for the raw and final rows in the later corrected audit. The missing per-component spatial rows must not be inferred or fabricated.

## Aggregate annotated-ID durations

| Row ID | Configuration | Correct [s] | Wrong [s] | Lost/no-output [s] | Absent-output [s] | No-selection [s] | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `raw_tracker` | Raw tracker | 163.122 | 8.477 | 170.990 | 0.000 | 0.000 | Pass |
| `geometry_only` | Geometry-only TIM | 247.375 | 72.933 | 22.281 | 5.662 | 0.000 | Fail |
| `geometry_positive_appearance` | Geometry + positive appearance | 266.996 | 1.550 | 74.043 | 0.000 | 0.000 | Pass |
| `geometry_appearance_margin` | Geometry + appearance margin | 266.746 | 1.550 | 74.293 | 0.000 | 0.000 | Pass |
| `geometry_hard_negatives` | Geometry + hard negatives | 266.996 | 1.550 | 74.043 | 0.000 | 0.000 | Pass |
| `geometry_persistence` | Geometry + persistence | 245.600 | 64.652 | 32.337 | 0.250 | 0.000 | Fail |
| `final_simplified_tim_mars` | Final simplified TIM-MARS | 292.337 | 2.750 | 47.502 | 0.000 | 0.000 | Pass |

### Aggregate ratios and deltas

| Row ID | Correct ratio | Wrong ratio | Lost ratio | Wrong delta vs raw [s] | Absence delta vs raw [s] |
| --- | ---: | ---: | ---: | ---: | ---: |
| `raw_tracker` | 0.4761 | 0.0247 | 0.4991 | 0.000 | 0.000 |
| `geometry_only` | 0.7221 | 0.2129 | 0.0650 | 64.456 | 5.662 |
| `geometry_positive_appearance` | 0.7793 | 0.0045 | 0.2161 | -6.927 | 0.000 |
| `geometry_appearance_margin` | 0.7786 | 0.0045 | 0.2169 | -6.927 | 0.000 |
| `geometry_hard_negatives` | 0.7793 | 0.0045 | 0.2161 | -6.927 | 0.000 |
| `geometry_persistence` | 0.7169 | 0.1887 | 0.0944 | 56.175 | 0.250 |
| `final_simplified_tim_mars` | 0.8533 | 0.0080 | 0.1387 | -5.727 | 0.000 |


## May hard re-entry

| Row ID | Configuration | Correct [s] | Wrong [s] | Lost/no-output [s] | Absent-output [s] | No-selection [s] | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `raw_tracker` | Raw tracker | 38.283 | 7.927 | 21.490 | 0.000 | 0.000 | Pass |
| `geometry_only` | Geometry-only TIM | 55.057 | 12.143 | 0.500 | 0.000 | 0.000 | Fail |
| `geometry_positive_appearance` | Geometry + positive appearance | 63.113 | 0.150 | 4.437 | 0.000 | 0.000 | Pass |
| `geometry_appearance_margin` | Geometry + appearance margin | 63.113 | 0.150 | 4.437 | 0.000 | 0.000 | Pass |
| `geometry_hard_negatives` | Geometry + hard negatives | 63.113 | 0.150 | 4.437 | 0.000 | 0.000 | Pass |
| `geometry_persistence` | Geometry + persistence | 49.377 | 16.353 | 1.970 | 0.000 | 0.000 | Fail |
| `final_simplified_tim_mars` | Final simplified TIM-MARS | 63.263 | 0.150 | 4.287 | 0.000 | 0.000 | Pass |

## June Seq01 clean four-person sequence

| Row ID | Configuration | Correct [s] | Wrong [s] | Lost/no-output [s] | Absent-output [s] | No-selection [s] | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `raw_tracker` | Raw tracker | 55.550 | 0.000 | 66.790 | 0.000 | 0.000 | Pass |
| `geometry_only` | Geometry-only TIM | 108.750 | 0.000 | 13.590 | 0.000 | 0.000 | Pass |
| `geometry_positive_appearance` | Geometry + positive appearance | 108.750 | 0.000 | 13.590 | 0.000 | 0.000 | Pass |
| `geometry_appearance_margin` | Geometry + appearance margin | 108.750 | 0.000 | 13.590 | 0.000 | 0.000 | Pass |
| `geometry_hard_negatives` | Geometry + hard negatives | 108.750 | 0.000 | 13.590 | 0.000 | 0.000 | Pass |
| `geometry_persistence` | Geometry + persistence | 108.750 | 0.000 | 13.590 | 0.000 | 0.000 | Pass |
| `final_simplified_tim_mars` | Final simplified TIM-MARS | 108.750 | 0.000 | 13.590 | 0.000 | 0.000 | Pass |

## June Seq03 OC-SORT crossing sequence

| Row ID | Configuration | Correct [s] | Wrong [s] | Lost/no-output [s] | Absent-output [s] | No-selection [s] | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `raw_tracker` | Raw tracker | 32.600 | 0.100 | 63.027 | 0.000 | 0.000 | Pass |
| `geometry_only` | Geometry-only TIM | 47.875 | 44.536 | 3.316 | 0.000 | 0.000 | Fail |
| `geometry_positive_appearance` | Geometry + positive appearance | 56.290 | 1.150 | 38.287 | 0.000 | 0.000 | Fail |
| `geometry_appearance_margin` | Geometry + appearance margin | 56.040 | 1.150 | 38.537 | 0.000 | 0.000 | Fail |
| `geometry_hard_negatives` | Geometry + hard negatives | 56.290 | 1.150 | 38.287 | 0.000 | 0.000 | Fail |
| `geometry_persistence` | Geometry + persistence | 42.658 | 47.499 | 5.570 | 0.000 | 0.000 | Fail |
| `final_simplified_tim_mars` | Final simplified TIM-MARS | 80.081 | 2.350 | 13.296 | 0.000 | 0.000 | Fail |

## June Seq04 OC-SORT occlusion sequence

| Row ID | Configuration | Correct [s] | Wrong [s] | Lost/no-output [s] | Absent-output [s] | No-selection [s] | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `raw_tracker` | Raw tracker | 36.689 | 0.450 | 19.683 | 0.000 | 0.000 | Pass |
| `geometry_only` | Geometry-only TIM | 35.693 | 16.254 | 4.875 | 5.662 | 0.000 | Fail |
| `geometry_positive_appearance` | Geometry + positive appearance | 38.843 | 0.250 | 17.729 | 0.000 | 0.000 | Pass |
| `geometry_appearance_margin` | Geometry + appearance margin | 38.843 | 0.250 | 17.729 | 0.000 | 0.000 | Pass |
| `geometry_hard_negatives` | Geometry + hard negatives | 38.843 | 0.250 | 17.729 | 0.000 | 0.000 | Pass |
| `geometry_persistence` | Geometry + persistence | 44.815 | 0.800 | 11.207 | 0.250 | 0.000 | Fail |
| `final_simplified_tim_mars` | Final simplified TIM-MARS | 40.243 | 0.250 | 16.329 | 0.000 | 0.000 | Pass |

## Later corrected raw-versus-final dual-oracle audit

The table below is extracted from the later tracked audit. It belongs to the later frozen P0.17 configuration and must not be merged into the earlier seven-row matrix as though all rows were rerun under the same implementation and evaluator contract.

| Development sequence | Raw spatial [s] | Raw annotated-ID [s] | TIM spatial [s] | TIM annotated-ID [s] |
| --- | ---: | ---: | ---: | ---: |
| May hard re-entry | 4.429 | 7.927 | 0.000 | 0.100 |
| June Seq01 | 0.000 | 0.000 | 0.000 | 0.000 |
| June Seq03 OC-SORT | 0.000 | 0.100 | 0.000 | 0.950 |
| June Seq04 OC-SORT | 0.310 | 0.450 | 0.000 | 0.250 |
| **Aggregate** | **4.739** | **8.477** | **0.000** | **1.300** |

The spatial total of `0.000 s` is not proof of flawless physical identity. Visual review found a short distractor handover that the spatial oracle accepted because the reference tracker box covered both people. The annotated-ID oracle retained `1.300 s` of wrong output in the corrected final row.

## Scientific interpretation

- Geometry alone increased aggregate wrong-target duration from `8.477 s` to `72.933 s` and produced `5.662 s` of target-absence output. Geometry alone is therefore insufficient.
- Persistence without appearance also reduced lost output but raised aggregate wrong-target duration to `64.652 s`. Short-gap identity continuity is unsafe when it preserves the wrong lineage.
- Adding positive appearance reduced aggregate wrong-target duration to `1.550 s` while increasing correct-target duration to `266.996 s`.
- The positive-appearance, appearance-margin, and hard-negative rows have the same aggregate wrong-target duration in this development matrix. These sequences therefore do not demonstrate a separate numerical contribution from the appearance-margin or hard-negative policies, even though those policies remain part of the final implementation and may affect other scenarios.
- The final simplified row has the highest aggregate correct-target duration, `292.337 s`, and less aggregate annotated-ID wrong output than raw (`2.750 s` versus `8.477 s`).
- Aggregate improvement does not make the final row sequence-safe. On June Seq03, annotated-ID wrong output increased from `0.100 s` to `2.350 s`, so that sequence fails the frozen safety comparison.
- The later corrected dual-oracle audit improves the raw-versus-final result under both retained oracles. The earlier component matrix and the later audit are different evidence versions. The corrected values must not be substituted into the earlier seven-row matrix to manufacture a mixed-version ablation.

## Claim boundary

This is development evidence from previously inspected May and June recordings. It supports component-level diagnosis and shows that appearance evidence is necessary in the evaluated scenarios.

It does not support:

- a held-out generalisation claim;
- zero wrong-target output;
- universal tracker portability;
- a claim that every final component has an independently measured benefit in these sequences;
- a formal flight-safety guarantee.

H01-H03 remain required before the final thesis claim is frozen.

## Provenance preservation

The two CSV files, aggregate JSON, run provenance, and ablation lock were copied byte-for-byte from the generated report. `SHA256SUMS` records the hashes of the tracked copies.

Historical generated files and bags were not edited or moved.
