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


def test_appearance_attachment_uses_tracks_message_time():
    tree = _tree()

    methods = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for node in node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_track_time_ns" in methods
    assert "_select_appearance_image" in methods
    assert "_attach_appearance_features" in methods

    attach_method = methods["_attach_appearance_features"]

    monotonic_calls = [
        node
        for node in ast.walk(attach_method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "time"
        and node.func.attr == "monotonic_ns"
    ]

    assert not monotonic_calls


def test_appearance_image_selection_rejects_future_images():
    tree = _tree()

    select_methods = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_select_appearance_image"
    ]

    assert len(select_methods) == 1

    comparisons = [
        node
        for node in ast.walk(select_methods[0])
        if isinstance(node, ast.Compare)
        and any(isinstance(op, ast.LtE) for op in node.ops)
    ]

    assert comparisons, (
        "Expected image selection to require image timestamp "
        "<= track timestamp"
    )


def test_image_callback_keeps_timestamp_ordered_buffer():
    tree = _tree()

    image_methods = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_on_image"
    ]

    assert len(image_methods) == 1

    sort_calls = [
        node
        for node in ast.walk(image_methods[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sort"
    ]

    assert sort_calls

def test_timestamp_paths_do_not_mix_monotonic_clock_domain():
    tree = _tree()

    relevant_methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_on_image",
            "_track_time_ns",
            "_attach_appearance_features",
        }
    }

    assert set(relevant_methods) == {
        "_on_image",
        "_track_time_ns",
        "_attach_appearance_features",
    }

    for method_name, method in relevant_methods.items():
        monotonic_calls = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
            and node.func.attr == "monotonic_ns"
        ]

        assert not monotonic_calls, (
            f"{method_name} must not mix monotonic time with "
            "message timestamps"
        )
