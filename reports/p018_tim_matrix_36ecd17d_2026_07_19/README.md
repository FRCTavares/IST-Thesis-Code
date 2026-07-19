# P0.18 Four-Tracker Evidence Package

This directory is an intentionally tracked exception to the repository-wide generated-report ignore rule.

It records the canonical P0.18 matrix generated from clean commit:

- `36ecd17da9a66c4b95f82234960d831fb4f5ba44`

The corresponding large ROS bags remain ignored under:

- `bags/replay/p018_tim_matrix_36ecd17d_2026_07_19/`

Key files:

- `canonical_matrix_summary.json`: full machine-readable result;
- `canonical_matrix_summary.csv`: compact tracker matrix;
- `canonical_matrix_summary.md`: human-readable scientific result;
- `unsafe_window_diagnostic.json`: exact unsafe intervals;
- `unsafe_window_summary.md`: compact unsafe-window interpretation;
- per-tracker evaluation and provenance metadata;
- `report_manifest.sha256`: integrity manifest.

Interpretation:

- evidence integrity passed, but the single canonical preset failed the safety-promotion criterion for all four trackers;
- the one-preset motion-only modularity claim is not supported on this hard-reentry sequence;
- the DeepSORT result supports keeping appearance-based tracker association outside the current safe layering claim;
- issue #43 remains open for OC-SORT crossing/occlusion evaluation and thesis-claim updates.
