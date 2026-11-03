# Closed-Loop Synchronous and Asynchronous Evaluation

Documenting the evaluation runner architecture and timing modes (DA-23, ADR-20).

## 1. Overview and Rationale

In real robot deployments, neural policy inference consumes non-zero computation time (approximately 160 ms for $\Psi_0$ per inference call on standard hardware). Under real-time chunking (RTC), action chunks are streamed to the robot controller asynchronously while subsequent observation frames are processed concurrently.

Standard synchronous simulation pauses the simulator clock while computing policy outputs, masking latency-induced faults such as:
- Buffer starvation and control jitter.
- State-action divergence at chunk boundaries (boundary jumps).
- Overshooting during high-velocity maneuvers due to delayed reaction times.

To provide both reproducible baseline comparisons and rigorous real-world validation, the closed-loop evaluation runner supports two modes:
1. **Synchronous Mode (`timing = "sync"`):** Simulator clock halts during inference. Used for G0 recipe reproduction (`g0_repro`) and Historical Experiments (`he`) to maintain parity with published author results.
2. **Asynchronous Mode (`timing = "async"`):** Simulates realistic policy inference latency using profiles sampled from empirical runtime measurements. Used for primary metrics in all data flywheel branches (`branch_train`, `round`, `holdout`).

## 2. Real-Time Chunking Inference Logging

For every rollout execution, the runner records chunk-level inference telemetry into `<job_dir>/rtc.jsonl`:
- `chunk_index`: Monotonically increasing chunk identifier.
- `observation_sent_s`: Simulation timestamp when state/image was sampled.
- `chunk_received_s`: Simulation timestamp when the action chunk arrived at the controller.
- `delay_steps`: Latency measured in discrete control cycles ($\lceil \Delta t / dt \rceil$).
- `buffer_level`: Remaining action buffer size at the controller.
- `boundary_jump`: Flag indicating whether the action buffer depleted before the arrival of the new chunk.

## 3. Configuration and RunPlan Integration

Default settings and mappings are declared in `configs/loop/eval.yaml`:

```yaml
default_timing: async

timing_by_purpose:
  g0_repro: sync
  he: sync
  branch_train: async
  round: async
  holdout: async
```

With zero injected latency (`fixed_delay_s = 0.0`), synchronous and asynchronous modes produce mathematically identical trajectories on the same random seed.
