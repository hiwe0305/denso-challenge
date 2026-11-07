// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type EpisodeId = string;
export type TableSha256 = string;
export type FailedStep = number | null;
export type RowId = string;
export type AttributeTo = string;
export type Intervention = string;
export type ConsumesBudget = boolean;
export type Confirmed = boolean;
export type Probe = string;
export type Where = string;
export type Value = number;
export type Threshold = number | null;
export type Evidence = ProbeMeasurement[];
export type Hypotheses = StageHypothesis[];
export type Code = string;
export type Reason = string;
export type Unavailable = DiagnosisSkip[];

/**
 * Stage hypotheses and unavailable table rows for one failure.
 */
export interface StageAttribution {
  episode_id: EpisodeId;
  table_sha256: TableSha256;
  failed_step?: FailedStep;
  hypotheses: Hypotheses;
  unavailable: Unavailable;
}
/**
 * A proposed attribution; confirmation belongs to the engineer.
 *
 * This interface was referenced by `StageAttribution`'s JSON-Schema
 * via the `definition` "StageHypothesis".
 */
export interface StageHypothesis {
  row_id: RowId;
  attribute_to: AttributeTo;
  intervention: Intervention;
  consumes_budget: ConsumesBudget;
  confirmed?: Confirmed;
  evidence?: Evidence;
}
/**
 * A probe measurement supporting an attribution hypothesis.
 *
 * This interface was referenced by `StageAttribution`'s JSON-Schema
 * via the `definition` "ProbeMeasurement".
 */
export interface ProbeMeasurement {
  probe: Probe;
  where: Where;
  value: Value;
  threshold?: Threshold;
}
/**
 * This interface was referenced by `StageAttribution`'s JSON-Schema
 * via the `definition` "DiagnosisSkip".
 */
export interface DiagnosisSkip {
  code: Code;
  reason: Reason;
}
