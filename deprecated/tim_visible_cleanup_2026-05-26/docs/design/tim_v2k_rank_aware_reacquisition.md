# TIM-V2K: Rank-Aware Appearance Reacquisition

Date: 2026-05-19

## Problem

TIM-V1 can preserve selected-target identity through simple ID switches, but hard re-entry cases expose a failure mode:

- the selected person reappears under a new tracker ID,
- the correct candidate is present but not rank 0,
- the rank-0 candidate is often a distractor,
- naive reacquisition follows the wrong person.

For UAV following, wrong target output is more dangerous than LOST or UNCERTAIN output.

## Key Observation

On the corrected TIM-V1M appearance-critical bag:

| Policy | Correct | Wrong | Lost |
|---|---:|---:|---:|
| rank0 baseline | 0.509 | 0.431 | 0.060 |
| oracle_if_present | 0.901 | 0.000 | 0.099 |
| TIM-V2K | 0.613 | 0.120 | 0.266 |

The oracle result shows that the correct target is usually available in the candidate list. The rank0 baseline shows that choosing the best geometric/TIM score is unsafe.

## Policy

TIM-V2K modifies LOST-state reacquisition.

Instead of reacquiring the rank-0 candidate, TIM-V2K scans all candidates and selects among plausible candidates using appearance evidence.

### Candidate plausibility

A candidate is considered for reacquisition only if:

- total score >= `lost_min_total`
- geometry score >= `lost_min_geom`
- appearance score >= `lost_min_app`

### Candidate selection

Among plausible candidates:

1. rank by appearance score,
2. break ties using geometry,
3. break remaining ties using total score.

### Confirmation

The selected reacquisition candidate must remain the best candidate for `lost_confirm_frames`.

### Safety

If no candidate satisfies the plausibility and confirmation conditions, TIM remains LOST/UNCERTAIN.

## Recommended Offline Configuration

From corrected TIM-V1M offline sweep:

| Parameter | Value |
|---|---:|
| lock_min_total | 0.30 |
| lock_min_geom | 0.10 |
| lost_min_total | 0.40 |
| lost_min_geom | 0.10 |
| lost_min_app | 0.05 |
| lost_app_margin | 0.03 |
| lost_confirm_frames | 1 |
| missing_ttl_frames | 8 |

## Result

Corrected TIM-V1M result:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| rank0 baseline | 0.509 | 0.431 | 0.060 |
| TIM-V2K | 0.613 | 0.120 | 0.266 |

Relative wrong-target reduction:

`(0.431 - 0.120) / 0.431 = 72.2%`

## Remaining Limitations

1. TIM-V2K still increases LOST duration.
2. The hardest remaining interval involves target ID 11 and near-duplicate target fragment ID 18.
3. Single-ID annotation can over-penalise same-person duplicate fragments.
4. Appearance evidence is still weak or unavailable when geometry gating blocks appearance.
5. Live implementation must preserve TIM-V1 defaults unless explicitly enabled.

## Implementation Direction

TIM-V2K should be added behind a disabled-by-default config flag:

`rank_aware_reacquisition_enabled: bool = False`

The implementation should first reproduce offline behaviour in replay before live use.
