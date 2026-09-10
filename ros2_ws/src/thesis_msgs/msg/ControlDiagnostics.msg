# Issue #74 controller decision + bounded-recovery diagnostics.
#
# One message is published for every command the controller emits on its
# cmd topic (`/control_ref/cmd_vel`), sharing that command's header.stamp so
# the two topics join 1:1 on the timestamp. Instrumentation only: publishing
# this message never influences the command path, and it supplements -- does
# not replace -- the controller text log.

std_msgs/Header header

# --- Resolved controller decision for this command ---------------------------
# mode:   NORMAL_FOLLOW | HOVER | RECOVERY_YAW_ONLY | NO_TARGET | AMBIGUITY_HOLD
# reason: policy reason token, or a code-path token for the non-policy zero
#         emissions (no_target_msg, tim_status_parse_error,
#         rejected_authority_epoch:<reason>, authority_epoch_reset,
#         authority_status_only, node_shutdown, ambiguity_hold).
string mode
string reason

# --- Target / TIM authority state feeding the decision -----------------------
string tim_state              # LOCKED | LOST | REACQUIRED | ... | NO_STATUS
string tim_control_mode       # NORMAL | CONFIRM | ... | NO_STATUS
int64 selection_generation    # -1 when no TIM status is held
string selection_session_id   # "" when no TIM status is held
bool status_fresh             # TIM authority status within the freshness gate
bool target_fresh             # controller-authoritative target within the gate
bool target_valid             # invalid_reason is None AND status target id match
string target_invalid_reason  # "" when valid; controller-side reason otherwise
int32 target_id               # /target_memory_mars id fed to the policy (0=none)

# --- Recovery configuration (resolved parameters, constant per run) ----------
bool recovery_enabled
float64 recovery_yaw_rate
float64 recovery_max_duration_s
float64 recovery_max_integrated_yaw_rad
float64 recovery_last_trusted_max_age_s

# --- Recovery runtime state -------------------------------------------------
bool recovery_active
string recovery_direction     # left | right | center | unknown
float64 recovery_elapsed_s
float64 recovery_integrated_yaw_rad
float64 recovery_budget_remaining_rad

# --- Last-trusted observation feeding recovery -----------------------------
bool last_trusted_valid              # a last-trusted observation has been stored
float64 last_trusted_age_s           # NaN when none
float64 last_trusted_horizontal_error  # NaN when none
int64 last_trusted_generation        # -1 when none
bool recovery_history_consumed       # the stored observation was already used

# --- Final shaped command published on the cmd topic this tick -------------
float64 command_vx
float64 command_vy
float64 command_yaw_z
bool command_saturated_yaw
