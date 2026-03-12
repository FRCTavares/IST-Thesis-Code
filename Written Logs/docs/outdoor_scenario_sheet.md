# Outdoor Scenario Sheet

**Purpose:** Standard test scenarios for outdoor perception validation.

**Scope:** Perception-only tests (no flight authority yet).

---

## Scenario 1: Single Person, Simple Motion

**Objective:** Validate basic target lock stability with slow, predictable motion.

**Setup:**
- One person in frame
- Start centered in camera view
- Distance: 3-5 meters

**Actions:**
1. Stand still for 10 seconds (baseline lock)
2. Small left motion (~1 meter) and stop
3. Small right motion (~1 meter) and stop
4. Small forward motion (~0.5 meter) and stop
5. Small backward motion (~0.5 meter) and stop
6. Return to center

**Expected:**
- Target lock remains stable
- Bounding box tracks smoothly
- No jumps or flickering
- `/target` publishes consistently at ~10-15 Hz

**Duration:** ~1 minute

---

## Scenario 2: Two People

**Objective:** Validate target selection consistency with multiple detections.

**Setup:**
- Two people in frame
- Both visible and moving slightly

**Actions:**
1. Both stand still (observe initial lock)
2. Selected target moves left/right
3. Non-selected target moves in front briefly
4. Selected target returns to center

**Expected:**
- Selected target ID remains consistent
- Tracker maintains lock on correct person
- No unexpected target switches

**Observations:**
- Note any target ID switches
- Note quality score behavior

**Duration:** ~1-2 minutes

---

## Scenario 3: Short Occlusion

**Objective:** Validate reacquisition behavior after brief occlusion.

**Setup:**
- One target person
- One occluding person or obstacle

**Actions:**
1. Target visible and locked
2. Target briefly passes behind occluding person (~2 seconds)
3. Target reappears on other side
4. Repeat 2-3 times

**Expected:**
- Tracker maintains ID through brief occlusion
- Reacquisition happens within 1-2 frames
- No track fragmentation

**Observations:**
- Note reacquisition time
- Note whether target ID changes
- Note quality score drop during occlusion

**Duration:** ~1-2 minutes

---

## Scenario 4: Larger Motion

**Objective:** Validate lock stability with faster, more dynamic motion.

**Setup:**
- One person in frame
- More space for motion

**Actions:**
1. Start centered
2. Walk left across frame (~3 meters)
3. Walk right across frame (~3 meters)
4. Walk forward toward camera (~2 meters)
5. Walk backward away from camera (~2 meters)
6. Faster left/right motion (not running, but brisk walk)

**Expected:**
- Tracker maintains lock during continuous motion
- Bounding box tracks accurately
- Detection cadence remains stable

**Observations:**
- Note any lock losses
- Note detection rate during fast motion
- Note bounding box jitter or lag

**Duration:** ~2 minutes

---

## Scenario 5: Edge Cases (Optional)

**Objective:** Test boundary conditions and failure modes.

**Setup:**
- One person in frame

**Actions:**
1. Target moves to edge of frame and stops
2. Target partially exits frame
3. Target fully exits frame and returns
4. Target moves very close to camera (< 1 meter)
5. Target moves far from camera (> 10 meters)

**Expected:**
- System handles edge cases gracefully
- No crashes or hangs
- Clean loss and reacquisition behavior

**Observations:**
- Note when target is lost
- Note reacquisition behavior
- Note any anomalies

**Duration:** ~2-3 minutes

---

## Post-Scenario Notes Template

**Scenario:** ___________  
**Date:** ___________  
**Bag name:** ___________  
**Duration:** ___________  

**Results:**
- Lock stability: stable / occasional loss / frequent loss
- Reacquisition: fast / slow / failed
- Detection rate: ~___ Hz
- Quality scores: typical range ___________

**Issues:**
- ___________

**Next steps:**
- ___________
