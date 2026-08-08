"""Generate deterministic thesis figures for the Issue #31 (P1.13) parameter
sensitivity aggregate. Reads only the already-computed aggregate CSV; does
not touch TIM-MARS, replay, or evaluation. Uses the non-interactive Agg
backend and fixed styling so repeated runs against the same aggregate CSV
produce the same figures.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
AGG_DIR = (
    REPO_ROOT
    / "reports"
    / "p031_parameter_sensitivity_5b340c2b_2026-08-08"
    / "aggregate"
)
FIG_DIR = AGG_DIR / "figures"

DIMENSION_ORDER = [
    "acceptance_pair",
    "ambiguity_margin",
    "appearance_conservative_min_similarity",
    "appearance_conservative_margin",
    "hard_negative_reject_similarity",
    "hard_negative_reject_margin",
    "confirmation_time",
]

DIMENSION_LABELS = {
    "acceptance_pair": "Acceptance pair\n(locked/lost)",
    "ambiguity_margin": "Ambiguity margin",
    "appearance_conservative_min_similarity": "Conservative appearance\nminimum",
    "appearance_conservative_margin": "Conservative appearance\nmargin",
    "hard_negative_reject_similarity": "Hard-negative reject\nsimilarity",
    "hard_negative_reject_margin": "Hard-negative reject\nmargin",
    "confirmation_time": "Confirmation time\n(effective frames)",
}

# Canonical value per dimension, from docs/issues/p1-13-parameter-sensitivity.md
# (the baseline row's overrides are {}, so its true value must come from the
# frozen protocol doc, not be assumed positionally).
CANONICAL_VALUE = {
    "acceptance_pair": 0.52,
    "ambiguity_margin": 0.07,
    "appearance_conservative_min_similarity": 0.65,
    "appearance_conservative_margin": 0.05,
    "hard_negative_reject_similarity": 0.80,
    "hard_negative_reject_margin": 0.03,
    "confirmation_time": 1,
}


def load_aggregate() -> list[dict]:
    with (AGG_DIR / "matrix_aggregate.csv").open() as fh:
        return list(csv.DictReader(fh))


def row_value(row: dict, dimension_id: str) -> float:
    if row["config_id"] == "baseline":
        return CANONICAL_VALUE[dimension_id]
    overrides = json.loads(row["overrides"])
    return float(next(iter(overrides.values())))


def dimension_rows(rows: list[dict], dimension_id: str) -> list[dict]:
    baseline = next(r for r in rows if r["config_id"] == "baseline")
    dim_rows = [r for r in rows if r["dimension_id"] == dimension_id]
    combined = [baseline] + dim_rows
    combined.sort(key=lambda r: row_value(r, dimension_id))
    return combined


def perturbation_label(row: dict) -> str:
    if row["config_id"] == "baseline":
        return "canonical"
    overrides = json.loads(row["overrides"])
    value = next(iter(overrides.values()))
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def plot_dimension(rows: list[dict], dimension_id: str, ax_wrong, ax_lost) -> None:
    dim_rows = dimension_rows(rows, dimension_id)
    labels = [perturbation_label(r) for r in dim_rows]
    wrong = [float(r["tim_wrong_s"]) for r in dim_rows]
    lost = [float(r["tim_lost_s"]) for r in dim_rows]
    baseline_idx = labels.index("canonical")

    x = range(len(dim_rows))
    ax_wrong.plot(x, wrong, marker="o", color="#b3261e")
    ax_wrong.scatter(
        [baseline_idx], [wrong[baseline_idx]], color="#b3261e", s=70, zorder=5
    )
    ax_wrong.set_title(DIMENSION_LABELS[dimension_id], fontsize=9)
    ax_wrong.set_xticks(list(x))
    ax_wrong.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
    ax_wrong.tick_params(axis="y", labelsize=7)
    ax_wrong.grid(alpha=0.3)

    ax_lost.plot(x, lost, marker="o", color="#1a5fb4")
    ax_lost.scatter(
        [baseline_idx], [lost[baseline_idx]], color="#1a5fb4", s=70, zorder=5
    )
    ax_lost.set_xticks(list(x))
    ax_lost.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
    ax_lost.tick_params(axis="y", labelsize=7)
    ax_lost.grid(alpha=0.3)


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_aggregate()

    fig, axes = plt.subplots(2, 7, figsize=(20, 6), sharey="row")
    for col, dimension_id in enumerate(DIMENSION_ORDER):
        plot_dimension(rows, dimension_id, axes[0][col], axes[1][col])
    axes[0][0].set_ylabel("Aggregate wrong-target [s]\n(safety)", fontsize=9)
    axes[1][0].set_ylabel("Aggregate lost-target [s]\n(availability)", fontsize=9)
    fig.suptitle(
        "Issue #31: TIM-MARS parameter sensitivity — 7 dimensions,"
        " 4 development sequences, aggregate wrong/lost duration",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = FIG_DIR / "p031_all_dimensions_wrong_lost.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[ok] wrote {out}")

    # Confirmation-time is the dominant trade-off; give it its own clear plot.
    fig2, ax = plt.subplots(figsize=(6, 4.5))
    dim_rows = dimension_rows(rows, "confirmation_time")
    labels = [perturbation_label(r) for r in dim_rows]
    wrong = [float(r["tim_wrong_s"]) for r in dim_rows]
    lost = [float(r["tim_lost_s"]) for r in dim_rows]
    x = range(len(dim_rows))
    ax.plot(x, wrong, marker="o", color="#b3261e", label="Wrong-target (safety) [s]")
    ax.plot(x, lost, marker="s", color="#1a5fb4", label="Lost-target (availability) [s]")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_xlabel("min_confirm_frames_after_reacquire (configured value)")
    ax.set_ylabel("Aggregate duration across 4 sequences [s]")
    ax.set_title("Confirmation-time safety-availability trade-off")
    ax.legend()
    ax.grid(alpha=0.3)
    fig2.tight_layout()
    out2 = FIG_DIR / "p031_confirmation_time_tradeoff.png"
    fig2.savefig(out2, dpi=150)
    plt.close(fig2)
    print(f"[ok] wrote {out2}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
