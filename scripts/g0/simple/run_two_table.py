"""Render the SONIC two-table env from outside the robot, with textured objects and segmentation.

SIMPLE's mujoco mode builds each object only from white collision pieces
(engines/mujoco.py, rgba=[1,1,1,1]); textured visuals live in USD for Isaac.
This script leaves the simulation untouched and builds a second, render-only
model: a copy of the compiled MjSpec where every object body also carries its
textured merged mesh (cocad_merge.obj + CustomMaterial.png from the same folder
as its collision pieces) as a visual-only geom. Each frame copies qpos from the
running sim into the render model, so both stay in lockstep.

The robot stands under GR00T decoupled WBC, the controller SIMPLE uses for
*Teleop-v0 tasks (agents/pico_decoupled_agent.py), without the PICO teleop
part: the upper body holds the WBC default pose and the navigate command is
zero. The WBC runs from the first step while the elastic band holds the pelvis;
the band is lowered at 0.15 m/s (SIMPLE's drop rate) and released once
length <= -0.25 m and the pelvis is still, as in agents/pico_sonic_agent.py.

Outputs: overview RGB video, segmentation video, head-camera RGB from the
textured model, still frames, a pelvis/uprightness trace and a report.json.

Run with the SIMPLE venv from scripts/g0/setup_simple.sh, standing then walking back:

    MUJOCO_GL=egl fwdata/simple/.venv/bin/python scripts/g0/simple/run_two_table.py \
        --walk-cmd=-0.25,0,0,0 --out fwdata/simple/two_table/walk
"""

import argparse
import json
import sys
import time
from pathlib import Path

import gymnasium as gym
import imageio.v2 as iio
import mujoco
import numpy as np
import tyro

SEG_COLORS = {
    "floor": (40, 48, 60),
    "scene": (90, 100, 112),
    "robot": (150, 120, 220),
    "table": (70, 130, 200),
    "other": (255, 255, 255),
}
OBJECT_PALETTE = [(235, 90, 50), (60, 190, 110), (240, 200, 40), (230, 80, 170), (60, 200, 220), (250, 150, 90), (180, 230, 80), (255, 120, 140)]
TABLE_RGBA = [0.62, 0.45, 0.30, 1.0]


def dominant_colour(png: Path) -> list[float]:
    """Mean colour of the texture's saturated or mid-tone pixels (drops black and white padding)."""
    img = iio.imread(png)[..., :3].astype(np.float32) / 255.0
    pixels = img.reshape(-1, 3)[:: max(1, img.shape[0] * img.shape[1] // 200_000)]
    lum = pixels.mean(axis=1)
    keep = (lum > 0.08) & (lum < 0.95)
    colour = pixels[keep].mean(axis=0) if keep.any() else pixels.mean(axis=0)
    return [*colour.tolist(), 1.0]


def visual_source(folder: Path) -> tuple[Path, Path | None, list[float] | None] | None:
    """Pick a visual mesh next to the collision pieces, with a UV texture or a colour.

    SIMPLE's "objects" set ships cocad_merge.obj with UVs and CustomMaterial.png.
    The GraspNet set ships meshes without UVs; its textures sit in
    <set>/ruled_models/textures/<id>_texture.png for the USD, so use their colour.
    """
    obj, png = folder / "cocad_merge.obj", folder / "CustomMaterial.png"
    if obj.exists() and png.exists():
        return obj, png, None
    mesh = next((folder / n for n in ("simply.obj", "manifold.obj", "coacd_merge.obj") if (folder / n).exists()), None)
    if mesh is None:
        return None
    set_root, model_id = folder.parents[2], folder.parent.name
    textures = set_root / "ruled_models" / "textures"
    tex = next((textures / f"{model_id}_texture{ext}" for ext in (".png", ".jpg") if (textures / f"{model_id}_texture{ext}").exists()), None)
    return mesh, None, dominant_colour(tex) if tex else [0.85, 0.55, 0.25, 1.0]


class StandAgent:
    """Decoupled WBC holding the default stance; PicoDecoupledAgent minus the PICO streamer."""

    def __init__(self, robot):
        from decoupled_wbc.control.main.teleop.configs.configs import ControlLoopConfig
        from decoupled_wbc.control.policy.wbc_policy_factory import get_wbc_policy
        from decoupled_wbc.control.robot_model.instantiation.g1 import instantiate_g1_robot_model

        self.robot = robot
        self.sim_dt = robot.sim_dt
        cfg = robot.sonic_config
        enable_waist = cfg.get("enable_waist", False)
        self._dwbc_robot_model = instantiate_g1_robot_model(
            waist_location="lower_and_upper_body" if enable_waist else "lower_body",
            high_elbow_pose=cfg.get("high_elbow_pose", False),
        )
        supp = self._dwbc_robot_model.supplemental_info
        assert supp.body_actuated_joints == robot.joint_names[:29]
        dwbc_config = ControlLoopConfig(enable_waist=enable_waist, high_elbow_pose=cfg.get("high_elbow_pose", False))
        wbc_config = dwbc_config.load_wbc_yaml()
        assert wbc_config["SIMULATE_DT"] == self.sim_dt
        self._wbc_policy = get_wbc_policy("g1", self._dwbc_robot_model, wbc_config, init_time=dwbc_config.upper_body_joint_speed)
        self._control_frequency = dwbc_config.control_frequency
        self._cached_target_q = None
        self._cached_left_hand_q = None
        self._cached_right_hand_q = None
        self.nav = None  # [vx, vy, yaw flag, target yaw]; None = stand still

    def reset(self):
        # As teleop_decoupled_wbc._on_episode_reset: fresh pipeline, RL lower body engaged.
        self._wbc_policy.reset(init_time=time.monotonic())
        self._wbc_policy.lower_body_policy.use_policy_action = True
        self._cached_target_q = None

    def _build_wbc_observation(self, sim_obs: dict) -> dict:
        # Copied from PicoDecoupledAgent._build_wbc_observation (importing that
        # module pulls in PICO video streaming deps this script does not need).
        rm = self._dwbc_robot_model
        nat = lambda q: np.concatenate([q[:3], q[5:7], q[3:5]])  # MJCF hand order -> natural
        z7 = np.zeros(7)

        def full(body_key, hand_key, default_body):
            return rm.get_configuration_from_actuated_joints(
                body_actuated_joint_values=sim_obs.get(body_key, default_body),
                left_hand_actuated_joint_values=nat(sim_obs.get(f"left_hand_{hand_key}", z7)),
                right_hand_actuated_joint_values=nat(sim_obs.get(f"right_hand_{hand_key}", z7)),
            )

        obs = {
            "q": full("body_q", "q", None),
            "dq": full("body_dq", "dq", None),
            "ddq": full("body_ddq", "ddq", np.zeros(29)),
            "tau_est": full("body_tau_est", "tau_est", np.zeros(29)),
            "floating_base_pose": sim_obs["floating_base_pose"],
            "floating_base_vel": sim_obs["floating_base_vel"],
            "floating_base_acc": sim_obs.get("floating_base_acc", np.zeros(6)),
            "torso_quat": sim_obs.get("secondary_imu_quat", np.array([1, 0, 0, 0])),
            "torso_ang_vel": sim_obs["secondary_imu_vel"][3:6] if "secondary_imu_vel" in sim_obs else np.zeros(3),
            "wrist_pose": sim_obs.get("wrist_pose", np.zeros(14)),
        }
        return obs

    def get_action(self):
        # Copied from PicoDecoupledAgent.get_stabilize_action: WBC default upper-body
        # pose, zero navigate command, default base height; 2 s ramp on the first step.
        from decoupled_wbc.control.main.constants import DEFAULT_BASE_HEIGHT, DEFAULT_NAV_CMD
        from simple.core.action import ActionCmd

        t_now = time.monotonic()
        self._wbc_policy.set_observation(self._build_wbc_observation(self.robot.prepare_obs()))
        first = self._cached_target_q is None
        self._wbc_policy.set_goal({
            "target_upper_body_pose": self._dwbc_robot_model.get_initial_upper_body_pose(),
            "navigate_cmd": np.asarray(self.nav if self.nav is not None else DEFAULT_NAV_CMD),
            "base_height_command": np.atleast_1d(np.asarray(DEFAULT_BASE_HEIGHT)),
            "target_time": t_now + (2.0 if first else 1 / self._control_frequency),
            "interpolation_garbage_collection_time": t_now - 2 / self._control_frequency,
            "timestamp": t_now,
        })
        wbc_action = self._wbc_policy.get_action(time=t_now)
        rm = self._dwbc_robot_model
        self._cached_target_q = rm.get_body_actuated_joints(wbc_action["q"])
        return ActionCmd(
            "decoupled_wbc",
            target_q=self._cached_target_q,
            target_waist=wbc_action["target_waist"],
            left_hand_q=rm.get_hand_actuated_joints(wbc_action["q"], side="left"),
            right_hand_q=rm.get_hand_actuated_joints(wbc_action["q"], side="right"),
        )


def uprightness(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    """z of the torso's up axis in world frame: 1 = upright, 0 = lying flat."""
    torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso_link")
    return float(data.xmat[torso].reshape(3, 3)[2, 2])


def build_render_model(spec: mujoco.MjSpec, object_actors: dict) -> tuple[mujoco.MjModel, mujoco.MjModel, dict]:
    """Copy the spec, attach textured visual meshes to object bodies, colour tables."""
    vis = spec.copy()
    attached = {}
    for label, actor in object_actors.items():
        meshes = getattr(actor.asset, "collision_meshes_mujoco", None) or []
        if not meshes:
            continue
        body = vis.body(label)
        found = visual_source(Path(meshes[0]).resolve().parent)
        if body is None or found is None:
            attached[label] = "no visual mesh"
            continue
        obj, png, rgba = found
        mat_name = f"vis_{label}_mat"
        if png is not None:
            tex = vis.add_texture(name=f"vis_{label}_tex", type=mujoco.mjtTexture.mjTEXTURE_2D, file=str(png))
            mat = vis.add_material(name=mat_name)
            mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = tex.name
            attached[label] = f"texture {png.name} on {obj.name}"
        else:
            vis.add_material(name=mat_name, rgba=rgba)
            attached[label] = f"dominant colour {[round(c, 2) for c in rgba[:3]]} on {obj.name}"
        mesh = vis.add_mesh(name=f"vis_{label}_mesh", file=str(obj))
        mesh.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
        body.add_geom(
            name=f"vis_{label}_geom", type=mujoco.mjtGeom.mjGEOM_MESH, meshname=mesh.name,
            material=mat_name, contype=0, conaffinity=0, density=0, group=1,
        )
        # Hide the white collision pieces in the render model only.
        for geom in body.geoms:
            if geom.name != f"vis_{label}_geom":
                geom.rgba = [1, 1, 1, 0]
    vis.visual.headlight.ambient = [0.45, 0.45, 0.45]
    vis.visual.headlight.diffuse = [0.6, 0.6, 0.6]
    for geom in vis.geoms:
        if geom.name and geom.name.startswith("table") and geom.name.endswith("_geom"):
            geom.rgba = TABLE_RGBA
    vis.visual.global_.offwidth = max(vis.visual.global_.offwidth, 1920)
    vis.visual.global_.offheight = max(vis.visual.global_.offheight, 1080)
    rgb_model = vis.compile()
    # Multisampling blends segment-id colours at edges into ids that do not exist.
    vis.visual.quality.offsamples = 0
    seg_model = vis.compile()
    return rgb_model, seg_model, attached


def segment_lut(model: mujoco.MjModel, object_labels: list[str]) -> tuple[np.ndarray, dict]:
    """Map every geom id to an RGB colour by what it belongs to."""
    pelvis = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
    robot_root = model.body_rootid[pelvis] if pelvis >= 0 else -1
    obj_colors = {label: OBJECT_PALETTE[i % len(OBJECT_PALETTE)] for i, label in enumerate(object_labels)}
    lut = np.zeros((model.ngeom, 3), dtype=np.uint8)
    for g in range(model.ngeom):
        body = model.geom_bodyid[g]
        bname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body) or ""
        gname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        if bname in obj_colors:
            lut[g] = obj_colors[bname]
        elif bname.startswith("table"):
            lut[g] = SEG_COLORS["table"]
        elif robot_root >= 0 and model.body_rootid[body] == robot_root:
            lut[g] = SEG_COLORS["robot"]
        elif body == 0 and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_PLANE:
            lut[g] = SEG_COLORS["floor"]
        elif body == 0:
            lut[g] = SEG_COLORS["scene"]
        else:
            lut[g] = SEG_COLORS["other"]
        del gname
    legend = {**{k: list(v) for k, v in SEG_COLORS.items()}, **{k: list(v) for k, v in obj_colors.items()}}
    return lut, legend


def colorize(seg: np.ndarray, lut: np.ndarray) -> np.ndarray:
    ids, types = seg[..., 0], seg[..., 1]
    out = np.zeros(ids.shape + (3,), dtype=np.uint8)
    mask = (ids >= 0) & (types == mujoco.mjtObj.mjOBJ_GEOM)
    out[mask] = lut[ids[mask]]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-id", default="simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--drop-rate", type=float, default=0.15)
    parser.add_argument("--walk-cmd", type=str, default="", help="vx,vy,yawflag,yaw sent for --walk-steps after release + 100 steps")
    parser.add_argument("--walk-steps", type=int, default=150)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    import simple.envs  # noqa: F401
    from gear_sonic.utils.mujoco_sim.configs import SimLoopConfig
    from simple.core.action import ActionCmd

    sonic_config = tyro.cli(SimLoopConfig, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[]).load_wbc_yaml()
    sonic_config["ENV_NAME"] = "simple"
    args.out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    env = gym.make(
        args.env_id, sim_mode="mujoco", headless=True, render_hz=50,
        physics_dt=float(sonic_config["SIMULATE_DT"]), webrtc=False, sonic_config=sonic_config,
    )
    env.reset(seed=args.seed)
    sim = env.unwrapped
    t_reset = time.perf_counter() - t0

    actors = sim.task.layout.actors
    object_actors = {}
    for actor in actors.values():
        asset = getattr(actor, "asset", None)
        label = getattr(asset, "label", None) or getattr(asset, "uid", None)
        if getattr(asset, "collision_meshes_mujoco", None) and label:
            object_actors[label] = actor
    vis_model, seg_model, attached = build_render_model(sim.mjSpec, object_actors)
    vis_data = mujoco.MjData(vis_model)
    assert vis_model.nq == sim.mjModel.nq, (vis_model.nq, sim.mjModel.nq)

    lut, legend = segment_lut(vis_model, list(object_actors))
    renderer = mujoco.Renderer(vis_model, height=args.height, width=args.width)
    seg_renderer = mujoco.Renderer(seg_model, height=args.height, width=args.width)
    seg_renderer.enable_segmentation_rendering()

    # Frame the camera on the two tables and the robot.
    centres = [sim.mjData.body(n).xpos.copy() for n in ("pelvis",) if mujoco.mj_name2id(sim.mjModel, mujoco.mjtObj.mjOBJ_BODY, n) >= 0]
    for b in range(sim.mjModel.nbody):
        name = mujoco.mj_id2name(sim.mjModel, mujoco.mjtObj.mjOBJ_BODY, b) or ""
        if name.startswith("table"):
            centres.append(sim.mjData.xpos[b].copy())
    lookat = np.mean(centres, axis=0)
    spread = float(np.max(np.linalg.norm(np.array(centres)[:, :2] - lookat[:2], axis=1)))
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = [lookat[0], lookat[1], 0.7]
    cam.distance = max(2.5, 1.7 * spread + 1.0)
    cam.elevation = -32
    head_cam = "head_stereo_left" if mujoco.mj_name2id(vis_model, mujoco.mjtObj.mjOBJ_CAMERA, "head_stereo_left") >= 0 else None

    robot = sim.task.robot
    agent = StandAgent(robot)
    agent.reset()
    band = robot.elastic_band
    band_cmd = ActionCmd("elastic_band", dropping=False, drop_rate=0.0)

    def hold_band():
        # Refresh the band force after every physics substep while it is on.
        if band is not None and band.enable:
            robot.apply_action(band_cmd)

    sim.substep_callback = hold_band
    control_dt = 1.0 / 50
    released_at = None
    trace = []
    rgb_writer = iio.get_writer(args.out / "overview_rgb.mp4", fps=25, codec="libx264", quality=8)
    seg_writer = iio.get_writer(args.out / "overview_seg.mp4", fps=25, codec="libx264", quality=8)
    stills = {}
    for i in range(args.steps):
        if band is not None and band.enable:
            # Stop lowering at -0.25 m (band target ~ standing height), then wait
            # for the pelvis to settle; lowering past it drags the robot into a squat.
            band.length = max(band.length - args.drop_rate * control_dt, -0.25)
            if band.length <= -0.25 and abs(sim.mjData.qvel[2]) < 0.05:
                band.enable = False
                sim.mjData.xfrc_applied[robot.band_attached_link] = 0.0
                released_at = i
        walking = bool(args.walk_cmd) and released_at is not None and released_at + 100 <= i < released_at + 100 + args.walk_steps
        agent.nav = [float(x) for x in args.walk_cmd.split(",")] if walking else None
        env.step(agent.get_action())
        trace.append({
            "step": i,
            "walking": walking,
            "pelvis_xy": [round(float(x), 3) for x in sim.mjData.body("pelvis").xpos[:2]],
            "pelvis_z": round(float(sim.mjData.body("pelvis").xpos[2]), 4),
            "upright": round(uprightness(sim.mjModel, sim.mjData), 4),
            "band_on": bool(band is not None and band.enable),
        })
        vis_data.qpos[:] = sim.mjData.qpos
        vis_data.mocap_pos[:] = sim.mjData.mocap_pos
        vis_data.mocap_quat[:] = sim.mjData.mocap_quat
        mujoco.mj_kinematics(vis_model, vis_data)
        mujoco.mj_camlight(vis_model, vis_data)  # model cameras (head) need cam_xpos
        cam.azimuth = 135 + 360.0 * i / args.steps
        renderer.update_scene(vis_data, camera=cam)
        rgb = renderer.render()
        seg_renderer.update_scene(vis_data, camera=cam)
        seg = colorize(seg_renderer.render(), lut)
        if i % 2 == 0:
            rgb_writer.append_data(rgb)
            seg_writer.append_data(seg)
        if i in (0, args.steps // 2, args.steps - 1):
            stills[f"overview_rgb_{i:03d}"] = rgb
            stills[f"overview_seg_{i:03d}"] = seg
    rgb_writer.close()
    seg_writer.close()
    # Close-up on the pick table: centre on the objects nearest the robot.
    obj_pos = np.array([vis_data.body(label).xpos for label in object_actors])
    pelvis_xy = vis_data.body("pelvis").xpos[:2]
    near = obj_pos[np.argsort(np.linalg.norm(obj_pos[:, :2] - pelvis_xy, axis=1))[:4]]
    close = mujoco.MjvCamera()
    close.type = mujoco.mjtCamera.mjCAMERA_FREE
    close.lookat[:] = near.mean(axis=0)
    close.distance, close.elevation, close.azimuth = 1.1, -40, cam.azimuth
    for name, r in (("closeup_rgb", renderer), ("closeup_seg", seg_renderer)):
        r.update_scene(vis_data, camera=close)
        img = r.render()
        stills[name] = colorize(img, lut) if name.endswith("seg") else img
    if head_cam:
        # SIMPLE's head camera intrinsics assume 640 x 360.
        head_renderer = mujoco.Renderer(vis_model, height=360, width=640)
        head_renderer.update_scene(vis_data, camera=head_cam)
        stills["head_stereo_left_textured"] = head_renderer.render()
    for name, image in stills.items():
        iio.imwrite(args.out / f"{name}.png", image)
    env.close()

    report = {
        "env_id": args.env_id,
        "steps": args.steps,
        "controller": "decoupled_wbc (GR00T Balance/Walk ONNX), default stance, nav 0",
        "band_released_at_step": released_at,
        "after_release": {
            "steps": len([t for t in trace if not t["band_on"]]),
            "pelvis_z_min": min((t["pelvis_z"] for t in trace if not t["band_on"]), default=None),
            "pelvis_z_end": trace[-1]["pelvis_z"],
            "upright_min": min((t["upright"] for t in trace if not t["band_on"]), default=None),
            "upright_end": trace[-1]["upright"],
        },
        "reset_s": round(t_reset, 1),
        "objects": {label: attached.get(label, "not attached") for label in object_actors},
        "segmentation_legend_rgb": legend,
        "camera": {"lookat": [round(float(x), 3) for x in cam.lookat], "distance": round(cam.distance, 2), "elevation": cam.elevation},
        "isaacsim_imported": "isaacsim" in sys.modules,
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2))
    (args.out / "trace.json").write_text(json.dumps(trace))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
