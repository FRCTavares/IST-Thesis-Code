#!/usr/bin/env python3
"""Frame rendering and export helpers for the TIM-MARS annotation UI.

This module owns the loaded UI cache and all image/video rendering functions.
FastAPI routes stay in tim_ui_backend.py; ROS bag parsing stays in
tim_ui_bag_cache.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from tim_ui_bag_cache import nearest_by_time, ref_id_at
from tim_ui_drawing import draw_dashed_model_box, draw_model_box, draw_model_corner_box


CACHE: dict[str, Any] = {}


def render_frame(idx: int, draw_detections: bool, draw_tracks: bool, draw_raw: bool, draw_tim: bool, only_ids: str):
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    images = CACHE["images"]
    idx = max(0, min(len(images) - 1, idx))
    t, img = images[idx]

    first_t = images[0][0]
    t_rel = (t - first_t) / 1e9

    frame = img.copy()
    detections = nearest_by_time(CACHE["detections"], t) or []
    tracks = nearest_by_time(CACHE["tracks"], t) or []
    raw = nearest_by_time(CACHE["raw"], t)
    tim = nearest_by_time(CACHE["tim"], t)
    ref_id = ref_id_at(t_rel, CACHE["annotations"])

    only = set()
    if only_ids.strip():
        only = {int(x.strip()) for x in only_ids.split(",") if x.strip()}

    if draw_detections:
        for det in detections:
            label = f"DET {det['score']:.2f}" if det["score"] > 0 else "DET"
            draw_model_box(frame, det["box"], label, (0, 165, 255), 1)

    if draw_tracks or only or ref_id is not None:
        for tid, box in tracks:
            if only and tid not in only:
                continue
            if not draw_tracks and not only and ref_id is not None and tid != ref_id:
                continue

            colour = (220, 220, 160)
            label = f"T{tid}"

            if ref_id is not None and tid == ref_id:
                colour = (0, 255, 255)
                label = f"REF id={tid}"

            draw_model_box(frame, box, label, colour, 1)

    if draw_raw and raw:
        draw_model_box(
            frame,
            raw["box"],
            f"RAW id={raw['id']} s={raw['score']:.2f}",
            (255, 120, 40),
            3,
        )

    if draw_tim and tim:
        draw_model_box(
            frame,
            tim["box"],
            f"TIM id={tim['id']} q={tim['quality']:.2f}",
            (80, 255, 80),
            4,
        )

    # The annotation workspace uses this renderer as a tracker-ID-only view.
    # In that mode, avoid the old debug header; the browser already shows frame/time.
    tracker_only_view = (
        draw_tracks
        and not draw_detections
        and not draw_raw
        and not draw_tim
        and not only_ids.strip()
    )

    if not tracker_only_view:
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 44), (0, 0, 0), -1)
        frame[:] = cv2.addWeighted(overlay, 0.65, frame, 0.35, 0)

        header = f"frame {idx}/{len(images)-1}    t={t_rel:.2f}s"
        if ref_id is not None:
            header += f"    REF id={ref_id}"

        cv2.putText(
            frame,
            header,
            (12, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.78,
            (245, 245, 245),
            2,
            cv2.LINE_AA,
        )

    return frame


def _clean_frame_base(idx: int):
    images = CACHE["images"]
    idx = max(0, min(len(images) - 1, idx))

    t, img = images[idx]
    first_t = images[0][0]
    t_rel = (t - first_t) / 1e9

    tracks = nearest_by_time(CACHE["tracks"], t) or []
    raw = nearest_by_time(CACHE["raw"], t)
    tim = nearest_by_time(CACHE["tim"], t)
    ref_id = ref_id_at(t_rel, CACHE["annotations"])

    return img, tracks, raw, tim, ref_id


def _draw_clean_output(frame, tracks, target, ref_id, draw_reference: bool):
    """Professional no-text viewer overlay.

    Visual rules:
      - accepted/correct selected target: clean green corner bracket;
      - wrong selected target: clean red corner bracket;
      - manual/reference target: subtle white corner bracket, only when useful.

    This avoids thick debug rectangles and dashed boxes in the interactive video.
    """
    ref_box = None
    if draw_reference and ref_id is not None:
        for tid, box in tracks:
            if int(tid) == int(ref_id):
                ref_box = box
                break

    target_is_correct = (
        target is not None
        and ref_id is not None
        and int(target.get("id", -1)) == int(ref_id)
    )

    # If the selected output is wrong or missing, show the reference as a quiet
    # white bracket. If the output is already correct, avoid double-drawing over
    # the same person; the green target bracket is enough.
    if ref_box is not None and not target_is_correct:
        draw_model_corner_box(
            frame,
            ref_box,
            (245, 245, 245),
            thickness=2,
            corner_ratio=0.32,
            shadow=True,
        )

    if target:
        if target_is_correct:
            colour = (60, 220, 90)      # correct: softer green
            thickness = 2
        else:
            colour = (40, 40, 235)      # wrong: red
            thickness = 3

        draw_model_corner_box(
            frame,
            target["box"],
            colour,
            thickness=thickness,
            corner_ratio=0.30,
            shadow=True,
        )

    return frame


def render_frame_clean(idx: int, draw_raw: bool, draw_tim: bool, draw_reference: bool):
    """Single-panel clean renderer."""
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    target = raw if draw_raw else tim if draw_tim else None
    return _draw_clean_output(frame, tracks, target, ref_id, draw_reference)


def render_frame_clean_comparison(idx: int, draw_reference: bool):
    """Side-by-side paper renderer.

    Left panel: RAW selected target.
    Right panel: TIM-MARS selected target.
    No text is drawn in the video.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)

    left = img.copy()
    right = img.copy()

    left = _draw_clean_output(left, tracks, raw, ref_id, draw_reference)
    right = _draw_clean_output(right, tracks, tim, ref_id, draw_reference)

    separator = np.zeros((left.shape[0], 8, 3), dtype=left.dtype)
    return np.hstack([left, separator, right])


def render_frame_paper_overlay(idx: int, draw_reference: bool):
    """Single-panel paper renderer.

    Dashed white: annotated/reference target.
    Red: RAW selected target.
    Blue: TIM-MARS selected target.
    No text is drawn in the video.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    if draw_reference and ref_id is not None:
        for tid, box in tracks:
            if int(tid) == int(ref_id):
                draw_dashed_model_box(frame, box, (245, 245, 245), thickness=3)
                break

    if raw:
        draw_model_box(frame, raw["box"], "", (0, 0, 230), 4)

    if tim:
        draw_model_box(frame, tim["box"], "", (230, 80, 0), 4)

    return frame


def _paper_time_label(idx: int) -> str:
    images = CACHE.get("images", [])
    if not images:
        return f"frame {idx}"
    idx = max(0, min(len(images) - 1, int(idx)))
    t0 = images[0][0]
    t = images[idx][0]
    t_rel = float(t - t0) / 1e9
    return f"frame {idx} | t={t_rel:.2f}s"


def _reference_box_from_tracks(tracks, ref_id):
    if ref_id is None:
        return None
    for tid, box in tracks:
        if int(tid) == int(ref_id):
            return box
    return None


def _draw_paper_status_label(frame, text: str) -> None:
    h, w = frame.shape[:2]
    pad = max(8, int(round(w * 0.012)))
    font_scale = max(0.55, min(1.0, w / 900.0))
    thickness = max(1, int(round(w / 450.0)))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    x1, y1 = pad, pad
    x2 = min(w - 1, x1 + tw + 2 * pad)
    y2 = min(h - 1, y1 + th + 2 * pad)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (15, 15, 15), -1)
    cv2.putText(
        frame,
        text,
        (x1 + pad, y2 - pad),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (245, 245, 245),
        thickness,
        cv2.LINE_AA,
    )


def _draw_paper_panel_frame(
    idx: int,
    mode: str,
    draw_reference: bool = True,
    label_mode: str = "time",
):
    """Draw one paper panel with no text.

    RAW row:
      - blue box for RAW selected-target output when not wrong;
      - red box when RAW output is wrong.

    TIM row:
      - green box for correct TIM-MARS output;
      - red box only if TIM-MARS publishes a wrong target;
      - no box when TIM-MARS suppresses output.

    The dashed white manual/reference box is drawn last, but thinner when it
    overlaps the output box so the output colour remains visible.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    ref_box = _reference_box_from_tracks(tracks, ref_id)
    target = raw if mode == "raw" else tim

    target_is_correct = (
        target is not None
        and ref_id is not None
        and int(target.get("id", -1)) == int(ref_id)
    )

    if target:
        if mode == "raw":
            # RAW is always drawn. Red means wrong; blue means normal/correct raw output.
            colour = (0, 0, 230) if not target_is_correct else (230, 110, 0)
            draw_model_box(frame, target["box"], "", colour, 4)
        else:
            # TIM is drawn only when it publishes. Green means correct; red means wrong.
            colour = (0, 210, 0) if target_is_correct else (0, 0, 230)
            draw_model_box(frame, target["box"], "", colour, 4)

    if draw_reference and ref_box is not None:
        # If reference and output overlap, use a thinner dashed reference so the
        # coloured output box remains visible.
        ref_thickness = 2 if target is not None else 3
        draw_dashed_model_box(frame, ref_box, (245, 245, 245), thickness=ref_thickness)

    boxes = []
    if ref_box is not None:
        boxes.append(ref_box)
    if target:
        boxes.append(target["box"])

    # For paper contact sheets, crop only around the relevant selected-target
    # evidence: manual reference plus RAW/TIM output. Including every tracker
    # box makes dense-group scenes too wide and prevents useful cropping.
    return frame, boxes, ""


def _draw_paper_overlay_frame(idx: int, draw_reference: bool = True, label_mode: str = "time"):
    """Backward-compatible single-panel overlay renderer."""
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    ref_box = _reference_box_from_tracks(tracks, ref_id)

    if raw:
        draw_model_box(frame, raw["box"], "", (0, 0, 230), 4)

    if tim:
        draw_model_box(frame, tim["box"], "", (0, 210, 0), 4)

    if draw_reference and ref_box is not None:
        draw_dashed_model_box(frame, ref_box, (245, 245, 245), thickness=3)

    label = _paper_time_label(idx) if label_mode == "time" else f"frame {idx}"
    _draw_paper_status_label(frame, label)

    boxes = []
    if ref_box is not None:
        boxes.append(ref_box)
    if raw:
        boxes.append(raw["box"])
    if tim:
        boxes.append(tim["box"])
    for _, box in tracks:
        boxes.append(box)

    return frame, boxes


def _crop_to_model_boxes(frame, boxes, pad_px: int):
    if not boxes:
        return frame

    h, w = frame.shape[:2]
    xs = []
    ys = []

    for box in boxes:
        try:
            x1, y1, x2, y2 = model_box_to_image_box(box, frame.shape)
        except Exception:
            continue
        xs.extend([x1, x2])
        ys.extend([y1, y2])

    if not xs or not ys:
        return frame

    x1 = max(0, int(min(xs) - pad_px))
    y1 = max(0, int(min(ys) - pad_px))
    x2 = min(w, int(max(xs) + pad_px))
    y2 = min(h, int(max(ys) + pad_px))

    if x2 <= x1 or y2 <= y1:
        return frame

    return frame[y1:y2, x1:x2].copy()


def _shared_crop_rect(all_boxes, image_shape, pad_px: int, aspect: float = 1.55):
    """Compute one shared balanced crop rectangle.

    The crop is shared by all panels. It is centred on the union of the
    reference/output boxes and expanded to a fixed aspect ratio. This avoids
    per-panel crop changes while preventing dense scenes from keeping the
    whole field.
    """
    h, w = image_shape[:2]
    xs = []
    ys = []

    for box in all_boxes:
        try:
            x1, y1, x2, y2 = model_box_to_image_box(box, image_shape)
        except Exception:
            continue
        xs.extend([x1, x2])
        ys.extend([y1, y2])

    if not xs or not ys:
        return (0, 0, w, h)

    raw_x1 = max(0, int(min(xs)))
    raw_y1 = max(0, int(min(ys)))
    raw_x2 = min(w, int(max(xs)))
    raw_y2 = min(h, int(max(ys)))

    if raw_x2 <= raw_x1 or raw_y2 <= raw_y1:
        return (0, 0, w, h)

    cx = (raw_x1 + raw_x2) / 2.0
    cy = (raw_y1 + raw_y2) / 2.0

    box_w = raw_x2 - raw_x1
    box_h = raw_y2 - raw_y1

    # Balanced context: expand both dimensions from the object union, instead
    # of letting one axis dominate. This is the "crop horizontally and
    # vertically together" behaviour needed for paper figures.
    target_w = max(box_w + 2 * pad_px, int(round((box_h + 2 * pad_px) * aspect)))
    target_h = max(box_h + 2 * pad_px, int(round(target_w / aspect)))

    # Do not let the crop become the full court unless unavoidable.
    target_w = min(target_w, int(round(w * 0.72)))
    target_h = min(target_h, int(round(h * 0.72)))

    # Re-enforce aspect after clipping requested dimensions.
    if target_w / max(1, target_h) > aspect:
        target_w = int(round(target_h * aspect))
    else:
        target_h = int(round(target_w / aspect))

    x1 = int(round(cx - target_w / 2))
    x2 = int(round(cx + target_w / 2))
    y1 = int(round(cy - target_h / 2))
    y2 = int(round(cy + target_h / 2))

    # Shift inside image while preserving crop size when possible.
    if x1 < 0:
        x2 -= x1
        x1 = 0
    if y1 < 0:
        y2 -= y1
        y1 = 0
    if x2 > w:
        shift = x2 - w
        x1 -= shift
        x2 = w
    if y2 > h:
        shift = y2 - h
        y1 -= shift
        y2 = h

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return (0, 0, w, h)

    return (x1, y1, x2, y2)


def _apply_crop_rect(frame, rect):
    x1, y1, x2, y2 = rect
    return frame[y1:y2, x1:x2].copy()




def _trim_black_letterbox(frame, threshold: int = 12):
    """Remove black letterbox bands from top/bottom after crop."""
    if frame.size == 0:
        return frame

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    row_mean = gray.mean(axis=1)
    valid = np.where(row_mean > threshold)[0]

    if len(valid) == 0:
        return frame

    y1 = int(valid[0])
    y2 = int(valid[-1]) + 1

    if y2 <= y1:
        return frame

    return frame[y1:y2, :].copy()



def _add_paper_caption_band(panel, text: str):
    """No-op for final paper figures: keep panels image-only."""
    return panel



def _fit_panel_to_size(frame, panel_width: int, panel_height: int):
    """Fit image into a fixed panel without distortion.

    This prevents the paper contact sheet from becoming vertically stretched.
    """
    h, w = frame.shape[:2]
    panel_width = max(120, int(panel_width))
    panel_height = max(80, int(panel_height))

    if w <= 0 or h <= 0:
        return np.full((panel_height, panel_width, 3), 255, dtype=np.uint8)

    scale = min(panel_width / float(w), panel_height / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    out = np.full((panel_height, panel_width, 3), 255, dtype=np.uint8)
    x0 = (panel_width - new_w) // 2
    y0 = (panel_height - new_h) // 2
    out[y0:y0 + new_h, x0:x0 + new_w] = resized
    return out



def _resize_panel(frame, panel_width: int):
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return frame
    panel_width = max(120, int(panel_width))
    scale = panel_width / float(w)
    panel_height = max(1, int(round(h * scale)))
    return cv2.resize(frame, (panel_width, panel_height), interpolation=cv2.INTER_AREA)


def _pad_panel_to_size(panel, width: int, height: int):
    h, w = panel.shape[:2]
    out = np.full((height, width, 3), 255, dtype=np.uint8)
    out[:h, :w] = panel[:min(h, height), :min(w, width)]
    return out


def render_paper_contact_sheet(
    frame_indices,
    out_path: str,
    cols: int = 4,
    crop: bool = True,
    crop_pad: int = 80,
    panel_width: int = 520,
    draw_reference: bool = True,
    label_mode: str = "time",
):
    """Render a paper contact sheet as two rows.

    Top row: RAW selected-target output.
    Bottom row: TIM-MARS selected-target output.
    Columns correspond to the same frame indices, so each column is a direct
    RAW-vs-TIM comparison at one moment.

    A single shared crop rectangle is computed across all selected frames so
    every panel has identical dimensions and spatial context.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    images = CACHE.get("images", [])
    if not images:
        raise RuntimeError("No images loaded.")

    clean_indices = []
    for item in frame_indices:
        try:
            idx = int(str(item).strip())
        except Exception:
            continue
        clean_indices.append(max(0, min(len(images) - 1, idx)))

    if not clean_indices:
        raise RuntimeError("No valid frame indices were provided.")

    cols = max(1, int(cols))
    if cols < len(clean_indices):
        cols = len(clean_indices)

    # First render all panels and collect all boxes for one shared crop.
    rendered = {
        "raw": [],
        "tim": [],
    }
    all_boxes = []

    for mode in ("raw", "tim"):
        for idx in clean_indices:
            frame, boxes, label = _draw_paper_panel_frame(
                idx,
                mode=mode,
                draw_reference=draw_reference,
                label_mode=label_mode,
            )
            rendered[mode].append((frame, boxes, label))
            all_boxes.extend(boxes)

    shared_rect = None
    if crop:
        # Use the first rendered frame shape. All frames are from the same image stream.
        first_frame = rendered["raw"][0][0]
        shared_rect = _shared_crop_rect(all_boxes, first_frame.shape, int(crop_pad))

    rows = []
    for mode in ("raw", "tim"):
        panels = []
        for frame, _boxes, label in rendered[mode]:
            if crop and shared_rect is not None:
                frame = _apply_crop_rect(frame, shared_rect)
            frame = _trim_black_letterbox(frame)
            panel = _resize_panel(frame, int(panel_width))
            panel = _add_paper_caption_band(panel, label)
            panels.append(panel)

        # Enforce identical cell size inside the row.
        cell_w = max(p.shape[1] for p in panels)
        cell_h = max(p.shape[0] for p in panels)
        padded = [_pad_panel_to_size(p, cell_w, cell_h) for p in panels]

        gap = 10
        sep = np.full((cell_h, gap, 3), 255, dtype=np.uint8)
        pieces = []
        for c, panel in enumerate(padded):
            if c > 0:
                pieces.append(sep)
            pieces.append(panel)
        rows.append(np.hstack(pieces))

    # Enforce both rows to the same width.
    max_row_w = max(row.shape[1] for row in rows)
    fixed_rows = []
    for row in rows:
        if row.shape[1] < max_row_w:
            pad = np.full((row.shape[0], max_row_w - row.shape[1], 3), 255, dtype=np.uint8)
            row = np.hstack([row, pad])
        fixed_rows.append(row)

    gap = 14
    vsep = np.full((gap, max_row_w, 3), 255, dtype=np.uint8)
    sheet = np.vstack([fixed_rows[0], vsep, fixed_rows[1]])

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ok = cv2.imwrite(str(out), sheet)
    if not ok:
        raise RuntimeError(f"Failed to write contact sheet: {out}")

    return str(out)




def export_mp4(
    out_path: str,
    draw_detections: bool,
    draw_tracks: bool,
    draw_raw: bool,
    draw_tim: bool,
    only_ids: str,
    fps: float,
    clean: bool,
    draw_reference: bool,
    comparison: bool,
    paper_overlay: bool,
) -> str:
    """Export the currently loaded bag view as an MP4 video."""
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    images = CACHE.get("images", [])
    if not images:
        raise RuntimeError("No frames loaded.")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fps = float(fps)
    if fps <= 0:
        raise RuntimeError("FPS must be positive.")

    first_shape = None
    writer = None

    try:
        for idx in range(len(images)):
            if clean and paper_overlay:
                frame = render_frame_paper_overlay(idx=idx, draw_reference=draw_reference)
            elif clean and comparison:
                frame = render_frame_clean_comparison(idx=idx, draw_reference=draw_reference)
            elif clean:
                frame = render_frame_clean(
                    idx=idx,
                    draw_raw=draw_raw,
                    draw_tim=draw_tim,
                    draw_reference=draw_reference,
                )
            else:
                frame = render_frame(
                    idx=idx,
                    draw_detections=draw_detections,
                    draw_tracks=draw_tracks,
                    draw_raw=draw_raw,
                    draw_tim=draw_tim,
                    only_ids=only_ids,
                )

            if first_shape is None:
                first_shape = frame.shape[:2]
                h, w = first_shape
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(out), fourcc, fps, (w, h))
                if not writer.isOpened():
                    raise RuntimeError(f"Failed to open video writer: {out}")

            if frame.shape[:2] != first_shape:
                h, w = first_shape
                frame = cv2.resize(frame, (w, h))

            writer.write(frame)

    finally:
        if writer is not None:
            writer.release()

    if not out.exists() or out.stat().st_size <= 0:
        raise RuntimeError(f"Failed to write MP4: {out}")

    return str(out)
