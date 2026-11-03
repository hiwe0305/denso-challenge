# Trace fixtures for DA-13 (Issue #31)

Four traces for the system checks R3 (tracking), R4 (camera-state sync) and R5 (camera
calibration), written against `flywheel.contracts.trace`.

## Layout (PO decisions G1 and G1b on PR #48, 3/11/2026)

Each directory is one trace, named after its `trace_id`; `TraceRef.uri` points at it.

```
<trace_id>/
  steps.jsonl          one TraceStep per line, in step order
  camera_params.jsonl  one CameraParams per line, one per camera the policy sees,
                       each carrying the trace's trace_id
  rollout_result.json  the episode's v0 RolloutResult: infra_status (R6), sim_success
```

In `rollout_result.json`, `trace_ref.trace_id` is the directory's name, `trace_ref.uri`
names the directory (its last path component is the `trace_id`) and `trace_ref.sha256` is
the sha256 of `steps.jsonl`, so a result cannot be paired with steps it is not about. The
`SimpleSim` hook (DA-38) writes `uri` as the directory's path; these fixtures write the bare
`<trace_id>`, relative to this folder. Every fixture has `infra_status: "ok"`, so R6 finds
nothing; `sim_success` is `true` for `tr_clean/` only.

## Cases

Each trace has 100 control cycles at 50 Hz (`t_state` steps by 0.02 s) and the two head
cameras of the two-table task. A frame reaches the policy on even cycles (25 Hz);
`t_image` is `null` on the others.

| Directory | Case | Expected |
|---|---|---|
| `tr_clean/` | Tracking error at most 0.001 on every dimension; cameras equal the pinned reference | No finding |
| `tr_sync_delay/` | From cycle 20, each frame is 0.12 s old (`t_state - t_image = 0.12`) | R4 |
| `tr_calib_offset/` | Clean motion; `head_stereo_left` has `fx`, `fy` 10% high and 15° of pitch about the camera x axis; `head_stereo_right` is unchanged | R5 |
| `tr_missing/` | `meas_lower` is `"NaN"` throughout, as in raw psi-data, which records no lower-body measurement; from cycle 30 the camera loses every due frame (`t_image: null`, `dropped_frames: 1`) | R3 lower body and R4 are CHƯA RÕ; R3 upper body is still judged |

## Camera reference

`reference_sha256` is `fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2`, a
real hash, not a placeholder. It is the G0 reference of the two-table task, pinned by DA-38
(`docs/g0/camera-reference-two-table.yaml` at `f94d5bc`, SIMPLE `b75c678`). Per PO decision
Q3 (3/11/2026), each `CameraParams` copies the pinned hash from the RunPlan. It is never a
hash of the episode's own cameras: R5 compares the values against the reference within a
tolerance. The cameras of `tr_clean/`, `tr_sync_delay/` and `tr_missing/` hold exactly the
reference values, and `test_trace.py` recomputes the hash from them by DA-38's pinning rule.

## Conventions

- **Clock.** MuJoCo simulation time `data.time`, in seconds. `t_state` is when the state
  was read; `t_image` is the simulation time of the frame fed to the policy in that cycle.
- **No new frame.** `t_image: null`. Readers must treat it as "no measurement in this
  cycle", not repeat the last value, interpolate or shift the `step` axis.
- **Non-finite values** are the strings `"NaN"`, `"Infinity"`, `"-Infinity"`. A check that
  needs one says CHƯA RÕ and does not score it.
- **`dropped_frames`** counts the frames due in this cycle that never reached the policy.
  It is not a running total.
- **Dimensions.** `cmd_upper`/`meas_upper` have 28 values (`action[0:28]`, joint angles in
  rad) and `cmd_lower`/`meas_lower` have 7 (waist roll, pitch, yaw in rad; base height in m;
  vx, vy in m/s in the heading frame of the base; yaw in rad in the world frame). Names and
  order are `UPPER_BODY` and `LOWER_BODY` in `flywheel.contracts.trace`.
- **`run_plan_id`** is the RunPlan of the run. A run without one (G0, scripted eval) uses
  `g0-<story>-<yyyymmdd>`, for example `g0-DA-38-20261103` (PO decision G2). These fixtures
  use `rp_test`.

## Notes from the SimpleSim hook review (G3–G5)

- **G3 · density of `t_image`.** SIMPLE's `psi0_decoupled_wbc` agent does not use RTC: it
  sends a frame to the server only when its action queue is empty, so about once per chunk.
  In a hook trace only about one cycle per chunk has a non-null `t_image`, and one episode
  may have fewer than 100 samples for the p99 of R4. R4 therefore pools the samples of all
  the episodes of a run. The env renders on every cycle right after physics, so in sim
  `t_image == t_state`. The 25 Hz pattern above is a stand-in for tests, not what the hook
  writes.
- **G4 · `dropped_frames` in sim.** Rendering is synchronous, so the field is always 0 in
  sim. That 0 is a measured value, not a default.
- **G5 · success flag.** `TraceStep` has no success flag. The episode flag is
  `Episode.sim_success` / `RolloutResult.sim_success`, which the hook writes beside the
  trace. A per-cycle flag for DA-37 (SIMPLE calls `task.check_success` every step) would be
  a contract change, raised as an issue first.
