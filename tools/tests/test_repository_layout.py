"""Structural contracts for the repository root.

Keeps new root-level tracked files and directories deliberate. Derived from
tracked Git state, never a local ``ls``, so ignored local directories such as
``data/``, ``figures/``, ``thesis_env/`` and ``.pytest_cache/`` do not affect
these tests.

See docs/design/README_STANDARD.md for the folder-README convention.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_ROOT_FILES = {".envrc", ".gitignore", "LICENSE", "README.md"}

# Deliberate tracked architectural root directories.
ARCHITECTURAL_ROOT_DIRECTORIES = {
    "artifacts",
    "bags",
    "data",
    "docs",
    "models",
    "reports",
    "ros2_ws",
    "tools",
}


def _tracked_paths() -> list[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def test_only_the_intended_files_are_tracked_at_the_repository_root():
    root_files = {p for p in _tracked_paths() if "/" not in p}
    assert root_files == ALLOWED_ROOT_FILES


def test_tracked_root_directories_are_the_intended_architecture():
    root_dirs = {p.split("/", 1)[0] for p in _tracked_paths() if "/" in p}
    assert root_dirs == ARCHITECTURAL_ROOT_DIRECTORIES


def test_every_architectural_root_directory_has_a_readme():
    for name in sorted(ARCHITECTURAL_ROOT_DIRECTORIES):
        assert (REPO_ROOT / name / "README.md").is_file(), name


STORAGE_ROOT_DIRECTORIES = {
    "artifacts",
    "bags",
    "data",
    "reports",
}


def test_storage_root_readmes_are_reviewed():
    pattern = re.compile(
        r"^Last reviewed: \d{4}-\d{2}-\d{2}$",
        re.MULTILINE,
    )

    for name in sorted(STORAGE_ROOT_DIRECTORIES):
        path = REPO_ROOT / name / "README.md"
        text = path.read_text(encoding="utf-8")
        assert pattern.search(text), name


def test_root_readme_follows_the_documentation_standard():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert _first_heading(text) == "# Thesis-Code"
    assert re.search(r"^Last reviewed: \d{4}-\d{2}-\d{2}$", text, re.MULTILINE)


def test_no_generated_noise_is_tracked():
    for path in _tracked_paths():
        assert "__pycache__/" not in path, path
        assert not path.endswith((".pyc", ".pyo")), path
        assert Path(path).name != "hailort.log", path
        assert not path.startswith("log/"), path
