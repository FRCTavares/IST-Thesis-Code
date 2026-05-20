#!/usr/bin/env python3
"""
Train first tiny 16D TIM-V2E identity embedding.

Prototype only:
- Uses exported crop datasets from build_tim_embedding_dataset.py
- Trains on split=train rows
- Evaluates on split=test rows
- Does not touch live TIM
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
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
                    )
                )
    return samples


class CropDataset(Dataset):
    def __init__(self, samples: list[Sample], augment: bool):
        self.samples = samples
        self.augment = augment

    def __len__(self) -> int:
        return len(self.samples)

    def _augment(self, img: np.ndarray) -> np.ndarray:
        if random.random() < 0.5:
            img = cv2.flip(img, 1)

        if random.random() < 0.8:
            alpha = random.uniform(0.85, 1.15)
            beta = random.uniform(-12, 12)
            img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

        if random.random() < 0.2:
            img = cv2.GaussianBlur(img, (3, 3), 0)

        return img

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        img = cv2.imread(str(s.path))
        if img is None:
            raise RuntimeError(f"Could not read {s.path}")

        img = cv2.resize(img, (64, 128), interpolation=cv2.INTER_AREA)

        if self.augment:
            img = self._augment(img)

        # BGR -> RGB, CHW, float [0,1]
        img = img[:, :, ::-1].copy()
        x = torch.from_numpy(img).float().permute(2, 0, 1) / 255.0

        # Binary identity for this prototype:
        # selected_target vs distractor.
        y = 1 if s.role == "correct" else 0
        return x, y, s.role, s.event, str(s.path)


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
        self.cls = nn.Linear(emb_dim, 2)

    def forward(self, x):
        h = self.net(x).flatten(1)
        z = self.fc(h)
        z = F.normalize(z, p=2, dim=1)
        logits = self.cls(z)
        return z, logits


def embed_samples(model: nn.Module, samples: list[Sample], device: torch.device):
    ds = CropDataset(samples, augment=False)
    dl = DataLoader(ds, batch_size=64, shuffle=False, num_workers=0)

    zs = []
    ys = []
    events = []

    model.eval()
    with torch.no_grad():
        for x, y, _role, event, _path in dl:
            x = x.to(device)
            z, _ = model(x)
            zs.append(z.cpu())
            ys.append(y)
            events.extend(list(event))

    if not zs:
        return None, None, []

    return torch.cat(zs, dim=0), torch.cat(ys, dim=0).numpy(), events


def pairwise_metrics(
    model: nn.Module,
    memory_samples: list[Sample],
    eval_samples: list[Sample],
    device: torch.device,
) -> dict:
    memory_correct = [s for s in memory_samples if s.role == "correct"]
    if not memory_correct:
        return {}

    z_mem, y_mem, _events_mem = embed_samples(model, memory_correct, device)
    z_eval, y_eval, events = embed_samples(model, eval_samples, device)

    if z_mem is None or z_eval is None or y_eval is None:
        return {}

    mem = F.normalize(z_mem.mean(dim=0, keepdim=True), p=2, dim=1)
    sims = (z_eval @ mem.T).squeeze(1).numpy()

    correct_mask = y_eval == 1
    distractor_mask = y_eval == 0

    if correct_mask.sum() == 0 or distractor_mask.sum() == 0:
        return {}

    correct_sims = sims[correct_mask]
    distractor_sims = sims[distractor_mask]

    out = {
        "memory_correct_n": int(len(memory_correct)),
        "correct_mean": float(correct_sims.mean()),
        "distractor_mean": float(distractor_sims.mean()),
        "gap": float(correct_sims.mean() - distractor_sims.mean()),
        "correct_n": int(correct_mask.sum()),
        "distractor_n": int(distractor_mask.sum()),
    }

    event_out: Dict[str, dict] = {}
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


def write_report(path: Path, metrics: dict, args, train_n: int, test_n: int) -> None:
    lines = []
    lines.append("# TIM-V2E tiny embedding training result")
    lines.append("")
    lines.append("## Config")
    lines.append("")
    lines.append(f"- Embedding dim: {args.emb_dim}")
    lines.append(f"- Epochs: {args.epochs}")
    lines.append(f"- Batch size: {args.batch_size}")
    lines.append(f"- LR: {args.lr}")
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

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-roots", nargs="+", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--emb-dim", type=int, default=16)
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
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
        raise SystemExit("No train samples found.")
    if not test_samples:
        raise SystemExit("No test samples found.")

    print(f"[info] train={len(train_samples)} test={len(test_samples)}")

    device = torch.device("cpu")
    model = TinyEmbeddingNet(emb_dim=args.emb_dim).to(device)

    train_ds = CropDataset(train_samples, augment=True)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        accs = []

        for x, y, _role, _event, _path in train_dl:
            x = x.to(device)
            y = y.to(device)

            _z, logits = model(x)
            loss = F.cross_entropy(logits, y)

            opt.zero_grad()
            loss.backward()
            opt.step()

            pred = logits.argmax(dim=1)
            acc = (pred == y).float().mean().item()

            losses.append(float(loss.item()))
            accs.append(float(acc))

        print(f"[epoch {epoch:03d}] loss={np.mean(losses):.4f} acc={np.mean(accs):.3f}")

    metrics = pairwise_metrics(model, train_samples, test_samples, device)

    torch.save(
        {
            "model_state": model.state_dict(),
            "emb_dim": args.emb_dim,
            "input_size": [64, 128],
            "note": "TIM-V2E prototype tiny embedding. Offline only.",
        },
        args.output_dir / "tim_v2e_tiny_embedding.pt",
    )

    write_report(args.output_dir / "summary.md", metrics, args, len(train_samples), len(test_samples))

    print(f"[ok] wrote {args.output_dir / 'tim_v2e_tiny_embedding.pt'}")
    print(f"[ok] wrote {args.output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
