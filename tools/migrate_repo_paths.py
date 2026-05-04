#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path.cwd()

EXCLUDED_DIR_NAMES = {
    ".git", ".venv", "venv", "env", "ENV",
    "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "venv_hailo_rpi_examples",
    "site-packages",
}

EXCLUDED_PATH_PREFIXES = (
    ("ros2_ws", "build"),
    ("ros2_ws", "install"),
    ("ros2_ws", "log"),
    ("user-interface", "node_modules"),
    ("deprecated", "hailo-rpi5-examples"),
    ("deprecated", "pi-ai-kit-ubuntu"),
)

TEXT_SUFFIXES = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".toml",
    ".py", ".sh", ".bash", ".zsh", ".xml", ".launch",
    ".ts", ".tsx", ".js", ".jsx", ".css", ".html",
}

TEXT_NAMES = {".gitignore", "README", "RUNBOOK"}

THIS_SCRIPT = Path("tools/migrate_repo_paths.py")

REPLACEMENTS = [
    ("/home/francisco/Desktop/Thesis-Code/datasets/", "/home/francisco/Desktop/Thesis-Code/data/datasets/"),
    ("/home/francisco/Desktop/Thesis-Code/reports/", "/home/francisco/Desktop/Thesis-Code/artifacts/reports/"),
    ("/home/francisco/Desktop/Thesis-Code/bags/", "/home/francisco/Desktop/Thesis-Code/artifacts/bags/"),
    ("/home/francisco/Desktop/Thesis-Code/figures/", "/home/francisco/Desktop/Thesis-Code/artifacts/figures/"),
    ("/home/francisco/Desktop/Thesis-Code/Written Logs/", "/home/francisco/Desktop/Thesis-Code/docs/written_logs/"),

    (re.compile(r"(?<!data/)datasets/"), "data/datasets/"),
    (re.compile(r"(?<!artifacts/)reports/"), "artifacts/reports/"),
    (re.compile(r"(?<!artifacts/)bags/"), "artifacts/bags/"),
    (re.compile(r"(?<!artifacts/)figures/"), "artifacts/figures/"),
    ("Written Logs/", "docs/written_logs/"),
    ("Written Logs", "docs/written_logs"),
]


def is_under_prefix(rel: Path, prefix: tuple[str, ...]) -> bool:
    return len(rel.parts) >= len(prefix) and rel.parts[:len(prefix)] == prefix


def should_skip(path: Path, include_artifacts: bool) -> bool:
    if path.is_dir() or path.is_symlink():
        return True

    rel = path.relative_to(ROOT)

    if rel == THIS_SCRIPT:
        return True

    if rel.parts and rel.parts[0] == "artifacts" and not include_artifacts:
        return True

    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
        return True

    if any(is_under_prefix(rel, prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return True

    return not (path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES)


def rewrite_text(text: str) -> str:
    out = text
    for old, new in REPLACEMENTS:
        if isinstance(old, str):
            out = out.replace(old, new)
        else:
            out = old.sub(new, out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-artifacts", action="store_true")
    args = parser.parse_args()

    changed = []

    for path in ROOT.rglob("*"):
        if should_skip(path, include_artifacts=args.include_artifacts):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        new_text = rewrite_text(text)

        if new_text != text:
            rel = path.relative_to(ROOT)
            changed.append(rel)
            if args.apply:
                path.write_text(new_text, encoding="utf-8")

    print(f"[{'APPLY' if args.apply else 'DRY RUN'}] files changed: {len(changed)}")
    for rel in changed:
        print(rel)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
