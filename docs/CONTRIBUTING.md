# Contributing

Last reviewed: 2026-10-15

## Before you push

```bash
python3 -m pytest -q -p no:cacheprovider tools/tests            # tooling, launcher and documentation contracts
cd ros2_ws && colcon test && colcon test-result --verbose       # ROS packages
python3 tools/analysis/check_source_headers.py                  # source-header audit
```

Some launcher tests need Linux bash 4+; run them on the Pi, not on macOS.

## Changing things

- **Canonical TIM-MARS parameters** live only in
  `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`; the launcher never
  copies thresholds onto the command line (a test enforces this).
- **Control authority:** the controller consumes `/target_memory_mars` only. Do
  not wire raw `/target`, tracker or detector output to the controller.
- **Launcher options** are defined in `tools/lib/live_cli.sh` and documented in
  `tools/lib/live_usage.sh`; update both, plus `docs/OPERATIONS.md` if the
  option matters to operators.
- **Models:** changing a file in `models/` means updating its hash in
  `models/README.md` and `tools/setup/check_delivery_environment.py`.
- Never commit recordings, `thesis_env/`, `ros2_ws/{build,install,log}`, Wi-Fi
  credentials, Tailscale keys or SSH keys.

## Documentation rules

- Each top-level folder has a `README.md` that starts with `# <folder path>` and a
  `Last reviewed: YYYY-MM-DD` line, then *Purpose*, *Contents* and *Rules*. It
  names what lives there and links to deeper docs; it does not duplicate them.
- Procedures belong in `docs/`, not in folder READMEs. Experiment diaries,
  audit history and changelogs belong in Git history.
- Keep one place per fact: dataflow in `docs/ARCHITECTURE.md`, run commands in
  `docs/OPERATIONS.md`, field procedure in `docs/flight/field_day_runbook.md`.
  Link instead of copying.
- Paths written in backticks in the core docs are checked by
  `tools/tests/test_documentation_references.py`; Markdown links are checked
  everywhere.

## Source headers

Maintained source files start with a short comment block: project name,
one-line purpose, author, copyright, SPDX licence and the MIT notice (see any
file under `tools/` for the exact form). Generated files, data, fixtures, model
binaries and empty ament markers are exempt. Third-party templates keep their
original notices.
