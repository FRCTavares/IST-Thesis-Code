"""Supported detector model catalog for the dashboard bridge."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedModel:
    """Detector model option exposed by the dashboard model-switch API."""

    key: str
    hef_file: str


SUPPORTED_MODELS: tuple[SupportedModel, ...] = (
    SupportedModel("yolov5m", "yolov5m.hef"),
    SupportedModel("yolov6n", "yolov6n.hef"),
    SupportedModel("yolov8n", "yolov8n.hef"),
    SupportedModel("yolov8s", "yolov8s.hef"),
    SupportedModel("yolov8m", "yolov8m.hef"),
    SupportedModel("yolov8l", "yolov8l.hef"),
    SupportedModel("yolov8x", "yolov8x.hef"),
    SupportedModel("yolov10n", "yolov10n.hef"),
    SupportedModel("yolov10s", "yolov10s.hef"),
    SupportedModel("yolov10b", "yolov10b.hef"),
    SupportedModel("yolov10x", "yolov10x.hef"),
    SupportedModel("yolov11n", "yolov11n.hef"),
    SupportedModel("yolov11s", "yolov11s.hef"),
    SupportedModel("yolov11m", "yolov11m.hef"),
    SupportedModel("yolov11l", "yolov11l.hef"),
    SupportedModel("yolov11x", "yolov11x.hef"),
)
