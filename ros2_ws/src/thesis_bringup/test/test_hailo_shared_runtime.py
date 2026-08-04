"""Tests for shared detector and ReID ownership on one fake VDevice."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from thesis_bringup.perception.hailo_shared_runtime import (
    HailoSharedRuntime,
)
from thesis_bringup.perception.inference_engines import (
    HailoDirectInferenceEngine,
)


def make_fake_hailo_api(
    *,
    fail_reid_configuration=False,
):
    records = {
        "vdevices": [],
        "input_params": [],
        "output_params": [],
        "entered": [],
        "exited": [],
        "released": 0,
        "active": 0,
        "maximum_active": 0,
    }
    active_lock = threading.Lock()

    class FormatType:
        UINT8 = "uint8"
        AUTO = "auto"
        FLOAT32 = "float32"

    class HailoSchedulingAlgorithm:
        NONE = 0
        ROUND_ROBIN = 1

    class Params:
        def __init__(self):
            self.scheduling_algorithm = (
                HailoSchedulingAlgorithm.NONE
            )

    class HEF:
        def __init__(self, path):
            self.path = str(path)

    class Info:
        def __init__(self, name, shape):
            self.name = name
            self.shape = shape

    class NetworkGroup:
        def __init__(self, path):
            self.path = str(path)
            self.kind = (
                "reid"
                if "reid" in self.path
                else "detector"
            )

        def get_input_vstream_infos(self):
            if self.kind == "reid":
                return [
                    Info(
                        "repvgg/input",
                        (256, 128, 3),
                    )
                ]

            return [
                Info(
                    "detector/input",
                    (640, 640, 3),
                )
            ]

        def get_output_vstream_infos(self):
            if self.kind == "reid":
                return [
                    Info(
                        "repvgg/output",
                        (512,),
                    )
                ]

            return [
                Info(
                    "detector/output",
                    (80, 5, 100),
                )
            ]

    class VDevice:
        @staticmethod
        def create_params():
            return Params()

        def __init__(self, params):
            self.params = params
            self.released = False
            records["vdevices"].append(self)

        def configure(self, hef):
            if (
                fail_reid_configuration
                and "reid" in hef.path
            ):
                raise RuntimeError(
                    "synthetic ReID configuration failure"
                )

            return [NetworkGroup(hef.path)]

        def release(self):
            if not self.released:
                self.released = True
                records["released"] += 1

    class InputVStreamParams:
        @staticmethod
        def make(network_group, **kwargs):
            records["input_params"].append(
                (
                    network_group.kind,
                    dict(kwargs),
                )
            )
            return {
                "kind": network_group.kind,
                **kwargs,
            }

    class OutputVStreamParams:
        @staticmethod
        def make(network_group, **kwargs):
            records["output_params"].append(
                (
                    network_group.kind,
                    dict(kwargs),
                )
            )
            return {
                "kind": network_group.kind,
                **kwargs,
            }

    class InferVStreams:
        def __init__(
            self,
            network_group,
            input_params,
            output_params,
        ):
            self.network_group = network_group
            self.input_params = input_params
            self.output_params = output_params

        def __enter__(self):
            records["entered"].append(
                self.network_group.kind
            )
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            records["exited"].append(
                self.network_group.kind
            )

        def infer(self, inputs):
            assert len(inputs) == 1

            with active_lock:
                records["active"] += 1
                records["maximum_active"] = max(
                    records["maximum_active"],
                    records["active"],
                )

            try:
                time.sleep(0.01)

                if self.network_group.kind == "reid":
                    return {
                        "repvgg/output": np.arange(
                            512,
                            dtype=np.float32,
                        )[np.newaxis, :]
                    }

                return {
                    "detector/output": [
                        [
                            np.array(
                                [
                                    [
                                        0.10,
                                        0.20,
                                        0.60,
                                        0.70,
                                        0.90,
                                    ]
                                ],
                                dtype=np.float32,
                            )
                        ]
                        + [
                            np.empty(
                                (0, 5),
                                dtype=np.float32,
                            )
                            for _ in range(79)
                        ]
                    ]
                }
            finally:
                with active_lock:
                    records["active"] -= 1

    api = SimpleNamespace(
        FormatType=FormatType,
        HailoSchedulingAlgorithm=(
            HailoSchedulingAlgorithm
        ),
        HEF=HEF,
        VDevice=VDevice,
        InputVStreamParams=InputVStreamParams,
        OutputVStreamParams=OutputVStreamParams,
        InferVStreams=InferVStreams,
    )

    return api, records


def detector_batch():
    return np.zeros(
        (1, 640, 640, 3),
        dtype=np.uint8,
    )


def reid_batch():
    return np.zeros(
        (1, 256, 128, 3),
        dtype=np.uint8,
    )


def test_shared_runtime_configures_both_networks_round_robin():
    api, records = make_fake_hailo_api()

    runtime = HailoSharedRuntime(
        detector_hef_path="detector.hef",
        reid_hef_path="reid.hef",
        infer_timeout_ms=300,
        hailo_api=api,
    )

    assert len(records["vdevices"]) == 1
    assert (
        records["vdevices"][0]
        .params.scheduling_algorithm
        == api.HailoSchedulingAlgorithm.ROUND_ROBIN
    )
    assert records["entered"] == [
        "detector",
        "reid",
    ]
    assert runtime.detector_input_shape == (
        640,
        640,
        3,
    )
    assert runtime.reid_input_shape == (
        256,
        128,
        3,
    )
    assert runtime.has_reid

    output_formats = {
        kind: kwargs["format_type"]
        for kind, kwargs in records["output_params"]
    }

    assert output_formats == {
        "detector": api.FormatType.AUTO,
        "reid": api.FormatType.FLOAT32,
    }

    runtime.close()

    assert records["exited"] == [
        "reid",
        "detector",
    ]
    assert records["released"] == 1


def test_detector_only_runtime_fails_closed_for_reid():
    api, records = make_fake_hailo_api()

    runtime = HailoSharedRuntime(
        detector_hef_path="detector.hef",
        infer_timeout_ms=300,
        hailo_api=api,
    )

    assert not runtime.has_reid
    assert runtime.reid_input_shape is None
    assert runtime.reid_output_names == ()

    with pytest.raises(
        RuntimeError,
        match="not configured",
    ):
        runtime.infer_reid(reid_batch())

    result = runtime.infer_detector(
        detector_batch()
    )

    assert "detector/output" in result

    runtime.close()
    runtime.close()

    assert records["released"] == 1


def test_detector_and_reid_calls_are_serialized():
    api, records = make_fake_hailo_api()

    runtime = HailoSharedRuntime(
        detector_hef_path="detector.hef",
        reid_hef_path="reid.hef",
        infer_timeout_ms=300,
        hailo_api=api,
    )

    errors = []

    def run_detector():
        try:
            runtime.infer_detector(
                detector_batch()
            )
        except Exception as exc:
            errors.append(exc)

    def run_reid():
        try:
            runtime.infer_reid(
                reid_batch()
            )
        except Exception as exc:
            errors.append(exc)

    detector_thread = threading.Thread(
        target=run_detector
    )
    reid_thread = threading.Thread(
        target=run_reid
    )

    detector_thread.start()
    reid_thread.start()

    detector_thread.join()
    reid_thread.join()

    assert errors == []
    assert records["maximum_active"] == 1

    runtime.close()


def test_partial_reid_configuration_failure_releases_device():
    api, records = make_fake_hailo_api(
        fail_reid_configuration=True
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic ReID configuration failure",
    ):
        HailoSharedRuntime(
            detector_hef_path="detector.hef",
            reid_hef_path="reid.hef",
            infer_timeout_ms=300,
            hailo_api=api,
        )

    assert records["entered"] == ["detector"]
    assert records["exited"] == ["detector"]
    assert records["released"] == 1


def test_reload_recreates_detector_and_preserves_reid():
    api, records = make_fake_hailo_api()

    runtime = HailoSharedRuntime(
        detector_hef_path="detector.hef",
        reid_hef_path="reid.hef",
        infer_timeout_ms=300,
        hailo_api=api,
    )

    runtime.reload_detector(
        "detector-v2.hef"
    )

    assert runtime.detector_hef_path == (
        "detector-v2.hef"
    )
    assert runtime.has_reid
    assert len(records["vdevices"]) == 2
    assert records["released"] == 1

    runtime.close()

    assert records["released"] == 2


class FakeSharedRuntime:
    """Minimal runtime used to verify detector wrapper compatibility."""

    instances = []

    def __init__(
        self,
        *,
        detector_hef_path,
        infer_timeout_ms,
        reid_hef_path=None,
    ):
        self.detector_hef_path = (
            detector_hef_path
        )
        self.infer_timeout_ms = (
            infer_timeout_ms
        )
        self.reid_hef_path = reid_hef_path
        self.detector_input_name = (
            "detector/input"
        )
        self.detector_input_shape = (
            2,
            2,
            3,
        )
        self.detector_output_names = (
            "detector/output",
        )
        self.closed = False
        self.reloads = []
        self.__class__.instances.append(self)

    def infer_detector(self, _batch):
        return {
            "detector/output": [
                [
                    np.array(
                        [
                            [
                                0.10,
                                0.20,
                                0.60,
                                0.70,
                                0.90,
                            ]
                        ],
                        dtype=np.float32,
                    )
                ]
                + [
                    np.empty(
                        (0, 5),
                        dtype=np.float32,
                    )
                    for _ in range(79)
                ]
            ]
        }

    def infer_reid(self, _batch):
        return {
            "repvgg/output": np.ones(
                (1, 512),
                dtype=np.float32,
            )
        }

    def reload_detector(self, path):
        self.reloads.append(str(path))
        self.detector_hef_path = str(path)

    def close(self):
        self.closed = True


def test_direct_engine_preserves_detector_contract_and_exposes_reid():
    FakeSharedRuntime.instances = []

    engine = HailoDirectInferenceEngine(
        hef_path="detector.hef",
        infer_timeout_ms=300,
        label_filter="person",
        reid_hef_path="reid.hef",
        shared_runtime_factory=FakeSharedRuntime,
    )

    result = engine.infer(
        np.zeros(
            (2, 2, 3),
            dtype=np.uint8,
        ),
        1,
        2,
        3,
        300,
    )

    assert result is not None
    assert len(result["detections"]) == 1

    detection = result["detections"][0]

    assert detection["class_id"] == 0
    assert detection["label"] == "person"
    assert detection["score"] == pytest.approx(
        0.90
    )
    assert detection["x"] == pytest.approx(
        0.20
    )
    assert detection["y"] == pytest.approx(
        0.10
    )
    assert detection["w"] == pytest.approx(
        0.50
    )
    assert detection["h"] == pytest.approx(
        0.50
    )

    reid_outputs = engine.infer_reid(
        np.zeros(
            (1, 256, 128, 3),
            dtype=np.uint8,
        )
    )

    assert reid_outputs[
        "repvgg/output"
    ].shape == (1, 512)

    engine.reload_hef("detector-v2.hef")

    runtime = FakeSharedRuntime.instances[0]

    assert runtime.reloads == [
        "detector-v2.hef"
    ]
    assert engine.hef_path == (
        "detector-v2.hef"
    )

    engine.close()
    engine.close()

    assert runtime.closed
