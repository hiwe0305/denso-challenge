// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type RoundId = string | null;
export type ClusterId = string | null;
export type InterventionId = string;
export type InterventionType = string;
export type Diagnosis = string | null;
export type FailureKind = string;
export type FailureClass = ("approach" | "grasp" | "carry" | "place" | "balance") | null;
export type TaskFamily = string;
export type NConditions = number;
export type PParent = number;
export type PCandidate = number;
export type Fixed = number;

/**
 * Measured intervention fix rate event.
 */
export interface FixRateEvent {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  round_id?: RoundId;
  cluster_id?: ClusterId;
  intervention_id?: InterventionId;
  intervention_type?: InterventionType;
  diagnosis?: Diagnosis;
  failure_kind?: FailureKind;
  failure_class?: FailureClass;
  task_family?: TaskFamily;
  n_conditions?: NConditions;
  p_parent?: PParent;
  p_candidate?: PCandidate;
  fixed?: Fixed;
}
export interface Meta {
  [k: string]: unknown;
}
