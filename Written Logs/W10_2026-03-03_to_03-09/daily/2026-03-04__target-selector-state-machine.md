# Daily Log — 2026-03-04 — Make Target Selection Robust and Measurable (Week 10, Day 2)

## Goal
Make target selection robust and measurable. By end of day, target selection survives ambiguity and reacquires correctly with minimal switches.

**Target outcome:**
- Multi-feature score function (not just "time alive only")
- Explicit state machine: SEARCH → LOCKED → LOST → REACQUIRED
- Events and counters: lost_flag, reacquired_flag, lock_id_changes_total
- Ablation report showing improvement over time_alive baseline

**Critical insight:** "Track multiple and select one" + "choose ID by time alive" is NOT enough for outdoor multi-person scenes.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, all tests use bag replay. Camera integration planned for Week 11. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Target environment | Outdoor tennis court (multi-person, occlusion, ambiguity) |
| Current target selector | Time alive only (insufficient for robustness) |
| Goal | Multi-feature scoring + state machine for stability |

---

## Work Plan

### A) Replace "time alive only" with a score function
Design and implement a multi-feature candidate scoring function.

- [ ] Define score function components:
  - **time_alive_s:** Stability indicator (prefer established tracks)
  - **last_seen_dt:** Freshness (penalize stale tracks)
  - **bbox_area:** Distance proxy (prefer nearer if intended)
  - **motion_consistency:** Low jerk/acceleration (smooth motion preferred)
  - **appearance_similarity:** Match to locked target appearance (if available)
- [ ] Implement score calculation:
  ```python
  score = w_time * time_alive_norm 
        + w_fresh * freshness_norm 
        - w_dist * distance_norm 
        + w_motion * consistency_norm 
        + w_app * appearance_sim
  ```
- [ ] Normalize all features to [0, 1] range
- [ ] Make weights configurable via yaml
- [ ] Test on multi-person bags
- **Deliverable:** Updated `target_selector_node.py` with multi-feature scoring
- Notes: *(fill)*

**Feature implementation details:**

| Feature | Calculation | Normalization | Weight |
|---------|-------------|---------------|--------|
| time_alive | Track age in seconds | Sigmoid or clip to [0, 10s] | w_time = 0.3 |
| freshness | `1 / (1 + last_seen_dt)` | Already [0, 1] | w_fresh = 0.2 |
| distance | `1 / sqrt(bbox_area)` | Relative to typical area | w_dist = 0.2 |
| motion | `1 / (1 + jerk)` | Based on velocity variance | w_motion = 0.15 |
| appearance | Cosine similarity | Already [-1, 1] → [0, 1] | w_app = 0.15 |

**Tuning strategy:**
- Start with equal weights, adjust based on failure modes
- Increase w_time for stability in crowded scenes
- Increase w_app when occlusion/ambiguity high

### B) Add explicit state machine
Implement a 4-state FSM for target management.

- [ ] Define states:
  - **SEARCH:** No target locked, evaluating all candidates with score function
  - **LOCKED:** Tracking chosen ID, publish `/target`
  - **LOST:** Target temporarily missing (< 1s), attempt reacquisition on same ID
  - **REACQUIRED:** Transition event when target found again after LOST
- [ ] Implement state transitions:
  - SEARCH → LOCKED: When best candidate score > threshold
  - LOCKED → LOST: When target ID missing from /tracks
  - LOST → LOCKED: If original ID reappears within timeout
  - LOST → SEARCH: If timeout exceeded (1s default)
  - LOCKED → SEARCH: If user requests new target or confidence drop
- [ ] Add state to `/target` message or create `/target_state` topic
- [ ] Log state transitions for analysis
- **Deliverable:** FSM implementation in `target_selector_node.py`
- Notes: *(fill)*

**State machine diagram:**
```
            score > threshold
    SEARCH ──────────────────→ LOCKED
      ↑                           │
      │ timeout                   │ target missing
      │                           ↓
      └────────────────────── LOST
            ID reappears → REACQUIRED → LOCKED
```

**Parameters:**
- `lock_threshold`: 0.7 (score threshold to lock)
- `lost_timeout_s`: 1.0 (max time in LOST before returning to SEARCH)
- `reacquire_window_s`: 0.5 (prioritize original ID within this window)

### C) Emit events and counters
Add diagnostic outputs for control and analysis.

- [ ] Extend `/target` message or create separate `/target_events` topic:
  - `lost_flag`: True on transition LOCKED → LOST
  - `reacquired_flag`: True on transition LOST → LOCKED
  - `lock_id_changes_total`: Cumulative counter of ID switches
  - `current_state`: SEARCH | LOCKED | LOST | REACQUIRED
  - `confidence`: Current score of locked target
- [ ] Publish events on state transitions
- [ ] Log all events to CSV for offline analysis
- [ ] Add to `/timing_tracker` or separate diagnostics topic
- **Deliverable:** Enhanced target selector with events
- Notes: *(fill)*

**Message schema (proposed):**
```python
# TargetState.msg
std_msgs/Header header
uint8 state  # 0=SEARCH, 1=LOCKED, 2=LOST, 3=REACQUIRED
bool lost_flag
bool reacquired_flag
uint32 lock_id_changes_total
float32 confidence
int32 target_id  # -1 if no target
```

### D) Run ablation study
Compare old (time_alive only) vs new (multi-feature + FSM) target selector.

- [ ] Run evaluation suite on both versions:
  - Scenario: clean
  - Scenario: occlusion_1s
  - Scenario: ambiguous_crossing (if available)
- [ ] Compare metrics:
  - Switches per minute
  - False reacquisitions (wrong ID after occlusion)
  - Lock stability (% time in LOCKED state)
  - Average confidence of locked target
- [ ] Generate comparison report
- **Deliverable:** `reports/compare/W10_target_selector_ablation.md`
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] Multi-feature score function implemented with configurable weights
- [ ] State machine (SEARCH/LOCKED/LOST/REACQUIRED) implemented
- [ ] Events and counters added to target selector output
- [ ] Ablation report comparing old vs new selector

### Ablation study results

**Comparison table:**

| Metric | Before (time_alive only) | After (multi-feature + FSM) | Improvement |
|--------|--------------------------|----------------------------|-------------|
| Switches per minute | — | — | — |
| False reacquisitions | — | — | — |
| Lock stability (% locked) | — | — | — |
| Avg confidence | N/A | — | New metric |
| Mean time in LOST | — | — | — |

**Scenario breakdown:**

| Scenario | Metric | Before | After | Notes |
|----------|--------|--------|-------|-------|
| clean | Switches/min | — | — | |
| occlusion_1s | Reacquire time p95 | — | — | |
| occlusion_1s | Correct ID % | — | — | % of reacquisitions that locked correct ID |
| ambiguous_crossing | Switches/min | — | — | |

### State transition statistics

From test bag (duration: *(fill)* s):
- SEARCH time: *(fill)* s (*(fill)* %)
- LOCKED time: *(fill)* s (*(fill)* %)
- LOST time: *(fill)* s (*(fill)* %)
- Lost events: *(fill)* (*(fill)* per minute)
- Reacquired events: *(fill)* (success rate: *(fill)* %)
- ID changes: *(fill)* total

**Conclusion:**
*(Fill after analysis - does multi-feature scoring + FSM improve robustness? Which features contribute most?)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Weight tuning requires multi-person bags (limited availability without camera)
- Appearance similarity requires appearance descriptor (Day 05 dependency)
- Threshold tuning (lock_threshold, lost_timeout) may need outdoor adjustment

---

## Next steps (Day 05)
- [ ] Implement appearance descriptor v1 (HSV histogram + gradient)
- [ ] Integrate appearance into association cost
- [ ] Use appearance similarity in target selector score function
- [ ] Run eval suite with appearance enabled

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Ablation report: `../../reports/compare/W10_target_selector_ablation.md`
- Config: `../../config/target_selector.yaml`
