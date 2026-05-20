# TIM-V2 Current Status Summary

Date: 2026-05-20

## Current Conclusion

TIM-V2 has separated two different failure classes:

1. **LOST-state reacquisition failure**
   - The selected target is no longer locked.
   - The correct target may be present but not rank 0.
   - TIM-V2K helps here.

2. **wrong-LOCKED persistence failure**
   - TIM remains confidently locked on the wrong person.
   - The correct target has re-entered under a different tracker ID.
   - TIM-V2K does not help here.
   - TIM-V2M partially helps but is too blunt.

## TIM-V2K Result

TIM-V2K implements rank-aware appearance reacquisition from LOST/UNCERTAIN.

It is implemented in the core TIM module, exposed in the ROS target-memory node, and disabled by default.

Status:

- core implementation: done
- ROS parameters: done
- unit tests: done
- replay hooks: done
- useful for LOST-state reacquisition
- not sufficient for wrong-LOCKED persistence

## TIM-V2M Result

TIM-V2M tested armed wrong-LOCKED suppression.

Best useful result on hard-reentry:

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.554 | 0.264 | 0.182 |

It reduced wrong-target duration but did not meet the practical target:

- correct >= 0.55
- wrong <= 0.25
- lost <= 0.25

Conclusion:

> TIM-V2M should not be implemented live in its current form.

## Main Technical Finding

The current HSV appearance cue is useful but unreliable. In several hard intervals, appearance is either unavailable because geometry gates it out, or it cannot distinguish same-person duplicate fragments.

The strongest current design direction is:

> keep TIM-V2K for LOST-state reacquisition, but do not expect it to solve wrong-LOCKED persistence.

## Next Research Step

The next improvement should focus on a better identity cue or a more specific wrong-LOCKED detector.

Recommended path:

1. Keep TIM-V2K as the implemented candidate.
2. Do not implement TIM-V2M yet.
3. Develop a stronger appearance/identity signal:
   - frozen upper-body template,
   - better crop policy,
   - or tiny learned embedding.
4. Re-test wrong-LOCKED suppression only after identity evidence improves.

## Practical Next Action

Prepare a supervisor update explaining:

- TIM-V2K works for one failure class.
- TIM-V2M exposed the remaining failure class.
- The next contribution should be stronger target identity evidence, not more threshold tuning.
