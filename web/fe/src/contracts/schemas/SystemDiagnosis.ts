// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type EpisodeId = string;
export type Diagnosis =
  "clean" | "unknown" | "controller" | "runtime" | "sync" | "calibration" | "infra";
export type ConfigSha256 = string;
export type TraceSha256 = string;
export type RtcSha256 = string | null;
export type CameraSha256 = string | null;
export type InfraSha256 = string | null;
export type InfraStatus = string | null;
export type Code = "R1" | "R2" | "R3" | "R4" | "R5" | "R6";
export type Value = number;
export type Threshold = number | null;
export type Part = ("upper" | "lower") | null;
export type Where = string | null;
export type Detail = string | null;
export type Findings = SystemFinding[];
export type Code1 = string;
export type Reason = string;
export type Skipped = DiagnosisSkip[];
export type Timing = ("sync" | "async") | null;
export type Recorded = SystemFinding[];
export type RecordedSkipped = DiagnosisSkip[];

/**
 * One episode's system verdict, with unjudged checks and input hashes.
 */
export interface SystemDiagnosis {
  episode_id: EpisodeId;
  diagnosis: Diagnosis;
  config_sha256: ConfigSha256;
  trace_sha256: TraceSha256;
  rtc_sha256?: RtcSha256;
  camera_sha256?: CameraSha256;
  infra_sha256?: InfraSha256;
  infra_status?: InfraStatus;
  findings: Findings;
  skipped: Skipped;
  timing?: Timing;
  recorded?: Recorded;
  recorded_skipped?: RecordedSkipped;
}
/**
 * One measured F-SYS fault; part identifies the body half for R3.
 *
 * This interface was referenced by `SystemDiagnosis`'s JSON-Schema
 * via the `definition` "SystemFinding".
 */
export interface SystemFinding {
  code: Code;
  value: Value;
  threshold?: Threshold;
  part?: Part;
  where?: Where;
  detail?: Detail;
}
/**
 * This interface was referenced by `SystemDiagnosis`'s JSON-Schema
 * via the `definition` "DiagnosisSkip".
 */
export interface DiagnosisSkip {
  code: Code1;
  reason: Reason;
}
