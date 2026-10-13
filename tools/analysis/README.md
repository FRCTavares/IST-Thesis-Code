# tools/analysis

Last reviewed: 2026-10-13

## Purpose

Runtime diagnostics and post-run checks for the live stack: timing statistics,
control-diagnostics summaries, visual-time bounds and source-header audits.
Research evaluation tooling (target-correctness evaluators, physical-reference
conversion, sensitivity sweeps, benchmark adapters) is not in this tree; it is
at Git tag `archive/thesis-final-20261013`.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `analyse_bag_timing.py` | Timing | Offline schema-v4 timing statistics and plots for a recorded bag. Writes under `analysis_out/timing/` by default. Imports `tools.timing_contract`. |
| `check_live_timing_invariants.py` | Timing | Live `/timing` ordering and sanity checks against a running stack. |
| `summarize_control_diagnostics.py` | Diagnostics | Integrity summary of recorded `/control_ref/diagnostics`: mode occupancy, reason counts, recovery-attempt bookkeeping, and the hard check that recovery is never active with non-zero translation. |
| `bound_visual_mcap_time.py` | Evidence | Conditionally bounds ffmpeg receipt time of the separate MKV visual against the field MCAP; not a physical-person attribution. |
| `check_source_headers.py` | Audit | Verifies purpose, authorship and upstream notices across maintained source files. |

## Rules

- Generated output goes under `analysis_out/` (git-ignored), never next to the
  sources.
- The timing contract lives in `tools/timing_contract.py`; analysers import it
  rather than redefining field names.

## See also

- `docs/RUNTIME_METRICS.md` - timing schema v4
- `docs/design/tim_tooling_index.md` - path authority
