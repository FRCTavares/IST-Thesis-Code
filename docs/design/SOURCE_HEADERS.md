# Source header standard

Last reviewed: 2026-10-04

## Purpose

Every maintained source file should identify its engineering role and its
attribution before the implementation. Keep the purpose specific to the file;
explain detailed inputs, outputs and constraints in the existing module docstring.

## Project code

Use the following comment block for Python, shell, ROS message definitions,
CMake, YAML, package configuration and host-service assets:

```text
# Thesis-Code
# Purpose: Describe what this file does in one concrete sentence.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
```

Retain a shell or Python shebang as the first line and retain any Python encoding
declaration before the block. Use an XML comment after the package XML processing
instructions. Comments must not change executable statements, configuration
values, ROS fields or existing documentation.

## Upstream work

For the generated Open Source Robotics Foundation ament tests, identify their
purpose and credit `Thesis integration: Francisco Tavares`. Preserve the original
copyright and Apache-2.0 notice. Do not label those templates as entirely original
MIT code. Project ownership does not replace attribution to external tracker
algorithms, inference libraries or model authors.

## Exclusions

Historical source/evidence copies under docs and reports retain their original
bytes and hashes. Test fixtures, model binaries, JSON/CSV data and empty ament
resource markers are data or provenance artifacts, rather than maintained code
requiring a comment block. Do not insert comments into formats that reject them.
The audit lists these exclusions explicitly.

## Evidence and reproduction

A comment-only header changes a file's SHA-256 even when its executable content
is identical. Historical manifests and source commits remain the authorities for
research reproduction. The delivery audit retains before/after hashes and checks
that existing Python syntax trees, configuration values and message fields are
unchanged. The documented delivery checkout is not a replacement for a frozen
research revision. Do not refresh evidence hashes to make a new checkout appear
to be its historical source.

## Verification

Run from the repository root:

```bash
python3 tools/analysis/check_source_headers.py
python3 tools/analysis/check_source_headers.py --json analysis_out/source_header_audit.json
```

The audit reads maintained tracked files and unignored new source files. It does
not load ROS, run the live stack or connect to hardware.
