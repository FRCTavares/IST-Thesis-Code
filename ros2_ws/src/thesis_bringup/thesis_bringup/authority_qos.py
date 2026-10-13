# Thesis-Code
# Purpose: QoS contracts at the TIM-MARS controller-authority boundary.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""QoS contracts at the TIM-MARS controller-authority boundary."""

from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


AUTHORITY_QOS_DEPTH = 10


def target_state_qos() -> QoSProfile:
    """Return the high-rate controller-target state profile."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=AUTHORITY_QOS_DEPTH,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )


def authority_status_qos() -> QoSProfile:
    """Return the reliable, non-latched authority-status profile."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=AUTHORITY_QOS_DEPTH,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )
