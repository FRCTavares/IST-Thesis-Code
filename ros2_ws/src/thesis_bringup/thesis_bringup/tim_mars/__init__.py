# Thesis-Code
# Purpose: TIM-MARS selected-target memory package.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""TIM-MARS selected-target memory package.

This package contains the TIM-MARS selected-target memory layer used above
detection, multi-object tracking, and raw target selection. TIM-MARS converts
tracker candidates into one conservative controller-facing target stream.

Pure algorithmic logic is kept separate from ROS glue:
- target_memory.py owns the selected-target memory state machine.
- policy/scoring modules own geometry, appearance, ambiguity, and recovery helpers.
- ros_params.py, ros_messages.py, and target_memory_mars_node.py own ROS integration.
"""
