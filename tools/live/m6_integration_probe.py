#!/usr/bin/env python3
"""Issue #55 M6 — external-frontend / dashboard-backend integration probe.

Engineering integration check only. Exercises the HTTP control API, the
telemetry WebSocket, the MJPEG video path, and the TIM-MARS target-authority
command path against an already-running replay stack. Writes JSON evidence
into the run directory and exits non-zero if any required assertion fails.

This probe never starts or stops ROS processes and never touches the
controller, MAVROS, or any flight component.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import websockets
except Exception as exc:  # pragma: no cover - environment guard
    print(f"FATAL: websockets import failed: {exc}", file=sys.stderr)
    raise SystemExit(3)


RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    status = "PASS" if ok else "FAIL"
    print(f"[probe] {status:4}  {name}  {detail}".rstrip())
    return bool(ok)


def http_request(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, bytes, dict[str, str]]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers or {})


async def collect_ws(uri: str, seconds: float, max_messages: int = 400) -> list[dict]:
    messages: list[dict] = []
    deadline = time.monotonic() + seconds
    async with websockets.connect(uri, open_timeout=10, close_timeout=5) as ws:
        while time.monotonic() < deadline and len(messages) < max_messages:
            try:
                remaining = max(0.1, deadline - time.monotonic())
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            try:
                messages.append(json.loads(raw))
            except Exception:
                pass
    return messages


def dominant_track_id(messages: list[dict]) -> int | None:
    counts: dict[int, int] = {}
    for msg in messages:
        for track in msg.get("tracks", []) or []:
            tid = int(track.get("id", 0))
            if tid > 0:
                counts[tid] = counts.get(tid, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--ws-url", required=True)
    parser.add_argument("--video-base", required=True)
    parser.add_argument("--ui-base", required=True)
    parser.add_argument("--dashboard-topic", default="/camera/dashboard")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, Any] = {}

    # 1. External UI static serve + runtime configuration.
    try:
        status, raw, _ = http_request("GET", f"{args.ui_base}/", timeout=10)
        body = raw.decode("utf-8", "replace")
        check(
            "ui_index_served",
            status == 200 and '<div id="root">' in body,
            f"status={status}",
        )
        evidence["ui_index_status"] = status
    except Exception as exc:
        check("ui_index_served", False, str(exc))

    try:
        status, raw, _ = http_request(
            "GET", f"{args.ui_base}/runtime-config.js", timeout=10
        )
        cfg_text = raw.decode("utf-8", "replace")
        evidence["runtime_config_js"] = cfg_text.strip()
        want_api = args.api_base
        want_ws = args.ws_url
        check(
            "ui_runtime_config_points_at_backend",
            status == 200
            and want_api in cfg_text
            and want_ws in cfg_text,
            f"status={status} api={want_api in cfg_text} ws={want_ws in cfg_text}",
        )
    except Exception as exc:
        check("ui_runtime_config_points_at_backend", False, str(exc))

    # 2. HTTP control API discovery.
    try:
        status, raw, _ = http_request(
            "GET", f"{args.api_base}/api/models", timeout=10
        )
        payload = json.loads(raw.decode("utf-8"))
        (out / "api_models.json").write_text(json.dumps(payload, indent=2))
        check(
            "api_models_ok",
            status == 200 and payload.get("ok") is True
            and isinstance(payload.get("models"), list)
            and len(payload["models"]) > 0,
            f"status={status} n={len(payload.get('models', []))}",
        )
    except Exception as exc:
        check("api_models_ok", False, str(exc))

    # 5/6. Telemetry WebSocket + target-authority information.
    baseline_msgs: list[dict] = []
    try:
        baseline_msgs = asyncio.run(collect_ws(args.ws_url, 6.0))
        (out / "ws_baseline.jsonl").write_text(
            "\n".join(json.dumps(m) for m in baseline_msgs)
        )
        check(
            "ws_telemetry_received",
            len(baseline_msgs) >= 3,
            f"messages={len(baseline_msgs)}",
        )
        required_keys = {
            "tracks",
            "detections",
            "target",
            "target_requested",
            "target_active",
            "target_authority_source",
            "target_authority_generation",
            "target_authority_reason",
            "target_authority_session_id",
            "target_memory",
        }
        last = baseline_msgs[-1] if baseline_msgs else {}
        missing = sorted(required_keys - set(last.keys()))
        check(
            "ws_target_authority_fields_present",
            not missing,
            f"missing={missing}",
        )
        evidence["ws_baseline_last"] = last
        evidence["ws_baseline_generation"] = last.get("target_authority_generation")
        evidence["ws_baseline_session"] = last.get("target_authority_session_id")
    except Exception as exc:
        check("ws_telemetry_received", False, str(exc))
        check("ws_target_authority_fields_present", False, str(exc))

    # 9. Fresh TIM receives tracks + image input (tracks visible through bridge).
    track_id = dominant_track_id(baseline_msgs)
    check(
        "tracks_visible_in_telemetry",
        track_id is not None,
        f"dominant_track_id={track_id}",
    )

    # 7/8. web_video_server MJPEG stream carrying the replayed dashboard image.
    stream_url = (
        f"{args.video_base}/stream?topic={args.dashboard_topic}"
        "&type=mjpeg&qos_profile=sensor_data"
    )
    mjpeg_bytes = b""
    ctype = ""
    try:
        req = urllib.request.Request(stream_url)
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = resp.headers.get("Content-Type", "")
            deadline = time.monotonic() + 12.0
            # Read until we have at least two SOI markers (one complete frame)
            # or the read window closes.
            while time.monotonic() < deadline and len(mjpeg_bytes) < 4_000_000:
                block = resp.read(32768)
                if not block:
                    break
                mjpeg_bytes += block
                if mjpeg_bytes.count(b"\xff\xd8\xff") >= 2:
                    break
        jpeg_frames = mjpeg_bytes.count(b"\xff\xd8\xff")
        (out / "mjpeg_head.bin").write_bytes(mjpeg_bytes[:1_000_000])
        evidence["mjpeg_content_type"] = ctype
        evidence["mjpeg_bytes_read"] = len(mjpeg_bytes)
        evidence["mjpeg_soi_markers"] = jpeg_frames
        check(
            "web_video_server_mjpeg_stream",
            "multipart/x-mixed-replace" in ctype and jpeg_frames >= 1,
            f"ctype={ctype!r} soi={jpeg_frames} bytes={len(mjpeg_bytes)}",
        )
    except Exception as exc:
        check("web_video_server_mjpeg_stream", False, str(exc))

    # 8. Decode one real JPEG frame out of the MJPEG stream to prove the
    # replayed /camera/dashboard image is actually being delivered.
    try:
        first = mjpeg_bytes.find(b"\xff\xd8\xff")
        nxt = mjpeg_bytes.find(b"\xff\xd8\xff", first + 3) if first >= 0 else -1
        end = mjpeg_bytes.rfind(b"\xff\xd9", first, nxt) if first >= 0 and nxt > 0 else -1
        frame = b""
        if first >= 0 and end > first:
            frame = mjpeg_bytes[first : end + 2]
        elif first >= 0:
            frame = mjpeg_bytes[first:]
        (out / "dashboard_frame.jpg").write_bytes(frame)
        decoded_ok = False
        dims = None
        try:
            import cv2  # noqa: PLC0415
            import numpy as np  # noqa: PLC0415

            arr = cv2.imdecode(
                np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if arr is not None and arr.size > 0:
                decoded_ok = True
                dims = [int(arr.shape[1]), int(arr.shape[0])]
        except Exception:
            decoded_ok = frame[:3] == b"\xff\xd8\xff"
        evidence["dashboard_frame_bytes"] = len(frame)
        evidence["dashboard_frame_dims"] = dims
        check(
            "dashboard_image_has_replayed_traffic",
            len(frame) > 1000 and decoded_ok,
            f"bytes={len(frame)} dims={dims}",
        )
    except Exception as exc:
        check("dashboard_image_has_replayed_traffic", False, str(exc))

    # 4. Runtime model/tracker reconfiguration remains protected while frozen.
    generations: list[int] = []
    if evidence.get("ws_baseline_generation") is not None:
        generations.append(int(evidence["ws_baseline_generation"]))

    try:
        status, raw, _ = http_request(
            "POST", f"{args.api_base}/api/model", {"model": "yolov8s"}, timeout=10
        )
        payload = json.loads(raw.decode("utf-8"))
        (out / "api_model_denied.json").write_text(json.dumps(payload, indent=2))
        check("api_model_switch_denied_409", status == 409, f"status={status}")
        if "target_authority_generation" in payload:
            generations.append(int(payload["target_authority_generation"]))
        evidence["api_model_denied"] = payload
    except Exception as exc:
        check("api_model_switch_denied_409", False, str(exc))

    try:
        status, raw, _ = http_request(
            "POST",
            f"{args.api_base}/api/tracker",
            {"tracker": "bytetrack"},
            timeout=10,
        )
        payload = json.loads(raw.decode("utf-8"))
        (out / "api_tracker_denied.json").write_text(json.dumps(payload, indent=2))
        check("api_tracker_switch_denied_409", status == 409, f"status={status}")
        if "target_authority_generation" in payload:
            generations.append(int(payload["target_authority_generation"]))
        evidence["api_tracker_denied"] = payload
    except Exception as exc:
        check("api_tracker_switch_denied_409", False, str(exc))

    # 10/11/12. Operator target selection reaches the fresh TIM node.
    if track_id is not None:
        try:
            status, raw, _ = http_request(
                "POST",
                f"{args.api_base}/api/target",
                {"target": int(track_id)},
                timeout=10,
            )
            payload = json.loads(raw.decode("utf-8"))
            (out / "api_target_select.json").write_text(json.dumps(payload, indent=2))
            check(
                "api_target_select_ok",
                status == 200 and payload.get("ok") is True,
                f"status={status} gen={payload.get('target_authority_generation')}",
            )
            if "target_authority_generation" in payload:
                generations.append(int(payload["target_authority_generation"]))
            evidence["api_target_select"] = payload
        except Exception as exc:
            check("api_target_select_ok", False, str(exc))

        time.sleep(2.0)
        after_select = asyncio.run(collect_ws(args.ws_url, 5.0))
        (out / "ws_after_select.jsonl").write_text(
            "\n".join(json.dumps(m) for m in after_select)
        )
        sel_last = after_select[-1] if after_select else {}
        check(
            "telemetry_reflects_target_request",
            int(sel_last.get("target_requested") or 0) == int(track_id),
            f"target_requested={sel_last.get('target_requested')} want={track_id}",
        )
        if sel_last.get("target_authority_generation") is not None:
            generations.append(int(sel_last["target_authority_generation"]))
        evidence["ws_after_select_last"] = sel_last

        # 13. Target clear.
        try:
            status, raw, _ = http_request(
                "POST",
                f"{args.api_base}/api/target",
                {"target": None},
                timeout=10,
            )
            payload = json.loads(raw.decode("utf-8"))
            (out / "api_target_clear.json").write_text(json.dumps(payload, indent=2))
            check(
                "api_target_clear_ok",
                status == 200 and payload.get("ok") is True,
                f"status={status} gen={payload.get('target_authority_generation')}",
            )
            if "target_authority_generation" in payload:
                generations.append(int(payload["target_authority_generation"]))
            evidence["api_target_clear"] = payload
        except Exception as exc:
            check("api_target_clear_ok", False, str(exc))

        time.sleep(1.5)
        after_clear = asyncio.run(collect_ws(args.ws_url, 4.0))
        (out / "ws_after_clear.jsonl").write_text(
            "\n".join(json.dumps(m) for m in after_clear)
        )
        clr_last = after_clear[-1] if after_clear else {}
        check(
            "telemetry_reflects_target_clear",
            clr_last.get("target_requested") in (None, 0),
            f"target_requested={clr_last.get('target_requested')}",
        )
        if clr_last.get("target_authority_generation") is not None:
            generations.append(int(clr_last["target_authority_generation"]))

    # 12. Authority generation advances monotonically across the session.
    evidence["authority_generations_observed"] = generations
    monotonic = all(b >= a for a, b in zip(generations, generations[1:]))
    strictly_grew = len(generations) >= 2 and generations[-1] > generations[0]
    check(
        "target_authority_generation_monotonic",
        bool(generations) and monotonic and strictly_grew,
        f"generations={generations}",
    )

    (out / "probe_evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
    summary = {
        "checks": [
            {"name": n, "passed": ok, "detail": d} for n, ok, d in RESULTS
        ],
        "passed": sum(1 for _, ok, _ in RESULTS if ok),
        "failed": sum(1 for _, ok, _ in RESULTS if not ok),
    }
    (out / "probe_summary.json").write_text(json.dumps(summary, indent=2))

    failed = summary["failed"]
    print(f"[probe] {summary['passed']} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
