# TIM-MARS frozen evaluation split

The active prospective machine-readable authority is:

`docs/data/splits/tim_mars_split_v3.json`

The matching active prospective comparison authority is:

`docs/data/splits/tim_mars_final_comparison_v2.json`

`tim_mars_split_v2.json` is retained unchanged as historical provenance for
the 1 September 2026 prospective freeze. It was superseded before any H01--H03
capture or outcome access because reviewed behavior-affecting Issues #89 and
#90 were subsequently promoted.

`tim_mars_split_v1.json` is retained unchanged as historical provenance for
the 23 July 2026 freeze. TIM-MARS development continued after that freeze, but
H01--H03 were never captured or inspected. Split v3 therefore binds the
current final algorithm prospectively before any held-out outcome exists; this
is a protocol update, not post-test tuning.

The original split was introduced after the existing May and June recordings
had already been inspected and used during development. They therefore remain
development/legacy data in v2 and are not relabeled as held-out data.

## Sets

| Set | Sequences | Permitted use |
| --- | --- | --- |
| Development | May hard re-entry; June Seq01; OCSORT-frozen Seq03 and Seq04 | Threshold selection, debugging, regression tests, and ablations during development |
| Legacy validation | June Seq02 | Diagnostic comparison only; no tuning and no held-out claim |
| Final held-out | H01 exit/re-entry; H02 crossing; H03 occlusion/distractor | One final evaluation after capture, annotation, identity records, and hashes are frozen |

The three final sequences are currently `reserved_pending_capture`. They are
not ready for final evaluation, and issue #27 must remain open until the
release gate passes.

## People and clothing overlap

- June Seq01–Seq04 form one contiguous 19 June four-person recording session at
  the same court. They are recorded as one people group and one outfit group.
  Results across them are not person- or clothing-independent.
- The historical May recording has no participant/outfit codes. Overlap with
  June or the prospective final set is unknown, so it cannot support a
  subject-independent claim.
- Each new held-out recording must use anonymous participant codes (for
  example `P01`, `P02`) and outfit codes (for example `P01_O1_black_top`) and
  explicitly state whether each code appears in development/legacy data.
  Names or biometric identifiers are neither needed nor desired.

## No-leakage rule

Only the `development` set may influence thresholds. Recording-integrity checks
on held-out data may inspect topic presence, duration, timestamps, corruption,
and file completeness. Do not inspect TIM correctness, event results, or
candidate scores until all three held-out sequences and their annotations are
frozen.

If a threshold changes after held-out outcomes are viewed, create a new split
version and move the accessed recordings out of the final held-out set. They
may remain development data but cannot support the final held-out claim.

## Capture-to-release procedure

For each H01–H03 recording:

1. Record the source bag using the approved source-only field procedure.
2. Perform recording-integrity checks only.
3. Assign anonymous participant and outfit codes and record exact overlap.
4. Freeze the tracker/output-generation contract and annotation before viewing
   TIM results.
5. Add the source path, annotation path, selected target, file sizes, and
   SHA-256 values to `tim_mars_split_v3.json`; change status to `ready`.
6. Run:

   ```bash
   python3 tools/analysis/validate_tim_evaluation_split.py \
     --verify-hashes --require-final-ready
   ```

7. Only after the command passes may the final TIM evaluation or #28 final
   ablation matrix run on H01–H03.

The normal schema/freeze check intentionally permits pending captures:

```bash
python3 tools/analysis/validate_tim_evaluation_split.py
```

It must report `final_ready=0/3` until the September held-out recordings are captured, annotated, identity/outfit-audited, hashed, and frozen.
