// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type JobId = string;
export type TaskId = string;
export type Version = string;
export type ConditionId = string;
export type Seed = number;
export type Vector = number[];
export type Level = number;
export type RolloutSeed = number;
export type TraceId = string;
export type Uri = string;
export type Sha256 = string | null;
export type Step = number;
export type Kind = string;
export type MaxSteps = number;
export type Cameras = string[];
export type Signals = string[];
export type Timing = "sync" | "async";
export type LatencyProfileRef = string | null;

export interface RolloutRequest {
  job_id: JobId;
  task: TaskRef;
  condition: Condition;
  level: Level;
  rollout_seed: RolloutSeed;
  start_state?: StateRef | null;
  visual_override?: VisualOverride | null;
  fault?: FaultSpec | null;
  max_steps: MaxSteps;
  record?: RecordSpec;
  timing?: Timing;
  latency_profile_ref?: LatencyProfileRef;
}
/**
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "TaskRef".
 */
export interface TaskRef {
  task_id: TaskId;
  version?: Version;
}
/**
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "Condition".
 */
export interface Condition {
  condition_id: ConditionId;
  task: TaskRef;
  seed: Seed;
  values?: Values;
  vector?: Vector;
}
export interface Values {
  [k: string]: boolean | number | string;
}
/**
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "StateRef".
 */
export interface StateRef {
  trace: TraceRef;
  step: Step;
}
/**
 * A rollout trace (flywheel.contracts.trace; PO decisions G1, G1b on PR #48, 3/11/2026).
 *
 * `uri` names the directory `<trace_id>/` (its last path component is `trace_id`) holding
 * `steps.jsonl`, `camera_params.jsonl` and `rollout_result.json`; `sha256` is the sha256
 * of `steps.jsonl`.
 *
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "TraceRef".
 */
export interface TraceRef {
  trace_id: TraceId;
  uri: Uri;
  sha256?: Sha256;
}
/**
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "VisualOverride".
 */
export interface VisualOverride {
  values?: Values1;
}
export interface Values1 {
  [k: string]: boolean | number | string;
}
/**
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "FaultSpec".
 */
export interface FaultSpec {
  kind: Kind;
  parameters?: Parameters;
}
export interface Parameters {
  [k: string]: boolean | number | string;
}
/**
 * This interface was referenced by `RolloutRequest`'s JSON-Schema
 * via the `definition` "RecordSpec".
 */
export interface RecordSpec {
  cameras?: Cameras;
  signals?: Signals;
}
