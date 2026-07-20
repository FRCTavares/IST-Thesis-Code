# P0.4 Clean OC-SORT Sequence Evidence

This intentionally promoted compact package records repeated clean OC-SORT
plus TIM-MARS evidence from commit
`1b7dc4002c19e5235703913826e174df1025f1d0`.

The corresponding ROS bags remain ignored under:

- `bags/replay/p004_ocsort_tim_1b7dc400_2026_07_20/`

Key files:

- `canonical_ocsort_sequence_summary.json`, `.csv`, and `.md`;
- `regeneration_audit.json`;
- `DIGEST_SCHEMA_MIGRATION.md`;
- per-run aggregate and event-level evaluation CSVs;
- canonical configuration, resolved-runtime, and replay-metadata sidecars;
- `report_manifest.sha256`.

Seq03 exceeds the wrong-target tolerance and Seq04 lies at the one-step
boundary. The canonical preset is not promoted as universally safe.
