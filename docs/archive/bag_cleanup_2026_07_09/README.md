> **Archived provenance.** This folder is the audit trail for the 2026-07-09 bag deletion.
> It was tracked under `docs/bag_cleanup_2026_07_09/`, removed from version control on
> 2026-07-20, and restored here on 2026-08-28 so a clone can still audit what was deleted.
> The removed bags themselves are not recoverable from this record; only their names and
> recording `metadata.yaml` are kept. Not current methodology or result authority.

# Bag cleanup 2026-07-09

This folder documents the thesis bag cleanup.

## Goal

Keep only:

- curated source bags that can be reused for new TIM or tracker pipeline runs;
- official field-flight bags in a protected folder;
- delivered-paper replay bags used for the final result tables and diagnostics;
- the historical `tim_good` reference bag.

Delete:

- failed/tuning replay bags;
- old lab archive bags;
- duplicate full-pipeline bags;
- annotation-input bags that can be regenerated;
- MAVROS-only or obsolete support bags.

## Protected bag locations

- `bags/source/curated/`
- `bags/source/official_flights/2026-06-19/`
- `bags/replay/paper_final_tim_results_2026_07_03/`
- selected final DeepSORT replay folders
- `bags/reference/tim_good/`

## Reproducibility

The removed bags themselves are intentionally not kept. Their names and `metadata.yaml` files are preserved here. Evaluation reports and CSV summaries remain under `reports/`.
