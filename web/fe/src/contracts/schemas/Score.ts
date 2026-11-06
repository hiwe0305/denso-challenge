// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type EpisodeId = string;
export type ConfigSha256 = string;
export type TraceSha256 = string;
export type ScorerVersion = string;
export type Success = boolean | null;
export type StepStatus = ("pass" | "fail" | "not_attempted" | "unknown")[];
export type UnknownReason =
  (("missing_signal" | "signal_all_null" | "step_not_in_trace" | "no_verdict") | null)[] | null;
export type StepEnterS = (number | null)[] | null;
export type StepExitS = (number | null)[] | null;
export type FirstFailedStep = number | null;
export type FailureKind = string | null;
export type FailureClass = ("approach" | "grasp" | "carry" | "place" | "balance") | null;
export type Level = number | null;
export type BalanceViolated = boolean;

/**
 * Episode task evaluation score.
 */
export interface Score {
  site_id?: SiteId;
  task_id: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  episode_id: EpisodeId;
  config_sha256: ConfigSha256;
  trace_sha256: TraceSha256;
  scorer_version?: ScorerVersion;
  success?: Success;
  step_status?: StepStatus;
  unknown_reason?: UnknownReason;
  step_enter_s?: StepEnterS;
  step_exit_s?: StepExitS;
  first_failed_step?: FirstFailedStep;
  failure_kind?: FailureKind;
  failure_class?: FailureClass;
  level?: Level;
  balance_violated?: BalanceViolated;
}
export interface Meta {
  [k: string]: unknown;
}
