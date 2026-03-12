# Questions for Supervisors - W12 Preparation

**Ask these BEFORE Tuesday session to avoid surprises**

---

## Critical Safety Questions

### 1. RC Override and Manual Control
- [ ] **How do I immediately take manual control from MAVROS?**
  - Which switch/stick on RC transmitter?
  - What flight mode should RC be in?
  - Should I practice this before Tuesday?

- [ ] **What happens if I switch to manual while MAVROS is commanding?**
  - Does it override cleanly?
  - Any dangerous transition behavior?

### 2. Arming and Disarming
- [ ] **What is the arm sequence for this vehicle?**
  - Even though I won't arm, I should know it
  
- [ ] **Emergency disarm procedure?**
  - If vehicle arms accidentally, how to disarm immediately?
  - Does pulling throttle stick down work?
  - Is there a kill switch?

- [ ] **What LEDs/indicators show armed state?**
  - Pixhawk LED patterns
  - Any audible warnings?

### 3. Flight Modes for MAVROS
- [ ] **Which flight mode accepts MAVROS velocity commands?**
  - Should be GUIDED mode for ArduPilot
  - How do I set this mode? (via RC? GCS? Code?)
  
- [ ] **Can I switch modes safely via RC during testing?**
  - What mode should I use for safest ground testing?
  - STABILIZE for manual, GUIDED for MAVROS?

- [ ] **What mode does vehicle default to on boot?**
  - Important to know initial state

### 4. Failsafes and Safety Features
- [ ] **What happens if RC signal is lost?**
  - RTL (Return to Launch)?
  - LAND?
  - Hover in place?
  - Can I test this with RC off?

- [ ] **What happens if battery gets critically low?**
  - Voltage threshold for warning?
  - Automatic landing behavior?
  
- [ ] **What happens if MAVROS disconnects while commanding?**
  - Does vehicle hover?
  - Switch to RC?
  - Automatic failsafe?

- [ ] **Can failsafes be triggered manually for safe testing?**
  - Good to test behavior before real failure

### 5. Network and Pixhawk Configuration
- [ ] **What is the Pixhawk Ethernet IP address?**
  - Default 192.168.1.1 or different?
  - How to verify/change if needed?

- [ ] **How is the Pi5 connected to Pixhawk network?**
  - Direct Ethernet cable?
  - Through a switch?
  - Any network configuration required on Pi5?

### 6. Command Limits and Tuning
- [ ] **What are safe velocity command limits for this vehicle?**
  - Max forward/lateral velocity (m/s)?
  - Max yaw rate (rad/s)?
  - Are these already configured in firmware?

- [ ] **Recommended conservative values for first tests?**
  - Should I start with 0.1 m/s max?
  - Should I limit yaw to 0.1 rad/s?

- [ ] **Is there a geofence or other position limits configured?**
  - What happens if vehicle tries to exceed them?

### 7. Battery and Power
- [ ] **Battery voltage when fully charged?**
  - 4S LiPo nominal: 14.8V, max: 16.8V
  - Verify for your specific battery

- [ ] **At what voltage should I stop testing?**
  - Don't over-discharge
  - Typical cutoff: 3.3-3.5V per cell (13.2-14.0V for 4S)

- [ ] **How long can system run on this battery?**
  - For planning session duration
  - Pi5 + Pixhawk + camera power draw

### 8. Emergency Procedures
- [ ] **If vehicle starts behaving unexpectedly, what's the sequence?**
  1. RC override immediately?
  2. Power disconnect?
  3. Something else?

- [ ] **Who should I contact if something goes wrong during testing?**
  - Phone number accessible
  - Are you available on-call Tuesday/Thursday?

### 9. Previous Testing History
- [ ] **Has this vehicle been flown recently?**
  - Any known issues?
  - Last calibration date?

- [ ] **Has MAVROS been used with this vehicle before?**
  - Any lessons learned?
  - Known gotchas?

### 10. Field Access and Logistics
- [ ] **Exact location for testing on football field?**
  - Where's the safe area?
  - Any obstacles or keep-out zones?

- [ ] **Is the football field in use Tuesday/Thursday afternoons?**
  - Confirm no conflicts with sports teams

- [ ] **Where should I set up (table, power access if needed)?**

---

## Information to Document

### For Your Reference (ask to write down or take photos):
- [ ] RC transmitter model and basic controls
- [ ] Pixhawk firmware version
- [ ] ArduCopter vehicle type and frame configuration
- [ ] Any custom parameters or modifications
- [ ] Emergency contact numbers

### Before Tuesday
- [ ] Practice RC override (if transmitter available before session)
- [ ] Review vehicle documentation if available
- [ ] Understand at least: arm/disarm, mode switching, emergency stop

---

## Priority Questions (If Time Limited)

**MUST ASK (Can't proceed safely without):**
1. RC override procedure
2. Which mode for MAVROS (GUIDED?)
3. Pixhawk Ethernet IP
4. Emergency disarm procedure
5. Safe velocity command limits

**SHOULD ASK (Very helpful):**
6. Failsafe behaviors
7. Battery voltage guidelines
8. Emergency contact

**NICE TO KNOW (Can learn during testing):**
9. Previous testing history
10. Exact field location details

---

**Ask these questions:** Before Monday evening if possible, definitely before Tuesday session  
**Document answers in:** Session plan or safety checklist before Tuesday
