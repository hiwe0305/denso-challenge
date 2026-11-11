// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type TraceId = string;
export type EpisodeId = string;
/**
 * RunPlan of the run; a run without one (G0, scripted eval) uses g0-<story>-<yyyymmdd>, for example g0-DA-38-20261103.
 */
export type RunPlanId = string;
export type Step = number;
/**
 * Simulation time the state was read, s.
 */
export type TState = number | ("NaN" | "Infinity" | "-Infinity");
/**
 * Simulation time of the frame fed to the policy in this cycle, s; null when the cycle has no new frame (not a repeat of the last one).
 */
export type TImage = number | ("NaN" | "Infinity" | "-Infinity") | null;
/**
 * Commanded joint angles, rad: action[0:28], in the order of UPPER_BODY.
 *
 * @minItems 28
 * @maxItems 28
 */
export type CmdUpper = [
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity")
];
/**
 * Measured joint angles, rad, in the order of UPPER_BODY.
 *
 * @minItems 28
 * @maxItems 28
 */
export type MeasUpper = [
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity")
];
/**
 * action[28:34] + action[35]: waist roll, pitch, yaw (rad), base_height (m), vx, vy (m/s, heading frame of the base), target_yaw (rad, world).
 *
 * @minItems 7
 * @maxItems 7
 */
export type CmdLower = [
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity")
];
/**
 * Measured, same order: waist joint angles, base height, base velocity in the heading frame, base yaw in the world frame.
 *
 * @minItems 7
 * @maxItems 7
 */
export type MeasLower = [
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity"),
  number | ("NaN" | "Infinity" | "-Infinity")
];
/**
 * Camera frames due in this cycle that never reached the policy; a count for this cycle, not a running total. Renders are synchronous in sim, so 0 there is measured.
 */
export type DroppedFrames = number;

/**
 * A single control cycle in a rollout trace; one line of `steps.jsonl`.
 *
 * One clock: MuJoCo simulation time `data.time`, in seconds. Non-finite values are
 * written as the strings "NaN", "Infinity", "-Infinity" so the line stays JSON; a
 * check that needs such a value says CHƯA RÕ instead of scoring it.
 */
export interface TraceStep {
  trace_id: TraceId;
  episode_id: EpisodeId;
  run_plan_id: RunPlanId;
  step: Step;
  t_state: TState;
  t_image?: TImage;
  cmd_upper: CmdUpper;
  meas_upper: MeasUpper;
  cmd_lower: CmdLower;
  meas_lower: MeasLower;
  dropped_frames?: DroppedFrames;
}
