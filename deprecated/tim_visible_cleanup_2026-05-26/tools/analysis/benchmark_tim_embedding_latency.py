#!/usr/bin/env python3
"""
Benchmark TIM-V2E Tiny16 embedding inference latency on CPU.

Measures:
- model-only forward pass
- batch sizes 1, 2, 4, 8
- mean, p50, p95, p99
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

import torch


def load_hybrid_module():
    path = Path("tools/analysis/train_tim_embedding_hybrid.py")
    spec = importlib.util.spec_from_file_location("train_tim_embedding_hybrid", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def bench(model, batch_size: int, warmup: int, iters: int, device: torch.device) -> dict:
    x = torch.rand(batch_size, 3, 128, 64, device=device)

    model.eval()

    with torch.no_grad():
        for _ in range(warmup):
            _z, _logits = model(x)

    times_ms = []
    with torch.no_grad():
        for _ in range(iters):
            t0 = time.perf_counter()
            _z, _logits = model(x)
            t1 = time.perf_counter()
            times_ms.append((t1 - t0) * 1000.0)

    return {
        "batch_size": batch_size,
        "iters": iters,
        "mean_ms": statistics.mean(times_ms),
        "p50_ms": percentile(times_ms, 0.50),
        "p95_ms": percentile(times_ms, 0.95),
        "p99_ms": percentile(times_ms, 0.99),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
        "per_crop_mean_ms": statistics.mean(times_ms) / batch_size,
        "per_crop_p95_ms": percentile(times_ms, 0.95) / batch_size,
    }


def write_summary(path: Path, results: list[dict], args) -> None:
    lines = []
    lines.append("# TIM-V2E Tiny16 CPU Latency Benchmark")
    lines.append("")
    lines.append("## Setup")
    lines.append("")
    lines.append(f"- Checkpoint: `{args.checkpoint}`")
    lines.append(f"- Device: CPU")
    lines.append(f"- Warmup iterations: {args.warmup}")
    lines.append(f"- Timed iterations: {args.iters}")
    lines.append(f"- Input shape per crop: 3x128x64")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Batch | mean_ms | p50_ms | p95_ms | p99_ms | per_crop_mean_ms | per_crop_p95_ms |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")

    for r in results:
        lines.append(
            f"| {r['batch_size']} | "
            f"{r['mean_ms']:.3f} | "
            f"{r['p50_ms']:.3f} | "
            f"{r['p95_ms']:.3f} | "
            f"{r['p99_ms']:.3f} | "
            f"{r['per_crop_mean_ms']:.3f} | "
            f"{r['per_crop_p95_ms']:.3f} |"
        )

    lines.append("")
    lines.append("## Interpretation guide")
    lines.append("")
    lines.append("- For event-triggered TIM-V2E, batch 1 and batch 2 are the most relevant cases.")
    lines.append("- If p95 per crop is below a few milliseconds on Pi CPU, CPU inference is likely feasible.")
    lines.append("- This benchmark measures model inference only, not crop extraction or ROS message handling.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--warmup", type=int, default=50)
    p.add_argument("--iters", type=int, default=300)
    p.add_argument("--batch-sizes", default="1,2,4,8")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    module = load_hybrid_module()

    ckpt = torch.load(args.checkpoint, map_location="cpu")
    emb_dim = int(ckpt.get("emb_dim", 16))

    model = module.TinyEmbeddingNet(emb_dim=emb_dim)
    model.load_state_dict(ckpt["model_state"])
    model.to(torch.device("cpu"))

    torch.set_num_threads(1)

    batch_sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]
    results = []

    for bs in batch_sizes:
        print(f"[bench] batch={bs}")
        results.append(
            bench(
                model=model,
                batch_size=bs,
                warmup=args.warmup,
                iters=args.iters,
                device=torch.device("cpu"),
            )
        )

    json_path = args.output_dir / "latency_results.json"
    md_path = args.output_dir / "summary.md"

    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_summary(md_path, results, args)

    print(f"[ok] wrote {json_path}")
    print(f"[ok] wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
