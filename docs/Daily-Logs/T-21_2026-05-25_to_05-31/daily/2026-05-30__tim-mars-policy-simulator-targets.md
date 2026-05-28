# Daily Plan - 2026-05-30 - TIM-MARS policy simulator

## Main objective

Use the Friday failure audit to design and test TIM-MARS policy improvements offline before changing the ROS node.

## Target outputs

Create or extend:

    tools/analysis/simulate_tim_mars_policy.py
    reports/tim_mars_policy_sweep/hard_reentry_policy_comparison.csv
    reports/tim_mars_policy_sweep/hard_reentry_policy_comparison.md

Optional:

    reports/tim_mars_policy_sweep/hard_reentry_best_policy_timeline.png

## Candidate policies to test

### 1. Baseline TIM-MARS

Reproduce the current TIM-MARS behaviour as closely as possible.

Metrics:

- correct ratio
- wrong ratio
- lost ratio
- wrong duration
- recovery timing

### 2. Appearance rejection policy

Rule:

    if current output appearance similarity < threshold:
        suppress output or enter UNCERTAIN

Goal:

- reduce wrong-target duration.

Risk:

- may increase lost duration.

### 3. Candidate promotion policy

Rule:

    if candidate appearance similarity is high
    and candidate score exceeds current score by margin
    and candidate persists for confirm_frames:
        promote candidate as selected target

Goal:

- recover faster after ID switches.

Risk:

- may switch to distractor if threshold is too loose.

### 4. Ambiguity suppression policy

Rule:

    if best_score - second_score < ambiguity_margin:
        output invalid target

Goal:

- avoid wrong target during crossings.

Risk:

- may increase lost duration.

### 5. Negative distractor memory

Rule:

    candidate_score = positive_similarity - lambda * distractor_similarity

Goal:

- avoid repeated distractor ID 1 / checkered-shirt target.

Risk:

- requires careful handling in live mode without ground-truth labels.

## Evaluation priority

Rank policies by:

1. lowest wrong ratio
2. highest correct ratio
3. lowest lost ratio
4. lowest expected runtime cost

Wrong target duration is the main failure to reduce.

## Success criteria

By the end of Saturday:

- At least 3 policy variants tested.
- A comparison table exists.
- One candidate policy is selected for ROS implementation.
- The selected policy has a clear reason and not just a better single metric.

## Do not do

Do not tune only for correct duration if wrong duration increases.
