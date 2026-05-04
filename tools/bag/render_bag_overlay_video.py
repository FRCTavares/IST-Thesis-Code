#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import re

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


BBox = Tuple[int, int, int, int]


@dataclass
class DetectionBox:
    bbox: BBox
    score: Optional[float] = None


@dataclass
class TrackBox:
    bbox: BBox
    track_id: int = -1
    score: Optional[float] = None


@dataclass
class TargetState:
    target_id: int = 0
    visible: bool = False
    bbox: Optional[BBox] = None
    quality: Optional[float] = None


def safe_get(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default

def is_number(x: Any) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool)

def clamp_box(box: Tuple[float, float, float, float], width: int, height: int) -> BBox:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, int(round(x1))))
    y1 = max(0, min(height - 1, int(round(y1))))
    x2 = max(0, min(width - 1, int(round(x2))))
    y2 = max(0, min(height - 1, int(round(y2))))

    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1

    return x1, y1, x2, y2

def maybe_norm(value: float, size: int) -> float:
    if -0.05 <= value <= 1.5:
        return value * size
    return value

def box_center_size(cx: float, cy: float, w: float, h: float, img_w: int, img_h: int) -> BBox:
    cx = maybe_norm(cx, img_w)
    cy = maybe_norm(cy, img_h)
    w = maybe_norm(w, img_w)
    h = maybe_norm(h, img_h)
    return clamp_box((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), img_w, img_h)

def box_xywh(x: float, y: float, w: float, h: float, img_w: int, img_h: int) -> BBox:
    x = maybe_norm(x, img_w)
    y = maybe_norm(y, img_h)
    w = maybe_norm(w, img_w)
    h = maybe_norm(h, img_h)
    return clamp_box((x, y, x + w, y + h), img_w, img_h)

def box_x1y1x2y2(x1: float, y1: float, x2: float, y2: float, img_w: int, img_h: int) -> BBox:
    x1 = maybe_norm(x1, img_w)
    y1 = maybe_norm(y1, img_h)
    x2 = maybe_norm(x2, img_w)
    y2 = maybe_norm(y2, img_h)
    return clamp_box((x1, y1, x2, y2), img_w, img_h)

def read_flight_metadata(bag_path: Path) -> Dict[str, str]:
    metadata_path = bag_path / "flight_metadata.txt"
    metadata: Dict[str, str] = {}

    if not metadata_path.exists():
        return metadata

    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metadata[key.strip()] = value.strip()

    return metadata

def parse_size(value: str, default_w: int, default_h: int) -> Tuple[int, int]:
    match = re.search(r"(\d+)\s*x\s*(\d+)", value)
    if not match:
        return default_w, default_h
    return int(match.group(1)), int(match.group(2))

def parse_output_size(value: str) -> Tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", value.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, e.g. 1280x720")

    width = int(match.group(1))
    height = int(match.group(2))

    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError("output size must be positive")

    return width, height

def map_overlay_box_to_image(
    box: BBox,
    src_w: int,
    src_h: int,
    img_w: int,
    img_h: int,
    resize_mode: str,
) -> BBox:
    x1, y1, x2, y2 = box

    if src_w == img_w and src_h == img_h:
        return clamp_box((x1, y1, x2, y2), img_w, img_h)

    if resize_mode == "letterbox":
        scale = min(src_w / img_w, src_h / img_h)
        content_w = img_w * scale
        content_h = img_h * scale
        pad_x = (src_w - content_w) / 2.0
        pad_y = (src_h - content_h) / 2.0

        mapped = (
            (x1 - pad_x) / scale,
            (y1 - pad_y) / scale,
            (x2 - pad_x) / scale,
            (y2 - pad_y) / scale,
        )
        return clamp_box(mapped, img_w, img_h)

    # Plain resize fallback.
    sx = img_w / src_w
    sy = img_h / src_h
    return clamp_box((x1 * sx, y1 * sy, x2 * sx, y2 * sy), img_w, img_h)

def bbox_from_any(obj: Any, img_w: int, img_h: int) -> Optional[BBox]:
    if obj is None:
        return None

    # vision_msgs/Detection2D.bbox, BoundingBox2D
    if hasattr(obj, "bbox"):
        out = bbox_from_any(obj.bbox, img_w, img_h)
        if out is not None:
            return out

    if hasattr(obj, "center") and hasattr(obj, "size_x") and hasattr(obj, "size_y"):
        center = obj.center
        pos = safe_get(center, ["position"], center)
        cx = safe_get(pos, ["x"])
        cy = safe_get(pos, ["y"])
        sx = safe_get(obj, ["size_x"])
        sy = safe_get(obj, ["size_y"])
        if all(is_number(v) for v in (cx, cy, sx, sy)):
            return box_center_size(float(cx), float(cy), float(sx), float(sy), img_w, img_h)

    # direct x1 y1 x2 y2
    x1 = safe_get(obj, ["x1", "xmin", "left"])
    y1 = safe_get(obj, ["y1", "ymin", "top"])
    x2 = safe_get(obj, ["x2", "xmax", "right"])
    y2 = safe_get(obj, ["y2", "ymax", "bottom"])
    if all(is_number(v) for v in (x1, y1, x2, y2)):
        return box_x1y1x2y2(float(x1), float(y1), float(x2), float(y2), img_w, img_h)

    # track/target common normalised centre fields
    cx = safe_get(obj, ["cx", "center_x", "bbox_cx", "target_bbox_cx"])
    cy = safe_get(obj, ["cy", "center_y", "bbox_cy", "target_bbox_cy"])
    bw = safe_get(obj, ["w", "width", "bbox_w", "target_bbox_w"])
    bh = safe_get(obj, ["h", "height", "bbox_h", "target_bbox_h"])
    if all(is_number(v) for v in (cx, cy, bw, bh)):
        return box_center_size(float(cx), float(cy), float(bw), float(bh), img_w, img_h)

    # x y w h
    x = safe_get(obj, ["x", "bbox_x"])
    y = safe_get(obj, ["y", "bbox_y"])
    w = safe_get(obj, ["w", "width", "bbox_w"])
    h = safe_get(obj, ["h", "height", "bbox_h"])
    if all(is_number(v) for v in (x, y, w, h)):
        return box_xywh(float(x), float(y), float(w), float(h), img_w, img_h)

    for nested in ["box", "bounding_box", "roi"]:
        if hasattr(obj, nested):
            out = bbox_from_any(getattr(obj, nested), img_w, img_h)
            if out is not None:
                return out

    return None

def image_msg_to_bgr(msg: Any) -> np.ndarray:
    encoding = str(msg.encoding).lower()
    h = int(msg.height)
    w = int(msg.width)
    step = int(msg.step)
    data = np.frombuffer(bytes(msg.data), dtype=np.uint8)

    if encoding in ("bgr8", "rgb8"):
        row_bytes = w * 3
        img = data.reshape((h, step))[:, :row_bytes].reshape((h, w, 3))
        if encoding == "rgb8":
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img.copy()

    if encoding in ("bgra8", "rgba8"):
        row_bytes = w * 4
        img = data.reshape((h, step))[:, :row_bytes].reshape((h, w, 4))
        if encoding == "rgba8":
            return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    if encoding in ("mono8", "8uc1"):
        img = data.reshape((h, step))[:, :w].reshape((h, w))
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    raise RuntimeError(f"Unsupported image encoding: {msg.encoding}")

def detection_score(det: Any) -> Optional[float]:
    results = safe_get(det, ["results"], [])
    if results:
        result = results[0]
        hyp = safe_get(result, ["hypothesis"], result)
        score = safe_get(hyp, ["score"])
        if is_number(score):
            return float(score)

    score = safe_get(det, ["score", "confidence"], None)
    return float(score) if is_number(score) else None

def extract_detections(msg: Any, img_w: int, img_h: int) -> List[DetectionBox]:
    out: List[DetectionBox] = []

    for det in safe_get(msg, ["detections"], []):
        box = bbox_from_any(det, img_w, img_h)
        if box is not None:
            out.append(DetectionBox(bbox=box, score=detection_score(det)))

    return out

def extract_tracks(msg: Any, img_w: int, img_h: int) -> List[TrackBox]:
    out: List[TrackBox] = []

    for trk in safe_get(msg, ["tracks"], []):
        box = bbox_from_any(trk, img_w, img_h)
        if box is None:
            continue

        tid = safe_get(trk, ["track_id", "id", "trackid"], -1)
        score = safe_get(trk, ["score", "confidence", "quality"], None)

        out.append(
            TrackBox(
                bbox=box,
                track_id=int(tid) if is_number(tid) else -1,
                score=float(score) if is_number(score) else None,
            )
        )

    return out

def extract_target(msg: Any, img_w: int, img_h: int) -> TargetState:
    target_id = safe_get(msg, ["target_id", "track_id", "id", "target_track_id"], 0)
    quality = safe_get(msg, ["quality", "score", "confidence"], None)

    visible = safe_get(msg, ["visible", "target_visible", "is_visible"], None)
    lost = safe_get(msg, ["lost", "target_lost"], None)

    if isinstance(visible, bool):
        is_visible = visible
    elif isinstance(lost, bool):
        is_visible = not lost
    else:
        is_visible = is_number(target_id) and int(target_id) > 0

    return TargetState(
        target_id=int(target_id) if is_number(target_id) else 0,
        visible=bool(is_visible),
        bbox=bbox_from_any(msg, img_w, img_h),
        quality=float(quality) if is_number(quality) else None,
    )

def extract_timing(msg: Any) -> Dict[str, float]:
    out: Dict[str, float] = {}

    if hasattr(msg, "get_fields_and_field_types"):
        for name in msg.get_fields_and_field_types().keys():
            value = getattr(msg, name)
            if is_number(value):
                out[name] = float(value)

    metrics = safe_get(msg, ["metrics"], None)
    if metrics:
        for metric in metrics:
            key = safe_get(metric, ["key", "name"], None)
            value = safe_get(metric, ["value", "data"], None)
            if key is not None and is_number(value):
                out[str(key)] = float(value)

    return out

def track_colour(track_id: int) -> Tuple[int, int, int]:
    if track_id < 0:
        return (220, 220, 220)

    rng = np.random.default_rng(track_id * 2654435761 % (2**32))
    b, g, r = rng.integers(70, 255, size=3)
    return int(b), int(g), int(r)

def draw_label(img: np.ndarray, text: str, x: int, y: int, colour: Tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.45
    thickness = 1
    (tw, th), base = cv2.getTextSize(text, font, scale, thickness)

    y0 = max(0, y - th - base - 5)
    cv2.rectangle(img, (x, y0), (x + tw + 6, y0 + th + base + 5), colour, -1)
    cv2.putText(img, text, (x + 3, y0 + th + 1), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)

def draw_box(img: np.ndarray, box: BBox, colour: Tuple[int, int, int], thickness: int, label: Optional[str]) -> None:
    x1, y1, x2, y2 = box
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, thickness)
    if label:
        draw_label(img, label, x1, y1, colour)

def draw_hud(
    img: np.ndarray,
    frame_idx: int,
    elapsed_s: float,
    camera_fps: Optional[float],
    det_timing: Dict[str, float],
    tracker_timing: Dict[str, float],
    target_timing: Dict[str, float],
    target: TargetState,
) -> None:
    rows = [
        f"frame={frame_idx}  t={elapsed_s:.2f}s",
        f"camera_fps={camera_fps:.1f}" if camera_fps is not None else "camera_fps=NA",
        f"target_id={target.target_id}  visible={int(target.visible)}",
    ]

    if "e2e_det_ms" in det_timing:
        rows.append(f"e2e_det={det_timing['e2e_det_ms']:.1f} ms")
    if "pub_dt_ms" in det_timing:
        rows.append(f"pub_dt={det_timing['pub_dt_ms']:.1f} ms")
    if "track_ms" in tracker_timing:
        rows.append(f"track={tracker_timing['track_ms']:.2f} ms")
    if "e2e_target_ms" in target_timing:
        rows.append(f"e2e_target={target_timing['e2e_target_ms']:.1f} ms")

    line_h = 19
    pad = 8
    box_w = 320
    box_h = pad * 2 + line_h * len(rows)

    overlay = img.copy()
    cv2.rectangle(overlay, (8, 8), (8 + box_w, 8 + box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)

    y = 8 + pad + 13
    for row in rows:
        cv2.putText(img, row, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        y += line_h

def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    storage_options = rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap")
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )

    reader = rosbag2_py.SequentialReader()
    reader.open(storage_options, converter_options)
    return reader

def topic_type_map(reader: rosbag2_py.SequentialReader) -> Dict[str, str]:
    return {t.name: t.type for t in reader.get_all_topics_and_types()}

def infer_fps(bag_path: Path, image_topic: str, fallback: float) -> float:
    reader = open_reader(bag_path)
    times: List[int] = []

    while reader.has_next():
        topic, _data, t = reader.read_next()
        if topic == image_topic:
            times.append(t)

    if len(times) < 3:
        return fallback

    dts = [(b - a) / 1e9 for a, b in zip(times[:-1], times[1:])]
    dts = [dt for dt in dts if 0.001 <= dt <= 1.0]

    if not dts:
        return fallback

    return max(1.0, min(60.0, 1.0 / statistics.median(dts)))

def main() -> None:
    parser = argparse.ArgumentParser(description="Render a thesis video bag with detection/track/target overlays.")
    parser.add_argument("bag", help="Path to bag folder")
    parser.add_argument("-o", "--output", default="", help="Output MP4 path")
    parser.add_argument("--fps", type=float, default=0.0, help="Output FPS. Default: infer from /camera/dashboard")
    parser.add_argument("--default-fps", type=float, default=15.0)
    parser.add_argument("--output-size", type=parse_output_size, default=None, help="Output video size, e.g. 1280x720")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--preview", action="store_true")

    parser.add_argument("--image-topic", default="/camera/dashboard")
    parser.add_argument("--detections-topic", default="/detections")
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--target-topic", default="/target")
    parser.add_argument("--camera-fps-topic", default="/camera/fps")
    parser.add_argument("--timing-topic", default="/timing")
    parser.add_argument("--timing-tracker-topic", default="/timing_tracker")
    parser.add_argument("--timing-target-topic", default="/timing_target")

    parser.add_argument("--draw-detections", action="store_true", help="Draw raw detector boxes in addition to tracks")
    parser.add_argument("--no-tracks", action="store_true")
    parser.add_argument("--no-target", action="store_true")
    parser.add_argument("--no-hud", action="store_true")
    parser.add_argument("--det-labels", action="store_true")

    args = parser.parse_args()

    bag_path = Path(args.bag).expanduser().resolve()
    if not bag_path.exists():
        raise FileNotFoundError(f"Bag not found: {bag_path}")

    output = Path(args.output).expanduser() if args.output else Path("artifacts/reports/videos") / f"{bag_path.name}__overlay.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    fps = args.fps if args.fps > 0 else infer_fps(bag_path, args.image_topic, args.default_fps)

    metadata = read_flight_metadata(bag_path)
    overlay_src_w, overlay_src_h = parse_size(metadata.get("camera_publish", ""), 640, 640)
    overlay_resize_mode = metadata.get("camera_publish_resize_mode", "letterbox").lower()

    print(f"[info] overlay source: {overlay_src_w}x{overlay_src_h} mode={overlay_resize_mode}")

    reader = open_reader(bag_path)
    types = topic_type_map(reader)

    if args.image_topic not in types:
        raise RuntimeError(f"Missing image topic {args.image_topic}. Available topics: {sorted(types)}")

    msg_types = {topic: get_message(type_name) for topic, type_name in types.items()}

    latest_dets: List[DetectionBox] = []
    latest_tracks: List[TrackBox] = []
    latest_target = TargetState()
    latest_camera_fps: Optional[float] = None
    latest_det_timing: Dict[str, float] = {}
    latest_tracker_timing: Dict[str, float] = {}
    latest_target_timing: Dict[str, float] = {}

    img_w = 640
    img_h = 640
    writer: Optional[cv2.VideoWriter] = None
    first_image_t: Optional[int] = None
    frame_idx = 0

    print(f"[info] bag: {bag_path}")
    print(f"[info] output: {output}")
    print(f"[info] fps: {fps:.2f}")

    while reader.has_next():
        topic, data, t = reader.read_next()
        if topic not in msg_types:
            continue

        msg = deserialize_message(data, msg_types[topic])

        if topic == args.image_topic:
            img = image_msg_to_bgr(msg)
            img_h, img_w = img.shape[:2]

            if first_image_t is None:
                first_image_t = t

            if writer is None:
                if args.output_size is not None:
                    output_w, output_h = args.output_size
                else:
                    output_w, output_h = img_w, img_h

                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(output), fourcc, fps, (output_w, output_h))
                if not writer.isOpened():
                    raise RuntimeError(f"Could not open video writer for {output}")

                print(f"[info] input image: {img_w}x{img_h}")
                print(f"[info] output image: {output_w}x{output_h}")

            if args.draw_detections:
                for det in latest_dets:
                    label = None
                    if args.det_labels:
                        label = f"det {det.score:.2f}" if det.score is not None else "det"

                    draw_box(
                        img,
                        map_overlay_box_to_image(det.bbox, overlay_src_w, overlay_src_h, img_w, img_h, overlay_resize_mode),
                        (150, 150, 150),
                        1,
                        label,
                    )

            if not args.no_tracks:
                for trk in latest_tracks:
                    is_target_track = latest_target.visible and latest_target.target_id > 0 and trk.track_id == latest_target.target_id
                    colour = (0, 255, 255) if is_target_track else track_colour(trk.track_id)
                    thickness = 3 if is_target_track else 2

                    if is_target_track:
                        label = f"TARGET {trk.track_id}"
                    else:
                        label = f"ID {trk.track_id}"

                    draw_box(
                        img,
                        map_overlay_box_to_image(trk.bbox, overlay_src_w, overlay_src_h, img_w, img_h, overlay_resize_mode),
                        colour,
                        thickness,
                        label,
                    )
            if not args.no_target and latest_target.visible and latest_target.bbox is not None:
                draw_box(
                    img,
                    map_overlay_box_to_image(latest_target.bbox, overlay_src_w, overlay_src_h, img_w, img_h, overlay_resize_mode),
                    (0, 255, 255),
                    3,
                    f"TARGET {latest_target.target_id}",
                )
            if not args.no_hud:
                draw_hud(
                    img=img,
                    frame_idx=frame_idx,
                    elapsed_s=(t - first_image_t) / 1e9,
                    camera_fps=latest_camera_fps,
                    det_timing=latest_det_timing,
                    tracker_timing=latest_tracker_timing,
                    target_timing=latest_target_timing,
                    target=latest_target,
                )

            if args.output_size is not None:
                output_w, output_h = args.output_size
                img_out = cv2.resize(img, (output_w, output_h), interpolation=cv2.INTER_LINEAR)
            else:
                img_out = img

            writer.write(img_out)
            frame_idx += 1

            if args.preview:
                cv2.imshow("bag overlay", img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break

            if frame_idx % 100 == 0:
                print(f"[info] rendered {frame_idx} frames")

            continue

        if topic == args.detections_topic:
            latest_dets = extract_detections(msg, overlay_src_w, overlay_src_h)
        elif topic == args.tracks_topic:
            latest_tracks = extract_tracks(msg, overlay_src_w, overlay_src_h)
        elif topic == args.target_topic:
            latest_target = extract_target(msg, overlay_src_w, overlay_src_h)
        elif topic == args.camera_fps_topic:
            value = safe_get(msg, ["data"], None)
            if is_number(value):
                latest_camera_fps = float(value)
        elif topic == args.timing_topic:
            latest_det_timing = extract_timing(msg)
        elif topic == args.timing_tracker_topic:
            latest_tracker_timing = extract_timing(msg)
        elif topic == args.timing_target_topic:
            latest_target_timing = extract_timing(msg)

    if writer is not None:
        writer.release()

    if args.preview:
        cv2.destroyAllWindows()

    print(f"[ok] rendered frames: {frame_idx}")
    print(f"[ok] wrote: {output}")

if __name__ == "__main__":
    main()