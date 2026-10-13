# Thesis-Code
# Purpose: Check SORT detection-confidence transport.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""Check that SORT publishes the score of its current matched detection."""

import pytest

from thesis_tracker.backends.sort_backend import SortBackend


def test_scores_follow_association_when_detection_order_changes():
    backend = SortBackend(min_hits=1)
    left = (0, 0, 20, 40)
    right = (100, 0, 120, 40)

    first = backend.update([left, right], [0.41, 0.93], 0)
    assert [(track.track_id, track.score) for track in first] == [
        (1, 0.41), (2, 0.93)
    ]

    second = backend.update([right, left], [0.56, 0.87], 1)
    assert [(track.track_id, track.score) for track in second] == [
        (1, 0.87), (2, 0.56)
    ]


def test_unmatched_predictions_do_not_publish_stale_confidence():
    backend = SortBackend(min_hits=1)
    box = (0, 0, 20, 40)
    backend.update([box], [0.83], 0)

    assert backend.update([], [], 1) == []
    assert backend.tracker.tracks[0].detection_index is None
    assert backend.update([box], [0.42], 2)[0].score == 0.42


def test_scores_align_with_boxes_and_confirmation():
    backend = SortBackend(min_hits=3)
    box = (0, 0, 20, 40)

    assert backend.update([box], [0.9], 0) == []
    assert backend.update([box], [0.8], 1) == []
    assert backend.update([box], [0.7], 2)[0].score == 0.7
    with pytest.raises(ValueError):
        backend.update([box], [], 3)
