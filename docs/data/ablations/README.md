# TIM-MARS component-ablation specification

The machine-readable P0.17 authority is:

`docs/data/ablations/tim_mars_component_ablation_v1.yaml`

The matrix contains exactly the seven rows required by issue #28. Rows 3–6
are controlled one-factor additions to a common geometry core. The final row
is the canonical configuration with no overrides.

## Interpretation boundary

“Geometry-only TIM” still contains TIM’s finite-state target memory and normal
state hysteresis; removing them would make it a different system rather than an
ablation of TIM-MARS. The separately ablated “persistence” component is the
implemented short-gap identity policy:

- same-ID priority inside the grace interval;
- suppression of an unsupported new tracker ID inside that interval.

Positive appearance is required internally by the appearance-margin and
hard-negative rows. Those rows isolate the additional publication-margin and
distractor-memory policies respectively; they are not claimed to operate
without a positive identity reference.

## Safety gate

Every row is compared with the same frozen raw tracker stream using two
complementary oracles:

- the spatial oracle compares output boxes with the annotated target track
  box; it tolerates same-person tracker-ID fragmentation but can be optimistic
  when the reference tracker box merges two people;
- the annotated-ID oracle follows the manually reviewed target-ID intervals;
  it is conservative and can count same-person fragmentation.

The final simplified TIM-MARS row is not promotable if either oracle increases
wrong-target duration beyond the configured numerical tolerance, or if
target-absence output increases beyond tolerance. A zero-wrong-target claim is
valid only when both oracles report numerical zero.

The development matrix may run only on the `development` set frozen in
`docs/data/splits/tim_mars_split_v1.json`. The final held-out matrix must not run
until the split validator passes with `--require-final-ready`.
