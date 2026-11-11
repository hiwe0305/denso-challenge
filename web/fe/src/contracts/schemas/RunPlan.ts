// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type Name = string;
export type Purpose = "g0_repro" | "e1" | "branch_train" | "aa_test" | "round" | "holdout" | "hd";
export type Branch = string;
export type Method = "psi0" | "act" | "dp";
export type Status = "draft" | "frozen";
export type LockPath = string | null;
export type LockSha256 = string | null;
export type FrozenAt = string | null;

/**
 * Experimental RunPlan specification.
 */
export interface RunPlan {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  name: Name;
  purpose?: Purpose;
  branch?: Branch;
  method?: Method;
  status?: Status;
  lock_path?: LockPath;
  lock_sha256?: LockSha256;
  frozen_at?: FrozenAt;
  body?: Body;
}
export interface Meta {
  [k: string]: unknown;
}
export interface Body {
  [k: string]: unknown;
}
