# Presence-conditioned reporting — prospective implementation record (8 September 2026)

## Purpose

This is a small additive record documenting that the presence-conditioned
TIM-MARS reporting layer was **implemented before any H01/H02/H03 access**, so
its formulas cannot have been shaped by held-out outcomes.

## What was already frozen

The presence-conditioned identity-performance metric semantics were predeclared
in the Issue #27 Stage-7 prospective freeze, merged in PR #102
(`main` at `0087b8660d0777c99aa2b9666f7e60822d0eb090`):

- `docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`
  → `primary_metric_contract` (`target_presence_accounting`,
  `while_physical_target_present`, `while_physical_target_absent`,
  `development_percentage_characterisation`);
- `docs/data/splits/tim_mars_final_comparison_v3.json`
  → `physical_reference_and_evaluation`.

The frozen present-time denominator is:

```
physical_target_present_duration_s
    = correct_target_output_duration_s
    + wrong_person_output_duration_s
    + identity_unresolved_duration_s
    + lost_or_suppressed_duration_s
```

`reference_unavailable_duration_s` and `reference_gap_duration_s` remain
separate evaluator conditions and are never folded into that denominator.

The exact Stage-7 `percent_time_target_present` is also implemented directly:

```
percent_time_target_present
    = 100 * physical_target_present_duration_s
      / (physical_target_present_duration_s + physical_target_absent_duration_s)
```

Its denominator is the physically-classified present+absent time only;
`reference_unavailable_duration_s` and `reference_gap_duration_s` are excluded.
The separately named `physical_target_present_pct_of_total` (denominator
`total_evaluated_duration_s`) is a secondary descriptive quantity and is **not**
mapped to the Stage-7 metric.

## What this commit does

- adds `tools/analysis/derive_presence_conditioned_metrics.py`, a **pure
  arithmetic** downstream layer that consumes one frozen
  `tim_physical_target_bbox_v2` evaluator report and emits the
  presence-conditioned structure (derived schema
  `tim_presence_conditioned_metrics_v1`);
- adds `tools/tests/test_derive_presence_conditioned_metrics.py`;
- adds the development-only characterisation evidence
  `tim_mars_presence_conditioned_development_20260908.{json,md}`.

The helper only performs arithmetic. It does not import or duplicate Stage-A
identity classification, re-open bags, recompute identity attribution, modify
the source evaluator report, or introduce any pass/fail threshold.

## Invariants

- The frozen physical-v2 evaluator is **byte-identical**:
  - `tools/analysis/physical_target_reference_v2.py`
    `6299542c5ae3f4f21bb313112f8375774ed2685ccf0cb164bd56848c34094c96`
  - `tools/analysis/physical_target_bbox_evaluation_v2.py`
    `4e80edc4a574d0eaf9fadbcf5c085513afe2ba40758cb25bbaeb866400fdbcfd`
  - `tools/analysis/evaluate_physical_target_bbox_v2.py`
    `ab6012a3cf912c1a9c35be3487101c55d646c8a00d3bb47670ab20785076a631`
  - `ros2_ws/src/thesis_bringup/thesis_bringup/freshness.py`
    `4abda9ffab0b171f007d565e91bf6a0d2723ed6e5958f3c7d8abb0ba82aa46f6`
- No held-out data existed or was accessed at implementation time. H01/H02/H03
  were not captured, listed, opened, hashed, replayed, annotated, evaluated or
  inspected.
- No algorithm, canonical configuration, tracker configuration, model,
  detector, physical-v2 annotation, Stage-A classification, IoU threshold,
  freshness/interpolation semantics, evaluation step, split membership,
  architecture arm, bootstrap definition or primary-metric definition was
  changed.
- The absolute reconciliation tolerance is inherited from the frozen evaluator
  (`residual <= 1e-6`), not re-chosen.

## Relationship to the Stage-7 metric contract

The new helper is a **DERIVED reporting layer**, not a new evaluator contract.
The derived schema identifier `tim_presence_conditioned_metrics_v1` names the
arithmetic layer only. The reporting helper is pinned here by SHA-256 rather
than inside the frozen Stage-7 manifest, so the merged Stage-7 freeze artifacts
stay byte-identical:

- `tools/analysis/derive_presence_conditioned_metrics.py` — SHA-256 recorded in
  `tim_mars_presence_conditioned_development_20260908.json`
  (`reporting_tool.sha256`); regenerate with `sha256sum` after any change.

## Future held-out reporting

Every future H01/H02/H03 and architecture-arm presence-conditioned figure must
use these same formulas (this helper, or an arithmetic equivalent that produces
identical values from the same frozen buckets). The percentages are arithmetic
transformations of already-frozen buckets; they add no new classification and
no pass/fail threshold.
