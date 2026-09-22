# Issue #58 post-access source-time evaluator repair

Date: 22 September 2026. This is a correctness repair to the output timebase of
the frozen physical-v2 evaluation. It is not a new prospective freeze, tracker
experiment, annotation, parameter choice, or scoring contract. The retained
16 September evidence remains intact.

## Authorities and reproducibility

- Historical final run: `reports/p058_final_architecture_comparison/p058_final_architecture_protocol_repair_v2_20260916_184554` at `dc4c5c39cfbe9911b63cb9757d01ca3de096f696`.
- H01 detached replay: `Thesis-Code-p058-repro-dc4c5c39/reports/p058_final_architecture_comparison/p058_timebase_repro_h01_dc4c5c39_20260921`.
- H02/H03 detached replay: `Thesis-Code-p058-repro-dc4c5c39/reports/p058_final_architecture_comparison/p058_timebase_repro_h02_h03_dc4c5c39_ros_env_20260922`.
- Corrected runtime output remains under `reports/p058_source_time_evaluator_repair/`. The durable 12-cell verification record and H02/H03 corrected-run record are tracked under `docs/results/selected_target_tracking/p058_source_time_repair_provenance_20260922/`.
- Read-only audit tools: `tools/analysis/compare_target_reid_semantic.py`, `verify_p058_source_time_reproduction.py`, and `reconcile_p058_source_time_repair.py`. Byte-identical copies of the exact H02/H03 repeat and correction launch helpers are retained in the same tracked provenance directory; their absolute paths are intentionally preserved as historical execution provenance rather than portable tools.
- Full old, corrected, and delta values for all 14 required metrics in all 12 cells: `docs/results/selected_target_tracking/p058_source_time_repair_20260922.{json,csv,md}`. The JSON includes source origins, timestamp-read statistics, per-report hashes, and reconciliation objects. Delta means corrected minus old.

The detached runner used the retained source image plus detector stream, the
frozen split and comparison contract, and the original source and reference
hashes. ROS interfaces came from the installed ROS overlay; the historical
`thesis_tracker` source was first on `PYTHONPATH`. No detector inference or
current-main behaviour-bearing architecture code was used. An initial SSH
attempt without the ROS environment failed at `rclpy` import before any
bootstrap could execute; that failed diagnostic directory is separate from the
successful replay.

All 12 reproduced cells match the retained bootstrap decisions and frozen-v2
evaluations. ByteTrack, TIM-MARS, and DeepSORT match their historical semantic
fingerprints for each sequence. The original Target-ReID MCAP payloads were
pruned, so direct full-field comparison with those September 16 files is not
possible. Each reproduced Target-ReID cell matches its retained metadata and
frozen-v2 evaluation. An independent repeat from the same frozen ByteTrack
stream matches every `/target_reid` record timestamp and every deserialised
field: 1,865 H01, 1,544 H02, and 1,485 H03 messages. Raw Target-ReID MCAP
hash differences are retained in the verification JSON and are not treated as
semantic changes.

The source origins are positive first-image `header.stamp`: H01
`1789486281308955860`, H02 `1789486544612758276`, and H03
`1789487735873995680` ns. Every evaluated output message in the 12 cells
used positive `src_stamp_ns`, with zero header or bag-record fallbacks, zero
duplicates replaced, and zero non-monotonic skips. All corrected duration
reconciliations pass. The three frozen physical-v2 files remain byte-identical.

## Interpretation of the corrected comparison

| Architecture | Old correct total (s) | Corrected correct total (s) | Old wrong total (s) | Corrected wrong total (s) |
| --- | ---: | ---: | ---: | ---: |
| ByteTrack raw | 47.832376191 | 47.982273462 | 36.600816626 | 36.316996402 |
| Target-ReID 0.90 | 3.200199242 | 3.195887649 | 0.000000000 | 0.000000000 |
| ByteTrack + TIM-MARS | 62.649203216 | 62.799441663 | 0.099977678 | 0.000000000 |
| DeepSORT raw | 68.166777110 | 68.233159544 | 0.166664224 | 0.000000000 |

The scenario pattern remains: TIM-MARS has more correct authority than
DeepSORT on H01, while DeepSORT has more on H02 and H03. TIM-MARS retains much
more correct authority than the conservative Target-ReID baseline and greatly
reduces wrong authority relative to raw ByteTrack. The previous claim that
TIM-MARS has *less aggregate wrong-person duration than DeepSORT* is no longer
supported: both corrected totals are zero. H01 and H03's old small DeepSORT
wrong intervals, and H01's old small TIM-MARS wrong interval, disappear under
source-time alignment. No universal winner or formal safety conclusion follows
from these three sequences.

## F19/F20 exact timing impact; thesis files not edited

The inserted F19 and F20 figures were inspected together with the Chapter 6
text and `FIGURE_PLAN.md` in the separate thesis-report checkout. Their frames
and qualitative examples remain the same, but the displayed output times were
computed on the old record-relative axis.

- **F19:** The H01 physical-reference absence and return times stay
  `23.566355370` and `34.133082027` s. The first restored TIM-MARS authority
  message is `40.066353499` s on source time (old label `40.132681173` s),
  so return-to-authority is `5.933271472` s, displayed as **5.93 s** rather than
  6.00 s. The representative stable-lock message is `41.299634174` s (old
  `41.367102743` s). The absence interval remains 10.57 s when rounded; the
  restored-to-stable interval remains +1.23 s when rounded. The figure's
  approximate pre-exit and suppressed-output panel labels also move from
  22.999 to 22.933 s and from 38.533 to 38.466 s, respectively.
- **F20:** The same H03 camera frames remain selected. The camera labels for
  panels (a), (b), and (c) map from old `20.881600676`, `21.215252149`, and
  `24.115082067` s to source times `20.866269431`, `21.199743463`, and
  `24.099679255` s. The frame-819 DeepSORT decision's old
  `t_alg=24.133090668` s is also `24.099679255` s on source time, exactly
  matching the panel-(c) image header. The illustrated suppression and
  occlusion percentages belong to the same frames.

The Chapter 6 #58 duration table and discussion must be refreshed from the
corrected JSON before a thesis claim freeze. The thesis report and figure PDFs
have not been edited as part of this repair.
