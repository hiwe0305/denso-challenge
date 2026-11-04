// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type ReportId = string;
export type SubjectRef = string;
export type Stage = "dataset" | "train" | "stage1" | "stage3" | "inference" | "eval";
export type CreatedAt = string;
export type Name = string;
export type Revision = string;
export type Temperature = number;
export type PromptSha256 = string;
/**
 * @minItems 1
 */
export type Inputs = [AgentInput, ...AgentInput[]];
export type Ref = string;
export type Kind = string;
export type Sha256 = string;
export type FactId = string;
export type Name1 = string;
export type Value = number | string | boolean;
export type Unit = string;
export type SourceRef = string;
export type Facts = AgentFact[];
export type FindingId = string;
export type Code = string;
export type Rank = number;
export type TargetRef = string;
/**
 * @minItems 1
 */
export type Evidence = [string, ...string[]];
export type Figures = string[];
export type Insight = string;
export type Suggestion = string;
export type Findings = AgentFinding[];
export type EstimateId = string;
export type Quantity = string;
export type Low = number;
export type High = number;
export type Unit1 = string;
/**
 * @minItems 1
 */
export type Basis = [string, ...string[]];
export type Estimates = AgentEstimate[];
export type Status = "ok" | "broken";
export type Problems = string[];

/**
 * The complete QA/QC report produced by the agent for a single job or artifact.
 */
export interface AgentReport {
  report_id: ReportId;
  subject_ref: SubjectRef;
  stage: Stage;
  created_at: CreatedAt;
  model: AgentModel;
  inputs: Inputs;
  facts?: Facts;
  findings?: Findings;
  estimates?: Estimates;
  status: Status;
  problems?: Problems;
}
/**
 * Identification and configuration of the LLM generating the report.
 *
 * This interface was referenced by `AgentReport`'s JSON-Schema
 * via the `definition` "AgentModel".
 */
export interface AgentModel {
  name: Name;
  revision: Revision;
  temperature: Temperature;
  prompt_sha256: PromptSha256;
}
/**
 * An input artifact inspected by the agent.
 *
 * This interface was referenced by `AgentReport`'s JSON-Schema
 * via the `definition` "AgentInput".
 */
export interface AgentInput {
  ref: Ref;
  kind: Kind;
  sha256: Sha256;
}
/**
 * A deterministic fact computed by code that the agent's prose can reference.
 *
 * This interface was referenced by `AgentReport`'s JSON-Schema
 * via the `definition` "AgentFact".
 */
export interface AgentFact {
  fact_id: FactId;
  name: Name1;
  value: Value;
  unit?: Unit;
  source_ref: SourceRef;
}
/**
 * A specific problem or observation identified by the agent.
 *
 * This interface was referenced by `AgentReport`'s JSON-Schema
 * via the `definition` "AgentFinding".
 */
export interface AgentFinding {
  finding_id: FindingId;
  code: Code;
  rank: Rank;
  target_ref: TargetRef;
  evidence: Evidence;
  figures?: Figures;
  insight: Insight;
  suggestion: Suggestion;
}
/**
 * A range the agent predicts; the measured value lives in a later record, never here.
 *
 * This interface was referenced by `AgentReport`'s JSON-Schema
 * via the `definition` "AgentEstimate".
 */
export interface AgentEstimate {
  estimate_id: EstimateId;
  quantity: Quantity;
  low: Low;
  high: High;
  unit: Unit1;
  basis: Basis;
}
