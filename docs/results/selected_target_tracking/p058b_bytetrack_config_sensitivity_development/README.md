# p058b ByteTrack configuration sensitivity — development evidence

Machine-readable evidence for
[`../p058b_bytetrack_config_sensitivity.md`](../p058b_bytetrack_config_sensitivity.md).

Development-only OFAT screen of `track_thresh` (0.40 / 0.60), `match_thresh`
(0.70 / 0.90) and `track_buffer` (15 / 45) around the canonical ByteTrack
configuration, evaluated on the four `tim_mars_split_v3` development sequences
through the identity-independent physical-v2 evaluator against a freshly rerun
canonical baseline. No canonical configuration was changed; the recommendation
is **NO** (development evidence does not justify a canonical ByteTrack change).

Frozen methodology commit: `14c3ef20755863e7ced3350fe823ccc017277ae3`.
Run id: `p058b_bytetrack_config_sensitivity_14c3ef20_2026_09_07`.

## Files

| file | contents |
| --- | --- |
| `manifest_lock.json` | resolved matrix: 7 configurations, per-config parameter dicts and materialized-YAML sha256, canonical/TIM/manifest hashes, repo commit |
| `run_provenance.json` | run id, repo commit + clean status, split id/sha, MARS model sha, cell totals |
| `repeatability.json` | 8 baseline-repeat determinism checks (all passed, zero mismatches) |
| `classification.json` | improved / neutral / regressed / unsafe_regression per candidate and per sequence |
| `comparison_by_sequence.csv` / `.json` | each candidate vs the rerun canonical baseline, per sequence: correct/wrong/lost baseline, candidate and delta; verdict and reason |
| `tim_metrics.csv` | per-cell TIM-MARS physical-v2 buckets, IoU, transition counts, authority changes |
| `raw_tracker_metrics.csv` | per-cell raw fixed-ID ByteTrack physical-v2 buckets and identity-independent continuity diagnostics |
| `cells.csv` | per-cell status, duration, tracker and TIM generated-semantic digests |
| `cells.json` | complete per-cell record: bootstrap decision, physical-v2 raw + TIM buckets / localisation / reconciliation, raw-tracker continuity, TIM state occupancy, digests |
| `cell_digests.csv` | compact per-cell audit row: config sha256, bootstrap id + IoU, tracker/TIM generated-semantic digests |
| `run_console.log` | runner console output for the 36-cell run |
| `SHA256SUMS` | hashes of the files in this directory |

## Reproduction

The 36 intermediate replay MCAP bags (~54 GiB) were removed after evaluation.
The per-cell tracker-freeze metadata, TIM-replay metadata, generated-semantic
digests and resolved-runtime fingerprints are retained under
`bags/replay/p058b_bytetrack_config_sensitivity_14c3ef20_2026_09_07/`. Every
cell is auditable from those and reproducible by re-running the frozen runner
from commit `14c3ef20`; baseline repeatability is deterministic.
