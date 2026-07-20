# Data Catalogue

This folder contains the active metadata used to understand and locate thesis bag data.

Active files:

- `bag_layout.md`: human-readable explanation of the bag folder taxonomy.
- `bag_inventory.md`: readable historical inventory of bags known on 25 June 2026.
- `bag_inventory.yaml`: machine-readable historical inventory from the same audit.
- `tim_eval_catalogue.yaml`: generated canonical evidence contract for final TIM-MARS result rows.

## Canonical evidence contract

Regenerate the evidence catalogue with:

    python3 tools/catalogue/build_tim_eval_catalogue.py

Validate the committed catalogue without modifying it with:

    python3 tools/catalogue/build_tim_eval_catalogue.py --check

The catalogue is generated only from tracked report summaries and their tracked
per-run provenance sidecars. It does not promote a bag merely because it appears
in the historical inventory.

Each final row has two independent classifications:

- selection provenance:
  - `autonomous`;
  - `annotation-driven diagnostic`;
- replay scope:
  - `memory-only replay`;
  - `full-pipeline replay`.

This separation is intentional. For example, an autonomously selected tracker
stream can subsequently be evaluated through a memory-only TIM replay.

A final row must record:

- source and output bag paths;
- source-file manifest and hashes;
- selected tracker ID;
- tracker-specific annotation and hash;
- replay metadata and hash;
- canonical configuration and model hashes;
- replay commit;
- authoritative report and evaluator-output hashes.

There are currently no promoted full-pipeline rows. Existing annotations are
tracker-ID-specific, and compatibility with freshly rerun full pipelines has not
been proven.

Seq02 is explicitly non-final. The stale catalogue promoted target-ID `0`
replays, while the current ByteTrack annotation expects the target lineage
`1 -> 15 -> 23 -> 28 -> 40 -> 46`.

The P1.4 protected-appearance report remains diagnostic promotion evidence. Its
aggregate table lacks complete row-level source lineage, so it is not part of
the final canonical evidence-row set.

Archived files:

- `archive_legacy_cleanup/`: historical migration manifests from previous bag
  reorganisations. These are kept for traceability but are not part of the
  active catalogue.
