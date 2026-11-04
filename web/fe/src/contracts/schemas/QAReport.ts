// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type ReportId = string;
export type EpisodeId = string;
export type ThresholdVersion = string;
export type Decision = "pass" | "flag" | "quarantine" | "reject";
export type Reasons = string[];
export type Name = string;
export type Value = number;
export type Threshold = number;
export type Passed = boolean;
export type Checks = QACheck[];

export interface QAReport {
  report_id: ReportId;
  episode_id: EpisodeId;
  threshold_version: ThresholdVersion;
  decision: Decision;
  reasons: Reasons;
  checks: Checks;
}
/**
 * This interface was referenced by `QAReport`'s JSON-Schema
 * via the `definition` "QACheck".
 */
export interface QACheck {
  name: Name;
  value: Value;
  threshold: Threshold;
  passed: Passed;
}
