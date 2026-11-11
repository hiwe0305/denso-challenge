// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type ConditionSeed = number;
export type Level = number;
export type Vector = number[];
export type LayoutHash = string;
export type Split = "train" | "dev";
export type Origin = "generated" | "extracted_from_demo";
export type SetId = string | null;
export type Quarantined = boolean;
export type QuarantineReason = string | null;
export type LayoutUri = string | null;

/**
 * Environment initial condition with seed and typed vector values.
 */
export interface Condition {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  condition_seed: ConditionSeed;
  level?: Level;
  values?: Values;
  vector?: Vector;
  layout_hash: LayoutHash;
  split?: Split;
  origin?: Origin;
  set_id?: SetId;
  quarantined?: Quarantined;
  quarantine_reason?: QuarantineReason;
  layout_uri?: LayoutUri;
}
export interface Meta {
  [k: string]: unknown;
}
export interface Values {
  [k: string]: unknown;
}
