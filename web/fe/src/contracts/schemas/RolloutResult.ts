// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type JobId = string;
export type TraceId = string;
export type Uri = string;
export type Sha256 = string | null;
export type SimSuccess = boolean | null;
export type InfraStatus = "ok" | "simulator_error" | "policy_error" | "timeout" | "out_of_memory";
export type WallSeconds = number;
export type GpuSeconds = number;
export type CameraParamsHash = string | null;
export type Name = string;
export type Version = string;
export type ImageDigest = string | null;
export type Nondeterminism = string[];
export type Timing = ("sync" | "async") | null;
export type TimingVerdict = ("ok" | "starved" | "not_checked") | null;
export type StarvedSteps = number | null;

export interface RolloutResult {
  job_id: JobId;
  trace_ref: TraceRef | null;
  sim_success: SimSuccess;
  infra_status: InfraStatus;
  usage: ResourceUsage;
  camera_params_hash: CameraParamsHash;
  adapter_info: AdapterInfo;
  timing?: Timing;
  timing_verdict?: TimingVerdict;
  starved_steps?: StarvedSteps;
}
/**
 * A rollout trace (flywheel.contracts.trace; PO decisions G1, G1b on PR #48, 3/11/2026).
 *
 * `uri` names the directory `<trace_id>/` (its last path component is `trace_id`) holding
 * `steps.jsonl`, `camera_params.jsonl` and `rollout_result.json`; `sha256` is the sha256
 * of `steps.jsonl`.
 *
 * This interface was referenced by `RolloutResult`'s JSON-Schema
 * via the `definition` "TraceRef".
 */
export interface TraceRef {
  trace_id: TraceId;
  uri: Uri;
  sha256?: Sha256;
}
/**
 * This interface was referenced by `RolloutResult`'s JSON-Schema
 * via the `definition` "ResourceUsage".
 */
export interface ResourceUsage {
  wall_seconds: WallSeconds;
  gpu_seconds?: GpuSeconds;
}
/**
 * Identity and reproducibility information reported by an adapter.
 *
 * This interface was referenced by `RolloutResult`'s JSON-Schema
 * via the `definition` "AdapterInfo".
 */
export interface AdapterInfo {
  name: Name;
  version: Version;
  image_digest?: ImageDigest;
  nondeterminism?: Nondeterminism;
}
