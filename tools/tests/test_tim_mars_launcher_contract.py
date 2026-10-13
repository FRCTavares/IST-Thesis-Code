# Thesis-Code
# Purpose: Contract that the live launcher takes TIM-MARS parameters only from
# the canonical YAML.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""Contract that the live launcher takes TIM-MARS parameters from one YAML."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CONFIG = (
    REPO_ROOT / "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
)


# Decision thresholds and switches that must live only in the canonical YAML.
YAML_ONLY_PARAMETERS = (
    "appearance_conservative_margin",
    "hard_negative_reject_margin",
    "hard_negative_confirm_observations",
    "rank_aware_lost_app_margin",
    "absence_recovery_enabled",
    "absence_appearance_margin",
    "same_id_hijack_protection_enabled",
    "freshness_max_output_age_s",
    "freshness_future_tolerance_s",
    "global_reacquisition_enabled",
    "global_reacquisition_after_missed_frames",
    "appearance_prevent_repeated_source_adaptive_update",
    "same_id_fresh_challenge_enabled",
    "same_id_challenge_available_images_only",
    "appearance_gallery_consensus_recovery_enabled",
    "min_confirm_frames_after_reacquire",
)


def canonical_parameters() -> dict:
    document = yaml.safe_load(CANONICAL_CONFIG.read_text(encoding="utf-8"))
    return document["target_memory_mars_node"]["ros__parameters"]


def test_canonical_config_defines_the_yaml_only_parameters():
    parameters = canonical_parameters()
    for name in YAML_ONLY_PARAMETERS:
        assert name in parameters, name


def test_live_launcher_uses_canonical_params_without_threshold_copies():
    defaults = (REPO_ROOT / "tools/lib/live_defaults.sh").read_text(
        encoding="utf-8"
    )
    launcher = (REPO_ROOT / "tools/start_live_stack.sh").read_text(
        encoding="utf-8"
    )
    assert "tim_mars_canonical.yaml" in defaults
    assert '--params-file "$TARGET_MEMORY_MARS_CONFIG"' in launcher
    for parameter in YAML_ONLY_PARAMETERS:
        assert f"-p {parameter}:=" not in launcher
