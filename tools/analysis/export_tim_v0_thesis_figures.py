#!/usr/bin/env python3
"""Export thesis-ready TIM-V0 figures from generated analysis CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_TIM_DIR = Path(
    "reports/tim_v0/2026-05-05__09-55-39__video__tim_v0_occlusion_01"
)
DEFAULT_FAULT_DIR = Path(
    "reports/tim_v0_fault_injection_batch/2026-05-05__09-55-39__video__tim_v0_occlusion_01"
)
DEFAULT_OUT = Path("figures/tim_v0")


STATE_ORDER = ["NO_TARGET", "LOCKED", "UNCERTAIN", "LOST", "REACQUIRED"]
STATE_TO_Y = {s: i for i, s in enumerate(STATE_ORDER)}


def _ensure_out(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_bool_series(df: pd.DataFrame, col: str) -> pd.Series:
    if df[col].dtype == bool:
        return df[col]
    return df[col].astype(str).str.lower().isin(["true", "1", "yes"])


def _first_selection_time(status: pd.DataFrame) -> float:
    selected = status[status["state"] != "NO_TARGET"]
    if selected.empty:
        return float(status["t"].min())
    return float(selected["t"].iloc[0])


def _state_transitions(status: pd.DataFrame) -> pd.DataFrame:
    if status.empty:
        return status
    changed = status["state"].ne(status["state"].shift())
    return status.loc[changed, ["t", "state"]].copy()


def figure_state_timeline(status: pd.DataFrame, out: Path) -> None:
    df = status.copy()
    df = df[df["state"].isin(STATE_TO_Y)].copy()
    df["y"] = df["state"].map(STATE_TO_Y)

    t0 = max(0.0, _first_selection_time(df) - 1.0)
    df = df[df["t"] >= t0].copy()

    fig, ax = plt.subplots(figsize=(10, 3.6), dpi=180)
    ax.step(df["t"], df["y"], where="post", linewidth=2)

    transitions = _state_transitions(df)
    key_events = transitions[transitions["state"].isin(["LOCKED", "UNCERTAIN", "REACQUIRED", "LOST"])]
    for idx, (_, row) in enumerate(key_events.iterrows()):
        ax.axvline(row["t"], linestyle=":", linewidth=1, alpha=0.45)
        # Stagger labels near the top to avoid collisions during short transitions.
        y_text = len(STATE_ORDER) - 0.35 - 0.25 * (idx % 2)
        ax.text(
            row["t"],
            y_text,
            row["state"],
            rotation=90,
            va="top",
            ha="center",
            fontsize=7,
        )

    ax.set_yticks(list(STATE_TO_Y.values()))
    ax.set_yticklabels(STATE_ORDER)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("TIM-V0 state")
    ax.set_title("TIM-V0 selected-target state timeline")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "tim_v0_state_timeline_thesis.png")
    fig.savefig(out / "tim_v0_state_timeline_thesis.pdf")
    plt.close(fig)


def figure_validity_timeline(raw: pd.DataFrame, tim: pd.DataFrame, status: pd.DataFrame, out: Path) -> None:
    raw = raw.copy()
    tim = tim.copy()
    raw["valid_num"] = _read_bool_series(raw, "valid").astype(int)
    tim["valid_num"] = _read_bool_series(tim, "valid").astype(int)

    t0 = max(0.0, _first_selection_time(status) - 1.0)
    raw = raw[raw["t"] >= t0]
    tim = tim[tim["t"] >= t0]

    fig, ax = plt.subplots(figsize=(10, 3.4), dpi=180)
    ax.step(raw["t"], raw["valid_num"], where="post", linewidth=2, label="raw selected ID")
    ax.step(tim["t"], tim["valid_num"] + 0.04, where="post", linewidth=2, label="TIM-V0 output")

    transitions = _state_transitions(status[status["t"] >= t0])
    key_events = transitions[transitions["state"].isin(["UNCERTAIN", "LOST", "REACQUIRED"])]
    for idx, (_, row) in enumerate(key_events.iterrows()):
        ax.axvline(row["t"], linestyle=":", linewidth=1, alpha=0.45)
        y_text = 1.28 - 0.12 * (idx % 2)
        ax.text(row["t"], y_text, row["state"], rotation=90, va="top", ha="center", fontsize=7)

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["invalid", "valid"])
    ax.set_ylim(-0.15, 1.35)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("target output")
    ax.set_title("Raw selected-ID target versus TIM-V0 output")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "tim_v0_raw_vs_memory_validity_thesis.png")
    fig.savefig(out / "tim_v0_raw_vs_memory_validity_thesis.pdf")
    plt.close(fig)


def figure_latency(status: pd.DataFrame, out: Path) -> None:
    lat = pd.to_numeric(status["lat_ms"], errors="coerce").dropna()
    lat = lat[lat >= 0]

    p50 = float(np.percentile(lat, 50))
    p95 = float(np.percentile(lat, 95))
    p99 = float(np.percentile(lat, 99))
    mean = float(np.mean(lat))
    outliers = int((lat > 1.0).sum())

    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=180)
    ax.hist(lat.clip(upper=1.0), bins=40)
    ax.axvline(p50, linestyle="--", linewidth=1.5, label=f"p50 = {p50:.3f} ms")
    ax.axvline(p95, linestyle="--", linewidth=1.5, label=f"p95 = {p95:.3f} ms")
    ax.axvline(p99, linestyle="--", linewidth=1.5, label=f"p99 = {p99:.3f} ms")

    text = (
        f"mean = {mean:.3f} ms\n"
        f"p50 = {p50:.3f} ms\n"
        f"p95 = {p95:.3f} ms\n"
        f"p99 = {p99:.3f} ms\n"
        f">1 ms samples = {outliers}/{len(lat)}"
    )
    ax.text(0.98, 0.95, text, transform=ax.transAxes, ha="right", va="top",
            bbox=dict(boxstyle="round", alpha=0.15))

    ax.set_xlim(0, 1.0)
    ax.set_xlabel("TIM-V0 update latency [ms], clipped at 1 ms")
    ax.set_ylabel("count")
    ax.set_title("TIM-V0 latency distribution")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper center")
    fig.tight_layout()
    fig.savefig(out / "tim_v0_latency_distribution_thesis.png")
    fig.savefig(out / "tim_v0_latency_distribution_thesis.pdf")
    plt.close(fig)


def figure_validity_gain(fault: pd.DataFrame, out: Path) -> None:
    df = fault.copy()
    df["label"] = df.apply(
        lambda r: f"{int(r['gap_start_s'])}s/{int(r['gap_duration_s'])}s", axis=1
    )

    fig, ax = plt.subplots(figsize=(10, 3.8), dpi=180)
    x = np.arange(len(df))
    ax.bar(x, df["validity_gain"])
    ax.axhline(float(df["validity_gain"].mean()), linestyle="--", linewidth=1.3,
               label=f"mean gain = {df['validity_gain'].mean():.3f}")

    for i, row in df.iterrows():
        if not bool(row["reacquired"]):
            ax.text(i, 0.03, "fail", rotation=90, ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(df["label"], rotation=45, ha="right")
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("fault case: gap start / gap duration")
    ax.set_ylabel("TIM valid ratio - raw valid ratio")
    ax.set_title("TIM-V0 validity gain under injected ID-switch faults")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "tim_v0_fault_validity_gain_thesis.png")
    fig.savefig(out / "tim_v0_fault_validity_gain_thesis.pdf")
    plt.close(fig)


def figure_reacquisition_time(fault: pd.DataFrame, out: Path) -> None:
    df = fault.copy()
    df["label"] = df.apply(
        lambda r: f"{int(r['gap_start_s'])}s/{int(r['gap_duration_s'])}s", axis=1
    )
    df["reacq_plot"] = pd.to_numeric(df["reacq_time_s"], errors="coerce").fillna(0.0)

    fig, ax = plt.subplots(figsize=(10, 3.8), dpi=180)
    x = np.arange(len(df))
    ax.bar(x, df["reacq_plot"])
    ax.axhline(1.0, linestyle="--", linewidth=1.4, label="1.0 s target")

    for i, row in df.iterrows():
        if not bool(row["reacquired"]):
            ax.text(i, 0.06, "fail", rotation=90, ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(df["label"], rotation=45, ha="right")
    ax.set_xlabel("fault case: gap start / gap duration")
    ax.set_ylabel("reacquisition time [s]")
    ax.set_title("TIM-V0 reacquisition time after injected ID-switch faults")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "tim_v0_fault_reacquisition_time_thesis.png")
    fig.savefig(out / "tim_v0_fault_reacquisition_time_thesis.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tim-dir", type=Path, default=DEFAULT_TIM_DIR)
    parser.add_argument("--fault-dir", type=Path, default=DEFAULT_FAULT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    _ensure_out(args.out)

    status = pd.read_csv(args.tim_dir / "target_memory_status.csv")
    raw = pd.read_csv(args.tim_dir / "target_raw.csv")
    tim = pd.read_csv(args.tim_dir / "target_memory.csv")
    fault = pd.read_csv(args.fault_dir / "summary.csv")

    figure_state_timeline(status, args.out)
    figure_validity_timeline(raw, tim, status, args.out)
    figure_latency(status, args.out)
    figure_validity_gain(fault, args.out)
    figure_reacquisition_time(fault, args.out)

    print(f"[ok] wrote thesis figures to {args.out}")


if __name__ == "__main__":
    main()
