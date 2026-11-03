"""The virtual PICO operator on the planner's toy world, through PICO's signal path (DA-35 task 5).

The toy world reads what SIMPLE's pipeline would make of the signal: wrist
targets from WristsPreProcessor's forward map, a hand closed when any grasp
button is pressed, the walking command as G1GearWbcPolicy reads it (turning
towards `target_yaw` only while |vyaw| >= 0.1).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.tray.pico.operator import (
    Calibration,
    OperatorConfig,
    PicoSignal,
    VirtualOperator,
)
from flywheel_simple.tray.pico.virtual import (
    GRASP_FINGERTIP,
    TURN_FLAG,
    YawStick,
    pico_fingers,
    sample_style,
    style_seed_for,
    teleop_to_robot,
)
from flywheel_simple.tray.planner import Phase, PlannerCommand, TrayPlanner
from flywheel_simple.tray.predicates import StepTracker

sys.path.insert(0, str(Path(__file__).parents[1]))
from toy_world import DT, ToyWorld  # noqa: E402

SCALE = 1.2  # any motion scale: the operator inverts what the pipeline applies


def run_operator(
    level: int, seed: int, style_seed: int | None = None, max_s: float = 150.0
) -> tuple[list[PicoSignal], ToyWorld, bool]:
    world = ToyWorld(level, seed)
    cfg = OperatorConfig.load()
    style = None if style_seed is None else sample_style(style_seed)
    operator = VirtualOperator(cfg)
    planner = TrayPlanner(world.planner_cfg, world.cfg, world.sample)
    operator.reset(planner, style=style, style_seed=style_seed or 0)
    calibration = Calibration(ee0=(world.start_wrists[0], world.start_wrists[1]), scale=SCALE)
    tracker = StepTracker(world.cfg, world.sample)
    state = world._state()
    report = tracker.update(state)
    signals: list[PicoSignal] = []
    activated = False
    while world.t < max_s:
        s = operator.step(state, world.base, report, calibration if activated else None)
        activated = activated or s.activate
        signals.append(s)
        if s.reset or report.success:
            break
        ctrl0 = operator.ctrl0
        left, right = (
            teleop_to_robot(s.controllers[k], calibration.ee0[k], ctrl0[k], SCALE) for k in range(2)
        )
        vx, vy, vyaw, target_yaw = s.navigate_cmd
        world._apply(
            PlannerCommand(
                phase=Phase.APPROACH_A,  # unused by the toy world
                nav=(vx, vy, vyaw),
                heading=target_yaw,
                left_wrist=left,
                right_wrist=right,
                hand_closure=(float(s.closed[0]), float(s.closed[1])),
                abort_reason=None,
            )
        )
        state = world._state()
        report = tracker.update(state)
    return signals, world, report.success


def test_operator_config_loads_every_key() -> None:
    cfg = OperatorConfig.load()
    assert cfg.grasp_name in GRASP_FINGERTIP
    assert cfg.yaw_rate_min >= TURN_FLAG


@pytest.mark.parametrize(("level", "seed"), [(0, 0), (1, 3)])
def test_virtual_operator_succeeds_through_the_pico_signal_path(level: int, seed: int) -> None:
    signals, _, success = run_operator(level, seed)
    assert success
    assert signals[0].activate and not any(s.activate for s in signals[1:])
    stages = [s.stage for s in signals]
    assert stages[1] == "engage"
    for phase in ("REACH", "GRASP", "LIFT", "CARRY", "LOWER", "RELEASE"):
        assert phase in stages


def test_operator_holds_the_activation_pose_until_calibrated_and_engaged() -> None:
    world = ToyWorld(0, 0)
    operator = VirtualOperator(OperatorConfig.load())
    operator.reset(TrayPlanner(world.planner_cfg, world.cfg, world.sample))
    report = StepTracker(world.cfg, world.sample).update(world._state())
    first = operator.step(world._state(), world.base, report, None)
    assert first.activate and first.stage == "activate"
    for _ in range(200):  # no calibration yet: stays in engage however long
        world.t += DT
        s = operator.step(world._state(), world.base, report, None)
        assert s.stage == "engage" and not s.activate
        np.testing.assert_array_equal(s.controllers[0], operator.ctrl0[0])
        assert s.navigate_cmd[:3] == (0.0, 0.0, 0.0) and s.closed == (False, False)


def test_target_yaw_is_the_integral_of_the_stick() -> None:
    signals, _, _ = run_operator(0, 0)
    vyaw = np.array([s.navigate_cmd[2] for s in signals])
    target = np.array([s.navigate_cmd[3] for s in signals])
    gap = target - np.cumsum(vyaw) * DT
    np.testing.assert_allclose(np.arctan2(np.sin(gap), np.cos(gap)), 0.0, atol=1e-9)
    pushed = vyaw[vyaw != 0.0]
    assert pushed.size > 0 and np.all(np.abs(pushed) >= TURN_FLAG)


def test_hands_use_one_pico_grasp_or_open() -> None:
    signals, _, _ = run_operator(0, 0)
    closed = [s.closed for s in signals]
    assert (True, True) in closed and (False, False) in closed


def test_operator_gives_up_after_the_planner_aborts() -> None:
    world = ToyWorld(0, 0)
    world.block_base()  # never reaches the table: APPROACH_A times out
    cfg = OperatorConfig.load()
    operator = VirtualOperator(cfg)
    operator.reset(TrayPlanner(world.planner_cfg, world.cfg, world.sample))
    calibration = Calibration(ee0=(world.start_wrists[0], world.start_wrists[1]), scale=1.0)
    tracker = StepTracker(world.cfg, world.sample)
    abort_t = None
    for k in range(3000):
        state = world._state()
        s = operator.step(state, world.base, tracker.update(state), calibration if k else None)
        if s.stage == "ABORT" and abort_t is None:
            abort_t = world.t
        if s.reset:
            assert abort_t is not None
            assert world.t - abort_t == pytest.approx(cfg.give_up_s, abs=2 * DT)
            return
        world.t += DT
    pytest.fail("operator never gave up")


def test_style_changes_the_wrist_path_and_is_deterministic() -> None:
    def wrist_path(style_seed: int) -> np.ndarray:
        signals, _, _ = run_operator(0, 0, style_seed=style_seed, max_s=12.0)
        return np.array([s.controllers[0][:3, 3] for s in signals])

    a, b, c = wrist_path(1), wrist_path(1), wrist_path(2)
    np.testing.assert_array_equal(a, b)
    n = min(len(a), len(c))
    assert np.abs(a[:n] - c[:n]).max() > 0.005


@pytest.mark.parametrize("k", range(6))
def test_styled_operator_succeeds(k: int) -> None:
    # The planner's sag correction must not integrate the style's lag: it froze 4 cm
    # of it in GRASP while the hands kept their style near the tray.
    level, seed = k % 2, 20 + k
    _, _, success = run_operator(level, seed, style_seed=style_seed_for(0, level, seed, 1))
    assert success


def test_yaw_stick_turns_and_lets_go() -> None:
    stick = YawStick(DT, rate_max=0.5)
    yaw, heading, out = 0.0, math.radians(90), []
    for _ in range(500):
        vyaw, target = stick.step(heading, yaw)
        if abs(vyaw) >= TURN_FLAG:  # G1GearWbcPolicy
            yaw += float(np.clip((target - yaw) / 0.5, -1, 1)) * DT
        out.append(vyaw)
    assert abs(yaw - heading) < math.radians(2.0)
    assert max(out) == pytest.approx(0.5)
    assert out[-1] == 0.0  # let go once there


def test_yaw_stick_keeps_the_target_next_to_the_heading() -> None:
    # Level 1 seed 20 on the sim: steering by the body's error alone let target_yaw
    # drift to -0.36 rad for a heading near -0.15, and the body never got there.
    stick = YawStick(DT, rate_max=0.6)
    stick.target_yaw = -0.36  # left behind on the far side
    rng = np.random.default_rng(0)
    yaw, heading, worst = -0.10, -0.15, 0.0
    for k in range(1500):
        vyaw, target = stick.step(heading, yaw)
        if abs(vyaw) >= TURN_FLAG:
            yaw += float(np.clip((target - yaw) / 0.5, -1, 1)) * DT
        yaw += float(rng.normal(scale=0.002))  # the walk sways the heading
        if k > 200:
            worst = max(worst, abs(target - heading))
    assert worst < 0.05
    assert abs(yaw - heading) < math.radians(3.0)


def test_yaw_stick_turns_half_round_one_way() -> None:
    # The toy world's 180 degree turn: the wrapped error flipped sign with every
    # wobble of the body, and the stick rocked in place.
    stick = YawStick(DT, rate_max=0.5)
    yaw, signs = 0.0, set()
    for _ in range(600):
        vyaw, target = stick.step(math.pi, yaw)
        if math.cos(yaw) > -0.5:  # still more than 60 degrees from the heading
            signs.add(float(np.sign(vyaw)))
        if abs(vyaw) >= TURN_FLAG:
            error = math.atan2(math.sin(target - yaw), math.cos(target - yaw))
            yaw += float(np.clip(error / 0.5, -1, 1)) * DT
    assert len(signs - {0.0}) == 1
    assert abs(math.atan2(math.sin(math.pi - yaw), math.cos(math.pi - yaw))) < math.radians(2)


def test_yaw_stick_lets_go_when_not_steering() -> None:
    stick = YawStick(DT, rate_max=0.5)
    stick.step(0.5, 0.0)
    assert stick.step(0.5, 0.0, steer=False) == (0.0, stick.target_yaw)


def test_yaw_stick_refuses_a_minimum_below_the_turn_flag() -> None:
    with pytest.raises(ValueError):
        YawStick(DT, rate_max=0.5, rate_min=0.05)


@pytest.mark.parametrize("grasp", sorted(GRASP_FINGERTIP))
def test_pico_fingers_decode_as_decoupled_wbc_reads_them(grasp: str) -> None:
    # G1GripperInverseKinematicsSolver: a finger closes when its tip is within 5 cm of the thumb's.
    def closed_fingers(tips: np.ndarray) -> list[int]:
        pos = tips[:, :3, 3]
        return [i for i in (9, 14, 19, 24) if np.linalg.norm(pos[4] - pos[i]) < 0.05]

    assert closed_fingers(pico_fingers(False, grasp)) == []
    assert closed_fingers(pico_fingers(True, grasp)) == [GRASP_FINGERTIP[grasp]]
