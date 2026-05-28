#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def check_video(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"[error] missing {label} video: {path}")
    if path.suffix.lower() != ".mp4":
        raise SystemExit(f"[error] {label} is not an mp4: {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--deep", required=True, type=Path)
    ap.add_argument("--hsv", required=True, type=Path)
    ap.add_argument("--mars", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    args = ap.parse_args()

    for label, path in [
        ("raw", args.raw),
        ("deep", args.deep),
        ("hsv", args.hsv),
        ("mars", args.mars),
    ]:
        check_video(path, label)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    w = args.width
    h = args.height

    vf = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[v0];"
        f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[v1];"
        f"[2:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[v2];"
        f"[3:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[v3];"
        "[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(args.raw),
        "-i", str(args.deep),
        "-i", str(args.hsv),
        "-i", str(args.mars),
        "-filter_complex", vf,
        "-map", "[v]",
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(args.out),
    ]

    print("[info] running ffmpeg")
    subprocess.run(cmd, check=True)
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
