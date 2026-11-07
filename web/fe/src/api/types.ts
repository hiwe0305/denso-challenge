// Response shapes of the read API (DESIGN.md §7.1, §7.4).
//
// Each shape mirrors one view or table in web/schema/70-views.sql, column for
// column, so the FastAPI layer (milestone M2) can return the view rows without
// renaming. Field names follow the contract (DESIGN.md §1 rule 5).
//
// Three rules hold for every shape:
//   - every record carries `origin` so the FE can label mock rows (§4.4b);
//   - a value nobody measured is `null`, never 0 (§6.4, BR-12);
//   - a check that could not run is listed with its reason, never folded
//     into "no fault" (BR-12).
import type {
  ClusterDiagnosis,
  DataClass,
  DeidStatus,
  EvalMode,
  FailureClass,
  HeVariant,
  InfraStatus,
  InterventionKind,
  Origin,
  QaAgentVerdict,
  QaDecision,
  Renderer,
  SourceKind,
  Split,
  StageRunStatus,
  StepStatus,
  SyncStatus,
  SystemDiagnosis,
  TaskId,
} from "../contracts/enums";

// ---------------------------------------------------------------- common

/** One page of a list endpoint (§7.3): `?cursor=&limit=`. */
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
  total: number;
}

/** The single error shape (§7.3). */
export interface ApiError {
  code: string;
  message: string;
  hint: string | null;
  ref: string | null;
}

/** 202 body of every endpoint that records a human action (§7.3). */
export interface ActionAccepted {
  action_id: string;
  sync_status: SyncStatus;
}

/** GET /actions/{id} · v_action_status. */
export interface ActionStatusRow {
  action_id: string;
  action_kind: string;
  target_kind: string;
  target_id: string;
  sync_status: SyncStatus;
  reason: string | null;
  reject_reason: string | null;
  created_at: string;
  exported_at: string | null;
  applied_at: string | null;
}

/** GET /decisions · `decisions`, newest first. */
export interface DecisionRow {
  id: string;
  kind: string | null;
  target_kind: string | null;
  target_id: string | null;
  conclusion: string | null;
  reason: string | null;
  /** Set when the decision answers a web action (W7). */
  source_action_id: string | null;
  origin: Origin;
}

/** GET /sync/runs · one pass of `POST /sync/run` (table `sync_runs`). */
export interface SyncRunRow {
  id: string;
  direction: string;
  status: "ok" | "partial" | "failed";
  started_at: string;
  finished_at: string;
  exported: string[];
  applied: string[];
  fake_core: boolean;
  errors: Array<Record<string, unknown>>;
}

/**
 * A check that did not run, with its reason (BR-12).
 * `source` says where the skip came from, so the FE can phrase the code:
 * an algorithm step number, a diagnostic check name, or a system code R1–R6.
 */
export interface SkippedItem {
  source: "algo_step" | "diagnostic_run" | "system_check" | "train_diagnosis";
  code: string;
  reason: string;
  eval_episode_id: string | null;
}

// ---------------------------------------------------------------- M7

export type RecommendationStatus =
  | "RUNNING"
  | "AWAITING_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "DONE"
  | "FAILED";

/** GET /recommendations · one row per Failure → Data round. */
export interface RecommendationSummary {
  id: string;
  round_no: number;
  task_id: TaskId;
  status: RecommendationStatus;
  checkpoint_id: string;
  evaluation_id: string;
  run_plan_id: string;
  started_at: string | null;
  finished_at: string | null;
  origin: Origin;
}

export type BudgetResource = "usd" | "human_minutes" | "gpu_hours";

/**
 * One of the three parallel budget ceilings (BR-07). `used` is what the
 * round has already measured in the ledger; `proposed` is the sum of the
 * interventions at their target quantity.
 */
export interface BudgetLine {
  resource: BudgetResource;
  cap: number;
  used: number;
  proposed: number;
  remaining: number;
}

export type InterventionStatus =
  | "PROPOSED"
  | "APPROVED"
  | "REJECTED"
  | "IN_PROGRESS"
  | "FULFILLED"
  | "CANCELLED";

/** v_cost_by_intervention, plus the g/c the right column sorts by. */
export interface InterventionRow {
  id: string;
  recommendation_id: string;
  cluster_id: string;
  kind: InterventionKind;
  status: InterventionStatus;
  unit: string;
  target_quantity: number;
  approved_quantity: number | null;
  /** Counted from episodes, never typed in. */
  fulfilled_count: number;
  n_failures: number;
  n_eff: number;
  expected_gain_pp: number;
  estimated_usd: number;
  estimated_human_minutes: number;
  estimated_gpu_hours: number;
  /** g / c in percentage points per $100 (spec v10.5 §6.10); null when c = 0. */
  gain_pp_per_100usd: number | null;
  measured_usd: number | null;
  measured_human_minutes: number | null;
  measured_gpu_hours: number | null;
  spec: Record<string, unknown>;
  origin: Origin;
}

/** GET /recommendations/{id} · the round, its three ceilings and its proposals. */
export interface Recommendation extends RecommendationSummary {
  budget: BudgetLine[];
  /** Sorted by gain_pp_per_100usd, best first. */
  interventions: InterventionRow[];
  /** Stop rule: below this g/c the round proposes nothing (spec v10.5 §8). */
  stop_threshold_pp_per_100usd: number;
}

export type AlgoStepStatus = "pending" | "running" | "done" | "skipped" | "failed";

/** GET /recommendations/{id}/steps · flywheel_algo_steps, 12 rows. */
export interface AlgoStep {
  step_no: number;
  name: string;
  status: AlgoStepStatus;
  started_at: string | null;
  finished_at: string | null;
  rollout_count: number;
  skip_reason: string | null;
  origin: Origin;
}

/** GET /recommendations/{id}/clusters · v_cluster_board. */
export interface ClusterBoardRow {
  cluster_id: string;
  recommendation_id: string;
  task_id: TaskId;
  failed_step: number;
  failure_code: string;
  level: number;
  member_count: number;
  diagnosis: ClusterDiagnosis | null;
  diagnosis_source: "auto" | "engineer_override" | null;
  override_reason: string | null;
  consumes_data_budget: boolean;
  is_system_fault: boolean;
  card_uri: string | null;
  checks: Record<string, unknown>;
  diagnostic_run_count: number;
  diagnostic_rollouts: number;
  skipped_checks: number;
  repair_ticket_count: number;
  origin: Origin;
}

/** diagnostic_runs, one per (cluster, check). */
export interface DiagnosticRun {
  cluster_id: string;
  step_no: number;
  check_name: string;
  outcome: "passed" | "failed" | "skipped";
  value: number | null;
  threshold: number | null;
  rollout_count: number;
  gpu_seconds: number;
  representative_episode_id: string | null;
  skip_reason: string | null;
  origin: Origin;
}

/** repair_tickets. */
export interface RepairTicket {
  id: string;
  cluster_id: string;
  diagnosis: ClusterDiagnosis;
  title: string;
  detail: string | null;
  status: "OPEN" | "IN_PROGRESS" | "FIXED" | "WONT_FIX";
  rebaseline_required: boolean;
  origin: Origin;
}

/** A representative episode shown on the evidence card. */
export interface Representative {
  eval_episode_id: string;
  episode_index: number;
  video_uri: string | null;
  trajectory_log_uri: string | null;
  system_diagnosis: SystemDiagnosis | null;
}

/** GET /clusters/{id}/card · the evidence card. */
export interface ClusterCard {
  cluster: ClusterBoardRow;
  diagnostic_runs: DiagnosticRun[];
  /** Every code that could not be scored, from all three sources (BR-12). */
  skipped: SkippedItem[];
  /** System check of every member episode (v_system_check). */
  system_checks: SystemCheckRow[];
  representatives: Representative[];
  interventions: InterventionRow[];
  repair_tickets: RepairTicket[];
}

/** GET /fix-rates · v_fix_rate. A kind with no row has only the Beta(1, 1) prior. */
export interface FixRate {
  intervention_kind: InterventionKind;
  event_count: number;
  n_conditions: number;
  fixed_count: number;
  alpha: number;
  beta: number;
  mean_fix_rate: number;
}

// ---------------------------------------------------------------- M6

/** GET /evaluations · v_eval_summary plus what the selector needs. */
export interface EvaluationSummary {
  evaluation_id: string;
  task_id: TaskId;
  checkpoint_id: string;
  branch: string | null;
  split: Split;
  level: number | null;
  renderer: Renderer;
  eval_mode: EvalMode;
  scorer_version: string;
  total_episodes: number;
  infra_failed_count: number;
  success_count: number;
  /** The headline number is the simulator flag (ADR-14). */
  sim_success_rate: number | null;
  scorer_success_rate: number | null;
  sim_scorer_gap: number | null;
  /** Step names of the task, so the funnel has exactly that many steps. */
  step_names: string[];
  started_at: string | null;
  finished_at: string | null;
  sealed_until: string | null;
  is_sealed: boolean;
  origin: Origin;
}

/** GET /evaluations/{id}/episodes · eval_episodes. */
export interface EvalEpisodeRow {
  id: string;
  evaluation_id: string;
  episode_index: number;
  level: number;
  condition_id: string;
  episode_seed: number;
  rollout_seed: number;
  infra_status: InfraStatus;
  sim_success: boolean | null;
  scorer_success: boolean | null;
  step_status: StepStatus[];
  first_failed_step: number | null;
  failure_code: string | null;
  failure_class: FailureClass | null;
  failure_time_s: number | null;
  video_uri: string | null;
  trajectory_log_uri: string | null;
  origin: Origin;
}

/** GET /evaluations/{id}/funnel · v_eval_funnel, one row per (episode level, step). */
export interface FunnelRow {
  evaluation_id: string;
  task_id: TaskId;
  split: Split;
  eval_level: number | null;
  renderer: Renderer;
  eval_mode: EvalMode;
  episode_level: number;
  step_no: number;
  reached_or_beyond: number;
  step_pass: number;
  step_fail: number;
  step_not_attempted: number;
  step_unknown: number;
  is_sealed: boolean;
  origin: Origin;
}

/** GET /evaluations/{id}/system-checks · v_system_check. */
export interface SystemCheckRow {
  id: string;
  eval_episode_id: string;
  evaluation_id: string;
  task_id: TaskId;
  episode_index: number;
  level: number;
  diagnosis: SystemDiagnosis;
  config_sha256: string;
  trace_sha256: string;
  infra_status: InfraStatus;
  fired_codes: string[];
  skipped_codes: string[];
  finding_count: number;
  skipped_count: number;
  findings: Array<Record<string, unknown>>;
  skipped: Array<{ code: string; reason: string }>;
  measurements: Record<string, unknown>;
  /** Rollout mode (DESIGN.md 0.5). null: the producer did not say, so R1, R2 counted. */
  timing: "sync" | "async" | null;
  /** R1, R2 of a sync rollout: measured and kept, never in `diagnosis`. */
  recorded: Array<Record<string, unknown>>;
  recorded_skipped: Array<{ code: string; reason: string }>;
  usable_as_policy_evidence: boolean;
  is_sealed: boolean;
  origin: Origin;
}

export type FailureFamily = "F-DATA" | "F-TRAIN" | "F-OFF" | "F-CL" | "F-SYS";

export interface FailureFamilyRow {
  code: string;
  count: number;
  detail: string | null;
}

/**
 * One of the five signal families of the failure table (design 27/10 §10).
 * `not_run` means nobody produced this family for the evaluation; the FE shows
 * EmptyState, not "no fault".
 */
export interface FailureFamilyBlock {
  family: FailureFamily;
  status: "ok" | "not_run";
  rows: FailureFamilyRow[];
  skipped: SkippedItem[];
}

/** GET /evaluations/{id}/failures. */
export interface FailureBoard {
  evaluation_id: string;
  families: FailureFamilyBlock[];
}

// ---------------------------------------------------------------- M2

export type DatasetStatus = string;

/** GET /datasets · datasets. */
export interface DatasetRow {
  id: string;
  dataset_code: string;
  source_id: string | null;
  source_kind: SourceKind;
  source_detail: string | null;
  data_class: DataClass;
  license: string;
  episode_count: number;
  has_seeded_faults: boolean;
  status: DatasetStatus;
  note: string | null;
  origin: Origin;
}

/** v_pipeline_current, one row per (dataset, stage); empty stage → null run. */
export interface StageRow {
  dataset_id: string;
  stage_number: number;
  stage_code: string;
  stage_run_id: string | null;
  attempt_no: number | null;
  status: StageRunStatus | null;
  qa_code_decision: QaDecision | null;
  qa_agent_verdict: QaAgentVerdict | null;
  started_at: string | null;
  finished_at: string | null;
  log_uri: string | null;
  origin: Origin | null;
}

/** pipeline_stage_runs, every attempt, current or not. */
export interface StageRunRow {
  id: string;
  dataset_id: string;
  stage_number: number;
  attempt_no: number;
  is_current: boolean;
  status: StageRunStatus;
  qa_code_decision: QaDecision | null;
  qa_agent_verdict: QaAgentVerdict | null;
  started_at: string | null;
  finished_at: string | null;
  log_uri: string | null;
  origin: Origin;
}

/** GET /datasets/{id}/stages · the 6-stage stepper and the attempt history. */
export interface PipelineView {
  stages: StageRow[];
  attempts: StageRunRow[];
}

/** GET /datasets/{id}/episodes · episodes with their latest QA decision. */
export interface EpisodeRow {
  id: string;
  dataset_id: string;
  source_kind: SourceKind;
  kind: string;
  split: Split;
  deid_status: DeidStatus;
  data_class: DataClass;
  operator_kind: "human" | "machine";
  is_root: boolean;
  action_quality: string;
  /** Latest QA decision; null means QA has not run, not "pass". */
  qa_decision: QaDecision | null;
  qa_reasons: string[];
  origin: Origin;
}

/** v_dataset_report, one row per (dataset, source_kind, synthetic_tier). */
export interface DatasetReportRow {
  dataset_id: string;
  source_kind: SourceKind;
  synthetic_tier: string | null;
  episode_count: number;
  root_human_count: number;
  qa_pass: number;
  qa_flag: number;
  qa_quarantine: number;
  qa_reject: number;
  qa_not_run: number;
  egocentric_raw: number;
  mean_duration_s: number | null;
  origin: Origin;
}

/** One QA check across the dataset: how many episodes passed and failed it. */
export interface QaCheckRow {
  name: string;
  passed: number;
  failed: number;
}

/** GET /datasets/{id}/report. */
export interface DatasetReport {
  rows: DatasetReportRow[];
  by_check: QaCheckRow[];
}

// ---------------------------------------------------------------- M9

/** GET /results/branches?task_id= · v_branch_comparison. */
export interface BranchComparisonRow {
  task_id: TaskId;
  branch: string;
  method: string;
  experiment_id: string;
  evaluation_id: string;
  level: number | null;
  sim_success_rate: number | null;
  total_episodes: number;
  infra_failed_count: number;
  measured_usd: number | null;
  measured_human_minutes: number | null;
  measured_gpu_hours: number | null;
  estimated_usd: number | null;
  origin: Origin;
}

/** GET /results/he-curve · v_he_curve. */
export interface HeCurvePoint {
  task_id: TaskId;
  branch: string;
  hypothesis: string;
  /** One curve per variant (design 27/10 §7.2). */
  he_variant: HeVariant | null;
  n_demos: number;
  train_seed: number | null;
  level: number | null;
  sim_success_rate: number | null;
  n_scored: number;
  is_sealed: boolean;
  origin: Origin;
}

/** GET /results/e1-curve · success rate by number of demos and method. */
export interface E1CurvePoint {
  task_id: TaskId;
  method: string;
  n_demos: number;
  sim_success_rate: number | null;
  n_scored: number;
  origin: Origin;
}

// ---------------------------------------------------------------- M8

/** GET /cost/ledger · cost_ledger_entries, append-only (BR-06). */
export interface LedgerRow {
  id: string;
  entry_kind: "ENTRY" | "REVERSAL";
  activity: string;
  resource_type: string;
  quantity: number;
  unit: string;
  price_book_name: string | null;
  branch: string | null;
  experiment_id: string | null;
  evaluation_id: string | null;
  dataset_id: string | null;
  recommendation_id: string | null;
  cluster_id: string | null;
  intervention_id: string | null;
  estimated_usd: number | null;
  estimated_human_minutes: number | null;
  estimated_gpu_hours: number | null;
  measured_usd: number | null;
  measured_human_minutes: number | null;
  measured_gpu_hours: number | null;
  reverses_entry_id: string | null;
  note: string | null;
  origin: Origin;
}

/** v_cost_by_branch. */
export interface CostByBranchRow {
  branch: string | null;
  task_id: TaskId | null;
  price_book_name: string | null;
  entry_count: number;
  estimated_usd: number | null;
  measured_usd: number | null;
  /** measured − estimated, summed only over rows that carry both; null when none does. */
  usd_forecast_error: number | null;
  /** How many rows carry both an estimate and a measurement. */
  forecast_pairs: number;
  estimated_human_minutes: number | null;
  measured_human_minutes: number | null;
  estimated_gpu_hours: number | null;
  measured_gpu_hours: number | null;
  reversal_count: number;
  origin: Origin;
}

/** v_r_demo. */
export interface RDemoRow {
  task_id: TaskId;
  branch: string;
  method: string;
  human_root_episodes: number;
  origin: Origin;
}

/**
 * v_cost_data_allocation (BR-05): a dataset's measured cost, shared by the
 * experiments that trained on it in proportion to the episodes they used.
 */
export interface DataAllocationRow {
  experiment_id: string;
  task_id: TaskId;
  branch: string;
  method: string;
  hypothesis: string;
  dataset_id: string;
  episodes_used: number;
  dataset_episodes: number;
  share: number | null;
  allocated_usd: number | null;
  allocated_human_minutes: number | null;
  allocated_gpu_hours: number | null;
  origin: Origin;
}

/** GET /cost/by-branch. */
export interface CostByBranch {
  rows: CostByBranchRow[];
  r_demo: RDemoRow[];
  data_allocation: DataAllocationRow[];
}

/** GET /cost/sensitivity?price_book= · the ledger repriced under each price book. */
export interface SensitivityRow {
  price_book_name: string;
  sha256: string;
  note: string | null;
  rates: Record<string, { unit: string; usd_per_unit: number }>;
  by_branch: Array<{ branch: string | null; usd: number }>;
  total_usd: number;
}

// ---------------------------------------------------------------- M3

/** `{hit, total, value}` of DA-31; `value` is null when `total` is 0, never 0. */
export interface DefectRate {
  hit: number;
  total: number;
  value: number | null;
}

export type BenchLayer = "code" | "agent";
export type ByLayer<T> = Record<BenchLayer, T>;

/** v_defect_detection: one rate of one layer in one group of one bench run. */
export interface DefectScoreRow {
  result_sha256: string;
  bench_version: string;
  group_name: string;
  injected_copy: string;
  clean_copy: string;
  layer: BenchLayer;
  metric: "recall" | "recall_unmasked" | "precision" | "false_alarm";
  /** Kind for recall, code for precision, "*" for the false alarm. */
  subject: string;
  hit: number;
  total: number;
  value: number | null;
  masked: number | null;
  bound: "upper" | null;
  created_at: string;
  is_latest: boolean;
  origin: Origin;
}

/** One defect kind: what code caught, what the agent adds (DA-31 AC 3). */
export interface DefectKindRow {
  kind: string;
  code: string;
  injected: number;
  by_code: number;
  agent_adds: number;
  together: number;
  agent_alone: number;
  /** Defects of this kind hidden by a natural defect of the real data. */
  masked: ByLayer<number>;
  recall: ByLayer<DefectRate>;
  recall_unmasked: ByLayer<DefectRate>;
}

export interface DefectTotals {
  injected: number;
  by_code: number;
  agent_adds: number;
  together: number;
}

/** One agent finding judged against the key, with the engineer's review. */
export interface DefectFinding {
  copy: string;
  report_id: string;
  finding_id: string;
  rank: number;
  target: string;
  code: string;
  label: "hit" | "false" | "natural" | "clean";
  review: "agree" | "override" | "unreviewed";
  reason: string;
}

/** One group (`data`, `logs`) of a bench run: an injected copy and its clean twin. */
export interface DefectBenchGroup {
  group_name: string;
  injected_copy: string;
  clean_copy: string;
  defects: number;
  totals: DefectTotals;
  kinds: DefectKindRow[];
  codes: Array<{ code: string; precision: ByLayer<DefectRate> }>;
  /** An upper bound: the clean copy still holds the real data's own defects. */
  false_alarm: ByLayer<DefectRate>;
  /** Seconds from the job's end to the report, per copy; null = not measured. */
  seconds_to_report: ByLayer<Record<string, number | null>>;
  clean_reports: ByLayer<Array<[string, string]>>;
  natural: ByLayer<Array<[string, string]>>;
  not_a_unit: ByLayer<string[]>;
  agent_ranking: DefectRate;
  agent_reviews: Record<string, Record<string, number>>;
  agent_findings: DefectFinding[];
}

/** GET /defects/scoreboard · the newest bench run; `result_sha256` null when none. */
export interface DefectScoreboard {
  result_sha256: string | null;
  bench_version: string | null;
  created_at: string | null;
  measured_on: string | null;
  false_alarm_note: string | null;
  totals: DefectTotals;
  groups: DefectBenchGroup[];
  origin: Origin | null;
}

// ---------------------------------------------------------------- M5

/** The RunPlan card: what a branch's training is pinned to (03 §4.3). */
export interface RunPlanCard {
  id: string;
  purpose: string;
  config_sha256: string;
  lock_uri: string;
  frozen_at: string;
  seed_range: string | null;
}

export type TrainCodeStatus = "fired" | "clean" | "skipped" | "partial" | "not_run";

export interface DiagnosisSummary {
  ran: boolean;
  fired: number;
  clean: number;
  skipped: number;
  partial: number;
  not_run: number;
}

/** GET /experiments. */
export interface ExperimentRow {
  experiment_id: string;
  task_id: TaskId;
  branch: string;
  method: string;
  hypothesis: string | null;
  status: string;
  train_seed: number | null;
  hyperparams: Record<string, unknown>;
  base_source_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  run_plan: RunPlanCard | null;
  releases: Array<{ release_id: string; mix_weight: number; episodes_used: number | null }>;
  best_checkpoint_id: string | null;
  /** Telemetry rows loaded; 0 means none, so the chart says so instead of drawing nothing. */
  metric_rows: number;
  diagnosis: DiagnosisSummary | null;
  origin: Origin;
}

/** GET /experiments/{id}/metrics?split=&every= · one row of `metrics.jsonl`. */
export interface TrainingMetricRow {
  step: number;
  split: "train" | "val";
  attempt: number;
  epoch: number;
  /** null when not finite; `loss_nonfinite` then says which. */
  loss: number | null;
  loss_nonfinite: "NaN" | "Infinity" | "-Infinity" | null;
  lr: number;
  /** Per action group (arm, hand, base); only val rows carry it. */
  loss_by_group: Record<string, number>;
  grad_norm_vlm: number | null;
  grad_norm_action: number | null;
  vram_gb: number | null;
  throughput: number | null;
  wall_time_s: number;
}

export interface TrainFinding {
  start_step: number;
  group: string | null;
  dim: number | null;
  value: number | null;
  value_nonfinite: string | null;
  threshold: number | null;
  stop_job: boolean;
  checkpoint_id: string | null;
}

/** GET /experiments/{id}/diagnoses · all twelve codes, each with a status (BR-12). */
export interface TrainDiagnosisView {
  experiment_id: string;
  config_sha256: string[];
  checkpoint_ids: string[];
  summary: DiagnosisSummary;
  codes: Array<{
    code: string;
    family: "F-TRAIN" | "F-OFF";
    status: TrainCodeStatus;
    findings: TrainFinding[];
    skipped: Array<{ code: string; reason: string }>;
  }>;
}

/** GET /experiments/{id}/probes · payload is the ProbeP1..P4 artifact as written. */
export interface ProbeRow {
  probe: "P1" | "P2" | "P3" | "P4";
  checkpoint_id: string;
  parent_checkpoint_id: string | null;
  dataset_sha256: string | null;
  payload: Record<string, unknown>;
  origin: Origin;
}

/** GET /experiments/{id}/checkpoints. */
export interface CheckpointRow {
  checkpoint_id: string;
  parent_checkpoint_id: string | null;
  release_id: string | null;
  method: string;
  step: number | null;
  weights_sha256: string;
  uri: string;
  is_best: boolean;
  is_latest: boolean;
  train_seed: number | null;
  origin: Origin;
}

// ---------------------------------------------------------------- M4

export type GuardCheckName = "split" | "benchmark_copy" | "raw_egocentric" | "qa_not_pass" | "near_duplicate";

/** What must hold before a release is frozen; `not_run` is never shown as ok. */
export interface SplitGuard {
  ok: boolean;
  checks: Array<{
    name: GuardCheckName;
    status: "ok" | "fail" | "not_run";
    count: number;
    /** Up to five episode ids that break the check. */
    examples: string[];
  }>;
}

/** GET /releases. */
export interface ReleaseRow {
  release_id: string;
  name: string;
  status: "draft" | "frozen";
  parent_release_id: string | null;
  manifest_sha256: string | null;
  manifest_uri: string | null;
  split_plan_sha256: string | null;
  license_summary: string | null;
  frozen_at: string | null;
  /** Items kept; excluded ones are counted apart and listed with their reason. */
  item_count: number;
  excluded_count: number;
  by_source: Record<string, number>;
  used_by: string[];
  guard: SplitGuard;
  origin: Origin;
}

/** GET /releases/{id}/items. */
export interface ReleaseItemRow {
  episode_id: string;
  dataset_id: string | null;
  source_kind: string | null;
  split: string | null;
  sample_weight: number;
  excluded: boolean;
  exclude_reason: string | null;
  qa_decision: string | null;
  origin: Origin;
}

// ---------------------------------------------------------------- M5 drafts

/** The editable part of an experiment draft (W table `experiment_drafts`). */
export interface DraftBody {
  task_id: TaskId;
  branch: string;
  method: string;
  hypothesis: string | null;
  base_checkpoint_ref: string;
  run_plan_ref?: string | null;
  hyperparams: Record<string, unknown>;
  release_mix: Array<{ release_id: string; mix_weight: number }>;
}

/** GET /experiment-drafts · newest first. Submitting freezes it; the core answers. */
export interface ExperimentDraft extends DraftBody {
  id: string;
  run_plan_ref: string | null;
  status: "DRAFT" | "SUBMITTED" | "ACCEPTED" | "REJECTED";
  submit_action_id: string | null;
  experiment_id: string | null;
  reject_reason: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}
