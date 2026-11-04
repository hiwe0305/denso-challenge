// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type ReportId = string;
export type Reviewer = string;
export type DecidedAt = string;
export type FindingId = string;
export type Decision = "agree" | "override";
export type Reason = string;
export type Decisions = FindingDecision[];

/**
 * The engineer's answer to an AgentReport, recorded in fw review.
 */
export interface AgentReview {
  report_id: ReportId;
  reviewer: Reviewer;
  decided_at: DecidedAt;
  decisions?: Decisions;
}
/**
 * The engineer's review decision for a single finding.
 *
 * This interface was referenced by `AgentReview`'s JSON-Schema
 * via the `definition` "FindingDecision".
 */
export interface FindingDecision {
  finding_id: FindingId;
  decision: Decision;
  reason?: Reason;
}
