// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type CheckpointId = string;
export type ConfigSha256 = string;
export type Code =
  "T1" | "T2" | "T3" | "T4" | "T5" | "T6" | "T7" | "T8" | "O1" | "O2" | "O3" | "O4";
export type StartStep = number;
export type Group = string | null;
export type Dim = number | null;
export type Value = number | ("NaN" | "Infinity" | "-Infinity");
export type Threshold = number | null;
export type StopJob = boolean;
export type Findings = DiagnosisFinding[];
export type Code1 = string;
export type Reason = string;
export type Skipped = DiagnosisSkip[];

export interface TrainDiagnosis {
  checkpoint_id: CheckpointId;
  config_sha256: ConfigSha256;
  findings: Findings;
  skipped?: Skipped;
}
/**
 * This interface was referenced by `TrainDiagnosis`'s JSON-Schema
 * via the `definition` "DiagnosisFinding".
 */
export interface DiagnosisFinding {
  code: Code;
  start_step: StartStep;
  group?: Group;
  dim?: Dim;
  value: Value;
  threshold?: Threshold;
  stop_job?: StopJob;
}
/**
 * This interface was referenced by `TrainDiagnosis`'s JSON-Schema
 * via the `definition` "DiagnosisSkip".
 */
export interface DiagnosisSkip {
  code: Code1;
  reason: Reason;
}
