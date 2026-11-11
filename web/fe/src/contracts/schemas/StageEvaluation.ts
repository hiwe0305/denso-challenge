// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type StageSuccess = (boolean | null)[];
export type StageStatus = ("pass" | "fail" | "not_attempted" | "unknown")[] | null;
export type UnknownReason =
  (("missing_signal" | "signal_all_null" | "step_not_in_trace" | "no_verdict") | null)[] | null;
export type StepEnterS = (number | null)[] | null;
export type StepExitS = (number | null)[] | null;
export type FirstFailedStage = number | null;
export type FailureKind = string | null;
export type FailureClass = ("approach" | "grasp" | "carry" | "place" | "balance") | null;

export interface StageEvaluation {
  stage_success: StageSuccess;
  stage_status?: StageStatus;
  unknown_reason?: UnknownReason;
  step_enter_s?: StepEnterS;
  step_exit_s?: StepExitS;
  first_failed_stage?: FirstFailedStage;
  failure_kind?: FailureKind;
  failure_class?: FailureClass;
}
