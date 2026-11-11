// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SchemaVersion = string;
export type ClusterId = string;
export type RunPlanId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type Level = number;
export type FirstFailedStep = number;
export type FailureKind = string;
export type FailureClass = ("approach" | "grasp" | "carry" | "place" | "balance") | null;
/**
 * @minItems 1
 */
export type MemberEpisodeIds = [string, ...string[]];
export type RepresentativeSeed = number | null;
/**
 * @minItems 1
 */
export type Representatives = [Representative, ...Representative[]];
export type EpisodeId = string;
export type ScoreId = string;
export type ConditionSeed = number | null;
export type TraceSha256 = string;
export type SystemConfigSha256 = string;
export type StageTableSha256 = string | null;
export type Check =
  | "infra_status"
  | "tracking_error"
  | "latency_p99"
  | "buffer_underruns"
  | "sync_offset"
  | "camera_reference"
  | "camera_intrinsics_px"
  | "camera_position_m"
  | "camera_quaternion"
  | "planner_feasible"
  | "reset_success"
  | "nominal_visuals"
  | "in_train_domain"
  | "coverage_distance";
export type Part = string | null;
export type Outcome = "fired" | "not_fired" | "not_judged";
export type Value = boolean | number | string | null;
export type Threshold = number | string | string[] | null;
export type NSuccess = number | null;
export type NRuns = number | null;
export type SkippedReason = string | null;
export type Note = string | null;
export type Checks = CheckResult[];
export type RowId =
  | "stage1_perception"
  | "stage3_action_group"
  | "runtime_distribution_shift"
  | "stage3_forgetting"
  | "out_of_domain";
export type AttributeTo = string;
export type Intervention = string;
export type ConsumesBudget = boolean;
export type Confirmed = boolean;
export type Probe = "P1" | "P2" | "P3" | "P4" | "-";
export type Where = string;
export type Value1 = number;
export type Threshold1 = number | null;
export type Evidence = ProbeEvidence[];
export type StageHypotheses = StageHypothesis[];
export type RowId1 =
  | "stage1_perception"
  | "stage3_action_group"
  | "runtime_distribution_shift"
  | "stage3_forgetting"
  | "out_of_domain";
export type Reason = string;
export type StageUnavailable = Unavailable[];
export type Diagnosis =
  | "unknown"
  | "infra"
  | "controller"
  | "runtime"
  | "sync"
  | "calibration"
  | "infeasible"
  | "bad_start_state"
  | "perception"
  | "out_of_domain"
  | "coverage_gap"
  | "weak_skill";
export type Diagnosis1 =
  | (
      | "unknown"
      | "infra"
      | "controller"
      | "runtime"
      | "sync"
      | "calibration"
      | "infeasible"
      | "bad_start_state"
      | "perception"
      | "out_of_domain"
      | "coverage_gap"
      | "weak_skill"
    )
  | null;
export type Kind =
  | "sim_s1"
  | "sim_s2"
  | "sim_s3"
  | "sim_s4"
  | "teleop_correction"
  | "recovery_data"
  | "repair_ticket"
  | "report_only";
export type Description = string;
export type ConsumesBudget1 = boolean;
export type Quantity = number | null;
export type Unit = string | null;
export type NFailures = number;
export type Cap = number;
export type NEffective = number;
export type NDev = number;
export type FixRateAlpha = number;
export type FixRateBeta = number;
export type ExpectedGainPp = number;
export type MeasureKind = "estimated" | "measured";
export type UsdAmount = number;
export type HumanHours = number;
/**
 * @minItems 1
 */
export type LedgerEntryIds = [string, ...string[]];
export type InterventionId = string | null;
export type Verdict = "accept" | "override";
export type DecisionId = string;
export type SignedBy = string;
export type Reason1 = string | null;
export type Diagnosis2 =
  | (
      | "unknown"
      | "infra"
      | "controller"
      | "runtime"
      | "sync"
      | "calibration"
      | "infeasible"
      | "bad_start_state"
      | "perception"
      | "out_of_domain"
      | "coverage_gap"
      | "weak_skill"
    )
  | null;
export type Intervention1 =
  | (
      | "sim_s1"
      | "sim_s2"
      | "sim_s3"
      | "sim_s4"
      | "teleop_correction"
      | "recovery_data"
      | "repair_ticket"
      | "report_only"
    )
  | null;
export type ParentCheckpointId = string;
export type CandidateCheckpointId = string;
export type NConditions = number;
export type RunsPerCondition = number;
export type PParent = number;
export type PCandidate = number;
export type Fixed = number;
export type FixRateEventId = string | null;
export type GateDecisionId = string | null;

/**
 * One card per failure cluster (spec section 4.5). Not a catalog table.
 */
export interface EvidenceCard {
  schema_version?: SchemaVersion;
  cluster_id: ClusterId;
  run_plan_id: RunPlanId;
  task_id: TaskId;
  embodiment_id: EmbodimentId;
  level: Level;
  first_failed_step: FirstFailedStep;
  failure_kind: FailureKind;
  failure_class?: FailureClass;
  member_episode_ids: MemberEpisodeIds;
  representative_seed?: RepresentativeSeed;
  representatives: Representatives;
  diagnosis: Diagnosis1;
  proposal: InterventionProposal | null;
  decision?: EngineerDecision | null;
  result?: RetrainResult | null;
}
/**
 * One failure episode the expensive checks ran on (spec section 6.3).
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "Representative".
 */
export interface Representative {
  episode_id: EpisodeId;
  score_id: ScoreId;
  condition_seed?: ConditionSeed;
  trace_sha256: TraceSha256;
  system_config_sha256: SystemConfigSha256;
  stage_table_sha256?: StageTableSha256;
  checks: Checks;
  stage_hypotheses?: StageHypotheses;
  stage_unavailable?: StageUnavailable;
  diagnosis: Diagnosis;
}
/**
 * One check of one representative, with what it was judged by.
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "CheckResult".
 */
export interface CheckResult {
  check: Check;
  part?: Part;
  outcome: Outcome;
  value?: Value;
  threshold?: Threshold;
  n_success?: NSuccess;
  n_runs?: NRuns;
  skipped_reason?: SkippedReason;
  note?: Note;
}
/**
 * A row of the stage table that applied, as a proposal (spec section 6.4).
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
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
 * One probe measurement behind a stage hypothesis (`EvidenceRecord` of DA-13).
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "ProbeEvidence".
 */
export interface ProbeEvidence {
  probe: Probe;
  where: Where;
  value: Value1;
  threshold?: Threshold1;
}
/**
 * A stage row nobody could judge, and why.
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "Unavailable".
 */
export interface Unavailable {
  row_id: RowId1;
  reason: Reason;
}
/**
 * What the algorithm proposes for the cluster (spec sections 6.9-6.11).
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "InterventionProposal".
 */
export interface InterventionProposal {
  kind: Kind;
  description: Description;
  consumes_budget: ConsumesBudget1;
  quantity?: Quantity;
  unit?: Unit;
  gain?: ExpectedGain | null;
  cost?: Cost | null;
  intervention_id?: InterventionId;
}
/**
 * g_j of spec section 6.11, in points of dev success.
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "ExpectedGain".
 */
export interface ExpectedGain {
  n_failures: NFailures;
  cap: Cap;
  n_effective: NEffective;
  n_dev: NDev;
  fix_rate_alpha: FixRateAlpha;
  fix_rate_beta: FixRateBeta;
  expected_gain_pp: ExpectedGainPp;
}
/**
 * Money and hours, estimated or measured, as the ledger rows add them up.
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "Cost".
 */
export interface Cost {
  measure_kind: MeasureKind;
  usd_amount: UsdAmount;
  human_hours?: HumanHours;
  ledger_entry_ids: LedgerEntryIds;
}
/**
 * Accept or override, as the `Decision` it is regenerated from (spec section 6.14).
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "EngineerDecision".
 */
export interface EngineerDecision {
  verdict: Verdict;
  decision_id: DecisionId;
  signed_by: SignedBy;
  reason?: Reason1;
  diagnosis?: Diagnosis2;
  intervention?: Intervention1;
}
/**
 * Fix rate measured against the parent on new conditions (spec section 6.13).
 *
 * This interface was referenced by `EvidenceCard`'s JSON-Schema
 * via the `definition` "RetrainResult".
 */
export interface RetrainResult {
  parent_checkpoint_id: ParentCheckpointId;
  candidate_checkpoint_id: CandidateCheckpointId;
  n_conditions: NConditions;
  runs_per_condition: RunsPerCondition;
  p_parent: PParent;
  p_candidate: PCandidate;
  fixed: Fixed;
  fix_rate_event_id?: FixRateEventId;
  gate_decision_id?: GateDecisionId;
  cost: Cost;
}
