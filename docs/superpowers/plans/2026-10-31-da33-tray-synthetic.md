# DA-33 Tray Synthetic S1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scripted two-hand planner on decoupled WBC that carries the tray from table A to the target zone on table B, and a batch pipeline that turns its successful episodes into a hashed LeRobot v2.1 release in Ψ₀'s format (action 36, state 32), at least 80 QA-passed episodes by milestone M2 (8/11/2026).

**Architecture:** The planner replaces the PICO streamer only. It emits wrist targets, hand closure and `navigate_cmd`; SIMPLE's own `TeleopRetargetingIK`, `G1DecoupledWholeBodyPolicy` (Balance/Walk ONNX) and data exporter do the rest, so synthetic episodes have exactly the fields of teleop episodes. The data path is SIMPLE's three stages: record raw in `sim_mode=mujoco` → `replay-decoupled-wbc` in `mujoco` as QA → `scripts/postprocess_psi0_sonic.py` to Ψ₀ format. Pure logic (navigation integrator, planner phases, seed and log handling) stays free of `simple`/`mujoco` imports and runs in workspace CI; glue modules carry the `sim` marker.

**Tech Stack:** Python 3.10 SIMPLE venv (S1-02, `fwdata/simple/.venv`); SIMPLE `6d10628794d9c7de4596b4f2afb2c054a637c2bc`; `decoupled_wbc` (`TeleopRetargetingIK`, `instantiate_g1_hand_ik_solver`, `Gr00tDataExporter`, `get_dataset_features`); MuJoCo 3.3.6; numpy, pyarrow; Ψ₀ repo at `fwdata/psi0/Psi0` for stats and the loader check.

**Spec:** [design 28/10/2026](../specs/2026-10-28-tray-transfer-he-design.md) (sections 3, 4, 5, 7, 9), [design 27/10/2026](../specs/2026-10-27-g1-psi0-demo-design.md) section 6, story [DA-33](../../product/stories/DA-33-synthetic-s1-khay.md). Builds on DA-32 ([plan](2026-10-28-da32-tray-task.md); branch `DA-32-tray-task`, `docs/g0/tray/decisions.md` D-01 to D-09).

## Global Constraints

- Prerequisite: DA-32 is merged into `master`. Branch `DA-33-tray-synthetic` from the latest `origin/master` (CLAUDE.md: no branch from an unmerged branch). Symlink `fwdata` into the worktree as DA-32 did.
- Robot `g1_sonic`, env `simple/G1WholebodyTrayTransferTeleop-v0`, `sim_mode=mujoco` only, `physics_dt` 0.005, `render_hz` 50. No SIMPLE fork, no cuRobo, no `isaacsim` import.
- Scene axes as DA-32 D-05: table A at +x, table B at −x, robot spawns at yaw 0 facing A. The elastic band pulls yaw to 0, so the robot turns only after release.
- `navigate_cmd = [vx, vy, vyaw, target_yaw]` (m/s, m/s, rad/s, rad), `target_yaw` integrated from `vyaw` at 50 Hz and wrapped to [−π, π], as `PicoStreamer`; |vx|, |vy| ≤ 0.5 m/s, |vyaw| ≤ 1.0 rad/s. The lower body runs Balance.onnx when ‖(vx, vy, vyaw)‖ < 0.1, Walk.onnx otherwise.
- Ψ₀ layout (SIMPLE `baselines/psi0_decoupled_wbc.py`, `scripts/postprocess_psi0_sonic.py`): action 36 = left hand 7, right hand 7, left arm 7, right arm 7, waist roll/pitch/yaw 3, base height 1, `navigate_cmd` 4; state 32 = hands 14, arms 14, waist rpy 3, base height 1; image `observation.images.ego_view` = `head_stereo_left` 360 × 640; 50 Hz; LeRobot v2.1.
- Every episode's `environment_config` (task `state_dict`) carries a `flywheel` block: `source_kind = synthetic`, `source_detail = planner_wbc`, `synthetic_tier = S1`, `action_quality = planned`, `embodiment_id = g1_sonic_dwbc@1`, `renderer = mujoco`, `data_class = public`, `planner_version`, `seed`, `level`, `split`, `visuals_revision` (SimReady revision or `none`).
- Seeds only from the train range [0, 1 000 000); dev and holdout are never generated (DA-32 `split_of`).
- Every attempt, failed or not, gets one line in the append-only `gen_log.jsonl` with its reason and cost; nothing is deleted. Every batch job writes ledger rows to `docs/g0/ledger/DA-33.csv` (columns of `docs/g0/README.md` section 3), estimate and measurement in separate rows.
- Data, videos, releases live under `fwdata/` and are never committed.
- Commits on `DA-33-tray-synthetic`: `DA-33/<n>: <imperative English>`, body with AC and evidence, `Time-spent: <h>h` asked from Hiếu, then `Co-Authored-By`.

## Open questions for Hiếu (answer before Task 6)

| Code | Question | Default if unanswered |
|---|---|---|
| Q-33A | Randomisation level of training episodes? | Level 1 on train seeds; level 2 stays an evaluation shift (design 6.3) |
| Q-33B | How many attempts in the production batch? | 130 attempts → ≥ 100 recorded successes → ≥ 80 after replay QA (design 7, M2) |
| Q-33C | Which machine runs the batch? | **Answered 31/10/2026:** laptop RTX 3050 for Tasks 1–3; SSH host `rtx3060` (RTX 3060 12 GB, 64 CPU, 94 GB RAM, Isaac Sim installed) for Task 4 tuning and the batch in Tasks 6–9. Set up the SIMPLE venv there with `scripts/g0/setup_simple.sh` and record versions in `docs/g0/env-simple.md` (also S1-02 AC 4) |
| Q-33D | Data class for Colab training (S1-07 marked psi-data `restricted`; design 8.4 says `public`)? | This release is team-generated synthetic: `public`; psi-data's label is decided separately |

## Review Focus

1. The tray slips or one hand loses contact during the 180° turn → the planner must stop in `ABORT` with the tracker's label, not keep walking with a dangling tray; toy-world test in Task 3, sim check in Task 4.
2. The generating machine lacks the SimReady manifest, so images show plain boxes while evaluation shows textures → generation refuses to start without visuals unless `--allow-plain` and records `visuals_revision`; test in Task 6.
3. Replay drifts from the recorded run because the WBC interpolates on wall-clock time → replay QA must compare outcomes (success, final tray pose within 2 cm), and the pass rate goes in the release notes; test in Task 7.
4. Band and setup frames at the start of each episode teach Ψ₀ to idle → recording starts 0.5 s after band release; test in Task 5.
5. A seed outside the train range, or a resumed batch, regenerates a used seed → generator refuses non-train seeds and skips seeds already in `gen_log.jsonl`; test in Task 6.

---

### Task 1: Locomotion check, navigation integrator, scene file clean-up

**Files:**
- Create: `packages/flywheel-simple/src/flywheel_simple/wbc/navigate.py`
- Modify: `packages/flywheel-simple/src/flywheel_simple/tray/simple_task.py` (remove the per-process scene MJCF in `TrayTransferEnv.close()`)
- Test: `packages/flywheel-simple/tests/wbc/test_navigate.py` (pure), `packages/flywheel-simple/tests/wbc/test_locomotion.py` (`sim`)
- Create: `docs/g0/tray/locomotion.md`

**Interfaces:**
- Produces: `NavIntegrator(dt: float = 0.02)` with `reset(yaw: float = 0.0) -> None` and `command(vx: float, vy: float, vyaw: float) -> np.ndarray` returning `[vx, vy, vyaw, target_yaw]` (clipped to the limits in Global Constraints, `target_yaw` wrapped).

Why first: the 90 s episode recorded on 31/10/2026 moved only 0.28 m in 9.1 s at `vx = 0.2` with `target_yaw = 0` fixed, while `vx = −0.25` moved 0.78 m in 3.8 s, and both drifted 0.15 m sideways. The planner's carry depends on forward walking and turning, so measure before building on it.

- [ ] **Step 1: Write the failing tests**

```python
def test_target_yaw_integrates_and_wraps():
    nav = NavIntegrator(); nav.reset(yaw=3.0)
    for _ in range(25):
        cmd = nav.command(0.0, 0.0, 1.0)
    assert cmd[3] == pytest.approx(3.0 + 0.5 - 2 * math.pi, abs=1e-9)

def test_command_is_clipped():
    assert list(NavIntegrator().command(0.9, -0.9, 2.0)[:3]) == [0.5, -0.5, 1.0]

@pytest.mark.sim
@pytest.mark.parametrize("vx", [0.2, 0.3, 0.4])
def test_forward_walk_covers_most_of_the_command(tray_env_standing, vx):
    dx, drift, upright = walk(tray_env_standing, vx=vx, seconds=4.0)
    assert dx >= 0.6 * vx * 4.0 and abs(drift) <= 0.15 and upright >= 0.99

@pytest.mark.sim
def test_turns_in_place_by_pi(tray_env_standing):
    yaw, moved, upright = turn(tray_env_standing, vyaw=0.5, target=math.pi, max_seconds=10.0)
    assert yaw_error(yaw, math.pi) <= math.radians(10) and moved <= 0.2 and upright >= 0.99

@pytest.mark.sim
def test_env_close_removes_its_scene_file():
    env = make_env(seed=0); path = scene_dir() / f"scene_{os.getpid()}.xml"
    assert path.exists(); env.close(); assert not path.exists()
```

`tray_env_standing` (fixture in `tests/wbc/conftest.py`): tray env at seed 0 after `release_band`; `walk` and `turn` drive `StandWalkController` with `NavIntegrator` commands and return pelvis displacement along the heading, lateral drift, final yaw and minimum trunk uprightness.

- [ ] **Step 2: Run to verify failure** — `uv run pytest packages/flywheel-simple/tests/wbc/test_navigate.py -v` → FAIL (`ImportError`); the `sim` tests in the SIMPLE venv → FAIL.
- [ ] **Step 3: Implement `navigate.py` and the `close()` clean-up.**
- [ ] **Step 4: Run all tests.** If a forward-walk case fails, stop and use superpowers:systematic-debugging: log `lower_body_policy` (Balance/Walk) per step, the Walk policy's command input, arm and hand contacts with the table, and heading error against `target_yaw`. Record the speed table (commanded vs measured for vx ∈ {0.1 … 0.5}, backwards, turn rates) and the root cause in `docs/g0/tray/locomotion.md`. Expected after the fix: PASS. If the cause is in SIMPLE or decoupled_wbc and cannot be fixed from our package, keep the measured speeds as planner limits and write a `Decision` in `docs/g0/tray/decisions.md`.
- [ ] **Step 5: Commit** — `DA-33/1: Add a navigation integrator and characterise G1 walking in the tray scene`

### Task 2: Wrist-target IK and hand closure on decoupled WBC

**Files:**
- Create: `packages/flywheel-simple/src/flywheel_simple/wbc/upper_body.py`
- Modify: `packages/flywheel-simple/src/flywheel_simple/wbc/stand_walk.py` (`wrist_pose` stops raising)
- Test: `packages/flywheel-simple/tests/wbc/test_upper_body.py` (`sim`)

**Interfaces:**
- Consumes: `StandWalkController` (DA-32), `NavIntegrator` (Task 1).
- Produces: `UpperBodyIK(robot_model)` with `current_wrists(sim_obs) -> tuple[np.ndarray, np.ndarray]` (two 4 × 4 poses in the IK's body frame) and `solve(left: np.ndarray, right: np.ndarray) -> np.ndarray` (upper-body target pose for `set_goal`); `hand_q(side: Literal["left", "right"], closure: float) -> np.ndarray` (7 joints, natural order, closure 0 open … 1 closed, linear between two fixed poses); `StandWalkController.action(sim_obs, navigate_cmd, wrist_pose: tuple[np.ndarray, np.ndarray] | None = None, hand_closure: tuple[float, float] = (0.0, 0.0)) -> ActionCmd`; `StandWalkController.last_record: dict` with `action_eef` (14: left then right, xyz + wxyz), `navigate_cmd` (4), `base_height_command` (1), `target_waist` (3), `target_q` (29), `left_hand_q`, `right_hand_q` (7 each), the fields SIMPLE's teleop recorder reads.

Build `TeleopRetargetingIK(robot_model, left_hand_ik_solver, right_hand_ik_solver, body_active_joint_groups=["upper_body"])` as `PicoDecoupledAgent._init_decoupled_policy` does, and call `set_goal({"body_data": {hand_frame_names["left"]: L, hand_frame_names["right"]: R}, ...})` then `get_action()`. Which frame `body_data` poses live in is not documented: the round-trip test below decides it (start from the pelvis frame, the root of `robot_model`). Hands bypass the hand IK: overwrite the hand slots of the upper-body target with `hand_q`. Closed pose: 80 % of each Dex3 joint's range towards flexion, from the robot model's limits.

- [ ] **Step 1: Write the failing tests (marker `sim`)**

```python
def test_ik_round_trip_keeps_the_current_pose(tray_env_standing):
    ik = UpperBodyIK(model_of(tray_env_standing))
    left, right = ik.current_wrists(proprio(tray_env_standing))
    q = ik.solve(left, right)
    assert np.max(np.abs(q[ARM_SLICE] - arm_q(tray_env_standing))) < 0.05

def test_wrist_target_moves_the_palm(tray_env_standing):
    ctrl, ik = controller_and_ik(tray_env_standing)
    left, right = ik.current_wrists(proprio(tray_env_standing))
    p0 = palm(tray_env_standing, "left")
    run(tray_env_standing, ctrl, seconds=1.5, wrist_pose=(shift(left, dx=0.10), right))
    assert 0.07 <= forward_component(palm(tray_env_standing, "left") - p0) <= 0.13

def test_hand_closure_closes_the_fingers(tray_env_standing):
    ctrl, _ = controller_and_ik(tray_env_standing)
    run(tray_env_standing, ctrl, seconds=1.0, hand_closure=(1.0, 1.0))
    assert np.max(np.abs(hand_qpos(tray_env_standing, "left") - hand_q("left", 1.0))) < 0.15

def test_last_record_has_teleop_recorder_fields(tray_env_standing):
    ctrl, _ = controller_and_ik(tray_env_standing)
    ctrl.action(proprio(tray_env_standing))
    assert {k: np.shape(v) for k, v in ctrl.last_record.items()} >= {
        "action_eef": (14,), "navigate_cmd": (4,), "base_height_command": (1,), "target_waist": (3,)}
```

- [ ] **Step 2: Run to verify failure** — `MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/wbc/test_upper_body.py -m sim -v` → FAIL (`ImportError`).
- [ ] **Step 3: Implement `upper_body.py` and extend `StandWalkController`.**
- [ ] **Step 4: Run to verify pass** (same command, 4 passed); the DA-32 `wbc` and `tray` sim tests still pass.
- [ ] **Step 5: Commit** — `DA-33/2: Drive both wrists through TeleopRetargetingIK and add hand closure`

### Task 3: Planner phases (pure logic)

**Files:**
- Create: `configs/sim/tray_planner.yaml`, `packages/flywheel-simple/src/flywheel_simple/tray/planner.py`
- Modify: `packages/flywheel-simple/src/flywheel_simple/tray/config.py` (`load_flat_config(cls, path)` shared by `TrayConfig` and `PlannerConfig`)
- Test: `packages/flywheel-simple/tests/tray/test_planner.py`, toy world in `tests/tray/conftest.py`

**Interfaces:**
- Consumes: `TrayConfig`, `EpisodeSample`, `TrayState`, `scene_geometry_with_gap` (DA-32).
- Produces: `Phase` (enum: `APPROACH_A, REACH, GRASP, LIFT, BACK_OFF, TURN, CARRY, ARRIVE_B, LOWER, RELEASE, RETREAT, DONE, ABORT`); `PlannerConfig` (frozen, from `tray_planner.yaml`); `PlannerCommand(phase: Phase, nav: tuple[float, float, float], left_wrist: np.ndarray, right_wrist: np.ndarray, hand_closure: tuple[float, float], abort_reason: str | None)`; `TrayPlanner(cfg: PlannerConfig, tray_cfg: TrayConfig, sample: EpisodeSample)` with `step(state: TrayState, base: Pose2D, report: StepReport) -> PlannerCommand` and `reset()`. Wrist poses are in the robot base frame of Task 2.

Phase rules (every value a key in `tray_planner.yaml`, initial values from Task 1's measured speeds):

| Phase | Command | Leaves when | Scorer step |
|---|---|---|---|
| APPROACH_A | walk +x | base within `standoff` (0.30 m) of table A's edge | 1 |
| REACH | wrists to pre-grasp `pregrasp_offset` (0.06 m) outside each handle along ±y | both palms within 0.02 m of pre-grasp | 1 |
| GRASP | wrists onto the handles, then `hand_closure` → 1 | both handle contacts for 0.3 s | 2 |
| LIFT | wrists up `lift_height` (0.10 m), fixed in base frame | tray `h_lift` above table, parts in tray | 3 |
| BACK_OFF | walk −x `backoff` (0.35 m) | distance reached | 4 |
| TURN | `vyaw` until heading π | heading error ≤ 5° | 4 |
| CARRY | walk towards B, wrists fixed in base frame | base within `standoff` of table B's edge | 4–5 |
| ARRIVE_B | stand, align heading with target yaw | base speed < 0.05 m/s for 0.5 s | 5 |
| LOWER | wrists down until tray on B | `tray_on_table == "B"` | 6 |
| RELEASE | `hand_closure` → 0, wrists out by `pregrasp_offset` | no handle contact for 0.5 s | 7 |
| RETREAT | walk back `retreat` (0.20 m) | distance reached | 7 |

Every phase has a timeout (`timeout_<phase>` s); a timeout, a tracker failure label, or a tray on the floor ends in `ABORT` with the reason. Grasp targets come from the tray pose and the handle geometry of `TrayConfig`.

- [ ] **Step 1: Write the failing tests**

```python
def test_toy_world_episode_visits_phases_in_order_and_finishes(toy_world):
    phases = run_toy(toy_world)
    assert ordered_unique(phases) == [p for p in Phase if p not in (Phase.ABORT,)]

def test_wrists_stay_fixed_in_base_frame_while_carrying(toy_world):
    cmds = [c for c in run_toy_cmds(toy_world) if c.phase in (Phase.TURN, Phase.CARRY)]
    assert max_pose_change([c.left_wrist for c in cmds]) < 1e-9

def test_grasp_targets_mirror_about_the_tray(toy_world):
    cmd = first_cmd(toy_world, Phase.GRASP)
    assert grasp_symmetry_error(cmd, toy_world.tray_pose) < 1e-6

def test_contact_loss_while_turning_aborts(toy_world):
    toy_world.drop_left_contact_at(Phase.TURN)
    assert run_toy(toy_world)[-1] == Phase.ABORT

def test_phase_timeout_aborts_with_reason(toy_world):
    toy_world.block_base()
    cmd = run_toy_cmds(toy_world)[-1]
    assert cmd.phase == Phase.ABORT and cmd.abort_reason == "timeout:APPROACH_A"
```

The toy world integrates the base from `nav`, places palms at the commanded wrists, makes the tray follow the palms while both "contacts" hold, and builds `TrayState`/`StepReport` with DA-32's `StepTracker`.

- [ ] **Step 2: Run to verify failure** — `uv run pytest packages/flywheel-simple/tests/tray/test_planner.py -v` → FAIL (`ImportError`).
- [ ] **Step 3: Implement `planner.py`, `tray_planner.yaml`, the shared loader.**
- [ ] **Step 4: Run to verify pass**, plus the whole pure suite.
- [ ] **Step 5: Commit** — `DA-33/3: Add the tray planner phase machine`

### Task 4: First planned episode that succeeds in sim (target 6/11)

**Files:**
- Create: `packages/flywheel-simple/src/flywheel_simple/tray/agent.py`
- Modify: `scripts/g0/tray/view_scene.py` (`--agent planner`)
- Test: `packages/flywheel-simple/tests/tray/test_agent.py` (`sim`)

**Interfaces:**
- Consumes: Tasks 1–3, `tray_state`, `make_env` (DA-32).
- Produces: `TrayAgent(env, planner_cfg: PlannerConfig)` with `reset()` and `act(obs, info) -> ActionCmd`; `run_episode(env, agent, seed: int, level: int, on_step: Callable[[dict, dict, ActionCmd], None] | None = None) -> EpisodeResult(success: bool, failure: str | None, abort_reason: str | None, phases: list[tuple[str, float]], steps: int, sim_s: float, wall_s: float)`. Band release, then 0.5 s standing, happens inside `run_episode` before the planner starts.

- [ ] **Step 1: Write the failing tests (marker `sim`)**

```python
def test_planner_carries_the_tray_at_level0_seed0():
    result = run_episode(make_env(seed=0), TrayAgent(...), seed=0, level=0)
    assert result.success and result.failure is None and result.sim_s < 90

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_planner_succeeds_on_level1_train_seeds(seed):
    assert run_episode(make_env(seed=seed, level=1), TrayAgent(...), seed=seed, level=1).success
```

- [ ] **Step 2: Run to verify failure** → FAIL (`ImportError`).
- [ ] **Step 3: Implement `agent.py`; tune `tray_planner.yaml` against videos from `view_scene.py --agent planner`.** Follow design 9 when it fails: robot leans or falls under load → lower `carry_height`, keep wrists closer to the torso, slower `vx`; tray slips → adjust grasp height on the handle, then handle friction in `tray.yaml` (a DA-32 `Decision`); parts spill → slower turn rate. Each change that touches the task (not the planner) goes in `docs/g0/tray/decisions.md`.
- [ ] **Step 4: Run to verify pass**; keep `head.mp4` and `overview.mp4` of seed 0 under `fwdata/simple/tray/planner/` as evidence.
- [ ] **Step 5: Commit** — `DA-33/4: Carry the tray to table B with the scripted planner`

### Task 5: Episode recorder in SIMPLE's teleop format

**Files:**
- Create: `packages/flywheel-simple/src/flywheel_simple/tray/recorder.py`
- Modify: `packages/flywheel-simple/src/flywheel_simple/tray/simple_task.py` (`state_dict()["flywheel"]`, set by the generator)
- Test: `packages/flywheel-simple/tests/tray/test_recorder.py` (`sim`)

**Interfaces:**
- Consumes: `StandWalkController.last_record` (Task 2), `run_episode(on_step=...)` (Task 4).
- Produces: `EpisodeRecorder(save_dir: Path, task, robot_model, joint_names: list[str])` with `add(observation: dict, info: dict, record: dict) -> None`, `save() -> int` (episode index) and `discard() -> None`; `FlywheelMeta` (frozen dataclass with the fields listed in Global Constraints) set through `task.set_flywheel_meta(meta)`.

Mirror SIMPLE: features from `decoupled_wbc.data.utils.get_dataset_features(robot_model)` with `set_ego_view_feature_shape(features, (360, 640, 3))` and `observation.state` names = `joint_names`; frames with the keys of `simple.cli.teleop_decoupled_wbc._build_frame` (`observation.images.ego_view`, `observation.state`, `observation.eef_state`, `action`, `action.eef`, `observation.img_state_delta`, `teleop.navigate_command`, `teleop.base_height_command`, `observation.base_pose`, `observation.base_vel`, `observation.object_poses` for the tray and six parts); after `save()`, write `task.state_dict()` as `environment_config` into `meta/episodes.jsonl` as SIMPLE's `_save_episode_env_config` does. Do not import `simple.cli.teleop_decoupled_wbc` (it pulls PICO and PyAV); copy `_build_frame`'s key logic with a comment naming the source (SIMPLE is MIT).

- [ ] **Step 1: Write the failing tests (marker `sim`)**

```python
def test_recorded_features_match_simple_teleop(tmp_path):
    root = record_short_episode(tmp_path, seconds=2.0)
    info = json.loads((root / "meta/info.json").read_text())
    assert set(info["features"]) == SIMPLE_TELEOP_FEATURES | {"observation.object_poses"}
    assert info["fps"] == 50 and info["features"]["action"]["shape"] == [43]

def test_environment_config_carries_flywheel_meta(tmp_path):
    root = record_short_episode(tmp_path, seconds=2.0)
    env_cfg = json.loads(read_jsonl(root / "meta/episodes.jsonl")[0]["environment_config"])
    assert env_cfg["flywheel"]["synthetic_tier"] == "S1" and env_cfg["flywheel"]["split"] == "train"

def test_recording_starts_after_band_release(tmp_path):
    root = record_short_episode(tmp_path, seconds=2.0)
    assert first_frame_band_released(root)  # base height ≥ 0.70 m and moving < 0.05 m/s

def test_video_frames_match_rows(tmp_path):
    root = record_short_episode(tmp_path, seconds=2.0)
    assert video_frame_count(root, "observation.images.ego_view") == parquet_rows(root)
```

`SIMPLE_TELEOP_FEATURES` is the key set `get_dataset_features` returns plus the frame keys above; `record_short_episode` stands the robot for `seconds` through `run_episode` with a planner stub.

- [ ] **Step 2–4:** run → FAIL (`ImportError`); implement; run → PASS.
- [ ] **Step 5: Commit** — `DA-33/5: Record planned episodes in SIMPLE's teleop LeRobot format`

### Task 6: Batch generator, attempt log, minimal QA

**Files:**
- Create: `packages/flywheel-simple/src/flywheel_simple/tray/generate.py`, `scripts/g0/tray/generate.py` (thin CLI)
- Test: `packages/flywheel-simple/tests/tray/test_generate.py` (pure parts), `test_generate_sim.py` (`sim`)

**Interfaces:**
- Consumes: Tasks 4–5, `split_of`, `SEED_RANGES`, `load_manifest` (DA-32).
- Produces: `next_seeds(log: Path, start: int, n: int) -> list[int]` (train range only, skips seeds already logged); `append_attempt(log: Path, row: AttemptRow) -> None`; `AttemptRow` (seed, level, success, failure, abort_reason, phase_reached, steps, sim_s, wall_s, gpu_name, planner_version, recorded: bool, qa: str); `minimal_qa(episode_root: Path, index: int) -> str` (`"pass"` or the first failing check: success flag, length 5–90 s, NaN in any numeric column, all phases up to `RETREAT` visited); `generate(out: Path, n_attempts: int, level: int, seed_start: int, allow_plain: bool = False) -> GenSummary`.

CLI: `fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --out fwdata/simple/tray/gen/<run> --n 130 --level 1 --seed-start 0` (resume = run again with the same `--out`).

- [ ] **Step 1: Write the failing tests**

```python
def test_next_seeds_skips_logged_and_stays_in_train(tmp_path):
    log = tmp_path / "gen_log.jsonl"; append_attempt(log, row(seed=0)); append_attempt(log, row(seed=1))
    assert next_seeds(log, start=0, n=3) == [2, 3, 4]
    with pytest.raises(ValueError):
        next_seeds(log, start=999_999, n=2)

def test_log_is_append_only(tmp_path):
    log = tmp_path / "gen_log.jsonl"; append_attempt(log, row(seed=0)); before = log.read_bytes()
    append_attempt(log, row(seed=1))
    assert log.read_bytes().startswith(before)

@pytest.mark.sim
def test_generator_refuses_to_run_without_visuals(tmp_path, monkeypatch):
    monkeypatch.setattr(visuals, "default_manifest_path", lambda: None)
    with pytest.raises(RuntimeError, match="SimReady"):
        generate(tmp_path, n_attempts=1, level=1, seed_start=0)

@pytest.mark.sim
def test_two_attempts_are_logged_and_recorded(tmp_path):
    summary = generate(tmp_path, n_attempts=2, level=1, seed_start=0)
    rows = read_jsonl(tmp_path / "gen_log.jsonl")
    assert len(rows) == 2 and summary.recorded == sum(r["recorded"] for r in rows)
```

- [ ] **Step 2–4:** run → FAIL; implement (failed attempts call `recorder.discard()` but keep their log row); run → PASS.
- [ ] **Step 5: Commit** — `DA-33/6: Generate tray episodes in batches with an append-only attempt log`

### Task 7: Replay QA through SIMPLE's replay-decoupled-wbc

**Files:**
- Modify: `packages/flywheel-simple/src/flywheel_simple/tray/run.py` (add `replay-decoupled-wbc` → `simple.cli.replay_decoupled_wbc`)
- Create: `scripts/g0/tray/replay_qa.py`
- Test: `packages/flywheel-simple/tests/tray/test_replay_qa.py` (`sim`)

**Interfaces:**
- Produces: `replay_qa(raw_root: Path, replay_root: Path) -> list[ReplayVerdict(episode: int, success: bool, tray_error_m: float)]` running `python -m flywheel_simple.tray.run replay-decoupled-wbc simple/G1WholebodyTrayTransferTeleop-v0 --data-dir <raw> --sim-mode=mujoco --headless --render-hz=50 --save-dir <replay> --record`, then comparing each replayed episode's final tray pose with the recorded one.

Read `replay_decoupled_wbc.py` first: how it restores the scene from `environment_config` (our task `state_dict` must carry what `reset` needs: seed and level), and how `--success-criteria` relates to `check_success`. If replay cannot rebuild our scene from `environment_config`, add a `load_state_dict` path to the task and record it as a `Decision`.

- [ ] **Step 1: Write the failing test** — two recorded successful episodes replay with `success` and `tray_error_m < 0.02`.
- [ ] **Step 2–4:** run → FAIL; implement; run → PASS.
- [ ] **Step 5: Commit** — `DA-33/7: Replay recorded episodes in MuJoCo as QA`

### Task 8: Export to Ψ₀ format and contract test

**Files:**
- Create: `scripts/g0/tray/export_psi0.py`, `packages/flywheel-simple/tests/tray/test_export_contract.py` (`sim`: needs pyarrow and ffprobe from the SIMPLE venv)

**Interfaces:**
- Produces: `export_psi0(replay_root: Path, out: Path, max_episodes: int) -> Path` running SIMPLE's `scripts/postprocess_psi0_sonic.py --sim-root <replay_root> --out-dir <out> --skip 0 --total_episodes <n>`, then Ψ₀'s `scripts/data/calc_modality_stats.py` to write `meta/stats_psi0.json` (check its arguments; the fine-tune recipe reads `meta/stats_psi0.json`).

- [ ] **Step 1: Write the failing test** — the design 27/10 section 6.4 checklist on a 2-episode export:

```python
def test_export_contract(exported):
    info = json.loads((exported / "meta/info.json").read_text())
    assert info["codebase_version"] == "v2.1" and info["fps"] == 50
    assert info["features"]["action"]["shape"] == [36]
    assert info["features"]["observation.state"]["shape"] == [32]
    assert video_shape(exported, "observation.images.ego_view") == (360, 640)
    assert indices_continuous(exported) and frame_index_starts_at_zero(exported)
    assert timestamps_match_fps(exported, tol=0.5 / 50)
    assert all(t["task"] for t in read_jsonl(exported / "meta/tasks.jsonl"))
    assert video_frames_match_rows(exported) and stats_have_no_nan(exported / "meta/stats_psi0.json")

def test_export_features_match_psi_data(exported, psi_data_info):
    ours = json.loads((exported / "meta/info.json").read_text())["features"]
    assert {k: (v["dtype"], v["shape"]) for k, v in ours.items()} == {
        k: (v["dtype"], v["shape"]) for k, v in psi_data_info["features"].items()}
```

`psi_data_info` reads `meta/info.json` of the two-table teleop set from `fwdata/psi-data/` (S1-07); the test skips with that reason when it is absent. The Ψ₀ loader check (design 6.4 item 7) waits for DA-19's confirmed recipe and is added then.

- [ ] **Step 2–4:** run → FAIL; implement; run → PASS.
- [ ] **Step 5: Commit** — `DA-33/8: Export replayed episodes to Psi0's LeRobot layout`

### Task 9: Production batch, release, ledger (M2, 8/11)

**Files:**
- Create: `scripts/g0/tray/release.py`, `docs/g0/tray/synthetic-s1.md`, `docs/g0/ledger/DA-33.csv`
- Test: `packages/flywheel-simple/tests/tray/test_release.py` (pure)

**Interfaces:**
- Produces: `build_manifest(release_root: Path) -> dict` (every file's sha256 and size, sorted; `release_hash` = sha256 of the canonical JSON of that list) and `write_manifest(release_root: Path) -> str`.

- [ ] **Step 1: Write the failing tests** — same files give the same `release_hash`; changing one byte of one parquet changes it; the manifest lists every file under the root.
- [ ] **Step 2–4:** run → FAIL; implement; run → PASS.
- [ ] **Step 5: Run the batch on `rtx3060`** with the answers to Q-33A–C: generate → replay QA → export → release into `fwdata/releases/tray_s1_<release_hash[:12]>/`. Expected: ≥ 100 recorded successes, ≥ 80 after replay QA.
- [ ] **Step 6: Write `docs/g0/tray/synthetic-s1.md`**: attempts, success rate, abort reasons, replay pass rate, seconds per attempt (mean, p95), GPU, `release_hash`, the action and state layout table (36 / 32, from the export's modality file), controller (decoupled WBC, Balance/Walk ONNX), and the limits of synthetic S1. Add ledger rows (engineer time estimated and measured, GPU-hours measured from `gen_log.jsonl`, storage of the release).
- [ ] **Step 7: Commit** — `DA-33/9: Release the first tray synthetic S1 set with its manifest and costs`

---

## After DA-33

- DA-34 trains A (N_full = 80) and C (N_cut = 40, a hashed subset) from this release; it needs DA-19's confirmation of the `eval-decoupled-wbc` recipe and Q-33D for Colab.
- If the replay pass rate is below 80 %, look at time-based WBC interpolation first (Review Focus 3) before adding attempts.
