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
