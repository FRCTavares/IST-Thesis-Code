#!/usr/bin/env python3
"""
Train TIM-V2E Tiny16 embedding with triplet metric learning.

Prototype only:
- anchor: selected-target crop
- positive: selected-target crop from another frame/event
- negative: distractor crop, preferably same event if available
- memory for evaluation: train-split correct crops
- eval: test-split correct/distractor crops
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader


@dataclass
class Sample:
    path: Path
    role: str
    identity: str
    event: str
    split: str
    dataset_root: str
    t: float
    frame_id: int
    track_id: int


def load_samples(roots: list[Path]) -> list[Sample]:
    samples: list[Sample] = []

    for root in roots:
        csv_path = root / "samples.csv"
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)

        with csv_path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                role = r["role"]
                if role not in {"correct", "distractor"}:
                    continue

                samples.append(
                    Sample(
                        path=root / r["crop_path"],
                        role=role,
                        identity=r["identity_label"],
                        event=r["event_type"],
                        split=r.get("split", "unspecified"),
                        dataset_root=str(root),
                        t=float(r.get("t", 0.0) or 0.0),
                        frame_id=int(float(r.get("frame_id", 0) or 0)),
                        track_id=int(float(r.get("track_id", 0) or 0)),
                    )
                )

    return samples


def read_crop(path: Path, augment: bool) -> torch.Tensor:
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"Could not read crop: {path}")

    img = cv2.resize(img, (64, 128), interpolation=cv2.INTER_AREA)

    if augment:
        if random.random() < 0.5:
            img = cv2.flip(img, 1)

        if random.random() < 0.8:
            alpha = random.uniform(0.85, 1.15)
            beta = random.uniform(-12, 12)
            img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

        if random.random() < 0.2:
            img = cv2.GaussianBlur(img, (3, 3), 0)

    img = img[:, :, ::-1].copy()
    return torch.from_numpy(img).float().permute(2, 0, 1) / 255.0


class TripletCropDataset(Dataset):
    def __init__(self, samples: list[Sample], augment: bool = True):
        self.samples = samples
        self.augment = augment

        self.correct = [s for s in samples if s.role == "correct"]
        self.distractor = [s for s in samples if s.role == "distractor"]

        self.correct_by_event: Dict[str, list[Sample]] = defaultdict(list)
        self.distractor_by_event: Dict[str, list[Sample]] = defaultdict(list)

        for s in self.correct:
            self.correct_by_event[s.event].append(s)
        for s in self.distractor:
            self.distractor_by_event[s.event].append(s)

        if len(self.correct) < 2:
            raise RuntimeError("Need at least two correct samples for triplets.")
        if not self.distractor:
            raise RuntimeError("Need distractor samples for triplets.")

    def __len__(self) -> int:
        return max(1, len(self.correct))

    def __getitem__(self, idx: int):
        anchor = self.correct[idx % len(self.correct)]

        pos_pool = [s for s in self.correct if s.path != anchor.path]
        if not pos_pool:
            pos_pool = self.correct
        positive = random.choice(pos_pool)

        neg_pool = self.distractor_by_event.get(anchor.event) or self.distractor
        negative = random.choice(neg_pool)

        xa = read_crop(anchor.path, self.augment)
        xp = read_crop(positive.path, self.augment)
        xn = read_crop(negative.path, self.augment)

        return xa, xp, xn


class EvalCropDataset(Dataset):
    def __init__(self, samples: list[Sample]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        x = read_crop(s.path, augment=False)
        y = 1 if s.role == "correct" else 0
        return x, y, s.event, str(s.path)


class TinyEmbeddingNet(nn.Module):
    def __init__(self, emb_dim: int = 16):
        super().__init__()

        def dw_block(cin: int, cout: int, stride: int):
            return nn.Sequential(
                nn.Conv2d(cin, cin, 3, stride=stride, padding=1, groups=cin, bias=False),
                nn.BatchNorm2d(cin),
                nn.ReLU(inplace=True),
                nn.Conv2d(cin, cout, 1, bias=False),
                nn.BatchNorm2d(cout),
                nn.ReLU(inplace=True),
            )

        self.net = nn.Sequential(
            nn.Conv2d(3, 16, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            dw_block(16, 24, 2),
            dw_block(24, 32, 2),
            dw_block(32, 48, 2),
            nn.AdaptiveAvgPool2d(1),
        )
        self.fc = nn.Linear(48, emb_dim)

    def forward(self, x):
        h = self.net(x).flatten(1)
        z = self.fc(h)
        return F.normalize(z, p=2, dim=1)


def embed_samples(model: nn.Module, samples: list[Sample], device: torch.device):
    ds = EvalCropDataset(samples)
    dl = DataLoader(ds, batch_size=64, shuffle=False, num_workers=0)

    zs = []
    ys = []
    events = []
    paths = []

    model.eval()
    with torch.no_grad():
        for x, y, event, path in dl:
            x = x.to(device)
            z = model(x)
            zs.append(z.cpu())
            ys.append(y)
            events.extend(list(event))
            paths.extend(list(path))

    if not zs:
        return None, None, [], []

    return torch.cat(zs, dim=0), torch.cat(ys, dim=0).numpy(), events, paths


def pairwise_metrics(model: nn.Module, memory_samples: list[Sample], eval_samples: list[Sample], device: torch.device) -> dict:
    memory_correct = [s for s in memory_samples if s.role == "correct"]
    if not memory_correct:
        return {}

    z_mem, _y_mem, _ev_mem, _path_mem = embed_samples(model, memory_correct, device)
    z_eval, y_eval, events, _paths = embed_samples(model, eval_samples, device)

    if z_mem is None or z_eval is None or y_eval is None:
        return {}

    mem = F.normalize(z_mem.mean(dim=0, keepdim=True), p=2, dim=1)
    sims = (z_eval @ mem.T).squeeze(1).numpy()

    correct_mask = y_eval == 1
    distractor_mask = y_eval == 0

    out = {
        "memory_correct_n": int(len(memory_correct)),
        "correct_n": int(correct_mask.sum()),
        "distractor_n": int(distractor_mask.sum()),
        "correct_mean": float(sims[correct_mask].mean()) if correct_mask.sum() else float("nan"),
        "distractor_mean": float(sims[distractor_mask].mean()) if distractor_mask.sum() else float("nan"),
    }
    out["gap"] = out["correct_mean"] - out["distractor_mean"]

    event_out = {}
    for ev in sorted(set(events)):
        idx = np.array([e == ev for e in events], dtype=bool)
        c = sims[idx & correct_mask]
        d = sims[idx & distractor_mask]
        if len(c) and len(d):
            event_out[ev] = {
                "correct_n": int(len(c)),
                "distractor_n": int(len(d)),
                "correct_mean": float(c.mean()),
                "distractor_mean": float(d.mean()),
                "gap": float(c.mean() - d.mean()),
            }

    out["events"] = event_out
    return out


def export_similarity_scores(
    model: nn.Module,
    memory_samples: list[Sample],
    eval_samples: list[Sample],
    device: torch.device,
    output_csv: Path,
) -> None:
    memory_correct = [s for s in memory_samples if s.role == "correct"]
    z_mem, _y_mem, _events_mem, _paths_mem = embed_samples(model, memory_correct, device)
    z_eval, y_eval, events, paths = embed_samples(model, eval_samples, device)

    if z_mem is None or z_eval is None:
        raise RuntimeError("Could not embed samples.")

    mem = F.normalize(z_mem.mean(dim=0, keepdim=True), p=2, dim=1)
    sims = (z_eval @ mem.T).squeeze(1).numpy()

    by_path = {str(s.path): s for s in eval_samples}

    with output_csv.open("w", newline="") as f:
        fieldnames = [
            "dataset_root",
            "crop_path",
            "t",
            "frame_id",
            "track_id",
            "role",
            "identity_label",
            "event_type",
            "split",
            "target_label",
            "similarity_to_train_memory",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for path, y, ev, sim in zip(paths, y_eval, events, sims):
            sample = by_path.get(str(path))
            if sample is None:
                continue
            writer.writerow(
                {
                    "dataset_root": sample.dataset_root,
                    "crop_path": str(sample.path),
                    "t": f"{sample.t:.6f}",
                    "frame_id": int(sample.frame_id),
                    "track_id": int(sample.track_id),
                    "role": sample.role,
                    "identity_label": sample.identity,
                    "event_type": ev,
                    "split": sample.split,
                    "target_label": "correct" if int(y) == 1 else "distractor",
                    "similarity_to_train_memory": f"{float(sim):.6f}",
                }
            )


def write_report(path: Path, metrics: dict, args, train_n: int, test_n: int) -> None:
    lines = []
    lines.append("# TIM-V2E Tiny16 Triplet Training Result")
    lines.append("")
    lines.append("## Config")
    lines.append("")
    lines.append(f"- Embedding dim: {args.emb_dim}")
    lines.append(f"- Epochs: {args.epochs}")
    lines.append(f"- Batch size: {args.batch_size}")
    lines.append(f"- LR: {args.lr}")
    lines.append(f"- Margin: {args.margin}")
    lines.append(f"- Train samples: {train_n}")
    lines.append(f"- Test samples: {test_n}")
    lines.append(f"- Memory correct samples: {metrics.get('memory_correct_n', 0)}")
    lines.append("")
    lines.append("## Global test separation")
    lines.append("")
    lines.append("| correct_N | distractor_N | correct_mean | distractor_mean | gap |")
    lines.append("|---:|---:|---:|---:|---:|")
    lines.append(
        f"| {metrics.get('correct_n', 0)} | {metrics.get('distractor_n', 0)} | "
        f"{metrics.get('correct_mean', float('nan')):.3f} | "
        f"{metrics.get('distractor_mean', float('nan')):.3f} | "
        f"{metrics.get('gap', float('nan')):.3f} |"
    )
    lines.append("")
    lines.append("## Event-level test separation")
    lines.append("")
    lines.append("| Event | correct_N | distractor_N | correct_mean | distractor_mean | gap |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for ev, m in metrics.get("events", {}).items():
        lines.append(
            f"| {ev} | {m['correct_n']} | {m['distractor_n']} | "
            f"{m['correct_mean']:.3f} | {m['distractor_mean']:.3f} | {m['gap']:.3f} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-roots", nargs="+", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--emb-dim", type=int, default=16)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--margin", type=float, default=0.4)
    p.add_argument("--seed", type=int, default=7)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    all_samples = load_samples(args.dataset_roots)
    train_samples = [s for s in all_samples if s.split == "train"]
    test_samples = [s for s in all_samples if s.split == "test"]

    if not train_samples:
        raise SystemExit("No train samples.")
    if not test_samples:
        raise SystemExit("No test samples.")

    print(f"[info] train={len(train_samples)} test={len(test_samples)}")

    device = torch.device("cpu")
    model = TinyEmbeddingNet(emb_dim=args.emb_dim).to(device)

    train_ds = TripletCropDataset(train_samples, augment=True)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        pos_sims = []
        neg_sims = []

        for xa, xp, xn in train_dl:
            xa = xa.to(device)
            xp = xp.to(device)
            xn = xn.to(device)

            za = model(xa)
            zp = model(xp)
            zn = model(xn)

            pos_dist = 1.0 - (za * zp).sum(dim=1)
            neg_dist = 1.0 - (za * zn).sum(dim=1)

            loss = F.relu(pos_dist - neg_dist + args.margin).mean()

            opt.zero_grad()
            loss.backward()
            opt.step()

            losses.append(float(loss.item()))
            pos_sims.append(float((za * zp).sum(dim=1).mean().item()))
            neg_sims.append(float((za * zn).sum(dim=1).mean().item()))

        print(
            f"[epoch {epoch:03d}] "
            f"loss={np.mean(losses):.4f} "
            f"pos_sim={np.mean(pos_sims):.3f} "
            f"neg_sim={np.mean(neg_sims):.3f}"
        )

    metrics = pairwise_metrics(model, train_samples, test_samples, device)

    export_similarity_scores(
        model=model,
        memory_samples=train_samples,
        eval_samples=test_samples,
        device=device,
        output_csv=args.output_dir / "test_similarity_scores.csv",
    )
    export_similarity_scores(
        model=model,
        memory_samples=train_samples,
        eval_samples=all_samples,
        device=device,
        output_csv=args.output_dir / "all_similarity_scores.csv",
    )

    torch.save(
        {
            "model_state": model.state_dict(),
            "emb_dim": args.emb_dim,
            "input_size": [64, 128],
            "note": "TIM-V2E prototype tiny triplet embedding. Offline only.",
        },
        args.output_dir / "tim_v2e_tiny_triplet_embedding.pt",
    )

    write_report(args.output_dir / "summary.md", metrics, args, len(train_samples), len(test_samples))

    print(f"[ok] wrote {args.output_dir / 'summary.md'}")
    print(f"[ok] wrote {args.output_dir / 'test_similarity_scores.csv'}")
    print(f"[ok] wrote {args.output_dir / 'all_similarity_scores.csv'}")
    print(f"[ok] wrote {args.output_dir / 'tim_v2e_tiny_triplet_embedding.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
