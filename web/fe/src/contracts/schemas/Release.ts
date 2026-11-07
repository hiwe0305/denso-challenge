// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type Name = string;
export type Kind = "robot" | "egocentric";
export type ParentReleaseId = string | null;
export type SplitPlanCfgId = string | null;
export type Status = "draft" | "frozen";
export type ManifestSha256 = string | null;
export type HoldoutGuardPassed = boolean | null;
export type CombinedLicense = string | null;
export type Items = {
  [k: string]: unknown;
}[];
export type FrozenAt = string | null;

/**
 * Frozen or draft dataset release manifest.
 */
export interface Release {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  name: Name;
  kind?: Kind;
  parent_release_id?: ParentReleaseId;
  split_plan_cfg_id?: SplitPlanCfgId;
  status?: Status;
  manifest_sha256?: ManifestSha256;
  holdout_guard_passed?: HoldoutGuardPassed;
  combined_license?: CombinedLicense;
  counts?: Counts;
  items?: Items;
  frozen_at?: FrozenAt;
}
export interface Meta {
  [k: string]: unknown;
}
export interface Counts {
  [k: string]: unknown;
}
