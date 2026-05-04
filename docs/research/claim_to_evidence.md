# Claim-to-Evidence Note

Date: 2026-04-04
Owner: Thesis development

## Claim 1

- Claim: tiny-person-aware detector/tracker improvement increases selected-target robustness for small and distant people under embedded constraints.
- Why it matters: this is the main algorithmic thesis contribution.
- Evidence required: controlled baseline-versus-A experiments, size-bin analysis, and repeated onboard runs.
- Main metrics: recall by size bins, far-segment lock continuity, selected-target lock drop rate, selected-target ID switches.

## Claim 2

- Claim: the pipeline remains latency-bounded under onboard compute constraints while implementing the primary novelty.
- Why it matters: robustness gains are only defensible if real-time operation is preserved.
- Evidence required: long-run timing traces before and after A/C integration with queue-discipline checks.
- Main metrics: end-to-end latency p50/p95/p99, frame cadence stability, dropped-frame rate, per-stage timing budget.

## Claim 3

- Claim: selected-target continuity and reacquisition improve in ambiguity and short-occlusion conditions.
- Why it matters: continuity is central to target-relative control behaviour.
- Evidence required: scripted occlusion and crossing scenarios with repeatable event logs and ablation comparisons.
- Main metrics: reacquisition time, continuity duration, ID switch count, ambiguity-window recovery rate.

## Claim 4

- Claim: appearance support provides secondary gains for ambiguity resolution without becoming the main thesis mechanism.
- Why it matters: confirms supporting value while keeping thesis scope aligned.
- Evidence required: incremental comparison with Contribution B enabled versus disabled after A and C are stable.
- Main metrics: ambiguity-window ID switch reduction, reacquisition gain, trigger duty cycle, incremental latency overhead.

## Claim 5

- Claim: control behaviour remains safe under uncertain perception through latency-bounded validity logic.
- Why it matters: this is the primary systems contribution.
- Evidence required: transition-case tests covering confident, uncertain, stale, and lost states with command-trace review.
- Main metrics: invalid-to-safe transition time, command saturation frequency, burst count across mode transitions, responsiveness under confident lock.
