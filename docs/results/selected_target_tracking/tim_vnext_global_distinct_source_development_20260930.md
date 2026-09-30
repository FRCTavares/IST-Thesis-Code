# Global recovery appearance-source confirmation probe — 30 September 2026

Development-only diagnostic. No canonical TIM-MARS setting, frozen Issue #125 benchmark artifact, or H01–H03 evidence was changed. This branch starts from `origin/main` at `45eefd45`, separate from Issue #125. The VisDrone validation failure suggested the mechanism; the VisDrone outcomes were not used to score or select this candidate as independent evidence.

## Hypothesis and implementation

The current two-frame recovery confirmation can count two tracker frames that reuse one cached MARS appearance image. The default-off `--ablation-global-recovery-distinct-source` control makes only `global_identity_reacquisition` confirmation require a distinct appearance source image when provenance is available. Unknown source provenance can still advance the count, so this probe is not a fail-closed freshness rule. It does not alter other recovery paths, canonical YAML, ROS parameters, detector, tracker, appearance model, or the number of confirmations. The older AB-19 control applied the source rule to every persistence path.

The scoped control is implemented only for deterministic development replay. The production ROS node never enables it. All source changes were built with `tools/thesis_build.sh --base-paths /home/francisco/Desktop/Thesis-Code-tim-vnext/ros2_ws/src --build-base /home/francisco/Desktop/Thesis-Code-tim-vnext/ros2_ws/build --install-base /home/francisco/Desktop/Thesis-Code-tim-vnext/ros2_ws/install --packages-select thesis_bringup`. The focused recovery, persistence and replay test files pass 78/78. On Seq03, flag-off development replay and the untouched main-checkout runner produced the same semantic SHA-256, `56fe44a81fd3dba8790c39e8506745f182955a434781720403d8341dc2561ff6`.

## Matched development replay

May hard re-entry, June Seq03 crossing, and June Seq04 occlusion are the established development recordings in `docs/data/splits/tim_mars_split_v4.json`. Each default-off and flag-on pair used the same current source, source bag, selected ID, `available_image_challenge.yaml`, `mars-small128.pb`, physical-person reference, and pinned numerical environment `tim_pinned_replay_env_20260908.sh`. Every expected candidate-stream digest matched. Replays and physical-v2 reports are retained under ignored `bags/replay/tim_vnext_{default,global}_*` and `reports/tim_vnext_global_20260930/` on the Pi.

| Development sequence | Change in correct output (s) | Change in wrong-person output (s) | Change in LOST/suppressed (s) | Change in absent-with-output (s) |
| --- | ---: | ---: | ---: | ---: |
| May hard re-entry | −1.522600501 | 0 | +1.522600501 | 0 |
| June Seq03 crossing | −2.067728018 | 0 | +2.067728018 | 0 |
| June Seq04 occlusion | −10.066900216 | 0 | +10.066900216 | 0 |
| Sum across these three recordings | **−13.657228735** | **0** | **+13.657228735** | **0** |

Flag-on physical-v2 report SHA-256 values, in table order: `897e0614a77b25ee21c1ea1bdc37a5e397e53c3fe157b97c97bf3ece9197d20c`, `d8ca3372d4d39c717ad2e0b7392d9320bdf569a1ed08844e8ae2f713646e1377`, `72dc37e0ad1a906266adfb7791d2710f3d9c643dcfd649dac664fd51fc969234`.

The original September pinned baseline cannot be compared directly with today's runtime because canonical TIM-MARS has changed since that campaign. These numbers compare fresh default-off and flag-on replays made with the same current code and environment. The historical pinned baseline was not used to compute the table.

## Decision

**Do not promote.** The safeguard demonstrates the repeated-source mechanism but has an availability cost with no measured wrong-person benefit in the available development set. These recordings do not contain an observed wrong global recovery that the safeguard corrects, so they cannot establish its safety effectiveness. The frozen VisDrone benchmark remains an untouched comparison of the earlier canonical system. A vNext algorithm would require a separate development set with annotated false global recoveries and an independent prospective test set before any performance claim or field promotion.
