# Manual Review Notes - TIM-V1M Appearance-Critical Crossing

Bag:

artifacts/bags/live_camera/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

Reports:

reports/tim_v0/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing
reports/tim_v1_appearance/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

## Manual observations

- Around t=36-40 s, TIM is LOST and the best candidate is track ID 9.
- Manual review confirms track ID 9 is the selected person.
- The distractor is track ID 6.
- Around t=56.11 s, TIM reacquires track ID 10.
- Manual review confirms track ID 10 is also the selected person.
- Track ID 11 is also the selected person.
- During the long LOST period, the selected person is mostly occluded by the distractor, but still partially visible or intermittently detectable.

## Interpretation

This is an appearance-critical failure case.

TIM-V1 appearance was active and repeatedly selected candidates that appear to correspond to the true selected person, but the final matching score often remained below the conservative LOST-state acceptance threshold.

Representative rejected candidates:

- t=36.355 s, best_track_id=9, best_total=0.560, best_appearance=0.451, threshold=0.600
- t=36.386 s, best_track_id=9, best_total=0.570, best_appearance=0.495, threshold=0.600

Since track ID 9 was manually verified as the selected person, this suggests that accept_score_lost=0.60 may be too conservative for difficult re-entry/occlusion scenarios.

Next experiment:

Replay this bag with lower accept_score_lost values, for example 0.55, 0.50, and 0.45.
