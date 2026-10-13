#!/usr/bin/env python3
# Thesis-Code
# Purpose: Audit purpose and attribution headers on maintained source files.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""Check maintained source coverage without importing runtime or hardware code.

Frozen evidence, fixture data and generated package markers are classified as
exclusions rather than rewritten. Use --json PATH to retain the coverage report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SUFFIXES = {
    '.py', '.sh', '.bash', '.c', '.cc', '.cpp', '.h', '.hpp', '.msg', '.srv',
    '.action', '.yaml', '.yml', '.xml', '.cfg', '.conf', '.service', '.timer',
    '.default', '.cmake', '.toml', '.js', '.ts', '.tsx', '.css', '.html',
}
SPECIAL_NAMES = {'.envrc', 'CMakeLists.txt', 'Dockerfile', '90-thesis-pixhawk-disconnect'}


def classify(relative: str) -> tuple[bool, str]:
    """Separate maintained implementation from immutable evidence and data."""
    path = Path(relative)
    if relative.startswith(('docs/', 'reports/')) and path.suffix in SOURCE_SUFFIXES:
        return False, 'Frozen or historical research/evidence artifact; retain original bytes.'
    if relative.startswith(('tools/', 'ros2_ws/src/')) or relative == '.envrc':
        if '/fixtures/' in relative:
            return False, 'Test fixture data; preserve its source format and values.'
        if '/resource/' in relative:
            return False, 'Empty ament package marker; must remain empty.'
        if (path.suffix in SOURCE_SUFFIXES or path.name in SPECIAL_NAMES
                or path.name.startswith('requirements-') and path.suffix == '.txt'):
            return True, 'Maintained source, test, configuration or service asset.'
        if path.suffix in {'.json', '.csv', '.txt'}:
            return False, 'Machine-readable template/data; no comment header in its format.'
    return False, 'Documentation, binary asset or non-source file.'


def audit(root: Path = ROOT) -> dict:
    """Return a sorted, file-hashed inventory and every coverage failure."""
    result = subprocess.run(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
        cwd=root, check=True, capture_output=True,
    )
    paths = sorted(set(result.stdout.decode().split('\0')) - {''})
    files = []
    exclusions = []
    failures = []
    for relative in paths:
        include, reason = classify(relative)
        path = root / relative
        if not include:
            if reason != 'Documentation, binary asset or non-source file.':
                exclusions.append({'path': relative, 'reason': reason})
            continue
        if not path.is_file():
            failures.append({'path': relative, 'reason': 'Missing maintained file.'})
            continue
        data = path.read_bytes()
        header = '\n'.join(data.decode('utf-8').splitlines()[:25])
        upstream = 'Open Source Robotics Foundation' in header
        expected = 'Thesis integration: Francisco Tavares' if upstream else 'Author: Francisco Tavares'
        required = ['Thesis-Code', 'Purpose:', expected]
        required += ['Original copyright and Apache-2.0 licence are retained below.'] if upstream else [
            'Copyright (c) 2026 Francisco Carreira Tavares', 'SPDX-License-Identifier: MIT',
        ]
        missing = [value for value in required if value not in header]
        if missing:
            failures.append({'path': relative, 'missing': missing})
        files.append({
            'path': relative, 'sha256': hashlib.sha256(data).hexdigest(),
            'attribution': 'upstream integration' if upstream else 'project author',
        })
    return {
        'schema': 1, 'maintained_files': len(files), 'files': files,
        'exclusions': exclusions, 'failures': failures,
        'status': 'PASS' if not failures else 'FAIL',
    }


def main() -> int:
    """Print the coverage result and optionally save its JSON inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='Write the audited inventory to this path.')
    args = parser.parse_args()
    report = audit()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"{report['status']}: {report['maintained_files']} maintained files; "
          f"{len(report['failures'])} header failures.")
    for failure in report['failures']:
        print(json.dumps(failure))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
