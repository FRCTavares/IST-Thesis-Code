# Setup Tools

This folder contains host/runtime setup helpers for the thesis perception stack.

These scripts are operational setup aids. They should be used carefully because
they may download packages, install Python wheels, or modify local runtime
folders.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `install_host_hailo_bindings.sh` | Support workflow | Installs host-side Hailo Python bindings into a selected virtualenv when compatible wheels are available. |
| `setup_local_tappas_runtime.sh` | Support workflow | Prepares a local non-root TAPPAS runtime tree for single-process perception mode. |

## Usage policy

Prefer documented environment variables and explicit paths when running setup
scripts. Do not run them during evaluation unless the runtime environment
actually needs repair or recreation.

For normal replay/evaluation work, these scripts should not be needed.
