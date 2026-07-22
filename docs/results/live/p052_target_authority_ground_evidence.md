# P0.25 target-authority ground evidence

Issue: [#52](https://github.com/FRCTavares/IST-Thesis-Code/issues/52)

Date: 22 July 2026

Implementation under test:
`cfecf0bbb8890f499ba7f30d62b60df1d4e7bf69`

## Claim boundary

This evidence covers the live ROS target-authority graph using synthetic raw
target and tracker messages. Every run used a dedicated ROS domain and started
only `dashboard_bridge_node`, `target_memory_mars_node`, a MAVROS-disabled
`control_ref_node`, and an MCAP recorder. No camera, detector, tracker, MAVROS,
Pixhawk, hover, or aircraft was used. These results are ground software-safety
evidence, not flight-performance evidence.

## Retained runs

All retained runs started from a clean checkout of the implementation commit.
The complete 1.3 MiB evidence set remains locally under:

`bags/ground/p052_target_authority_cfecf0bb_2026_07_22/`

| Run | ROS domain | API / WS ports | Result | Authority-event SHA-256 | MCAP SHA-256 |
| --- | ---: | --- | --- | --- | --- |
| `run_01` | 89 | 18096 / 18771 | pass | `e3ae12399b47bccdaef46aa32178db811a81fb827bdefaeaf5fe17f118aed67a` | `1601d8399bf1b692552a10b773a4d540bce0395ea436b191ffb21a8b3743ba64` |
| `run_02` | 90 | 18097 / 18772 | pass | `b41a726e587e30a5c4b35ac7fa55eea23efc9cff2208e783bb02cf2da4dc7dfb` | `7017e17c50f7afb76c7a9cff719ce4aa9d216496961601babcaf479c498a35c9` |
| `run_03` | 91 | 18098 / 18773 | pass | `2accb30dd3de3787b8c6ed86a3059e112a71262105fb15d4d66bf1af9258f58a` | `4ae246242968139beef4d2e38b547dd1ecb33b8fb97503f7959fb4fc431de471` |

Each run retains:

- `ground_check_summary.json` with phase metrics and artifact hashes;
- `target_authority_events.jsonl` with session-scoped generations;
- process logs for dashboard, TIM-MARS, control, and rosbag;
- `rosbag/metadata.yaml` and one finalized MCAP file.

## Observed authority behavior

All three runs produced the same session-local authority generations `0`–`7`:

1. startup clear;
2. explicit target selection;
3. explicit clear;
4. explicit reselection;
5. rejected model-switch clear;
6. explicit reselection;
7. rejected tracker-switch clear;
8. explicit reselection before stale/restart checks.

| Phase | Required observation | Run 01 | Run 02 | Run 03 |
| --- | --- | ---: | ---: | ---: |
| Raw `/target` bypass | maximum command magnitude | 0.0 | 0.0 | 0.0 |
| Explicit validated selection | non-zero command observed | yes | yes | yes |
| Explicit clear | maximum settled command magnitude | 0.0 | 0.0 | 0.0 |
| Reused ID without selection | maximum command magnitude | 0.0 | 0.0 | 0.0 |
| Rejected model switch | maximum settled command magnitude | 0.0 | 0.0 | 0.0 |
| Rejected tracker switch | maximum settled command magnitude | 0.0 | 0.0 | 0.0 |
| Stale validated target | maximum settled command magnitude | 0.0 | 0.0 | 0.0 |
| TIM node restart | stopped/restarted maximum command magnitude | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

The restarted TIM node was identified by its ROS graph endpoint in every run,
published target ID `0`, and did not accept the reused synthetic tracker ID
without a new explicit selection.

## Validation

- focused target-authority, TIM, and control checks: 28 passed;
- `tools/tests`: 56 passed;
- `thesis_bringup` functional suite: 184 passed, 3 expected xfails;
- copyright/PEP257 checks: 1 passed, 1 skipped;
- `thesis_bringup` package build: passed;
- standalone ground-runner Flake8: passed;
- `git diff --check`: passed.

The package Flake8 test retains one pre-existing import-order failure in
`test_control_ref_safety.py`, tracked separately by Issue #48. The #52 changes
introduce no package lint finding.

## Conclusion

The retained runs support the scoped conclusion that operator commands reach
TIM-MARS, only validated TIM output can produce a control reference, and raw
targets, explicit resets, supported switch attempts, staleness, node restart,
and ID reuse all fail closed. Coordinate/time integrity and source-age control
remain separate blockers in Issues #53 and #23, so this evidence does not clear
the overall flight-readiness gate.
