// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type EpisodeId = string;
export type Kind =
  | "teleop_demo"
  | "teleop_correction"
  | "recovery"
  | "sim_rollout"
  | "variant"
  | "eval_rollout"
  | "diag_rollout";
export type OperatorKind = "human" | "machine";
export type IsRoot = boolean;
export type ConditionId = string;
export type RootId = string | null;
export type ParentId = string | null;
export type SourceId = string | null;
export type InterventionId = string | null;
export type CheckpointId = string | null;
export type RolloutSeed = number | null;
export type SimSuccess = boolean | null;
export type InfraStatus = string | null;
export type CameraParamsHash = string | null;
export type RunPlanId = string;
export type BundleUri = string;
export type License = string;
export type DataClass = "public" | "internal" | "restricted";
export type Split = string;
export type SourceKind = "teleop" | "synthetic" | "egocentric";
export type ActionQuality = "measured" | "planned" | "retargeted" | "pseudo" | "none";
export type DeidStatus = "raw" | "blurred" | "verified";
export type EmbodimentId = string;
export type SourceDetail =
  ("psi_data" | "teleop_keyboard" | "teleop_pico" | "planner_wbc" | "planner_amo") | null;
export type Renderer = ("mujoco" | "isaac") | null;
export type SyntheticTier = ("S1" | "S2" | "S3" | "S4") | null;
export type BenchmarkCopyId = string | null;

export interface Episode {
  episode_id: EpisodeId;
  kind: Kind;
  operator_kind: OperatorKind;
  is_root: IsRoot;
  condition_id: ConditionId;
  root_id?: RootId;
  parent_id?: ParentId;
  source_id?: SourceId;
  intervention_id?: InterventionId;
  checkpoint_id?: CheckpointId;
  rollout_seed?: RolloutSeed;
  sim_success?: SimSuccess;
  infra_status?: InfraStatus;
  camera_params_hash?: CameraParamsHash;
  run_plan_id: RunPlanId;
  bundle_uri: BundleUri;
  license: License;
  data_class: DataClass;
  split: Split;
  source_kind: SourceKind;
  action_quality: ActionQuality;
  deid_status: DeidStatus;
  embodiment_id: EmbodimentId;
  meta: EpisodeMetadata;
}
/**
 * This interface was referenced by `Episode`'s JSON-Schema
 * via the `definition` "EpisodeMetadata".
 */
export interface EpisodeMetadata {
  source_detail?: SourceDetail;
  renderer?: Renderer;
  synthetic_tier?: SyntheticTier;
  benchmark_copy_id?: BenchmarkCopyId;
}
