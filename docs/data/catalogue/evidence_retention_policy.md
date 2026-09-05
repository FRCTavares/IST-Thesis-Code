# Evidence Retention Policy

**Authority date:** 5 September 2026  
**Issue:** #49 — Consolidate replay bags and finish evidence-retention policy

This policy replaces the assumption that generated replay data should be
aggressively reduced. The objective is an auditable and scientifically safe
local evidence repository, not maximum disk reclamation.

## Retention classes

1. **Protected source evidence** — source/raw recordings, curated rerunnable
   inputs, official field recordings, and held-out captures. Never remove as
   routine cleanup.
2. **Promoted or referenced evidence** — any bag supporting a reviewed result,
   frozen experiment, thesis claim, promoted evidence package, or tracked
   reproduction procedure. Retain.
3. **Active dependency evidence** — data required by open roadmap work such as
   Issues #27, #32, #50, #58, or #64. Retain.
4. **Diagnostic evidence** — failed/fault/smoke evidence that documents a
   meaningful engineering or scientific conclusion. Retain while referenced or
   uniquely informative.
5. **Generated but unclassified evidence** — retain until a deletion proof is
   completed.
6. **Disposable generated evidence** — only generated data that is unreferenced,
   non-unique, reproducible from protected inputs, and explicitly recorded as
   safe to remove.

## Deletion gate

A bag may be removed only after all of the following are established:

- exact path and size;
- capture/source provenance;
- repository commit/configuration where applicable;
- repository, documentation, report, script, catalogue, annotation, alias, and
  GitHub-evidence references have been checked;
- semantic digest/checksum has been checked where available;
- no promoted result or active roadmap dependency requires it;
- any claimed canonical replacement has sufficient provenance;
- the action is recorded in tracked cleanup provenance.

Uncertainty means retain.

## Repetitions

There is no universal numeric repetition limit. Retain the canonical reviewed
run plus the repetitions required by the experiment's frozen methodology or
acceptance evidence. Additional deterministic repetitions may be removed only
after proving they are not referenced and add no unique diagnostic evidence.

## Smoke, pilot, failed, visual, temporary, and UI outputs

A name is not a deletion authorization. These outputs are disposable only when
they are generated, unreferenced, non-diagnostic, reproducible, and recorded in
the cleanup manifest.

## Annotation workflow

The historical `bags/annotation_inputs/` tree was removed in the July cleanup.
Current annotation work uses real source/replay paths and resolving convenience
aliases where useful. The annotation UI already provides role grouping and
client-side favourites.

Dangling aliases are not retained as historical evidence. Historical names are
recorded in tracked cleanup provenance instead.

## Current Issue #49 decision

The 5 September audit found approximately 72 GiB under `bags/`, including
approximately 39 GiB of replay data. This does not by itself justify deletion.

In particular, the large P030 external/oracle replay families are retained
because tracked final-result reproduction and analysis tooling depend on them.
Recent P025/P058 physical-v2 and P089/P090 development evidence is also retained.

The audit found no bulk replay set for which safe deletion was established.
Therefore Issue #49 does not manufacture a deletion target merely to reduce disk
usage.

Seven dangling symlinks left by the July cleanup were removed. No bag contents
were removed as part of that action.

The machine-readable current-state record is:

`docs/data/catalogue/evidence_retention_manifest_2026_09_05.json`

It contains both family-level retention classifications and an exact inventory
of every current ROS bag under the original Issue #49 scope. On 5 September
2026 that inventory contains 310 replay bags and one reference bag;
`bags/annotation_inputs/` and `bags/review/` are absent. Fields whose provenance
was not established by this audit are recorded as unknown rather than inferred.

Historical July deletion provenance remains under:

`docs/archive/bag_cleanup_2026_07_09/`

## Git and model-artifact storage decision

The repository currently has one Git object pack of approximately 4.52 GiB.
Tracked detector and appearance-model artifacts remain in their current tracked
state for Issue #49.

No Git-history rewrite, Git LFS migration, release-asset migration, or external
artifact-store migration is performed by this issue. Model provenance is not yet
complete enough to make such a migration safely: source weights, compilation
inputs/settings, and acquisition provenance remain unresolved for some tracked
artifacts.

A future storage migration, if still worthwhile, must be a separate planned
change with provenance recovery, backup, collaborator coordination, and
hash-preservation requirements. This storage decision is therefore closed for
Issue #49 as `retain current tracking; no history rewrite`.
