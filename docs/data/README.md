# Data Metadata

This folder contains small, tracked metadata related to recorded experimental data.

- `annotations/`: trusted manual annotation CSVs used by TIM-MARS evaluation.
- `catalogue/`: bag inventory, evaluation catalogue, migration manifests, and keep-policy notes.
- `runtime_characterization/`: Issue #32 canonical runtime/resource measurement manifest (architecture IDs, hashes, live-vs-replay measurement modes, warm-up/duration/sampling cadence).
- `final_experiment_inventory.md`: promoted final replay bags, reports, and annotation CSVs.
- `reproduce_final_results.md`: local verification steps for the final thesis result artifacts.

Actual ROS 2 bags remain under `bags/` and are generally not tracked by Git.
