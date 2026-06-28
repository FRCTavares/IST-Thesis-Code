from __future__ import annotations

import ast
from pathlib import Path


NODE = Path("ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/target_memory_mars_node.py")


def _tree():
    return ast.parse(NODE.read_text())


def test_on_tracks_passes_tracks_message_to_target_message_formatter():
    tree = _tree()

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_target_msg_from_output"
    ]

    assert calls, "Expected at least one _target_msg_from_output call"

    # The wrapper must receive the incoming Track2DArray message so it can copy
    # msg.header into the regenerated TargetState. Header time is required for
    # --timebase header evaluations.
    assert any(
        len(call.args) == 2
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "msg"
        for call in calls
    )


def test_target_message_formatter_copies_track_header():
    tree = _tree()

    assigns_header = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and target.attr == "header"
            for target in node.targets
        )
    ]

    assert assigns_header, "Expected regenerated TargetState header to be copied from tracks_msg.header"
