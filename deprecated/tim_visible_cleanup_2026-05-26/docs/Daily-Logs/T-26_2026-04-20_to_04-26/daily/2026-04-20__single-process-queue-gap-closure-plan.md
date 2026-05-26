# Daily Plan - 2026-04-20 (Day 20) - Single-Process Queue-Gap Closure

## Context Carry-Over

- Single-process parity work significantly reduced tails versus old baseline.
- Latest validated run: `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r1`.
- Current main remaining limiter is backend queue delay (`container_queue_ms`) rather than pure infer compute.
- Next candidate knobs already wired in launcher:
  - `--perception-hailo-queue-buffers`
  - `--perception-hailo-videoconvert-off|on`

## Primary Objective

Reduce remaining queue latency in single-process mode while preserving throughput, workload comparability, and timing contract integrity.

## Step-by-Step Legacy-Parity Playbook

### Step 1) Lock parity target and acceptance gates

- [x] Use legacy as target envelope for this cycle:
  - `e2e_det_ms p95 <= 35 ms`
  - `container_queue_ms p95 <= 5 ms`
  - `infer_ms p95 <= 10 ms`
  - no throughput collapse versus current seqfix baseline
- [ ] Treat parity as achieved only if the target is met in 2 consecutive runs.

### Step 2) Freeze test conditions (apples-to-apples)

- [x] Keep same camera settings, scene type, and run duration for all compared runs.
- [x] Keep same stack composition (tracker/target/control on/off state fixed across runs).
- [x] Do not change multiple variables in the same candidate run.

### Step 3) Capture control runs first

- [x] Run one fresh legacy control (`legacy_r3`) to anchor today's comparison.
- [x] Run one fresh single-process seqfix control (`single_process_inline_owner_seqfix_r2`).
- [x] Validate both before touching candidate knobs.

### Step 4) Candidate A: reduce Hailo queue depth

- [x] Run single-process with `--perception-hailo-queue-buffers 1`.
- [x] Save run as `single_process_inline_owner_seqfix_q1_r1`.
- [x] Validate canonical metrics and invariants.

### Step 5) Candidate B: queue depth + videoconvert off

- [x] Run single-process with `--perception-hailo-queue-buffers 1 --perception-hailo-videoconvert-off`.
- [x] Save run as `single_process_inline_owner_seqfix_q1_vc0_r1`.
- [x] Validate canonical metrics and invariants.

### Step 6) Compare and enforce keep/drop rule

- [x] Build one comparison table for controls and both candidates.
- [x] Keep a candidate only if all are true:
  - lower `container_queue_ms p95/p50`
  - no meaningful `/timing` Hz regression
  - workload comparability pass (`detections_per_msg.mean`, `zero_ratio`)
  - validators and invariants pass

### Step 7) If both candidates fail, execute backend-path iteration

- [x] Apply one backend-path change focused only on queue wait (no broad refactor):
  - tighten internal buffering behavior near pre-hailonet queue
  - preserve freshest-frame semantics end-to-end
  - keep single owner submission model
- [x] Rebuild, re-run single candidate benchmark, and re-apply the same gates.

### Step 8) Freeze outcome

- [x] If a candidate passes, promote it as the new operational baseline.
- [ ] If no candidate passes, explicitly keep current seqfix baseline and record numeric reason.
- [x] Update week index and artefacts checklist with final status.

### Step 9) Command discipline (individual steps only)

- [x] Run one command per line for startup, collect, validate, and stop.
- [x] Avoid long chained one-liners during benchmarking.
- [x] Keep run labels deterministic and unique for traceability.

## 2026-04-19 Execution Outcome (Post-Reboot Continuation)

- `legacy_r3`: validated anchor control.
- `single_process_inline_owner_seqfix_r2`: validated single-process control.
- `single_process_inline_owner_seqfix_q1_r1`: valid run; not better than `q1_vc0`.
- `single_process_inline_owner_seqfix_q1_vc0_r1`: best observed candidate this cycle.
- `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r1`: post-reboot appsrc-cap follow-up run completed and validated.
- Backend-path iterations (drop):
  - `single_process_inline_owner_seqfix_q1_vc0_backendq_r1`
  - `single_process_inline_owner_seqfix_q1_vc0_ptsalign_r1`

Keep/drop verdict:

- Promote `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r1` as current operational single-process baseline.
- Keep drop decisions for both backend-path iteration variants above due to queue/e2e regressions vs `q1_vc0_r1`.
- Legacy parity remains open (largest gap remains `container_queue_ms`).

Post-reboot continuation completion note:

- Appsrc-cap variant (`max-buffers=1 leaky-type=downstream`) benchmark completed under q1+vc0 settings.
- Versus `single_process_inline_owner_seqfix_q1_vc0_r1`:
  - `container_queue_ms` median/p95 improved: `94.23/117.46 -> 87.74/102.03`
  - `e2e_det_ms` median/p95 improved: `113.83/140.38 -> 105.27/125.00`
  - `pub_dt_ms` median/p95 improved: `119.95/255.17 -> 104.65/215.91`
- Canonical validation: pass.
- Invariants: recurring `B.pub_dt_vs_det_out_fps_consistent` failures remain present (same class observed in prior runs).

Replicate status update (same config, `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r2`):

- Full 120s replicate completed with strong latency gains vs `appsrccap_r1`:
  - `container_queue_ms` p95 `102.03 -> 91.45`
  - `e2e_det_ms` p95 `125.00 -> 108.03`
  - `pub_dt_ms` p95 `215.91 -> 111.24`
- Canonical validation: pass.
- Invariants: recurring `B.pub_dt_vs_det_out_fps_consistent` failures remain present.
- Detection-load shift observed in this replicate (`detections_per_msg.mean` `1.03 -> 0.19`, `zero_ratio` `0.00 -> 0.821`) is attributed to an out-of-frame period during capture, not a pipeline regression.
- Decision discipline: accept `appsrccap_r2` as a valid replicate confirming latency improvement for the appsrc-cap variant.

## Exact Command Sequence (Copy/Paste)

### A) Session setup

```bash
cd /home/francisco/Desktop/Thesis-Code
```

```bash
source /home/francisco/Desktop/Thesis-Code/.venv/bin/activate
```

```bash
source /opt/ros/jazzy/setup.bash
```

```bash
source /home/francisco/Desktop/Thesis-Code/ros2_ws/install/setup.bash
```

### B) Legacy control run (`legacy_r3`)

```bash
stop
```

```bash
./tools/start_live_stack.sh --perception-mode legacy --infer-queue-size 1 --infer-workers 2
```

```bash
python3 tools/collect_live_timing_stats.py --duration 120 --run-label legacy_r3 --json-out artifacts/reports/timing/live_post_refactor/legacy_r3.json
```

```bash
python3 deprecated/tools/timing/validate_canonical_metrics.py --json artifacts/reports/timing/live_post_refactor/legacy_r3.json --require-target
```

```bash
python3 tools/check_live_timing_invariants.py --duration 10
```

```bash
stop
```

### C) Single-process seqfix replicate (`single_process_inline_owner_seqfix_r2`)

```bash
./tools/start_live_stack.sh --perception-mode single-process --infer-queue-size 1 --infer-workers 2
```

```bash
grep -E "ingress_mode|frame_queue_size|prepared_queue_size|num_workers|hailo_queue_max_buffers|hailo_use_videoconvert" ros2_ws/log/live_stack/latest/perception_pipeline.log || echo "No mode lines found"
```

```bash
python3 tools/collect_live_timing_stats.py --duration 120 --run-label single_process_inline_owner_seqfix_r2 --json-out artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_r2.json
```

```bash
python3 deprecated/tools/timing/validate_canonical_metrics.py --json artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_r2.json --require-target
```

```bash
python3 tools/check_live_timing_invariants.py --duration 10
```

```bash
stop
```

### D) Ablation A - queue buffers=1 (`single_process_inline_owner_seqfix_q1_r1`)

```bash
./tools/start_live_stack.sh --perception-mode single-process --infer-queue-size 1 --infer-workers 2 --perception-hailo-queue-buffers 1
```

```bash
grep -E "ingress_mode|frame_queue_size|prepared_queue_size|num_workers|hailo_queue_max_buffers|hailo_use_videoconvert" ros2_ws/log/live_stack/latest/perception_pipeline.log || echo "No mode lines found"
```

```bash
python3 tools/collect_live_timing_stats.py --duration 120 --run-label single_process_inline_owner_seqfix_q1_r1 --json-out artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_r1.json
```

```bash
python3 deprecated/tools/timing/validate_canonical_metrics.py --json artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_r1.json --require-target
```

```bash
python3 tools/check_live_timing_invariants.py --duration 10
```

```bash
stop
```

### E) Ablation B - queue buffers=1 + videoconvert off (`single_process_inline_owner_seqfix_q1_vc0_r1`)

```bash
./tools/start_live_stack.sh --perception-mode single-process --infer-queue-size 1 --infer-workers 2 --perception-hailo-queue-buffers 1 --perception-hailo-videoconvert-off
```

```bash
grep -E "ingress_mode|frame_queue_size|prepared_queue_size|num_workers|hailo_queue_max_buffers|hailo_use_videoconvert" ros2_ws/log/live_stack/latest/perception_pipeline.log || echo "No mode lines found"
```

```bash
python3 tools/collect_live_timing_stats.py --duration 120 --run-label single_process_inline_owner_seqfix_q1_vc0_r1 --json-out artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_r1.json
```

```bash
python3 deprecated/tools/timing/validate_canonical_metrics.py --json artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_r1.json --require-target
```

```bash
python3 tools/check_live_timing_invariants.py --duration 10
```

```bash
stop
```

### F) One-table comparison output

```bash
python3 - <<'PY'
import json
from pathlib import Path

base = Path('artifacts/reports/timing/live_post_refactor')
labels = [
  'legacy_r1', 'legacy_r2', 'legacy_r3',
  'single_process_inline_owner_r1',
  'single_process_inline_owner_seqfix_r1',
  'single_process_inline_owner_seqfix_r2',
  'single_process_inline_owner_seqfix_q1_r1',
  'single_process_inline_owner_seqfix_q1_vc0_r1',
]

def get(path, *keys, default=float('nan')):
  cur = path
  for k in keys:
    if not isinstance(cur, dict):
      return default
    cur = cur.get(k)
  try:
    return float(cur)
  except Exception:
    return default

rows = []
for label in labels:
  p = base / f'{label}.json'
  if not p.exists():
    continue
  with p.open('r', encoding='utf-8') as f:
    d = json.load(f)
  rows.append({
    'label': label,
    'e2e_p95': get(d, 'metrics', '/timing', 'e2e_det_ms', 'p95'),
    'queue_p95': get(d, 'metrics', '/timing', 'container_queue_ms', 'p95'),
    'queue_p50': get(d, 'metrics', '/timing', 'container_queue_ms', 'p50'),
    'infer_p95': get(d, 'metrics', '/timing', 'infer_ms', 'p95'),
    'pubdt_p95': get(d, 'metrics', '/timing', 'pub_dt_ms', 'p95'),
    'hz': get(d, 'topics', '/timing', 'hz'),
    'det_mean': get(d, 'detection_stream', 'detections_per_msg', 'mean'),
    'zero_ratio': get(d, 'detection_stream', 'detections_per_msg', 'zero_ratio'),
  })

print('label|e2e_p95|queue_p95|queue_p50|infer_p95|pubdt_p95|timing_hz|det_mean|zero_ratio')
for r in rows:
  print(
    f"{r['label']}|{r['e2e_p95']:.3f}|{r['queue_p95']:.3f}|{r['queue_p50']:.3f}|"
    f"{r['infer_p95']:.3f}|{r['pubdt_p95']:.3f}|{r['hz']:.3f}|{r['det_mean']:.3f}|{r['zero_ratio']:.3f}"
  )
PY
```

## Tomorrow To-Do (Priority Ordered)

### 1) Pre-run discipline and baseline lock

- [ ] Ensure no stale stack processes are running before each benchmark.
- [ ] Start from seqfix path and confirm active mode in logs (`ingress_mode=inline_worker_owner`).
- [ ] Collect one replicate baseline run: `single_process_inline_owner_seqfix_r2`.

### 2) Controlled ablation A - queue buffers

- [ ] Run single-process with `--perception-hailo-queue-buffers 1`.
- [ ] Collect timing JSON for run label `single_process_inline_owner_seqfix_q1_r1`.
- [ ] Validate canonical metrics/invariants for this run.

### 3) Controlled ablation B - queue buffers + videoconvert off

- [ ] Run single-process with `--perception-hailo-queue-buffers 1 --perception-hailo-videoconvert-off`.
- [ ] Collect timing JSON for run label `single_process_inline_owner_seqfix_q1_vc0_r1`.
- [ ] Validate canonical metrics/invariants for this run.

### 4) Comparison and decision gate

- [ ] Produce a single table comparing:
  - `legacy_r1/r2`
  - `single_process_inline_owner_r1`
  - `single_process_inline_owner_seqfix_r1/r2`
  - `single_process_inline_owner_seqfix_q1_r1`
  - `single_process_inline_owner_seqfix_q1_vc0_r1`
- [ ] Apply keep/drop gates:
  - queue p95/p50 improved
  - no meaningful `/timing` Hz regression
  - workload comparability pass
  - validators/invariants pass

### 5) Baseline freeze update

- [ ] If a candidate passes gates, record it as new operational baseline.
- [ ] If no candidate passes, explicitly retain current seqfix baseline and record why.
- [ ] Update week index and artefacts checklist with final verdict.

## Practical Timebox

- Block A: baseline replicate + mode verification
- Block B: queue-buffer ablation run + validation
- Block C: queue-buffer + videoconvert-off run + validation
- Block D: delta table + keep/drop decision
- Block E: write-up and baseline freeze note

## Definition of Done for 2026-04-20

At least one full ablation cycle is completed end-to-end (run, validation, comparison, decision), and the selected baseline status is explicitly recorded with numeric evidence.
