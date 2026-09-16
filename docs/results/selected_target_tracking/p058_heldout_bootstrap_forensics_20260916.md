# Issue #58 held-out bootstrap forensic record

Date: 16 September 2026  
Status: pre-correction diagnosis, written before implementation changes

## Protected first prospective run

The first prospective run remains unchanged at
`reports/p058_final_architecture_comparison/p058_final_architecture_20260916_172556`.
It contains 92 files and is independently backed up on the Mac. A fresh
file-by-file SHA-256 comparison on 16 September confirmed identical content.
Its top-level hashes remain:

- `manifest_lock.json`: `2402d0038d198af773a8e8d36d9fb11d42c279a2976b887ea45c6652efed5c8a`
- `run_provenance.json`: `743374ecad5938b4824a52313a37a45dde2098650d8a1e032342aad675be4b1e`
- `comparison_by_architecture.json`: `bb4192fa035e83bbba96a3403c82a715e12cb780719154f31781259f924bfaf5`
- `comparison_by_architecture.csv`: `254720dafdea4d6396ea1180ad5442504faf9770d23d9c7a6846937ba7de962b`
- `comparison_by_architecture.md`: `6e48d453421c7e83f5a04b989fab4614af603903af828cc46a2e5a651f141b55`

The run recorded six valid cells and six bootstrap failures. This record does
not reinterpret a failed cell as evaluated evidence.

## Defect

`tools/analysis/resolve_bootstrap_target.py` obtains both the first
`present_scored` physical-reference box and its bag-relative time, but uses
only the box. It starts counting `/tracks` messages at the beginning of the
generated bag. The physical-v2 reference time is relative to the first source
image timestamp. Therefore the resolver compares geometry from one physical
instant with tracker output from another whenever tracker messages precede the
reference instant.

H02 proves the defect directly. Its first `present_scored` sample is at
`t = 3.266311891 s`, with box `[557.61, 342.65, 622.89, 459.3]`. The retained
resolver record compared that box with tracker frame 0 rather than the tracker
frame at `3.266311891 s`. The three ByteTrack-family H02 failures are therefore
invalid protocol executions, not measured architecture failures or scenario
limitations.

## DeepSORT forensic evidence

The frozen deterministic replay consumes source messages in original bag
sequence. DeepSORT requires a causal image at or before each detection. A
read-only prefix replay under the pinned numerical environment found:

| sequence | source messages before first image | first usable DeepSORT observation | first confirmed output (`n_init=3`) |
| --- | ---: | ---: | ---: |
| H01 | 2 detections | reference-relative frame 0 | reference-relative frame 2 |
| H02 | 2 detections | reference-relative frame 0 once the target first becomes `present_scored` | reference-relative frame 2 for a newly initiated target track |
| H03 | 1 detection | reference-relative frame 0 | reference-relative frame 2 |

The retained first run instead counted the pre-reference detection messages as
frames 0 onward. It consequently inspected H01/H02 detection indices 0--2 and
H03 indices 0--2, although the frozen physical-reference bootstrap windows
begin at their reference instants. No tracks exist in the reported first three
records because the early detections have no causal image and cannot create a
DeepSORT observation.

The DeepSORT lifecycle is otherwise consistent with the frozen rule: a new
track starts tentative with `hits=1`, two matched updates raise it to
`hits=3`, and confirmed output first appears at reference-relative frame 2.
The three-frame budget and predetermined frame index 2 are not changed.

## Decision before correction

This is one implementation defect affecting the shared bootstrap resolver:
failure to align the tracker stream to the physical-reference time origin and
first `present_scored` instant. It invalidates H02 ByteTrack-family bootstrap
and all three reported DeepSORT bootstrap decisions. The evidence does not
support changing tracker parameters, `n_init`, models, thresholds, frame
budgets, the predetermined bootstrap instants, physical-v2 evaluation, or any
TIM-MARS logic.

A protocol-repair run is scientifically required to implement the already
frozen physical-reference bootstrap rule. The smallest correction is to derive
the physical-reference time origin from the first retained source image,
discard `/tracks` messages before `origin + reference_sample_t_s`, and start
the unchanged architecture-specific frame budget there. Tests must demonstrate
that pre-reference tracker messages no longer consume the budget. The repair
must use a new output directory and preserve the first prospective run.

The corrective run is protocol-repair evidence. It is not a rerun selected by
cell performance, and all 12 cells must be regenerated under the corrected
shared resolver so no architecture or scenario is selectively rerun.
