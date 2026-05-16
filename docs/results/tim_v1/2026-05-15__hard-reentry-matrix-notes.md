# TIM Replay Matrix Notes - Hard Re-entry Bag

Bag:

`2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw`

Matrix run started for:

- SORT, TIM off/on
- OC-SORT, TIM off/on
- ByteTrack, TIM off/on

SORT and OC-SORT runs completed with target ID 1.

ByteTrack TIM-off completed with target ID 1, but this is not directly comparable unless the selected physical person is verified.

ByteTrack TIM-on failed for target ID 1 and target ID 26 because the requested ByteTrack ID appeared in `/tracks` but was not stable long enough for TIM to initialise. The script correctly rejected the run because `/target_memory` never locked.

Interpretation:

Target IDs are tracker-specific. A single numeric target ID cannot be reused across SORT, OC-SORT, and ByteTrack without verifying that it corresponds to the same physical person. Future matrix runs need either:

1. tracker-specific target IDs, e.g. `sort:1, ocsort:1, bytetrack:<id>`, or
2. automatic target selection by visual rule, e.g. largest person after a fixed delay.

Decision:

Do not use ByteTrack TIM-on results for this bag until the target selection method is made tracker-independent.
