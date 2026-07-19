# P0.18 OC-SORT Sequence Evidence Package

This directory is an intentionally tracked exception to the generated-report ignore rule.

It preserves repeated canonical OC-SORT plus TIM-MARS evidence for:

- Seq03 crossing ambiguity;
- Seq04 occlusion/no-exit.

Key files:

- `canonical_ocsort_sequence_summary.json`: complete machine-readable result;
- `canonical_ocsort_sequence_summary.csv`: compact sequence comparison;
- `canonical_ocsort_sequence_summary.md`: thesis-facing interpretation;
- `canonical_ocsort_event_analysis.json`: event-level authoritative-equivalence result;
- `seq03_repeatability.json` and `seq04_repeatability.json`: repeated-run checks;
- per-run evaluation CSV/Markdown and replay provenance metadata;
- `report_manifest.sha256`: package integrity manifest.

Scientific verdict:

- OC-SORT plus TIM-MARS improves correct-target availability on both required sequences;
- Seq03 introduces `+1.350 s` wrong-target output and fails the safety criterion;
- Seq04 introduces `+0.050 s` wrong-target output at the evaluator-step boundary;
- the single canonical preset is not safe for promotion across the OC-SORT sequence pair;
- the one-preset motion-only modularity claim is rejected.
