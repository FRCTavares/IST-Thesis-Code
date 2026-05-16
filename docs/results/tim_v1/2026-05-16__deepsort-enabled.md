# DeepSORT Enabled for Replay Matrix

DeepSORT initially failed in the replay matrix because TensorFlow was not available.

Installed TensorFlow 2.17.1 for Python 3.12 with:

python3 -m pip install --user --break-system-packages "tensorflow>=2.16,<2.18"

Validation:

- tensorflow.compat.v1 imports successfully.
- DeepSORT loads the MARS ReID model from models/reid/mars-small128.pb.
- tracker_node starts successfully with tracker_deepsort.yaml.

Initial replay validation:

- Bag: 2026-05-14__10-59-01__dataset__tim_v1_two_person_no_crossing_raw
- DeepSORT + TIM selected target successfully.
- Post-selection raw valid duration: 60.026 / 60.026 s
- Post-selection TIM valid duration: 60.026 / 60.026 s
- TIM state sequence: NO_TARGET -> LOCKED
- Reacquisition events: 0
- TIM p95 latency: 1.3643 ms

Important dependency note:

Installing TensorFlow downgraded ml-dtypes to 0.4.1, while ONNX currently expects ml-dtypes>=0.5.0. If ONNX tooling breaks later, DeepSORT should be isolated in a dedicated environment or the dependency conflict should be resolved explicitly.

## Hard re-entry replay result

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw

DeepSORT + TIM result:

- Raw valid duration after selection: 242.337 / 255.117 s
- TIM valid duration after selection: 254.994 / 254.994 s
- Reacquisition events: 1
- TIM p95 latency: 0.9838 ms
- TIM p99 latency: 1.9957 ms
- Appearance enabled: yes
- Appearance-used rows: 0

Interpretation:

DeepSORT produced a strong raw selected-ID baseline on this replay, and TIM closed the remaining validity gap. Appearance was extracted but did not influence association, which is expected because DeepSORT was already stable in this scenario.

The tracker logs show DeepSORT update times in the approximate 80-250 ms range on this bag, so DeepSORT remains much heavier than the lighter online trackers even when target continuity is strong.
