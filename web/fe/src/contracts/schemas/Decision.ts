// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type Kind =
  "plan_review" | "dev_gate" | "aa_test" | "holdout" | "milestone" | "repair_ticket";
export type SubjectKind = string;
export type SubjectId = string;
export type Verdict =
  "approved" | "overridden" | "rejected" | "pass" | "fail" | "open" | "closed" | "recorded";
export type SignedBy = string;
export type Reason = string;
export type SupersedesDecisionId = string | null;

/**
 * Logged lifecycle gate, review, or milestone decision.
 */
export interface Decision {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  kind: Kind;
  subject_kind: SubjectKind;
  subject_id: SubjectId;
  verdict?: Verdict;
  metrics?: Metrics;
  criteria?: Criteria;
  signed_by: SignedBy;
  reason: Reason;
  supersedes_decision_id?: SupersedesDecisionId;
}
export interface Meta {
  [k: string]: unknown;
}
export interface Metrics {
  [k: string]: unknown;
}
export interface Criteria {
  [k: string]: unknown;
}
