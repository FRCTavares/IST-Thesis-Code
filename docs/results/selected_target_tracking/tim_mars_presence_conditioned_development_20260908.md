# Presence-conditioned identity characterisation -- development sequences (8 September 2026)

**Development-only descriptive characterisation. No tuning was performed. No
H01/H02/H03 access.** The held-out sources were not captured, listed, opened,
hashed, replayed, annotated, evaluated or inspected.

The percentages below are pure arithmetic transformations of the **already
frozen** `tim_physical_target_bbox_v2` duration buckets. The presence-conditioned
formulas were predeclared in the Issue #27 Stage-7 prospective freeze
`primary_metric_contract`
(`docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`);
this record only implements them. It does **not** supersede or modify the
physical-v2 evaluator and introduces **no pass/fail threshold**.

- Reporting tool: `tools/analysis/derive_presence_conditioned_metrics.py`
  (sha256 `3388f880b5d2...`), derived schema
  `tim_presence_conditioned_metrics_v1`.
- Frozen physical-v2 evaluator files are byte-unchanged by this work.
- Algorithm: final selected TIM-MARS development baseline + production AB-16
  only (PR #101 merge `79f11b63...`, canonical
  `b0a98334...`). Source: the retained Stage-5 production-AB-16 physical-v2
  reports (`tim_mars_ab16_production_regression_20260908.json`, verdict PASS);
  no sequence was re-run or re-classified.

## Present-time denominator

`physical_target_present_duration_s = correct_target_output_duration_s
+ wrong_person_output_duration_s + identity_unresolved_duration_s
+ lost_or_suppressed_duration_s`

`reference_unavailable_duration_s` and `reference_gap_duration_s` are kept
strictly separate and are never folded into this denominator.

## Target-presence accounting

Two distinct quantities are reported and never share a label:

- **`% target present among physically classified present+absent time`**
  (`percent_time_target_present`) -- the exact Stage-7
  `primary_metric_contract` quantity, denominator
  `physical_target_present_duration_s + physical_target_absent_duration_s`;
- **`% target present of complete evaluated window`**
  (`physical_target_present_pct_of_total`) -- secondary descriptive quantity,
  denominator `total_evaluated_duration_s` (which also contains
  `reference_gap` / `reference_unavailable`).

| Sequence | Target present (s) | Target absent (s) | Present+absent (s) | % present of present+absent (Stage-7) | % present of complete window | Total eval (s) |
|---|---:|---:|---:|---:|---:|---:|
| `dev_may_hard_reentry` | 67.864910 | 0.000000 | 67.864910 | 100.0000% | 100.0000% | 67.864910 |
| `dev_june_seq01` | 61.200517 | 0.000000 | 61.200517 | 100.0000% | 100.0000% | 61.200517 |
| `dev_june_seq03_ocsort` | 83.766798 | 0.000000 | 83.766798 | 100.0000% | 99.8802% | 83.867251 |
| `dev_june_seq04_ocsort` | 72.500042 | 13.900030 | 86.400072 | 83.9120% | 83.8142% | 86.500956 |

## Presence-conditioned identity table

| Sequence | Target present (s) | Correct while present | Wrong while present | Unresolved while present | LOST/suppressed while present | Absence leakage |
|---|---:|---:|---:|---:|---:|---:|
| `dev_may_hard_reentry` | 67.864910 | 62.796330 (92.5314%) | 0.033394 (0.0492%) | 0.000000 (0.0000%) | 5.035186 (7.4194%) | 0.000000 (N/A) |
| `dev_june_seq01` | 61.200517 | 61.200517 (100.0000%) | 0.000000 (0.0000%) | 0.000000 (0.0000%) | 0.000000 (0.0000%) | 0.000000 (N/A) |
| `dev_june_seq03_ocsort` | 83.766798 | 24.600414 (29.3677%) | 0.000000 (0.0000%) | 0.000000 (0.0000%) | 59.166384 (70.6323%) | 0.000000 (N/A) |
| `dev_june_seq04_ocsort` | 72.500042 | 48.766241 (67.2637%) | 0.000000 (0.0000%) | 0.000000 (0.0000%) | 23.733801 (32.7363%) | 0.000000 (0.0000%) |

`Absence leakage` percentage is `N/A` where `target_absent_duration_s == 0`
(Seq03), never `0%`.

## Reference conditions kept separate

- `dev_may_hard_reentry`: reference_unavailable 0.000000 s, reference_gap 0.000000 s (both outside the present denominator); source report `reports/tim_ab16_prod_regression_20260908/prodab16/may/r1/tim_target_memory.json`, physical reference sha256 `45d620d97e64...`, replay commit `75147ecb0e4edce81f54aea1b303a25df0572d45`.
- `dev_june_seq01`: reference_unavailable 0.000000 s, reference_gap 0.000000 s (both outside the present denominator); source report `reports/tim_ab16_prod_regression_20260908/prodab16/seq01/r1/tim_target_memory.json`, physical reference sha256 `c0d7c2a3c747...`, replay commit `75147ecb0e4edce81f54aea1b303a25df0572d45`.
- `dev_june_seq03_ocsort`: reference_unavailable 0.000000 s, reference_gap 0.100453 s (both outside the present denominator); source report `reports/tim_ab16_prod_regression_20260908/prodab16/seq03/r1/tim_target_memory.json`, physical reference sha256 `9e03fedc8076...`, replay commit `75147ecb0e4edce81f54aea1b303a25df0572d45`.
- `dev_june_seq04_ocsort`: reference_unavailable 0.000000 s, reference_gap 0.100884 s (both outside the present denominator); source report `reports/tim_ab16_prod_regression_20260908/prodab16/seq04/r1/tim_target_memory.json`, physical reference sha256 `a99fb5ea98c3...`, replay commit `75147ecb0e4edce81f54aea1b303a25df0572d45`.

## Interpretation (descriptive only -- not a tuning signal)

- **Seq01**: 100% correct-while-present -- clean four-person visibility is
  handled with no wrong-person authority and no suppression.
- **May hard re-entry**: ~92.53% correct-while-present, ~0.05% wrong,
  ~7.42% LOST/suppressed -- the residual is dominated by conservative
  suppression around the hard exit/re-entry, not by wrong-person authority.
- **Seq04**: ~67.26% correct-while-present, 0% wrong, ~32.74%
  LOST/suppressed, and 0% absence leakage across ~13.9 s of true absence --
  the weakness is availability/conservatism, and absence handling is safe.
- **Seq03**: ~29.37% correct-while-present, **0% wrong**, ~70.63%
  LOST/suppressed. The remaining development weakness on the crossing
  sequence is **availability / conservatism**, not wrong-person authority.
  This is a descriptive observation and must not be treated as a tuning
  target: the algorithm and configuration are frozen for the prospective
  held-out evaluation.

**Issue #27 remains open. The final held-out H01/H02/H03 evaluation has not
happened.**
