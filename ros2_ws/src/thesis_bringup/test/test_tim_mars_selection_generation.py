from __future__ import annotations

import ast
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "tim_mars"
    / "target_memory_mars_node.py"
)


def class_methods():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "TargetMemoryMarsNode"
    )
    return {
        node.name: node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }


def called_attributes(method):
    return [
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]


def call_line(method, attribute):
    return min(
        node.lineno
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    )


def test_all_selection_authority_entry_points_advance_generation():
    methods = class_methods()

    for name in {
        "_on_raw_target",
        "_on_select",
        "_on_clear",
    }:
        assert "_advance_selection_generation" in called_attributes(
            methods[name]
        )


def test_mirrored_selection_revokes_old_authority_before_request():
    method = class_methods()["_on_raw_target"]

    assert call_line(method, "_advance_selection_generation") < call_line(
        method,
        "request_selection",
    )
    assert call_line(method, "clear") < call_line(
        method,
        "request_selection",
    )
    assert call_line(method, "_publish_target_reset") < call_line(
        method,
        "request_selection",
    )
    assert call_line(method, "_publish_status_only") < call_line(
        method,
        "request_selection",
    )


def test_explicit_positive_selection_revokes_old_authority():
    method = class_methods()["_on_select"]
    calls = called_attributes(method)

    assert "_advance_selection_generation" in calls
    assert "clear" in calls
    assert "_publish_target_reset" in calls
    assert "_publish_status_only" in calls
    assert "request_selection" in calls


def test_clear_advances_generation_and_publishes_revocation():
    method = class_methods()["_on_clear"]
    calls = called_attributes(method)

    assert "_advance_selection_generation" in calls
    assert "clear" in calls
    assert "_publish_target_reset" in calls
    assert "_publish_status_only" in calls
