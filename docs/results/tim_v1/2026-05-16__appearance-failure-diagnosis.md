# TIM-V1 Appearance Failure Diagnosis

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Manual review showed two wrong-target intervals:

- 69.32-101.20 s
- 110.84-116.31 s

## Diagnostic result

In both wrong-target intervals, appearance was rarely used.

### Wrong interval 1, 69.32-101.20 s

- rows: 251
- state mostly: LOCKED
- target_track_id mostly: 1
- best_track_id mostly: 1
- appearance used: 3 / 251 rows
- best appearance median: 0.000
- best total median: 0.931

### Wrong interval 2, 110.84-116.31 s

- rows: 31
- state mostly: LOCKED
- target_track_id mostly: 1
- best_track_id mostly: 1
- appearance used: 1 / 31 rows
- best appearance median: 0.000
- best total median: 0.900

## Interpretation

The failure was not caused by appearance selecting the wrong person.

The failure was caused by geometry being highly confident in the persistent distractor. TIM stayed with or returned to ID 1 because the geometric score was strong, while appearance was almost never used strongly enough to challenge the geometric association.

Manual ID interpretation:

- Initial selected target: ID 1
- Later selected target IDs: ID 96, ID 142, ID 161
- Persistent distractor during wrong intervals: ID 1

## Consequence

TIM-V1 as currently implemented improves validity and can improve correctness, but it does not reliably prevent wrong-target output during close crossings when the distractor has strong geometric continuity.

## Next improvement direction

The next TIM improvement should focus on appearance-gated ID-switch validation, not simply a stronger descriptor.

Candidate policy:

- when multiple people are close,
- and a new plausible candidate ID appears,
- compare the old ID and new ID using appearance,
- require an appearance margin before keeping or reacquiring the old geometrically smooth ID.

The goal is to reduce wrong-target duration, not only increase valid-target duration.
