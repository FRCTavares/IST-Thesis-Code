#!/usr/bin/env python3
"""Sequence-clustered paired inference for Issue #125 episode fractions."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PairedEpisode:
    sequence_name: str
    episode_key: str
    tim_wrong_fraction: float
    bytetrack_wrong_fraction: float
    tim_correct_fraction: float
    bytetrack_correct_fraction: float

    def __post_init__(self) -> None:
        if not self.sequence_name or not self.episode_key:
            raise ValueError("sequence and episode keys are required")
        for value in (
            self.tim_wrong_fraction,
            self.bytetrack_wrong_fraction,
            self.tim_correct_fraction,
            self.bytetrack_correct_fraction,
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("episode fractions must be finite in [0, 1]")

    @property
    def wrong_difference(self) -> float:
        return self.tim_wrong_fraction - self.bytetrack_wrong_fraction

    @property
    def correct_difference(self) -> float:
        return self.tim_correct_fraction - self.bytetrack_correct_fraction


def _clusters(episodes: Sequence[PairedEpisode]) -> list[tuple[str, int, float, float]]:
    if not episodes:
        raise ValueError("at least one paired episode is required")
    seen: set[tuple[str, str]] = set()
    grouped: dict[str, list[PairedEpisode]] = {}
    for episode in episodes:
        key = (episode.sequence_name, episode.episode_key)
        if key in seen:
            raise ValueError(f"duplicate paired episode {key}")
        seen.add(key)
        grouped.setdefault(episode.sequence_name, []).append(episode)
    return [
        (
            name,
            len(grouped[name]),
            sum(item.wrong_difference for item in grouped[name]),
            sum(item.correct_difference for item in grouped[name]),
        )
        for name in sorted(grouped)
    ]


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def analyse(
    episodes: Sequence[PairedEpisode],
    *,
    seed: int = 12520260930,
    bootstrap_replicates: int = 10000,
    sign_flip_draws: int = 100000,
) -> dict[str, object]:
    """Use episode-macro effects and source-sequence cluster resampling."""
    if bootstrap_replicates <= 0 or sign_flip_draws <= 0:
        raise ValueError("replicate and draw counts must be positive")
    clusters = _clusters(episodes)
    episode_count = sum(count for _, count, _, _ in clusters)
    wrong_sum = sum(wrong for _, _, wrong, _ in clusters)
    correct_sum = sum(correct for _, _, _, correct in clusters)
    wrong_effect = wrong_sum / episode_count
    correct_effect = correct_sum / episode_count

    bootstrap_rng = random.Random(seed)
    wrong_draws: list[float] = []
    correct_draws: list[float] = []
    for _ in range(bootstrap_replicates):
        sampled = [clusters[bootstrap_rng.randrange(len(clusters))] for _ in clusters]
        sampled_episode_count = sum(count for _, count, _, _ in sampled)
        wrong_draws.append(
            sum(wrong for _, _, wrong, _ in sampled) / sampled_episode_count
        )
        correct_draws.append(
            sum(correct for _, _, _, correct in sampled) / sampled_episode_count
        )

    if all(wrong == 0.0 for _, _, wrong, _ in clusters):
        p_value = 1.0
    else:
        sign_rng = random.Random(seed + 1)
        observed = abs(wrong_effect)
        extreme = 0
        for _ in range(sign_flip_draws):
            signed_sum = sum(
                wrong if sign_rng.getrandbits(1) else -wrong
                for _, _, wrong, _ in clusters
            )
            if abs(signed_sum / episode_count) >= observed - 1e-12:
                extreme += 1
        p_value = (extreme + 1) / (sign_flip_draws + 1)

    return {
        "paired_episode_count": episode_count,
        "source_sequence_count": len(clusters),
        "seed": seed,
        "bootstrap_replicates": bootstrap_replicates,
        "sign_flip_draws": sign_flip_draws,
        "wrong_fraction_tim_minus_bytetrack": {
            "episode_macro_mean": wrong_effect,
            "cluster_bootstrap_95_percentile_ci": [
                _percentile(wrong_draws, 0.025),
                _percentile(wrong_draws, 0.975),
            ],
            "two_sided_cluster_sign_flip_p_value": p_value,
        },
        "correct_fraction_tim_minus_bytetrack": {
            "episode_macro_mean": correct_effect,
            "cluster_bootstrap_95_percentile_ci": [
                _percentile(correct_draws, 0.025),
                _percentile(correct_draws, 0.975),
            ],
        },
    }
