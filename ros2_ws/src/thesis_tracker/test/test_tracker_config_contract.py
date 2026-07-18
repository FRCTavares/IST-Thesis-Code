"""Verify tracker YAML files expose only effective runtime parameters."""

from __future__ import annotations

import ast
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[4]
TRACKER_NODE = (
    ROOT
    / 'ros2_ws/src/thesis_tracker/thesis_tracker/nodes/tracker_node.py'
)
CONFIG_DIR = ROOT / 'ros2_ws/src/thesis_bringup/config'

COMMON_PARAMETERS = {
    'tracker_type',
    'image_topic',
    'min_score',
    'publish_tracks',
    'publish_tracks_requires_subscribers',
    'publish_timing_topic',
    'profiling_enabled',
    'profiling_log_every_n',
    'profiling_publish_details',
    'profiling_serialize_sample_every_n',
    'profiling_gc_probe',
}


def _tracker_branch_name(test: ast.expr) -> str | None:
    if not isinstance(test, ast.Compare):
        return None

    if not isinstance(test.left, ast.Name):
        return None

    if test.left.id != 'tracker_type':
        return None

    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None

    if len(test.comparators) != 1:
        return None

    comparator = test.comparators[0]

    if not isinstance(comparator, ast.Constant):
        return None

    if not isinstance(comparator.value, str):
        return None

    return comparator.value


def _declared_backend_parameters() -> dict[str, set[str]]:
    tree = ast.parse(TRACKER_NODE.read_text(encoding='utf-8'))

    create_backend = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == 'TrackerNode'
        for child in node.body
        if isinstance(child, ast.FunctionDef)
        and child.name == '_create_backend'
        for node in [child]
    )

    branch = next(
        statement
        for statement in create_backend.body
        if isinstance(statement, ast.If)
    )

    parameters_by_tracker: dict[str, set[str]] = {}

    while isinstance(branch, ast.If):
        tracker_name = _tracker_branch_name(branch.test)

        if tracker_name is not None:
            parameters: set[str] = set()

            for statement in branch.body:
                for node in ast.walk(statement):
                    if not isinstance(node, ast.Call):
                        continue

                    if not isinstance(node.func, ast.Attribute):
                        continue

                    if node.func.attr != '_declare_param_if_missing':
                        continue

                    if not node.args:
                        continue

                    name_node = node.args[0]

                    if (
                        isinstance(name_node, ast.Constant)
                        and isinstance(name_node.value, str)
                    ):
                        parameters.add(name_node.value)

            parameters_by_tracker[tracker_name] = parameters

        if len(branch.orelse) == 1 and isinstance(
            branch.orelse[0],
            ast.If,
        ):
            branch = branch.orelse[0]
        else:
            break

    return parameters_by_tracker


def _load_config(path: Path) -> dict[str, object]:
    document = yaml.safe_load(path.read_text(encoding='utf-8'))
    return dict(document['tracker_node']['ros__parameters'])


def test_tracker_configs_only_publish_consumed_parameters():
    """Reject YAML keys that the selected tracker branch never reads."""
    parameters_by_tracker = _declared_backend_parameters()

    for path in sorted(CONFIG_DIR.glob('tracker_*.yaml')):
        tracker_name = path.stem.removeprefix('tracker_')
        parameters = _load_config(path)

        assert parameters['tracker_type'] == tracker_name
        assert tracker_name in parameters_by_tracker

        allowed = COMMON_PARAMETERS | parameters_by_tracker[tracker_name]
        ignored = sorted(set(parameters) - allowed)

        assert ignored == [], (
            f'{path.name} contains parameters that its tracker branch '
            f'does not consume: {ignored}'
        )


def test_known_legacy_tracker_parameters_are_absent():
    """Keep known inert legacy parameters out of active tracker profiles."""
    bytetrack = _load_config(CONFIG_DIR / 'tracker_bytetrack.yaml')
    ocsort = _load_config(CONFIG_DIR / 'tracker_ocsort.yaml')
    deepsort = _load_config(CONFIG_DIR / 'tracker_deepsort.yaml')

    assert 'det_thresh' not in bytetrack

    assert 'centre_gate' not in ocsort
    assert 'asso_threshold' not in ocsort

    assert 'match_thresh' not in deepsort
    assert 'centre_gate' not in deepsort
    assert not any(name.startswith('appearance_') for name in deepsort)
