// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type Activity =
  | "data_download"
  | "teleop_session"
  | "data_generation"
  | "pipeline"
  | "qa"
  | "replay"
  | "export"
  | "train"
  | "probe"
  | "eval"
  | "diagnosis"
  | "agent_qa"
  | "holdout"
  | "storage"
  | "hd"
  | "review"
  | "other";
export type ResourceType = string;
export type Quantity = number;
export type Unit = string;
export type PricebookId = string;
export type UsdAmount = number;
export type HumanHours = number;
export type MeasureKind = "estimated" | "measured";
export type EstimateEntryId = string | null;
export type Branch = string | null;
export type RunPlanId = string;
export type ClusterId = string | null;
export type InterventionId = string | null;
export type JobId = string | null;
export type PersonCode = string | null;
export type ReversesEntryId = string | null;
export type Note = string | null;

/**
 * Cost ledger entry recording estimated or measured resource consumption.
 */
export interface LedgerEntry {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  activity: Activity;
  resource_type: ResourceType;
  quantity: Quantity;
  unit: Unit;
  pricebook_id?: PricebookId;
  usd_amount: UsdAmount;
  human_hours?: HumanHours;
  measure_kind: MeasureKind;
  estimate_entry_id?: EstimateEntryId;
  branch?: Branch;
  run_plan_id: RunPlanId;
  cluster_id?: ClusterId;
  intervention_id?: InterventionId;
  job_id?: JobId;
  person_code?: PersonCode;
  reverses_entry_id?: ReversesEntryId;
  note?: Note;
}
export interface Meta {
  [k: string]: unknown;
}
