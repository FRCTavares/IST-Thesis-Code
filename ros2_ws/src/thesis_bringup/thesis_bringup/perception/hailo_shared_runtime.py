"""One perception-owned HailoRT runtime shared by detector and ReID.

The live detector and selective ReID network must not create independent
VDevices for one physical Hailo-8. This runtime owns one ROUND_ROBIN VDevice,
configures the detector and optional ReID HEFs on that device, and serializes
all host inference calls behind one lock.

ROS transport, crop selection, target-memory mutation, and embedding
postprocessing deliberately remain outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any

import numpy as np


@dataclass
class _ConfiguredNetwork:
    """Entered VStream pipeline plus its host-visible tensor contract."""

    hef: Any
    network_group: Any
    infer_context: Any
    infer_pipeline: Any
    input_name: str
    input_shape: tuple[int, int, int]
    output_names: tuple[str, ...]


def _default_hailo_api():
    import hailo_platform

    return hailo_platform


class HailoSharedRuntime:
    """Own one scheduled VDevice for detector and optional ReID inference."""

    def __init__(
        self,
        *,
        detector_hef_path: str,
        infer_timeout_ms: int,
        reid_hef_path: str | None = None,
        hailo_api=None,
    ) -> None:
        detector_path = str(detector_hef_path).strip()
        reid_path = (
            None
            if reid_hef_path is None
            else str(reid_hef_path).strip()
        )

        if not detector_path:
            raise RuntimeError("detector HEF path cannot be empty")

        if reid_path == "":
            reid_path = None

        self.detector_hef_path = detector_path
        self.reid_hef_path = reid_path
        self.infer_timeout_ms = max(
            1,
            int(infer_timeout_ms),
        )

        self._api = (
            _default_hailo_api()
            if hailo_api is None
            else hailo_api
        )

        self._lock = threading.RLock()
        self._closed = False

        self._vdevice = None
        self._detector: _ConfiguredNetwork | None = None
        self._reid: _ConfiguredNetwork | None = None

        with self._lock:
            self._open_locked()

    def _configure_network_locked(
        self,
        *,
        hef_path: str,
        output_format_type,
    ) -> _ConfiguredNetwork:
        if self._vdevice is None:
            raise RuntimeError("Hailo VDevice is not open")

        hef = self._api.HEF(str(hef_path))
        configured_networks = self._vdevice.configure(hef)

        if len(configured_networks) != 1:
            raise RuntimeError(
                "shared Hailo runtime requires exactly one network "
                f"group per HEF (got={len(configured_networks)})"
            )

        network_group = configured_networks[0]
        input_infos = network_group.get_input_vstream_infos()

        if len(input_infos) != 1:
            raise RuntimeError(
                "shared Hailo runtime requires exactly one input "
                f"VStream (got={len(input_infos)})"
            )

        input_info = input_infos[0]
        input_shape = tuple(
            int(value)
            for value in tuple(input_info.shape)
        )

        if len(input_shape) != 3:
            raise RuntimeError(
                "unexpected shared Hailo input shape: "
                f"{input_shape}"
            )

        output_infos = (
            network_group.get_output_vstream_infos()
        )
        output_names = tuple(
            str(info.name)
            for info in output_infos
        )

        if not output_names:
            raise RuntimeError(
                "configured Hailo network has no output VStreams"
            )

        input_params = self._api.InputVStreamParams.make(
            network_group,
            format_type=self._api.FormatType.UINT8,
            timeout_ms=self.infer_timeout_ms,
            queue_size=1,
        )
        output_params = self._api.OutputVStreamParams.make(
            network_group,
            format_type=output_format_type,
            timeout_ms=self.infer_timeout_ms,
            queue_size=1,
        )

        infer_context = self._api.InferVStreams(
            network_group,
            input_params,
            output_params,
        )

        try:
            infer_pipeline = infer_context.__enter__()
        except Exception:
            try:
                infer_context.__exit__(
                    None,
                    None,
                    None,
                )
            except Exception:
                pass
            raise

        return _ConfiguredNetwork(
            hef=hef,
            network_group=network_group,
            infer_context=infer_context,
            infer_pipeline=infer_pipeline,
            input_name=str(input_info.name),
            input_shape=(
                input_shape[0],
                input_shape[1],
                input_shape[2],
            ),
            output_names=output_names,
        )

    @staticmethod
    def _close_network(
        binding: _ConfiguredNetwork | None,
    ) -> None:
        if binding is None:
            return

        try:
            binding.infer_context.__exit__(
                None,
                None,
                None,
            )
        except Exception:
            pass

    def _open_locked(self) -> None:
        params = self._api.VDevice.create_params()
        params.scheduling_algorithm = (
            self._api.HailoSchedulingAlgorithm.ROUND_ROBIN
        )

        self._vdevice = self._api.VDevice(params)

        try:
            self._detector = self._configure_network_locked(
                hef_path=self.detector_hef_path,
                output_format_type=self._api.FormatType.AUTO,
            )

            if self.reid_hef_path is not None:
                self._reid = self._configure_network_locked(
                    hef_path=self.reid_hef_path,
                    output_format_type=(
                        self._api.FormatType.FLOAT32
                    ),
                )
        except Exception:
            self._close_runtime_locked()
            raise

    def _close_runtime_locked(self) -> None:
        self._close_network(self._reid)
        self._close_network(self._detector)

        self._reid = None
        self._detector = None

        if self._vdevice is not None:
            try:
                self._vdevice.release()
            except Exception:
                pass

        self._vdevice = None

    def _require_open_locked(self) -> None:
        if self._closed:
            raise RuntimeError(
                "shared Hailo runtime is closed"
            )

        if self._vdevice is None or self._detector is None:
            raise RuntimeError(
                "shared Hailo runtime is not configured"
            )

    @staticmethod
    def _validated_batch(
        binding: _ConfiguredNetwork,
        batch: Any,
    ) -> np.ndarray:
        value = np.asarray(batch)

        if value.dtype != np.uint8:
            raise RuntimeError(
                "Hailo input batch must be uint8"
            )

        expected_shape = (
            1,
            binding.input_shape[0],
            binding.input_shape[1],
            binding.input_shape[2],
        )

        if value.shape != expected_shape:
            raise RuntimeError(
                "Hailo input batch shape mismatch "
                f"(got={value.shape}, expected={expected_shape})"
            )

        if value.flags.c_contiguous:
            return value

        return np.ascontiguousarray(
            value,
            dtype=np.uint8,
        )

    def _infer_locked(
        self,
        *,
        binding: _ConfiguredNetwork,
        batch: Any,
    ) -> dict[str, Any]:
        value = self._validated_batch(
            binding,
            batch,
        )
        outputs = binding.infer_pipeline.infer(
            {
                binding.input_name: value,
            }
        )

        if not isinstance(outputs, dict):
            raise RuntimeError(
                "Hailo inference must return an output mapping"
            )

        return outputs

    @property
    def detector_input_name(self) -> str:
        with self._lock:
            self._require_open_locked()
            assert self._detector is not None
            return self._detector.input_name

    @property
    def detector_input_shape(self) -> tuple[int, int, int]:
        with self._lock:
            self._require_open_locked()
            assert self._detector is not None
            return self._detector.input_shape

    @property
    def detector_output_names(self) -> tuple[str, ...]:
        with self._lock:
            self._require_open_locked()
            assert self._detector is not None
            return self._detector.output_names

    @property
    def reid_input_shape(self) -> tuple[int, int, int] | None:
        with self._lock:
            self._require_open_locked()

            if self._reid is None:
                return None

            return self._reid.input_shape

    @property
    def reid_output_names(self) -> tuple[str, ...]:
        with self._lock:
            self._require_open_locked()

            if self._reid is None:
                return ()

            return self._reid.output_names

    @property
    def has_reid(self) -> bool:
        with self._lock:
            return bool(
                not self._closed
                and self._reid is not None
            )

    def infer_detector(
        self,
        batch: Any,
    ) -> dict[str, Any]:
        """Run one detector batch while holding shared device ownership."""
        with self._lock:
            self._require_open_locked()
            assert self._detector is not None

            return self._infer_locked(
                binding=self._detector,
                batch=batch,
            )

    def infer_reid(
        self,
        batch: Any,
    ) -> dict[str, Any]:
        """Run one ReID batch or fail closed if ReID is unavailable."""
        with self._lock:
            self._require_open_locked()

            if self._reid is None:
                raise RuntimeError(
                    "shared Hailo ReID network is not configured"
                )

            return self._infer_locked(
                binding=self._reid,
                batch=batch,
            )

    def reload_detector(
        self,
        detector_hef_path: str,
    ) -> None:
        """Recreate the shared runtime with a replacement detector HEF."""
        new_path = str(detector_hef_path).strip()

        if not new_path:
            raise RuntimeError(
                "detector HEF path cannot be empty"
            )

        with self._lock:
            if self._closed:
                raise RuntimeError(
                    "cannot reload a closed shared Hailo runtime"
                )

            self._close_runtime_locked()
            self.detector_hef_path = new_path
            self._open_locked()

    def close(self) -> None:
        """Close entered VStreams and release the single owned device."""
        with self._lock:
            if self._closed:
                return

            self._closed = True
            self._close_runtime_locked()


__all__ = [
    "HailoSharedRuntime",
]
