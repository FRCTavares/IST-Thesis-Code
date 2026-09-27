# tools/issues/p032

Last reviewed: 2026-09-27

## P032 — Final runtime/resource characterization

Active Issue #32 measurement and analysis tooling.

- `measure_p032_live_resources.py` attaches bounded resource measurement to an
  existing production live run.
- `sample_p032_live_process_trees.py` samples CPU/RSS for pinned live process
  roots and descendants.
- `analyse_p032_final_resources.py` produces the retained final resource
  analysis.

These tools remain active until final mounted characterization is complete.
