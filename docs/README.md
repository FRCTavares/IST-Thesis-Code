# Thesis documentation

This directory contains the maintained research contracts, operational
documentation, frozen data definitions, curated result summaries, and
historical records for the TIM-MARS thesis project.

## Start here

The core thesis authority is:

1. [Frozen research questions](research_question.md)
2. [Research position and novelty contract](NOVELTY.md)
3. [Active GitHub issue queue](TODO_LIST.md)
4. [TIM-MARS algorithm and final scope](algorithm/tim_mars_versions.md)
5. [Evidence versions and claim boundaries](algorithm/tim_mars_evidence_versions.md)
6. [Maintained implementation and tooling index](design/tim_tooling_index.md)

## Authority hierarchy

Use repository sources in this order:

1. current implementation and canonical runtime configuration;
2. frozen research, algorithm, coordinate, freshness, and split contracts;
3. versioned evidence maps and promoted tracked result summaries;
4. generated reports with complete provenance;
5. archived historical material for traceability only.

Generated content under `reports/` is not automatically thesis authority.
A result becomes citable only after it is reviewed and promoted into
`docs/results/` or an explicitly tracked evidence package.

## Folder map

- `algorithm/` — active algorithm definitions, evidence-version boundaries,
  coordinate contracts, and output-freshness contracts.
- `control/` — maintained Pixhawk, MAVROS, and controller integration notes.
- `data/` — annotations, experiment manifests, splits, catalogues, and
  machine-readable research inputs.
- `debug/` — current Hailo, camera, and unattended-host recovery procedures.
- `design/` — maintained implementation and tooling indexes.
- `flight/` — current recording, readiness, and run-provenance procedures.
- `results/` — reviewed current evidence and thesis-facing result summaries.
- `archive/` — superseded result interpretations and historical cleanup
  records retained only for traceability.

## Current selected-target evidence

Start with:

- [Canonical selected-target evidence](results/selected_target_tracking/hard_reentry_multi_tracker_summary.md)
- [Current dual-oracle development audit](results/selected_target_tracking/p028_wrong_oracle_audit.md)
- [Compute and throughput summary](results/selected_target_tracking/hard_reentry_compute_throughput_summary.md)
- [Current result index](results/README.md)

Consult the evidence-version authority before combining values from different
documents.

## Frozen evaluation inputs

- [Data directory index](data/README.md)
- [Evaluation split policy](data/splits/README.md)
- [Component-ablation specification](data/ablations/README.md)
- [Evidence catalogue](data/catalogue/README.md)

Annotation CSV files are research inputs. They do not need individual links
from this top-level page when their authoritative manifest or result document
records their exact paths and hashes.

## Operational documentation

- [Source-first field recording plan](flight/SOURCE_FIRST_FIELD_RECORDING_PLAN.md)
- [Flight-readiness procedure](flight/P023_FLIGHT_READINESS.md)
- [Hailo recovery](debug/HAILO_RECOVERY.md)
- [Live camera recovery](debug/LIVE_STACK_CAMERA_RECOVERY.md)
- [Unattended Pi operation](debug/UNATTENDED_PI_OPERATION.md)
- [Pixhawk 6X Ethernet and MAVROS report](control/pixhawk6x_ethernet_mavros_report.md)

## Historical-material policy

Files under `archive/` are preserved for provenance but must not be used as the
current methodology or result authority.

Historical roadmap records, when retained, belong under `archive/` with other
superseded planning material. No separate top-level planning directory is
maintained.

Do not delete historical files merely because they are superseded. Move them
with `git mv`, document why they are historical, and retain any required
provenance.
