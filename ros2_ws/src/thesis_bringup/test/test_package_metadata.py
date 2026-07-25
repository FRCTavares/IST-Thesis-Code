"""Validate the public metadata contract for thesis_bringup."""

from __future__ import annotations

import ast
from pathlib import Path
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[2]
PACKAGE_XML = PACKAGE_ROOT / 'package.xml'
SETUP_PY = PACKAGE_ROOT / 'setup.py'
LICENSE_FILE = REPOSITORY_ROOT / 'LICENSE'
README = REPOSITORY_ROOT / 'README.md'

EXPECTED_VERSION = '0.1.0'
EXPECTED_LICENSE = 'MIT'
EXPECTED_MAINTAINER = 'Francisco Carreira Tavares'
EXPECTED_DESCRIPTION = (
    'ROS 2 runtime composition for onboard perception, tracking, '
    'TIM-MARS target validation, dashboard telemetry, and control.'
)

REQUIRED_DEPENDENCIES = {
    'cv_bridge',
    'geometry_msgs',
    'launch',
    'launch_ros',
    'rcl_interfaces',
    'rclpy',
    'sensor_msgs',
    'std_msgs',
    'thesis_msgs',
    'thesis_tracker',
    'vision_msgs',
}

REQUIRED_EXEC_DEPENDENCIES = {
    'python3-gi',
    'python3-numpy',
    'python3-opencv',
    'python3-websockets',
}


def setup_keywords() -> dict[str, object]:
    """Return literal keyword values passed to setuptools.setup."""
    tree = ast.parse(SETUP_PY.read_text(encoding='utf-8'))

    setup_call = next(
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'setup'
        )
    )

    values = {}

    for keyword in setup_call.keywords:
        if keyword.arg is None:
            continue

        try:
            values[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, TypeError):
            continue

    return values


def xml_values(tag: str) -> set[str]:
    """Return stripped values for one package.xml tag."""
    root = ET.parse(PACKAGE_XML).getroot()

    return {
        element.text.strip()
        for element in root.findall(tag)
        if element.text
    }


def test_package_and_python_metadata_match():
    """Keep package.xml and setup.py public metadata aligned."""
    root = ET.parse(PACKAGE_XML).getroot()
    setup = setup_keywords()

    assert root.findtext('version') == EXPECTED_VERSION
    assert setup['version'] == EXPECTED_VERSION

    assert root.findtext('description') == EXPECTED_DESCRIPTION
    assert setup['description'] == EXPECTED_DESCRIPTION

    assert root.findtext('license') == EXPECTED_LICENSE
    assert setup['license'] == EXPECTED_LICENSE

    maintainer = root.find('maintainer')
    assert maintainer is not None
    assert maintainer.text == EXPECTED_MAINTAINER
    assert setup['maintainer'] == EXPECTED_MAINTAINER


def test_package_declares_runtime_dependencies():
    """Declare ROS and system-Python imports through package.xml."""
    assert REQUIRED_DEPENDENCIES <= xml_values('depend')
    assert REQUIRED_EXEC_DEPENDENCIES <= xml_values('exec_depend')


def test_metadata_contains_no_placeholders():
    """Reject reintroduction of generated package placeholders."""
    combined = (
        PACKAGE_XML.read_text(encoding='utf-8')
        + SETUP_PY.read_text(encoding='utf-8')
    ).lower()

    assert 'todo:' not in combined
    assert 'license declaration' not in combined
    assert 'package description' not in combined


def test_repository_has_mit_license_and_install_contract():
    """Keep licensing and clean-checkout setup visible at repository level."""
    license_text = LICENSE_FILE.read_text(encoding='utf-8')
    readme = README.read_text(encoding='utf-8')

    assert license_text.startswith('MIT License')
    assert 'Copyright (c) 2026 Francisco Carreira Tavares' in license_text

    assert '## Clean-checkout installation' in readme
    assert 'rosdep install' in readme
    assert 'tools/thesis_build.sh' in readme
    assert 'Hailo runtime is platform-specific' in readme
