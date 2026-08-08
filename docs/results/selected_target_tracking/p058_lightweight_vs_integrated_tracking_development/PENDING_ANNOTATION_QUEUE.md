# Issue #58 pending annotation queue

Status: 6 cells `pending_annotation` (not failures). Nothing here changes
the frozen architecture definitions, the May results, the SORT calibration
outcome (`no_safe_configuration_found`), or current provisional
conclusions -- this document only prepares the workload for a later
session.

## 1. The six required annotations

| # | ID | Sequence | Tracker | Replay bag | Expected CSV | `/tracks` duration | Distinct candidate IDs (workload proxy, not identity) |
|---|---|---|---|---|---:|---:|---:|
| 1 | `seq01_deepsort` | `dev_june_seq01` | deepsort | `bags/replay/p058_seq01_annotation_prep_6231fdc1_2026_08_08/deepsort` | `docs/data/annotations/june_hard_sequences/seq01_deepsort.csv` | 105.405 s | 23 |
| 2 | `seq01_sort` | `dev_june_seq01` | sort | `bags/replay/p058_seq01_annotation_prep_6231fdc1_2026_08_08/sort` | `docs/data/annotations/june_hard_sequences/seq01_sort.csv` | 105.405 s | 71 |
| 3 | `seq03_deepsort` | `dev_june_seq03` | deepsort | `bags/replay/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/tracker_bags/dev_june_seq03/deepsort` | `docs/data/annotations/june_hard_sequences/seq03_deepsort.csv` | 96.078 s | 37 |
| 4 | `seq03_sort` | `dev_june_seq03` | sort | `bags/replay/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/tracker_bags/dev_june_seq03/sort` | `docs/data/annotations/june_hard_sequences/seq03_sort.csv` | 96.078 s | 90 |
| 5 | `seq04_deepsort` | `dev_june_seq04` | deepsort | `bags/replay/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/tracker_bags/dev_june_seq04/deepsort` | `docs/data/annotations/june_hard_sequences/seq04_deepsort.csv` | 66.394 s | 26 |
| 6 | `seq04_sort` | `dev_june_seq04` | sort | `bags/replay/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/tracker_bags/dev_june_seq04/sort` | `docs/data/annotations/june_hard_sequences/seq04_sort.csv` | 66.394 s | 57 |

Note for #5/#6 in the table above: `docs/data/annotations/june_hard_sequences/seq04_deepsort.csv`
**already exists on disk but is stale** (see Section 3) -- the new CSV must
overwrite it only after passing validation, never silently.

"Distinct candidate IDs" is a cheap structural count (every track ID that
ever appeared anywhere in the bag, for any of the four people in frame),
not a labeled transition count -- it is a rough proxy for how fragmented
each tracker's output is, not the number of clicks required. SORT is
consistently 2.4-3.1x more fragmented than DeepSORT on the same sequence
(71 vs 23 on Seq01, 90 vs 37 on Seq03, 57 vs 26 on Seq04), consistent with
SORT having no appearance-based re-identification.

**Important duration note:** each `/tracks` duration above is the fresh
replay bag's actual first-to-last `/tracks` timestamp span, computed the
same way the future validator will check it -- it is the authoritative
"annotate through this timestamp" value. It differs from the historical
ByteTrack annotation's nominal end time in some cases (e.g. Seq01's
existing ByteTrack annotation runs to 122.340 s, but the fresh SORT/
DeepSORT `/tracks` stream only spans 105.405 s) -- annotate to the
replay bag's own duration above, not the ByteTrack reference's end time.

## 2. Full provenance (per replay bag)

| Bag | Source bag | Source SHA-256 | Tracker config SHA-256 | Model SHA-256 | `/tracks` bag SHA-256 | Detections processed | Commit |
|---|---|---|---|---|---|---:|---|
| `seq01_deepsort` | `bags/source/official_flights/2026-06-19/seq01_clean_four_person/full_pipeline/2026-06-19__12-45-45__...` | `fcdcb2c9a3c8655c...` | `d586e2e04c283313606cb366b64c0e7bad19692207f185d7dd9b89c89e33efb0` | `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1` | `ed7f174e94422f55338ca8bcf2f34a1609036b15c1dd42f0cbd9eb5ddc404e71` | 2465 | `6231fdc1370b78a55ffeee9a403adbbddf4fb424` |
| `seq01_sort` | (same source as above) | `fcdcb2c9a3c8655c...` | `78051b9606cae6d2f6c8de25bffe38d26697e2edf153a9961bbf31934016319c` | n/a | `3270b9deef01ff2e622ff1a108e62d6a784569d5297315c5205dd4a48a8a1cae` | 2465 | `6231fdc1370b78a55ffeee9a403adbbddf4fb424` |
| `seq03_deepsort` | `bags/source/official_flights/2026-06-19/seq03_crossing_ambiguity/full_pipeline/2026-06-19__12-57-48__...` | `c3016fc90db91efb...` | `d586e2e04c283313606cb366b64c0e7bad19692207f185d7dd9b89c89e33efb0` | `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1` | `fc35354c713f0d28b0e8ccbc352db90bb7a5471d95df221581d1013a0b2749ce` | 2336 | `6231fdc1370b78a55ffeee9a403adbbddf4fb424` |
| `seq03_sort` | (same source as above) | `c3016fc90db91efb...` | `78051b9606cae6d2f6c8de25bffe38d26697e2edf153a9961bbf31934016319c` | n/a | `af46d5444e85ff82e2149a5447798e6c50a33121d95304490f3ffaf66ad1c869` | 2336 | `6231fdc1370b78a55ffeee9a403adbbddf4fb424` |
| `seq04_deepsort` | `bags/source/official_flights/2026-06-19/seq04_occlusion_no_exit/full_pipeline/2026-06-19__13-01-36__...` | `50455abd49d0be4d...` | `d586e2e04c283313606cb366b64c0e7bad19692207f185d7dd9b89c89e33efb0` | `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1` | `3259d2dfa5633d9763f63b122fa442bd0e021e86cafa4d537a0ffc61e32ba2b5` | 1589 | `6231fdc1370b78a55ffeee9a403adbbddf4fb424` |
| `seq04_sort` | (same source as above) | `50455abd49d0be4d...` | `78051b9606cae6d2f6c8de25bffe38d26697e2edf153a9961bbf31934016319c` | n/a | `d175460056d107e3d281258d42f802e4df573f01dbb89bfd1c8d8d2968a312cc` | 1589 | `6231fdc1370b78a55ffeee9a403adbbddf4fb424` |

Every paired (sort, deepsort) replay for the same sequence reads the
identical source bag SHA-256 and identical `detection_messages_processed`
count -- confirmed same detection stream, not just "same bag name."
Repository was clean at generation time for 5 of 6 (one, `seq04_deepsort`,
was generated while earlier same-session tooling files were still
untracked -- benign, those files were committed in the prior checkpoint,
not a canonical-input change).

## 3. Stale annotation quarantine

Two existing tracked files are **not valid** for Issue #58 paired
comparison and must not be used, edited, or deleted:

| File | References (wrong) source bag | Correct #58 source bag | Why invalid |
|---|---|---|---|
| `docs/data/annotations/june_hard_sequences/seq03_deepsort.csv` | `.../seq03_crossing_ambiguity/image_raw/2026-06-19__12-55-58__...` | `.../seq03_crossing_ambiguity/full_pipeline/2026-06-19__12-57-48__...` | Separate "image_raw"-only diagnostic capture recorded ~2 minutes before the canonical `full_pipeline` bag; genuinely different frame content, not a renumbering artifact |
| `docs/data/annotations/june_hard_sequences/seq04_deepsort.csv` | `.../seq04_occlusion_no_exit/image_raw/2026-06-19__12-59-53__...` | `.../seq04_occlusion_no_exit/full_pipeline/2026-06-19__13-01-36__...` | Same failure mode: separate ~2-minutes-earlier capture |

Confirmed empirically, not assumed: `seq04_deepsort.csv`'s first-interval
`correct_target_track_id=5` never appears anywhere in a fresh deterministic
replay of the canonical `full_pipeline` source (`tools/analysis/
validate_p058_annotation.py` now proves this programmatically for both
files -- see Section 4).

Both files are **retained unedited** as historical Issue #43 evidence (that
issue's four-tracker matrix used a different source-bag convention that was
valid for its own scope). They are not deleted, not rewritten, not
silently reinterpreted.

## 4. Fail-closed guard against reusing the stale files

`tools/analysis/validate_p058_annotation.py` checks every candidate
annotation's `bag_name` field against the canonical source-bag identifier
for its sequence (a positive allowlist, not just a blocklist of the two
known-stale files -- a new, still-wrong annotation would also be caught).
Running it against the two stale files now:

```
$ tools/analysis/validate_p058_annotation.py \
    docs/data/annotations/june_hard_sequences/seq04_deepsort.csv \
    --sequence dev_june_seq04 --tracker deepsort
[FAIL] 26 problem(s) ...
  - row 0: bag_name references a KNOWN-STALE source bag ('2026-06-19__12-59-53')
  - row 0: bag_name ... does not reference the canonical source for dev_june_seq04
```

Exit code 1. Confirmed for both files;
`tools/tests/test_validate_p058_annotation.py` regression-tests this
against the real tracked files (not just a synthetic fixture), plus 13
more tests covering interval continuity, visibility semantics, and that
validation never mutates the file it checks.

## 5. Inserting a completed annotation later requires no protocol change

Once a CSV exists at its expected path from Section 1:

1. Run `tools/analysis/validate_p058_annotation.py <csv> --sequence <id> --tracker <tracker> --replay-bag <bag>`.
2. If it passes, flip that (tracker, sequence) entry in
   `docs/data/lightweight_vs_integrated_tracking/p058_lightweight_vs_integrated_tracking_v1.yaml`'s
   `annotation_availability` from `pending_annotation` to `available`, and
   remove the corresponding entry from `pending_annotation_files`.
3. Re-run `tools/analysis/aggregate_lightweight_vs_integrated_report.py`.

No architecture, calibration rule, or result-dependent choice changes --
the manifest and runner were designed for exactly this insertion path from
the start.

## 6. Instructions for the future annotation session (do not run yet)

**Launch command:**
```
thesis_env/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host 100.69.42.62 --port 8888
```
Then open `http://100.69.42.62:8888` in a browser.

**Recommended order** (lowest fragmentation/workload first, builds
familiarity before the harder ones): `seq01_deepsort` (23 ids) ->
`seq04_deepsort` (26 ids) -> `seq03_deepsort` (37 ids) -> `seq04_sort`
(57 ids) -> `seq01_sort` (71 ids) -> `seq03_sort` (90 ids).

**Physical person to follow, per sequence** (from each sequence's existing,
valid ByteTrack reference annotation -- same physical human as the rest of
this thesis's evidence for that sequence):
- Seq01 (`seq01_bytetrack.csv`): the largest-box target at t=0
  (`target_largest` initialization), continuously visible for the entire
  ByteTrack reference (zero ID switches in ByteTrack's own stream).
- Seq03 (`seq03_bytetrack.csv`): the largest-box target at t=0. ByteTrack's
  own reference shows several `id_switch_fragmentation` and
  `occlusion_ambiguity` events (track ids 2->8->12->17->13 over the
  sequence) -- expect at least this many transitions in SORT/DeepSORT too,
  likely more given their higher fragmentation counts in Section 1.
- Seq04 (`seq04_bytetrack.csv`): the largest-box target at t=0. ByteTrack's
  own reference includes **two target-absence spans**
  (49.019-53.731 s and 58.959-62.241 s, plus a final 64.816-65.809 s span)
  and several id_switch_fragmentation/reentry events (ids
  1->21->26->31->32->35->36) -- expect target-absence intervals in the
  SORT/DeepSORT annotations too, not just clean_visible/occlusion_ambiguity.

**ID-switch rule:** if the tracker assigns a new ID to the same physical
human (occlusion, brief loss, reentry), start a new row with the new ID --
same rule already used throughout every existing annotation in this
repository. If an old ID drifts onto a different person, stop following
that ID; do not select a different person because their track looks
cleaner.

**Target-absence rule:** mark `target_visible=false`,
`event_type=target_absent`, leave `correct_target_track_id` empty --
matches the existing schema used by every other annotation file (validated
by `check_visibility_semantics` in the new tool).

**Save:** use the UI's save action, writing directly to the expected CSV
path from Section 1's table.

**Verification after each CSV:**
```
tools/analysis/validate_p058_annotation.py \
  docs/data/annotations/june_hard_sequences/<name>.csv \
  --sequence <dev_june_seq0N> --tracker <sort|deepsort> \
  --replay-bag <replay bag path from Section 1>
```
Fix and re-save if it reports problems; it never auto-corrects.
