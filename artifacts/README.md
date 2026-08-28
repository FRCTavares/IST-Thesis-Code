# artifacts/

Disposable, reproducible generated output.

Everything under `artifacts/` is git-ignored (`.gitignore`: `artifacts/**`).
Only this README and any `.gitkeep` files are tracked. Nothing here is thesis
authority and nothing here is expected to survive a clean checkout.

Tools create subdirectories here on demand. Any of the following may be present
after a run:

- `artifacts/figures/` — generated plots (`analyse_bag_timing.py --figdir`
  defaults to `artifacts/figures/timing/<bag>/`);
- `artifacts/reports/` — per-run working directories for annotation import,
  replay audits, and evaluation scratch (e.g. the `p064_*` and `issue25_*` CVAT
  and evaluation working sets);
- `artifacts/videos/`, `artifacts/logs/`, `artifacts/bags/`, `artifacts/log/` —
  rendered media, run logs, and migrated colcon/root log output.

## How this differs from the other data directories

| Directory | What it holds | Tracked? | Authority |
| --- | --- | --- | --- |
| `bags/` | raw source ROS recordings and generated replay/eval/tmp bags | only `bags/README.md`; the rest is local | source bags are protected; replay/tmp bags are disposable unless promoted (`bags/README.md`) |
| `data/` | datasets and frozen evaluation inputs; machine-readable catalogues, splits, and manifests live in `docs/data/` | `data/datasets/external` and `data/datasets/processed` are local | frozen inputs are authority; see `docs/data/README.md` |
| `artifacts/` | disposable reproducible intermediate output | no (this README only) | none |
| `reports/` | generated analysis outputs (timing, tracking, replay, diagnostics) | only `reports/README.md`, plus a few reviewed evidence packages force-added as explicit exceptions | a report is not authority until reviewed and promoted (`reports/README.md`) |
| `docs/results/` | reviewed, human-facing result summaries the thesis cites | yes | current result authority, bounded by `docs/algorithm/tim_mars_evidence_versions.md` |

## Promotion path

Generated output in `artifacts/` or `reports/` becomes citable only after review,
by one of:

- force-adding a compact evidence package under `reports/` with its provenance
  sidecars and integrity manifest (`reports/README.md`), and/or
- writing or rewriting a summary under `docs/results/`.

Do not cite anything under `artifacts/` directly.
