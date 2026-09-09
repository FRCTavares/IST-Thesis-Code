# H01–H03 captured-source handoff

This is operational preparation for the existing Stage-7 split v4 / comparison
v3. It does not supersede the protected P027 scenario sheets, the physical-v2
contract or the prospective freeze. No held-out results belong in this document.

## Field ownership

| Field | Before capture | Ready entry / consumers |
| --- | --- | --- |
| `expected_source_path` | Planned scenario root | Preserved planning metadata; never selects #58 input. |
| `planned_physical_v2_reference_path` | Planned annotation location | Preserved planning metadata; never overrides actual annotation. |
| `source_path` | Absent | Exact finalized timestamped bag directory, repository-relative; validator and #58 use it. |
| `files` | Empty | Complete sorted inventory of every file in that bag, including MCAPs, metadata and capture provenance; each has `path`, `size_bytes`, `sha256`. |
| `annotation_path` | Absent | Actual accepted human physical-v2 JSON, repository-relative; validator and #58 use it. |
| `annotation_sha256` | Absent | Frozen expected hash; #58 must not derive the expected hash from current file bytes. |
| `people_group`, `clothing_group` | `pending_capture` | Explicit anonymous participant and outfit codes. |
| `overlap_record` | Instruction | Explicit prose describing participant/clothing overlap and uncertainty. |
| `historical_exposure` | Absent | Explicit prior exposure/provenance statement, including source/annotation-only access and any known participant exposure. |
| `selected_target_id` | Absent | Integer `0`: unresolved legacy slot, not a selected tracker ID. |
| `status` | `reserved_pending_capture` | `ready` only in a validated, human-reviewed proposal that is explicitly applied. |
| `planned_annotation_status` | `not_yet_captured` | Original planning snapshot, retained unchanged; actual readiness is `status`. |

Historical development/legacy `selected_target_id` values keep their old
tracker-ID meaning. The Stage-7 runner never consumes that slot. It resolves
each architecture's tracker ID from the frozen physical-v2 person at the
predetermined bootstrap instant, **after all three entries pass release**.
Do not supply a positive tracker ID, inspect tracks to choose one, move the
bootstrap instant, or run the older component-ablation runner on these entries.
The four frozen #58 arms are the only final comparison path.

No new overlap categories are introduced: the existing four fields are
non-empty strings, not enums. Use `overlap_record` to name every
development/legacy group and say which anonymous people are the same, which
outfits are the same, whether individual garments overlap, and what is unknown.
The existing May participant/outfit history is incomplete: unknown must not
be converted into a claim of independence. `historical_exposure` must
distinguish participant familiarity from algorithm exposure of this recording.
The tool cannot verify these human assertions. Blank values and the literal
`pending_capture` are rejected.

## Future H01 procedure — do not execute before legitimate capture

Run from a validated checkout with ROS/CVAT dependencies available:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 tools/analysis/validate_tim_evaluation_split.py \
  docs/data/splits/tim_mars_split_v4.json --verify-hashes
THESIS_ROOT="$PWD" tools/experiments/record_p027_heldout_sequence.sh h01
```

Follow the protected H01 scenario sheet. Record the **exact retained path
printed by the helper**, not the newest directory in a search. Accept only
for physical-scene compliance, imagery and recording integrity. Preserve all
attempts and rejection reasons; never select a capture by algorithm quality.

Set the following variables explicitly (the path below is a placeholder):

```bash
SOURCE_BAG='bags/source/held_out/2026-09/h01_exit_reentry/<exact-capture-directory>'
WORK='reports/p027_preparation/h01_<unique-attempt-id>'
REFERENCE='docs/data/physical_target_references/heldout_h01_exit_reentry.json'
ros2 bag info "$SOURCE_BAG"
test ! -e "$WORK" || exit 1
mkdir -p "$WORK"
cp docs/data/preparation/p027/h01_cvat_preparation.json "$WORK/preparation.json"
cp docs/data/preparation/p027/overlap_metadata.json "$WORK/overlap.json"
```

Before processing, duplicate the finalized source to independent storage and
verify hashes. Keep `metadata.yaml`, all MCAP payloads, `run_metadata.json`
and the associated capture logs. The handoff requires the source-only topic
inventory (`/camera/image_raw` and `/detections`, both nonempty), complete
payload inventory and a clean full capture Git commit in `run_metadata.json`.
It does not deserialize bag messages or inspect algorithm topics.

Edit only these working copies:

- `preparation.json.source_bag_path`: exactly `SOURCE_BAG`.
- `coordinate_convention_evidence`: actual source/header coordinate evidence.
- `selected_physical_target_label`: anonymous physical-person description,
  never a tracker ID.
- `annotator`: responsible human.
- `allowed_roles`: `target` plus all actual distractor roles, using
  `phys_d001`, `phys_d002`, etc.; do not infer them from tracker IDs.
- All four fields of `overlap.json`, using the worksheet guidance above.

The template deliberately contains no intervals, bounding boxes, tracker IDs,
outcomes, evaluation-window adjustment or preselected bootstrap result.
Blank fields must be completed from source evidence/human records.

```bash
python3 tools/analysis/cvat_physical_reference.py prepare \
  --bag "$SOURCE_BAG" --preparation-config "$WORK/preparation.json" \
  --output-dir "$WORK/cvat"
```

Human annotation in CVAT:

1. Import the generated ordered source PNG archive using its task configuration.
2. Assign physical identities with `physical_ref`, not numeric CVAT IDs.
3. Review the entire source and fill the generated
   `$WORK/cvat/conversion_config.json` semantic intervals and required roles.
   The empty interval list intentionally blocks conversion until human review.
4. Preserve exact frame timestamps and the original window. Follow existing
   physical-v2 rules for absence, occlusion, unavailable reference and gaps.
   H03 physical presence during occlusion is not H01 absence.
5. Export **CVAT for images 1.1** to `$WORK/cvat/cvat_export.zip`.

Conversion writes its output, so refuse an existing accepted reference first:

```bash
test ! -e "$REFERENCE" || exit 1
python3 tools/analysis/cvat_physical_reference.py convert \
  --cvat-export "$WORK/cvat/cvat_export.zip" \
  --manifest "$WORK/cvat/frame_manifest.json" \
  --config "$WORK/cvat/conversion_config.json" --output "$REFERENCE"
python3 tools/analysis/cvat_physical_reference.py validate \
  --reference "$REFERENCE" --manifest "$WORK/cvat/frame_manifest.json"
```

The human must approve the annotation independently of algorithm outcomes.
Back up the reference, CVAT export, frame manifest, preparation/conversion
configs and overlap worksheet. Do not overwrite an accepted artifact to
silently correct it; preserve a documented version and rehash before release.

Generate the reviewable readiness proposal:

```bash
python3 tools/experiments/finalize_p027_heldout_entry.py \
  --scenario h01 --source-path "$SOURCE_BAG" \
  --annotation-path "$REFERENCE" \
  --frame-manifest "$WORK/cvat/frame_manifest.json" \
  --metadata "$WORK/overlap.json" --confirm-human-reviewed \
  --output-dir "$WORK/proposal"
```

The helper checks physical-v2/source linkage, frame-manifest linkage, source
inventory, annotation hash, metadata and the candidate split's Stage-7 gates.
It emits `ready-entry.json`, `split.proposed.json`, `split.patch` and
`proposal-provenance.json`. It never applies a patch, runs tracking, evaluates
architectures or chooses identities. It refuses re-finalization and existing
proposal output directories.

Review that the patch changes **only the intended pending entry** and preserves
all planning fields, scenario membership and freeze authority. Also review the
retained capture command, detector hash/resolved parameters and clean capture
commit against the existing prospective provenance requirements; do not fabricate
missing capture provenance. Candidate-stream hashes and resolved tracker IDs
are generated by #58 after release, never by inspecting tracks during handoff. Archive the
original split and proposal. Then explicitly apply the reviewed patch:

```bash
git apply --check "$WORK/proposal/split.patch"
git apply "$WORK/proposal/split.patch"
python3 tools/analysis/validate_tim_evaluation_split.py \
  docs/data/splits/tim_mars_split_v4.json --verify-hashes
git diff -- docs/data/splits/tim_mars_split_v4.json
```

Record the reviewed annotation/split transition in Git before evaluation.
This future status/path update is deliberate evidence finalization, not
permission for this preparation task to mutate any current held-out entry.
If the split changes after a proposal, regenerate from the latest split;
never force-apply or silently resolve conflicting proposals.

Repeat with `h02` / `h03`, the corresponding template, exact bag and planned
reference filename. Do not transplant intervals or identities from H01.

## Release and final runner — only after all three are ready

```bash
python3 tools/analysis/validate_tim_evaluation_split.py \
  docs/data/splits/tim_mars_split_v4.json --verify-hashes --require-final-ready
```

Require exit 0 and `final_ready=3/3`, clean committed state, independent
backups and the unchanged prospective authority. Only then:

```bash
python3 tools/experiments/run_p058_final_architecture_comparison.py \
  --set final_held_out --run --keep-bags \
  --output-dir "reports/p058_final_architecture_comparison/$(date +%Y%m%d_%H%M%S)"
```

Keep generated bags for subsequent frozen-artifact analysis. Do not use
`--overwrite`, retune, move bootstrap time, or recapture a poor result.
Run-time provenance remains the actual execution commit; the algorithm
authority and all model/config/evaluator hashes remain unchanged.
