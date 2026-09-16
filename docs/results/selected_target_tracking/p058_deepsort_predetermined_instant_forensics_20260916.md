# Issue #58 DeepSORT predetermined-instant forensic addendum

Date: 16 September 2026  
Status: pre-correction diagnosis, written after the complete reference-time
alignment run and before any second implementation change

## Evidence retained

The first reference-time-aligned run is retained unchanged at
`reports/p058_final_architecture_comparison/p058_final_architecture_protocol_repair_20260916_181235`
and independently backed up on the Mac. It ran all 12 cells from clean commit
`f11e949e96e3cecd66d945a9831943ca91fb0e8d`, with 11 valid cells, one
DeepSORT H02 bootstrap failure, and no other failure.

This run confirms that reference-time alignment repairs H01 and H03 DeepSORT:
after skipping the two and one pre-reference tracker messages respectively,
their first target-overlapping confirmed output occurs at the frozen
reference-relative frame index 2.

## H02 finding

H02 exposed a separate mismatch between the frozen exact instant and the
resolver interface. At the first `present_scored` reference instant
`3.266311891 s`, the aligned DeepSORT stream contains track ID 3 on all three
inspected frames:

| reference-relative frame | time (s) | best track ID | IoU against the frozen initial reference box |
| ---: | ---: | ---: | ---: |
| 0 | 3.266311891 | 3 | 0.845826 |
| 1 | 3.299674873 | 3 | 0.842899 |
| 2 | 3.332965284 | 3 | 0.838658 |

The resolver selects the first threshold-passing frame, so it records frame 0.
The runner then requires the frozen DeepSORT frame index 2 and rejects the
otherwise available mapping. Thus the reported H02 DeepSORT failure does not
mean that no target-overlapping DeepSORT output exists at the predetermined
instant. It is created by selecting an earlier frame and checking for exact
frame equality only afterwards.

The earlier forensic record hypothesised that H02 would initiate a new target
track and first expose it at frame 2. The aligned evidence disproves that
H02-specific hypothesis: track ID 3 is already confirmed when the physical
target first becomes `present_scored`. This does not permit moving the frozen
instant. It makes exact evaluation at frame 2 necessary.

## Decision before correction

The Stage-7 run manifest freezes DeepSORT bootstrap at frame index 2 with a
three-frame inspection budget. Evaluating frame 2 directly implements that
existing policy. Selecting the earliest passing frame and rejecting it when it
is earlier than frame 2 does not.

A second protocol correction is therefore required. The resolver will accept
an explicit required frame index, retain all inspected per-frame diagnostics,
and resolve only the track at that frame. The runner will pass index 0 for the
ByteTrack family and the unchanged index 2 for DeepSORT. The IoU threshold,
frame budgets, tracker lifecycle, tracker/model/configuration, physical-v2
reference, and all evaluation semantics remain unchanged.

The next run must again regenerate all 12 cells in a new directory. It is
protocol-repair evidence, not an outcome-selected rerun. The original first
prospective run and the first reference-time-aligned run remain immutable.
