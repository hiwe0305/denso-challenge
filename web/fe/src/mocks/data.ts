// Reads mock/demo-17-11/ at the repo root, the same directory `fwsync import`
// loads (DESIGN.md Appendix C), so the FE on MSW and the DB see one set of numbers.
//
// Only `*.jsonl`, `recommendation.json` and `bench_result.json` are read.
// `defect_manifest.json` is the answer key of the seeded defects and only the
// grader reads it (BR-08); it is deliberately not globbed here. The bench
// result is DA-31's score of that key, which the API may read (§4.4c).

const files = import.meta.glob("../../../../mock/demo-17-11/*.jsonl", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const recommendationFile = import.meta.glob("../../../../mock/demo-17-11/recommendation.json", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const benchFile = import.meta.glob("../../../../mock/demo-17-11/bench_result.json", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

function table<T>(name: string): T[] {
  const key = Object.keys(files).find((path) => path.endsWith(`/${name}.jsonl`));
  if (key === undefined) throw new Error(`mock file missing: ${name}.jsonl`);
  return (files[key] ?? "")
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line) as T);
}

function single<T>(): T {
  const text = Object.values(recommendationFile)[0];
  if (text === undefined) throw new Error("mock file missing: recommendation.json");
  return JSON.parse(text) as T;
}

/** DA-31 writes at most one result per run dir; the mock has one, or none. */
function bench(): RawBenchResult | null {
  const text = Object.values(benchFile)[0];
  return text === undefined ? null : (JSON.parse(text) as RawBenchResult);
}

/** sha256 of the exact JSON text, as `bench_result.sha256` beside it. */
const benchLock = import.meta.glob("../../../../mock/demo-17-11/bench_result.sha256", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

// ------------------------------------------------------------ raw shapes
// The fields of each mock file that the views read. Names are the file's own.

export interface RawRecommendation {
  recommendation_ref: string;
  run_plan_ref: string;
  checkpoint_ref: string;
  evaluation_ref: string;
  task_id: "two_table" | "tray";
  round_no: number;
  status: string;
  budget_usd: number;
  budget_human_minutes: number;
  budget_gpu_hours: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface RawCluster {
  cluster_ref: string;
  recommendation_ref: string;
  failed_step: number;
  failure_code: string;
  level: number;
  member_count: number;
  representative_refs: string[];
  diagnosis: string | null;
  diagnosis_source: "auto" | "engineer_override" | null;
  override_reason: string | null;
  checks: Record<string, unknown>;
  card_uri: string | null;
}

export interface RawAlgoStep {
  recommendation_ref: string;
  step_no: number;
  status: string;
  skip_reason: string | null;
  rollout_count: number;
  started_at: string | null;
  finished_at: string | null;
  detail: { name?: string };
}

export interface RawDiagnosticRun {
  cluster_ref: string;
  step_no: number;
  check_name: string;
  outcome: "passed" | "failed" | "skipped";
  value: number | null;
  threshold: number | null;
  rollout_count: number;
  gpu_seconds: number;
  representative_episode_ref: string | null;
  skip_reason: string | null;
}

export interface RawIntervention {
  intervention_ref: string;
  recommendation_ref: string;
  cluster_ref: string;
  kind: string;
  status: string;
  unit: string;
  target_quantity: number;
  approved_quantity: number | null;
  n_failures: number;
  n_eff: number;
  expected_gain_pp: number;
  estimated_usd: number;
  estimated_human_minutes: number;
  estimated_gpu_hours: number;
  spec: Record<string, unknown>;
}

export interface RawRepairTicket {
  cluster_ref: string;
  diagnosis: string;
  title: string;
  detail: string | null;
  status: string;
  rebaseline_required: boolean;
}

export interface RawSystemDiagnosis {
  eval_episode_ref: string;
  diagnosis: string;
  config_sha256: string;
  trace_sha256: string;
  infra_status: string;
  findings: Array<Record<string, unknown> & { code: string }>;
  skipped: Array<{ code: string; reason: string }>;
  measurements: Record<string, unknown>;
  // DESIGN.md 0.5 (PR #146). Optional: rows written before it do not carry them.
  timing?: "sync" | "async" | null;
  recorded?: Array<Record<string, unknown> & { code: string }>;
  recorded_skipped?: Array<{ code: string; reason: string }>;
}

export interface RawEvaluation {
  evaluation_ref: string;
  checkpoint_ref: string;
  run_plan_ref: string;
  task_id: "two_table" | "tray";
  split: "train" | "dev" | "holdout" | "unassigned";
  level: number | null;
  renderer: "mujoco" | "isaac";
  eval_mode: "sync" | "async";
  scorer_version: string;
  total_episodes: number;
  infra_failed_count: number;
  success_count: number;
  started_at: string | null;
  finished_at: string | null;
  sealed_until: string | null;
}

export interface RawEvalEpisode {
  eval_episode_ref: string;
  evaluation_ref: string;
  episode_index: number;
  level: number;
  condition_id: string;
  episode_seed: number;
  rollout_seed: number;
  infra_status: string;
  sim_success: boolean | null;
  scorer_success: boolean | null;
  step_status: string[];
  first_failed_step: number | null;
  failure_code: string | null;
  failure_class: string | null;
  failure_time_s: number | null;
  video_uri: string | null;
  trajectory_log_uri: string | null;
  details: { step_names?: string[] };
}

export interface RawCheckpoint {
  checkpoint_ref: string;
  experiment_code: string;
  is_best: boolean;
  method: string;
  release_ref: string | null;
  train_seed: number | null;
}

export interface RawExperiment {
  experiment_code: string;
  branch: string;
  hypothesis: string;
  hyperparams: { he_variant?: string; n_demos?: number };
  method: string;
  task_id: "two_table" | "tray";
  train_seed: number | null;
  status: string;
}

export interface RawExperimentDataset {
  experiment_code: string;
  release_ref: string;
  episodes_used: number;
  mix_weight: number;
}

export interface RawDataset {
  dataset_code: string;
  source_ref: string | null;
  source_kind: string;
  source_detail: string | null;
  data_class: string;
  license: string;
  episode_count: number;
  has_seeded_faults: boolean;
  status: string;
  note: string | null;
}

export interface RawStageRun {
  dataset_code: string;
  stage_number: number;
  attempt_no: number;
  is_current: boolean;
  status: string;
  qa_code_decision: string | null;
  qa_agent_verdict: string | null;
  started_at: string | null;
  finished_at: string | null;
  log_uri: string | null;
}

export interface RawEpisode {
  episode_id: string;
  source_id: string | null;
  intervention_id: string | null;
  source_kind: string;
  kind: string;
  split: string;
  deid_status: string;
  data_class: string;
  operator_kind: "human" | "machine";
  is_root: boolean;
  action_quality: string;
  meta: { synthetic_tier?: string | null; benchmark_copy_id?: string | null };
}

export interface RawQaReport {
  episode_id: string;
  decision: string;
  reasons: string[];
  checks: Array<{ name: string; passed: boolean }>;
}

export interface RawReleaseItem {
  release_ref: string;
  episode_ref: string;
  excluded: boolean;
}

export interface RawLedger {
  entry_ref: string;
  entry_kind: "ENTRY" | "REVERSAL";
  activity: string;
  resource_type: string;
  quantity: number;
  unit: string;
  price_book_name: string | null;
  branch?: string | null;
  experiment_code?: string | null;
  evaluation_ref?: string | null;
  dataset_code?: string | null;
  recommendation_ref?: string | null;
  cluster_ref?: string | null;
  intervention_ref?: string | null;
  estimated_usd?: number | null;
  estimated_human_minutes?: number | null;
  estimated_gpu_hours?: number | null;
  measured_usd?: number | null;
  measured_human_minutes?: number | null;
  measured_gpu_hours?: number | null;
  reverses_entry_ref: string | null;
  note?: string | null;
}

export interface RawDecision {
  decision_ref: string;
  kind: string | null;
  target_kind: string | null;
  target_id: string | null;
  conclusion: string | null;
  reason: string | null;
  source_action_id: string | null;
}

export interface RawPriceBook {
  name: string;
  sha256: string;
  note: string | null;
  rates: Record<string, { unit: string; usd_per_unit: number }>;
}

export interface RawTrainDiagnosis {
  checkpoint_id: string;
  config_sha256: string;
  findings: Array<{ code: string; value?: number | null; start_step?: number | null }>;
  skipped: Array<{ code: string; reason: string }>;
}

interface RawRate {
  hit: number;
  total: number;
  value: number | null;
}

/** One layer of one group of `bench_result.json` (DA-31, `da31-2`). */
export interface RawBenchLayer {
  recall_by_kind: Record<string, RawRate>;
  masked_by_kind: Record<string, number>;
  recall_unmasked_by_kind: Record<string, RawRate>;
  precision_by_code: Record<string, RawRate>;
  false_alarm_on_clean: RawRate & { bound: string };
  false_alarm_not_a_unit: string[];
  clean_reports: Array<[string, string]>;
  natural: Array<[string, string]>;
  seconds_to_report: Record<string, number | null>;
  uncoded: Record<string, string[]>;
}

export interface RawBenchGroup {
  group: string;
  injected_copy: string;
  clean_copy: string;
  defects: number;
  layers: { code: RawBenchLayer; agent: RawBenchLayer };
  split: Array<{
    kind: string;
    code: string;
    injected: number;
    by_code: number;
    agent_adds: number;
    together: number;
    agent_alone: number;
  }>;
  agent_quality: {
    ranking: RawRate;
    reviews: Record<string, Record<string, number>>;
    findings: Array<{
      copy: string;
      report_id: string;
      finding_id: string;
      rank: number;
      target: string;
      code: string;
      label: "hit" | "false" | "natural" | "clean";
      review: "agree" | "override" | "unreviewed";
      reason: string;
    }>;
  };
}

export interface RawBenchResult {
  bench_version: string;
  measured_on: string;
  false_alarm_on_clean: string;
  created_at: string;
  groups: RawBenchGroup[];
  /** Not in the file: the hash of it, from `bench_result.sha256`. */
  result_sha256: string;
}

export interface MockData {
  recommendation: RawRecommendation;
  clusters: RawCluster[];
  algoSteps: RawAlgoStep[];
  diagnosticRuns: RawDiagnosticRun[];
  interventions: RawIntervention[];
  repairTickets: RawRepairTicket[];
  systemDiagnoses: RawSystemDiagnosis[];
  evaluations: RawEvaluation[];
  evalEpisodes: RawEvalEpisode[];
  checkpoints: RawCheckpoint[];
  experiments: RawExperiment[];
  experimentDatasets: RawExperimentDataset[];
  datasets: RawDataset[];
  stageRuns: RawStageRun[];
  episodes: RawEpisode[];
  qaReports: RawQaReport[];
  releaseItems: RawReleaseItem[];
  ledger: RawLedger[];
  priceBooks: RawPriceBook[];
  trainDiagnoses: RawTrainDiagnosis[];
  decisions: RawDecision[];
  bench: RawBenchResult | null;
}

export function loadMockData(): MockData {
  return {
    recommendation: single<RawRecommendation>(),
    clusters: table("failure_clusters"),
    algoSteps: table("flywheel_algo_steps"),
    diagnosticRuns: table("diagnostic_runs"),
    interventions: table("interventions"),
    repairTickets: table("repair_tickets"),
    systemDiagnoses: table("system_diagnoses"),
    evaluations: table("evaluations"),
    evalEpisodes: table("eval_episodes"),
    checkpoints: table("checkpoints"),
    experiments: table("experiments"),
    experimentDatasets: table("experiment_datasets"),
    datasets: table("datasets"),
    stageRuns: table("pipeline_stage_runs"),
    episodes: table("episodes"),
    qaReports: table("qa_reports"),
    releaseItems: table("release_items"),
    ledger: table("ledger"),
    priceBooks: table("price_books"),
    trainDiagnoses: table("train_diagnoses"),
    decisions: table("decisions"),
    bench: withLock(bench()),
  };
}

function withLock(result: RawBenchResult | null): RawBenchResult | null {
  const lock = Object.values(benchLock)[0];
  if (result === null || lock === undefined) return result;
  return { ...result, result_sha256: lock.trim() };
}
