// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type RunPlanId = string;
export type FirstFailedStep = number;
export type FailureKind = string;
export type Level = number;
export type FailureClass = ("approach" | "grasp" | "carry" | "place" | "balance") | null;
export type ParentClusterId = string | null;
export type RepresentativeSeed = number | null;
export type MemberEpisodeIds = string[];
export type CardUri = string | null;

/**
 * Failure cluster grouping rollout failures.
 */
export interface Cluster {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  run_plan_id?: RunPlanId;
  first_failed_step: FirstFailedStep;
  failure_kind: FailureKind;
  level?: Level;
  failure_class?: FailureClass;
  parent_cluster_id?: ParentClusterId;
  representative_seed?: RepresentativeSeed;
  member_episode_ids?: MemberEpisodeIds;
  card_uri?: CardUri;
}
export interface Meta {
  [k: string]: unknown;
}
