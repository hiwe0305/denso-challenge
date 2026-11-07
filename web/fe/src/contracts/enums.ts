// File sinh ra. Không sửa tay.
// Nguồn: web/contracts/enums.py · sinh lại: uv run python -m web.contracts.generate_ts
//
// Ba nhóm, mức bảo đảm khác nhau (xem web/DESIGN.md Phụ lục A):
//   contract · lõi khai trong flywheel-contracts, test so từng bộ với nguồn
//   spec     · spec v10.5 / design 27/10 chốt, chưa vào hợp đồng, không máy nào kiểm
//   web      · của riêng web

// ========================================================================
// contract
// ========================================================================
/** contract · Episode.json:properties.source_kind */
export const sourceKind = ["teleop", "synthetic", "egocentric"] as const;
export type SourceKind = (typeof sourceKind)[number];
/** contract · EpisodeMetadata.json:properties.source_detail.anyOf[0] */
export const sourceDetail = ["psi_data", "teleop_keyboard", "teleop_pico", "planner_wbc", "planner_amo"] as const;
export type SourceDetail = (typeof sourceDetail)[number];
/** contract · EpisodeMetadata.json:properties.synthetic_tier.anyOf[0] */
export const syntheticTier = ["S1", "S2", "S3", "S4"] as const;
export type SyntheticTier = (typeof syntheticTier)[number];
/** contract · Episode.json:properties.action_quality */
export const actionQuality = ["measured", "planned", "retargeted", "pseudo", "none"] as const;
export type ActionQuality = (typeof actionQuality)[number];
/** contract · Episode.json:properties.kind */
export const episodeKind = ["teleop_demo", "teleop_correction", "recovery", "sim_rollout", "variant", "eval_rollout", "diag_rollout"] as const;
export type EpisodeKind = (typeof episodeKind)[number];
/** contract · Episode.json:properties.operator_kind */
export const operatorKind = ["human", "machine"] as const;
export type OperatorKind = (typeof operatorKind)[number];
/** contract · Episode.json:properties.data_class */
export const dataClass = ["public", "internal", "restricted"] as const;
export type DataClass = (typeof dataClass)[number];
/** contract · Episode.json:properties.deid_status */
export const deidStatus = ["raw", "blurred", "verified"] as const;
export type DeidStatus = (typeof deidStatus)[number];
/** contract · EpisodeMetadata.json:properties.renderer.anyOf[0] */
export const renderer = ["mujoco", "isaac"] as const;
export type Renderer = (typeof renderer)[number];
/** contract · QAReport.json:properties.decision */
export const qaDecision = ["pass", "flag", "quarantine", "reject"] as const;
export type QaDecision = (typeof qaDecision)[number];
/** contract · ReplayReport.json:properties.mode */
export const replayMode = ["kinematic", "dynamic"] as const;
export type ReplayMode = (typeof replayMode)[number];
/** contract · RolloutRequest.json:properties.timing */
export const evalMode = ["sync", "async"] as const;
export type EvalMode = (typeof evalMode)[number];
/** contract · flywheel.contracts.v0.InfraStatus */
export const infraStatus = ["ok", "simulator_error", "policy_error", "timeout", "out_of_memory"] as const;
export type InfraStatus = (typeof infraStatus)[number];
/** contract · flywheel.contracts.v0.FailureClass */
export const failureClass = ["approach", "grasp", "carry", "place", "balance"] as const;
export type FailureClass = (typeof failureClass)[number];
/** contract · TrainingMetric.json:properties.split */
export const trainSplit = ["train", "val"] as const;
export type TrainSplit = (typeof trainSplit)[number];
/** contract · flywheel.contracts.training.FindingCode */
export const trainFindingCode = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "O1", "O2", "O3", "O4"] as const;
export type TrainFindingCode = (typeof trainFindingCode)[number];
/** contract · TrainingMetric.json:properties.loss.anyOf[1] */
export const nonFinite = ["NaN", "Infinity", "-Infinity"] as const;
export type NonFinite = (typeof nonFinite)[number];
/** contract · ProbeP1.json, ProbeP2.json, ProbeP3.json, ProbeP4.json */
export const probe = ["P1", "P2", "P3", "P4"] as const;
export type Probe = (typeof probe)[number];

// ========================================================================
// spec
// ========================================================================
/** spec · DESIGN.md Phụ lục A [Đề xuất]; đối chiếu contract ở M0 */
export const taskId = ["two_table", "tray"] as const;
export type TaskId = (typeof taskId)[number];
/** spec · 03 §4.3 (cột Condition.split) */
export const split = ["train", "dev", "holdout", "unassigned"] as const;
export type Split = (typeof split)[number];
/** spec · design 27/10 §6; DESIGN.md §5.1 */
export const pipelineStage = ["INGEST", "NORMALIZE", "ANNOTATE", "QA", "RELEASE", "EXPORT"] as const;
export type PipelineStage = (typeof pipelineStage)[number];
/** spec · DESIGN.md §5.1 (enum của luồng, web giữ) */
export const stageRunStatus = ["PENDING", "RUNNING", "QA_EVALUATING", "PASSED", "PAUSED_FOR_REVIEW", "OVERRIDDEN", "FAILED", "ABORTED"] as const;
export type StageRunStatus = (typeof stageRunStatus)[number];
/** spec · DESIGN.md §5.1 bước 8 */
export const humanReviewAction = ["RETRY_STAGE", "APPLY_FIX_AND_RETRY", "FORCE_CONTINUE", "ABORT_PIPELINE"] as const;
export type HumanReviewAction = (typeof humanReviewAction)[number];
/** spec · design 27/10 §9.1 */
export const qaAgentVerdict = ["PASS", "WARNING", "FAIL"] as const;
export type QaAgentVerdict = (typeof qaAgentVerdict)[number];
/** spec · spec v10.5 §5.1; đã hiện thực trong DA-36 StepStatus */
export const stepStatus = ["pass", "fail", "not_attempted", "unknown"] as const;
export type StepStatus = (typeof stepStatus)[number];
/** spec · spec v10.5 §6.4; đã hiện thực trong DA-13 Diagnosis */
export const systemDiagnosis = ["clean", "unknown", "controller", "runtime", "sync", "calibration", "infra"] as const;
export type SystemDiagnosis = (typeof systemDiagnosis)[number];
/** spec · spec v10.5 §5.2 */
export const failureCodeTwoTable = ["L-REACH", "L-GRASP", "L-SLIP", "L-WALK", "L-COLLIDE", "L-PLACE", "L-RELEASE", "L-BALANCE", "L-TIMEOUT", "L-UNKNOWN"] as const;
export type FailureCodeTwoTable = (typeof failureCodeTwoTable)[number];
/** spec · design 28/10 §3.3 [Đề xuất] */
export const failureCodeTray = ["L-PART-DROP", "L-TRAY-TILT", "L-ONE-HAND", "L-PLACE-POSE", "L-TIMEOUT", "L-BALANCE"] as const;
export type FailureCodeTray = (typeof failureCodeTray)[number];
/** spec · spec v10.5 §6.9; design 27/10 §10 */
export const clusterDiagnosis = ["CHUA_RO", "HE_THONG_CONTROLLER", "HE_THONG_RUNTIME", "HE_THONG_DONG_BO", "HE_THONG_CALIBRATION", "KHONG_KHA_THI", "TRANG_THAI_DAU_XAU", "NHAN_THUC", "NGOAI_MIEN", "THIEU_VUNG_PHU", "KY_NANG_YEU"] as const;
export type ClusterDiagnosis = (typeof clusterDiagnosis)[number];
/** spec · spec v10.5 §6.9 (3 trong 11) */
export const dataBudgetDiagnosis = ["TRANG_THAI_DAU_XAU", "THIEU_VUNG_PHU", "KY_NANG_YEU"] as const;
export type DataBudgetDiagnosis = (typeof dataBudgetDiagnosis)[number];
/** spec · spec v10.5 §6.10 */
export const interventionKind = ["SIM_AROUND_FAILURE", "TELEOP_CORRECTION", "RECOVERY_DATA"] as const;
export type InterventionKind = (typeof interventionKind)[number];
/** spec · spec v10.5 §7.2 */
export const branchTwoTable = ["A", "A_07", "B", "C", "B_FAIL", "B_PLUS"] as const;
export type BranchTwoTable = (typeof branchTwoTable)[number];
/** spec · design 28/10 §7 */
export const branchTray = ["TRAY_A", "TRAY_C", "TRAY_B", "TRAY_C_EGO", "TRAY_C_NOEGO"] as const;
export type BranchTray = (typeof branchTray)[number];
/** spec · design 27/10 §7.2 */
export const heVariant = ["V_EGO", "V_EGO10", "V_NOEGO"] as const;
export type HeVariant = (typeof heVariant)[number];
/** spec · spec v10.5 §7.4 */
export const method = ["PSI0", "ACT", "DIFFUSION_POLICY"] as const;
export type Method = (typeof method)[number];
/** spec · spec v10.5 §3 */
export const hypothesis = ["HS", "HT", "HTa", "HTb", "HD", "HE", "HE_T", "M"] as const;
export type Hypothesis = (typeof hypothesis)[number];
/** spec · design 27/10 §10 (F-DATA) */
export const dataFaultCode = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"] as const;
export type DataFaultCode = (typeof dataFaultCode)[number];
/** spec · design 27/10 §10 (F-SYS) */
export const systemFaultCode = ["R1", "R2", "R3", "R4", "R5", "R6"] as const;
export type SystemFaultCode = (typeof systemFaultCode)[number];

// ========================================================================
// web
// ========================================================================
/** web · web/DESIGN.md Phụ lục A.2 */
export const actionKind = ["INTAKE_SUBMIT", "STAGE_REVIEW", "EXPERIMENT_SUBMIT", "RECOMMENDATION_DECISION", "DIAGNOSIS_OVERRIDE", "RELEASE_FREEZE_REQUEST", "EVAL_REQUEST", "FLYWHEEL_RUN_REQUEST", "HOLDOUT_UNSEAL", "SOFT_DELETE", "CHAT_ACTION_CONFIRM"] as const;
export type ActionKind = (typeof actionKind)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const syncStatus = ["PENDING", "EXPORTED", "APPLIED", "REJECTED"] as const;
export type SyncStatus = (typeof syncStatus)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const jobKind = ["PIPELINE_RUN", "PIPELINE_RETRY_FROM", "TRAIN", "PROBE", "EVAL", "RELEASE_FREEZE", "FLYWHEEL_RUN"] as const;
export type JobKind = (typeof jobKind)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const jobStatus = ["OPEN", "PICKED", "DONE", "FAILED", "CANCELLED"] as const;
export type JobStatus = (typeof jobStatus)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const draftStatus = ["DRAFT", "SUBMITTED", "ACCEPTED", "REJECTED"] as const;
export type DraftStatus = (typeof draftStatus)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const interventionDecision = ["APPROVE", "APPROVE_EDITED", "REJECT"] as const;
export type InterventionDecision = (typeof interventionDecision)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const origin = ["core", "mock"] as const;
export type Origin = (typeof origin)[number];
/** web · web/DESIGN.md Phụ lục A.2 */
export const userRole = ["DATA_ENGINEER", "ML_ENGINEER", "LEAD", "JUDGE_VIEWER", "ADMIN"] as const;
export type UserRole = (typeof userRole)[number];

/** Hành động bắt buộc có lý do (BR-04, BR-10). */
export const actionNeedsReason = ["DIAGNOSIS_OVERRIDE", "HOLDOUT_UNSEAL", "SOFT_DELETE"] as const;
