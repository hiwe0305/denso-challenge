// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type Origin = "upstream" | "trained";
export type Method = "psi0" | "act" | "dp";
export type Branch = string | null;
export type BaseSourceId = string | null;
export type ParentCheckpointId = string | null;
export type ReleaseId = string | null;
export type Seed = number | null;
export type Step = number | null;
export type WeightsSha256 = string;
export type Uri = string;
export type IsFinal = boolean;

/**
 * Model checkpoint reference with origin and weights hash.
 */
export interface Checkpoint {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  origin?: Origin;
  method?: Method;
  branch?: Branch;
  base_source_id?: BaseSourceId;
  parent_checkpoint_id?: ParentCheckpointId;
  release_id?: ReleaseId;
  seed?: Seed;
  step?: Step;
  weights_sha256: WeightsSha256;
  uri: Uri;
  is_final?: IsFinal;
}
export interface Meta {
  [k: string]: unknown;
}
