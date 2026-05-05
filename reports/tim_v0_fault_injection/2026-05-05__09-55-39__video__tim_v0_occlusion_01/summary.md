# TIM-V0 Deterministic Fault-Injection Evaluation

- Bag: `/home/francisco/Desktop/Thesis-Code/artifacts/bags/live_camera/2026-05-05__09-55-39__video__tim_v0_occlusion_01`
- Selected ID before fault: 1
- Injected replacement ID after fault: 3
- Gap start: 28.00 s
- Gap duration: 2.00 s

## Post-fault validity

- Raw ID selector valid samples after fault start: 0/110
- TIM-V0 valid samples after fault start: 85/110

## Reacquisition

- TIM reacquired at t=30.01 s
- Time after reappearance: 0.01 s
- Reacquired ID: 3
- Quality: 0.825
- Reason: reacquired_candidate

## Interpretation

The raw selector follows only the original selected track ID. After the injected ID switch, it cannot recover because the selected ID no longer exists. TIM-V0 uses target memory and geometric consistency, so it can reacquire the same physical target under the new tracker ID.