from __future__ import annotations

import ast
from pathlib import Path


NODE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "tim_mars"
    / "target_memory_mars_node.py"
)


def _tree():
    return ast.parse(NODE.read_text())


def _methods():
    tree = _tree()
    return {
        node.name: node
        for class_node in tree.body
        if isinstance(class_node, ast.ClassDef)
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }


def test_node_constructs_shared_runtime():
    tree = _tree()

    constructor_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "TimMarsRuntime"
    ]

    assert constructor_calls


def test_image_callback_delegates_to_runtime_add_image():
    method = _methods()["_on_image"]

    calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_image"
    ]

    assert calls


def test_track_callback_delegates_to_runtime_process_tracks():
    method = _methods()["_on_tracks"]

    calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "process_tracks"
    ]

    assert calls


def test_selection_callbacks_delegate_to_runtime():
    methods = _methods()

    select_calls = [
        node
        for node in ast.walk(methods["_on_select"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"request_selection", "clear"}
    ]
    clear_calls = [
        node
        for node in ast.walk(methods["_on_clear"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "clear"
    ]

    assert select_calls
    assert clear_calls


def test_node_no_longer_duplicates_runtime_processing_helpers():
    methods = _methods()

    duplicated_helpers = {
        "_candidate_from_track",
        "_track_time_ns",
        "_select_appearance_image",
        "_attach_appearance_features",
        "_clip_bbox",
        "_bbox_area",
        "_find_candidate",
    }

    assert duplicated_helpers.isdisjoint(methods)


def test_on_tracks_passes_tracks_message_to_target_message_formatter():
    method = _methods()["_on_tracks"]

    calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_target_msg_from_output"
    ]

    assert any(
        len(call.args) == 2
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "msg"
        for call in calls
    )


def test_target_message_formatter_copies_track_source_context():
    method = _methods()["_target_msg_from_output"]

    assignments = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and target.attr == "header"
            for target in node.targets
        )
    ]

    assigned_fields = {
        target.attr
        for assignment in ast.walk(method)
        if isinstance(assignment, ast.Assign)
        for target in assignment.targets
        if isinstance(target, ast.Attribute)
    }

    assert assignments
    assert {
        "header",
        "frame_id",
        "src_stamp_ns",
        "t_cam_msg_seen_ns",
    } <= assigned_fields


def test_status_carries_shared_freshness_result():
    method = _methods()["_publish_status"]

    keyword_names = {
        keyword.arg
        for call in ast.walk(method)
        if isinstance(call, ast.Call)
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert {
        "freshness_contract",
        "freshness_status",
        "freshness_is_fresh",
        "freshness_source_age_ms",
        "freshness_max_output_age_ms",
    } <= keyword_names


def test_message_timestamp_paths_do_not_use_monotonic_clock():
    methods = _methods()

    for method_name in {"_on_image"}:
        monotonic_calls = [
            node
            for node in ast.walk(methods[method_name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
            and node.func.attr == "monotonic_ns"
        ]

        assert not monotonic_calls


def test_node_does_not_keep_legacy_tim_alias():
    tree = _tree()

    legacy_assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and target.attr == "_tim"
            for target in node.targets
        )
    ]

    assert not legacy_assignments


def test_node_does_not_read_private_memory_cooldown_state():
    tree = _tree()

    private_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and node.value == "_appearance_update_cooldown_frames_remaining"
    ]

    assert not private_reads
