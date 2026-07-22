# Evidence Catalogue Tool

This directory owns the reproducible TIM-MARS evidence catalogue builder.

| Tool | Status | Purpose |
| --- | --- | --- |
| `build_tim_eval_catalogue.py` | Evidence workflow | Validates tracked report, annotation, model, configuration, and replay provenance before writing the canonical catalogue. |

Run from the repository root:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 tools/catalogue/build_tim_eval_catalogue.py --check
```

The builder intentionally contains exact evidence paths and SHA-256 values.
Unlike a convenience wrapper, these are validation inputs covered by
`tools/tests/test_tim_eval_catalogue.py`; a missing or changed artifact must
fail rather than silently select different evidence.
