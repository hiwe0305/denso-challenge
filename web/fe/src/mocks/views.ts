// The read API, computed from the mock files.
//
// Each function mirrors one view of web/schema/70-views.sql (named in its
// comment), so the numbers MSW serves are the numbers Postgres will serve once
// `fwsync import` has loaded the same directory. Mock refs (`clu_1`, `ev_B_dev`)
// stand in for the database ids.
import type {
  AlgoStep,
  AlgoStepStatus,
  BranchComparisonRow,
  BudgetLine,
  ClusterBoardRow,
  ClusterCard,
  CostByBranch,
  CostByBranchRow,
  DatasetReport,
  DatasetReportRow,
  DataAllocationRow,
  DatasetRow,
  DecisionRow,
  CheckpointRow,
  DiagnosisSummary,
  ExperimentRow,
  ProbeRow,
  TrainCodeStatus,
  TrainDiagnosisView,
  TrainingMetricRow,
  DefectBenchGroup,
  DefectRate,
  DefectScoreboard,
  DefectScoreRow,
  DefectTotals,
  DiagnosticRun,
  E1CurvePoint,
  EpisodeRow,
  EvalEpisodeRow,
  EvaluationSummary,
  FailureBoard,
  FailureFamilyBlock,
  FailureFamilyRow,
  FixRate,
  FunnelRow,
  HeCurvePoint,
  InterventionRow,
  InterventionStatus,
  LedgerRow,
  PipelineView,
  RDemoRow,
  Recommendation,
  RecommendationStatus,
  RecommendationSummary,
  RepairTicket,
  Representative,
  SensitivityRow,
  SkippedItem,
  StageRow,
  StageRunRow,
  SystemCheckRow,
} from "../api/types";
import {
  dataBudgetDiagnosis,
  pipelineStage,
  type ClusterDiagnosis,
  type DataClass,
  type DeidStatus,
  type FailureClass,
  type HeVariant,
  type InfraStatus,
  type InterventionKind,
  type QaAgentVerdict,
  type QaDecision,
  type SourceKind,
  type Split,
  type StageRunStatus,
  type StepStatus,
  type SystemDiagnosis,
  type TaskId,
  type UserRole,
} from "../contracts/enums";
import type {
  MockData,
  RawCluster,
  RawEvalEpisode,
  RawEvaluation,
  RawIntervention,
  RawLedger,
  RawSystemDiagnosis,
} from "./data";

const ORIGIN = "mock" as const;

/** The twelve codes of the train diagnosis (DA-08). */
const TRAIN_CODES = [
  ...Array.from({ length: 8 }, (_, i) => `T${i + 1}`),
  ...Array.from({ length: 4 }, (_, i) => `O${i + 1}`),
];

/** A skip names a code or one branch of it (`T8a`), never another code. */
function skipOf(skipCode: string, code: string): boolean {
  return skipCode === code || (skipCode.startsWith(code) && !/^\d/.test(skipCode.slice(code.length)));
}

type BenchLayer = "code" | "agent";
const BENCH_LAYERS: readonly BenchLayer[] = ["code", "agent"];

/** `hit / total`; null when there is nothing to divide by (DA-31's `value: null`). */
function ratio(hit: number, total: number): number | null {
  return total ? hit / total : null;
}

function benchTotals(parts: DefectTotals[]): DefectTotals {
  const sum = (k: keyof DefectTotals) => parts.reduce((acc, p) => acc + p[k], 0);
  return { injected: sum("injected"), by_code: sum("by_code"), agent_adds: sum("agent_adds"), together: sum("together") };
}

/** g/c stop rule: 1 percentage point per $100 (spec v10.5 §8, "Ngưỡng dừng g/c"). */
export const STOP_THRESHOLD_PP_PER_100USD = 1;

const sum = (values: Array<number | null | undefined>): number =>
  values.reduce<number>((acc, v) => acc + (v ?? 0), 0);

/** Sum that stays null when no value was measured: "not measured" is not 0. */
const sumOrNull = (values: Array<number | null | undefined>): number | null => {
  const present = values.filter((v): v is number => v !== null && v !== undefined);
  return present.length === 0 ? null : present.reduce((a, b) => a + b, 0);
};

const round = (value: number, digits = 4): number => {
  const f = 10 ** digits;
  return Math.round(value * f) / f;
};

function isSealed(ev: RawEvaluation, now: Date): boolean {
  return ev.sealed_until !== null && new Date(ev.sealed_until) > now;
}

/** BR-10: a sealed evaluation is visible to ADMIN only. */
export function canSee(ev: RawEvaluation, role: UserRole, now: Date): boolean {
  return role === "ADMIN" || !isSealed(ev, now);
}

export class MockViews {
  constructor(
    private readonly d: MockData,
    private readonly now: () => Date = () => new Date(),
  ) {}

  /** `decisions`, newest first (M10). */
  decisions(): DecisionRow[] {
    return [...this.d.decisions].reverse().map((d) => ({
      id: d.decision_ref,
      kind: d.kind ?? null,
      target_kind: d.target_kind ?? null,
      target_id: d.target_id ?? null,
      conclusion: d.conclusion ?? null,
      reason: d.reason ?? null,
      source_action_id: d.source_action_id ?? null,
      origin: ORIGIN,
    }));
  }

  // ============================================================== M5

  private experiment(id: string) {
    return this.d.experiments.find((x) => x.experiment_code === id);
  }

  /** The experiment a telemetry line belongs to: by RunPlan, else by checkpoint (fwsync). */
  private metricExperiment(m: { run_plan_id: string; checkpoint_id: string }): string | undefined {
    return (
      this.d.experiments.find((x) => x.run_plan_ref === m.run_plan_id)?.experiment_code ??
      this.d.checkpoints.find((c) => c.checkpoint_ref === m.checkpoint_id)?.experiment_code
    );
  }

  experiments(): ExperimentRow[] {
    return this.d.experiments.map((x) => {
      const plan = this.d.runPlans.find((p) => p.run_plan_ref === x.run_plan_ref);
      return {
        experiment_id: x.experiment_code, task_id: x.task_id, branch: x.branch, method: x.method,
        hypothesis: x.hypothesis ?? null, status: x.status, train_seed: x.train_seed ?? null,
        hyperparams: x.hyperparams ?? {}, base_source_id: x.base_source_ref ?? null,
        started_at: x.started_at ?? null, finished_at: x.finished_at ?? null,
        run_plan: plan === undefined ? null : {
          id: plan.run_plan_ref, purpose: plan.purpose, config_sha256: plan.config_sha256,
          lock_uri: plan.lock_uri, frozen_at: plan.frozen_at, seed_range: plan.seed_range ?? null,
        },
        releases: this.d.experimentDatasets
          .filter((d) => d.experiment_code === x.experiment_code)
          .map((d) => ({ release_id: d.release_ref, mix_weight: d.mix_weight, episodes_used: d.episodes_used ?? null })),
        best_checkpoint_id: this.d.checkpoints.find((c) => c.experiment_code === x.experiment_code && c.is_best)?.checkpoint_ref ?? null,
        metric_rows: this.d.trainingMetrics.filter((m) => this.metricExperiment(m) === x.experiment_code).length,
        diagnosis: this.diagnoses(x.experiment_code)?.summary ?? null,
        origin: ORIGIN,
      };
    });
  }

  metrics(id: string, split: string | null, every: number | null): TrainingMetricRow[] | null {
    if (this.experiment(id) === undefined) return null;
    return this.d.trainingMetrics
      .filter((m) => this.metricExperiment(m) === id && (split === null || m.split === split))
      .filter((m) => every === null || every <= 1 || m.step % every === 0)
      .map((m) => ({
        step: m.step, split: m.split, attempt: m.attempt, epoch: m.epoch,
        loss: typeof m.loss === "number" ? m.loss : null,
        loss_nonfinite: typeof m.loss === "number" ? null : m.loss,
        lr: m.lr, loss_by_group: m.loss_by_group ?? {},
        grad_norm_vlm: m.grad_norm_vlm ?? null, grad_norm_action: m.grad_norm_action ?? null,
        vram_gb: m.vram_gb ?? null, throughput: m.throughput ?? null, wall_time_s: m.wall_time_s,
      }));
  }

  /** T1–T8, O1–O4: a code with no finding is clean only if a diagnosis ran and did not skip it. */
  diagnoses(id: string): TrainDiagnosisView | null {
    if (this.experiment(id) === undefined) return null;
    const mine = new Set(this.d.checkpoints.filter((c) => c.experiment_code === id).map((c) => c.checkpoint_ref));
    const runs = this.d.trainDiagnoses.filter((t) => mine.has(t.checkpoint_id));
    const findings = runs.flatMap((r) => r.findings.map((f) => ({ ...f, checkpoint_id: r.checkpoint_id })));
    const skips = runs.flatMap((r) => r.skipped);
    const ran = findings.length + skips.length > 0;
    const codes = TRAIN_CODES.map((code) => {
      const fired = findings.filter((f) => f.code === code).map((f) => ({
        start_step: f.start_step ?? 0, group: f.group ?? null, dim: f.dim ?? null,
        value: typeof f.value === "number" ? f.value : null,
        value_nonfinite: typeof f.value === "string" ? f.value : null,
        threshold: f.threshold ?? null, stop_job: f.stop_job ?? false, checkpoint_id: f.checkpoint_id,
      }));
      const skipped = skips.filter((k) => skipOf(k.code, code)).map((k) => ({ code: k.code, reason: k.reason }));
      const status: TrainCodeStatus = !ran ? "not_run" : fired.length ? "fired"
        : skipped.some((k) => k.code === code) ? "skipped" : skipped.length ? "partial" : "clean";
      return { code, family: code.startsWith("T") ? "F-TRAIN" as const : "F-OFF" as const, status, findings: fired, skipped };
    });
    const count = (s: TrainCodeStatus) => codes.filter((c) => c.status === s).length;
    const summary: DiagnosisSummary = {
      ran, fired: count("fired"), clean: count("clean"), skipped: count("skipped"),
      partial: count("partial"), not_run: count("not_run"),
    };
    return {
      experiment_id: id,
      config_sha256: [...new Set(runs.map((r) => r.config_sha256))].sort(),
      checkpoint_ids: [...new Set(runs.map((r) => r.checkpoint_id))].sort(),
      summary,
      codes,
    };
  }

  probes(id: string): ProbeRow[] | null {
    if (this.experiment(id) === undefined) return null;
    const mine = new Set(this.d.checkpoints.filter((c) => c.experiment_code === id).map((c) => c.checkpoint_ref));
    return this.d.probes.filter((p) => mine.has(p.checkpoint_id)).map((p) => ({
      probe: p.probe, checkpoint_id: p.checkpoint_id, parent_checkpoint_id: p.parent_checkpoint_id ?? null,
      dataset_sha256: p.dataset_sha256 ?? null, payload: p as Record<string, unknown>, origin: ORIGIN,
    }));
  }

  checkpoints(id: string): CheckpointRow[] | null {
    if (this.experiment(id) === undefined) return null;
    return this.d.checkpoints.filter((c) => c.experiment_code === id).map((c) => ({
      checkpoint_id: c.checkpoint_ref, parent_checkpoint_id: c.parent_checkpoint_ref ?? null,
      release_id: c.release_ref ?? null, method: c.method, step: c.step ?? null,
      weights_sha256: c.weights_sha256, uri: c.uri, is_best: Boolean(c.is_best),
      is_latest: Boolean(c.is_latest), train_seed: c.train_seed ?? null, origin: ORIGIN,
    }));
  }

  // ============================================================== M3

  /** v_defect_detection, in the order `fwsync` loads the file (mapper order). */
  defectScores(): DefectScoreRow[] {
    const b = this.d.bench;
    if (b === null) return [];
    const out: DefectScoreRow[] = [];
    for (const g of b.groups) {
      for (const layer of BENCH_LAYERS) {
        const l = g.layers[layer];
        const row = (metric: DefectScoreRow["metric"], subject: string, r: { hit: number; total: number },
          masked: number | null, bound: "upper" | null): DefectScoreRow => ({
          result_sha256: b.result_sha256, bench_version: b.bench_version, group_name: g.group,
          injected_copy: g.injected_copy, clean_copy: g.clean_copy, layer, metric, subject,
          hit: r.hit, total: r.total, value: ratio(r.hit, r.total), masked, bound,
          created_at: b.created_at, is_latest: true, origin: ORIGIN,
        });
        for (const [kind, r] of Object.entries(l.recall_by_kind)) {
          out.push(row("recall", kind, r, l.masked_by_kind[kind] ?? 0, null));
        }
        for (const [kind, r] of Object.entries(l.recall_unmasked_by_kind)) {
          out.push(row("recall_unmasked", kind, r, null, null));
        }
        for (const [code, r] of Object.entries(l.precision_by_code)) {
          out.push(row("precision", code, r, null, null));
        }
        out.push(row("false_alarm", "*", l.false_alarm_on_clean, null, "upper"));
      }
    }
    return out;
  }

  /** M3 · the newest bench run, one block per group, code and agent side by side. */
  defectScoreboard(): DefectScoreboard {
    const b = this.d.bench;
    const groups = b === null ? [] : [...b.groups].sort((x, y) => (x.group < y.group ? -1 : 1)).map((g) => {
      const rate = (r: { hit: number; total: number } | undefined): DefectRate =>
        r ? { hit: r.hit, total: r.total, value: ratio(r.hit, r.total) } : { hit: 0, total: 0, value: null };
      const both = <T>(pick: (layer: BenchLayer) => T) => ({ code: pick("code"), agent: pick("agent") });
      const kinds = g.split.map((s) => ({
        kind: s.kind, code: s.code, injected: s.injected, by_code: s.by_code, agent_adds: s.agent_adds,
        together: s.together, agent_alone: s.agent_alone,
        masked: both((l) => g.layers[l].masked_by_kind[s.kind] ?? 0),
        recall: both((l) => rate(g.layers[l].recall_by_kind[s.kind])),
        recall_unmasked: both((l) => rate(g.layers[l].recall_unmasked_by_kind[s.kind])),
      }));
      const codes = [...new Set(BENCH_LAYERS.flatMap((l) => Object.keys(g.layers[l].precision_by_code)))].sort();
      const block: DefectBenchGroup = {
        group_name: g.group, injected_copy: g.injected_copy, clean_copy: g.clean_copy, defects: g.defects,
        totals: benchTotals(kinds),
        kinds,
        codes: codes.map((code) => ({ code, precision: both((l) => rate(g.layers[l].precision_by_code[code])) })),
        false_alarm: both((l) => rate(g.layers[l].false_alarm_on_clean)),
        seconds_to_report: both((l) => g.layers[l].seconds_to_report),
        clean_reports: both((l) => g.layers[l].clean_reports),
        natural: both((l) => g.layers[l].natural),
        not_a_unit: both((l) => g.layers[l].false_alarm_not_a_unit),
        agent_ranking: rate(g.agent_quality.ranking),
        agent_reviews: g.agent_quality.reviews,
        agent_findings: g.agent_quality.findings,
      };
      return block;
    });
    return {
      result_sha256: b?.result_sha256 ?? null,
      bench_version: b?.bench_version ?? null,
      created_at: b?.created_at ?? null,
      measured_on: b?.measured_on ?? null,
      false_alarm_note: b?.false_alarm_on_clean ?? null,
      totals: benchTotals(groups.map((g) => g.totals)),
      groups,
      origin: b === null ? null : ORIGIN,
    };
  }

  // ============================================================== M7

  recommendations(): RecommendationSummary[] {
    return [this.recommendationSummary()];
  }

  private recommendationSummary(): RecommendationSummary {
    const r = this.d.recommendation;
    return {
      id: r.recommendation_ref,
      round_no: r.round_no,
      task_id: r.task_id,
      status: r.status as RecommendationStatus,
      checkpoint_id: r.checkpoint_ref,
      evaluation_id: r.evaluation_ref,
      run_plan_id: r.run_plan_ref,
      started_at: r.started_at,
      finished_at: r.finished_at,
      origin: ORIGIN,
    };
  }

  recommendation(id: string): Recommendation | null {
    const r = this.d.recommendation;
    if (r.recommendation_ref !== id) return null;
    const interventions = this.d.interventions
      .filter((iv) => iv.recommendation_ref === id)
      .map((iv) => this.interventionRow(iv))
      .sort((a, b) => (b.gain_pp_per_100usd ?? -1) - (a.gain_pp_per_100usd ?? -1));
    return {
      ...this.recommendationSummary(),
      budget: this.budget(id, interventions),
      interventions,
      stop_threshold_pp_per_100usd: STOP_THRESHOLD_PP_PER_100USD,
    };
  }

  /**
   * The three ceilings (BR-07). `used` is what the round measured in the
   * ledger (diagnostic rollouts so far); `proposed` is every live
   * intervention at its approved quantity, or its target when not yet approved.
   */
  private budget(id: string, interventions: InterventionRow[]): BudgetLine[] {
    const r = this.d.recommendation;
    const spent = this.d.ledger.filter((l) => l.recommendation_ref === id);
    const live = interventions.filter((iv) => iv.status !== "REJECTED" && iv.status !== "CANCELLED");
    const line = (
      resource: BudgetLine["resource"],
      cap: number,
      used: number,
      proposed: number,
    ): BudgetLine => ({
      resource,
      cap,
      used: round(used),
      proposed: round(proposed),
      remaining: round(cap - used - proposed),
    });
    const scaled = (iv: InterventionRow, value: number) =>
      (value * (iv.approved_quantity ?? iv.target_quantity)) / iv.target_quantity;
    return [
      line("usd", r.budget_usd, sum(spent.map((l) => l.measured_usd)),
        sum(live.map((iv) => scaled(iv, iv.estimated_usd)))),
      line("human_minutes", r.budget_human_minutes, sum(spent.map((l) => l.measured_human_minutes)),
        sum(live.map((iv) => scaled(iv, iv.estimated_human_minutes)))),
      line("gpu_hours", r.budget_gpu_hours, sum(spent.map((l) => l.measured_gpu_hours)),
        sum(live.map((iv) => scaled(iv, iv.estimated_gpu_hours)))),
    ];
  }

  /** v_cost_by_intervention, plus g/c. */
  private interventionRow(iv: RawIntervention): InterventionRow {
    const measured = this.d.ledger.filter((l) => l.intervention_ref === iv.intervention_ref);
    return {
      id: iv.intervention_ref,
      recommendation_id: iv.recommendation_ref,
      cluster_id: iv.cluster_ref,
      kind: iv.kind as InterventionKind,
      status: iv.status as InterventionStatus,
      unit: iv.unit,
      target_quantity: iv.target_quantity,
      approved_quantity: iv.approved_quantity,
      fulfilled_count: this.d.episodes.filter((e) => e.intervention_id === iv.intervention_ref).length,
      n_failures: iv.n_failures,
      n_eff: iv.n_eff,
      expected_gain_pp: iv.expected_gain_pp,
      estimated_usd: iv.estimated_usd,
      estimated_human_minutes: iv.estimated_human_minutes,
      estimated_gpu_hours: iv.estimated_gpu_hours,
      gain_pp_per_100usd:
        iv.estimated_usd > 0 ? round(iv.expected_gain_pp / (iv.estimated_usd / 100), 3) : null,
      measured_usd: sumOrNull(measured.map((l) => l.measured_usd)),
      measured_human_minutes: sumOrNull(measured.map((l) => l.measured_human_minutes)),
      measured_gpu_hours: sumOrNull(measured.map((l) => l.measured_gpu_hours)),
      spec: iv.spec,
      origin: ORIGIN,
    };
  }

  steps(id: string): AlgoStep[] {
    return this.d.algoSteps
      .filter((s) => s.recommendation_ref === id)
      .sort((a, b) => a.step_no - b.step_no)
      .map((s) => ({
        step_no: s.step_no,
        name: s.detail.name ?? `bước ${s.step_no}`,
        status: s.status as AlgoStepStatus,
        started_at: s.started_at,
        finished_at: s.finished_at,
        rollout_count: s.rollout_count,
        skip_reason: s.skip_reason,
        origin: ORIGIN,
      }));
  }

  /** v_cluster_board. */
  clusters(id: string): ClusterBoardRow[] {
    return this.d.clusters.filter((c) => c.recommendation_ref === id).map((c) => this.clusterRow(c));
  }

  private clusterRow(c: RawCluster): ClusterBoardRow {
    const runs = this.d.diagnosticRuns.filter((r) => r.cluster_ref === c.cluster_ref);
    const diagnosis = c.diagnosis as ClusterDiagnosis | null;
    return {
      cluster_id: c.cluster_ref,
      recommendation_id: c.recommendation_ref,
      task_id: this.d.recommendation.task_id,
      failed_step: c.failed_step,
      failure_code: c.failure_code,
      level: c.level,
      member_count: c.member_count,
      diagnosis,
      diagnosis_source: c.diagnosis_source,
      override_reason: c.override_reason,
      consumes_data_budget:
        diagnosis !== null && (dataBudgetDiagnosis as readonly string[]).includes(diagnosis),
      is_system_fault: diagnosis !== null && diagnosis.startsWith("HE_THONG"),
      card_uri: c.card_uri,
      checks: c.checks,
      diagnostic_run_count: runs.length,
      diagnostic_rollouts: sum(runs.map((r) => r.rollout_count)),
      skipped_checks: runs.filter((r) => r.outcome === "skipped").length,
      repair_ticket_count: this.d.repairTickets.filter((t) => t.cluster_ref === c.cluster_ref).length,
      origin: ORIGIN,
    };
  }

  /**
   * Members of a cluster: failed, infra-clean episodes of the round's
   * evaluation that carry the cluster key (step, code, level).
   */
  clusterMembers(clusterId: string): RawEvalEpisode[] {
    const c = this.d.clusters.find((x) => x.cluster_ref === clusterId);
    if (!c) return [];
    const evaluation = this.d.recommendation.evaluation_ref;
    return this.d.evalEpisodes.filter(
      (e) =>
        e.evaluation_ref === evaluation &&
        e.infra_status === "ok" &&
        e.sim_success === false &&
        e.first_failed_step === c.failed_step &&
        e.failure_code === c.failure_code &&
        e.level === c.level,
    );
  }

  card(clusterId: string): ClusterCard | null {
    const c = this.d.clusters.find((x) => x.cluster_ref === clusterId);
    if (!c) return null;
    const members = this.clusterMembers(clusterId);
    const memberRefs = new Set(members.map((m) => m.eval_episode_ref));
    const systemChecks = this.d.systemDiagnoses
      .filter((s) => memberRefs.has(s.eval_episode_ref))
      .map((s) => this.systemCheckRow(s))
      .filter((row): row is SystemCheckRow => row !== null);
    const runs: DiagnosticRun[] = this.d.diagnosticRuns
      .filter((r) => r.cluster_ref === clusterId)
      .map((r) => ({
        cluster_id: r.cluster_ref,
        step_no: r.step_no,
        check_name: r.check_name,
        outcome: r.outcome,
        value: r.value,
        threshold: r.threshold,
        rollout_count: r.rollout_count,
        gpu_seconds: r.gpu_seconds,
        representative_episode_id: r.representative_episode_ref,
        skip_reason: r.skip_reason,
        origin: ORIGIN,
      }));

    const clusterSkips = (c.checks.skipped ?? []) as Array<{ step: number; reason: string }>;
    const skipped: SkippedItem[] = [
      ...clusterSkips.map((s) => ({
        source: "algo_step" as const,
        code: String(s.step),
        reason: s.reason,
        eval_episode_id: null,
      })),
      ...runs
        .filter((r) => r.outcome === "skipped")
        .map((r) => ({
          source: "diagnostic_run" as const,
          code: r.check_name,
          reason: r.skip_reason ?? "",
          eval_episode_id: r.representative_episode_id,
        })),
      ...systemChecks.flatMap((s) =>
        s.skipped.map((k) => ({
          source: "system_check" as const,
          code: k.code,
          reason: k.reason,
          eval_episode_id: s.eval_episode_id,
        })),
      ),
    ];

    const byRef = new Map(this.d.evalEpisodes.map((e) => [e.eval_episode_ref, e]));
    const diagByRef = new Map(this.d.systemDiagnoses.map((s) => [s.eval_episode_ref, s]));
    const representatives: Representative[] = c.representative_refs.flatMap((ref) => {
      const e = byRef.get(ref);
      if (!e) return [];
      return [{
        eval_episode_id: ref,
        episode_index: e.episode_index,
        video_uri: e.video_uri,
        trajectory_log_uri: e.trajectory_log_uri,
        system_diagnosis: (diagByRef.get(ref)?.diagnosis ?? null) as SystemDiagnosis | null,
      }];
    });

    return {
      cluster: this.clusterRow(c),
      diagnostic_runs: runs,
      skipped,
      system_checks: systemChecks,
      representatives,
      interventions: this.d.interventions
        .filter((iv) => iv.cluster_ref === clusterId)
        .map((iv) => this.interventionRow(iv)),
      repair_tickets: this.repairTickets().filter((t) => t.cluster_id === clusterId),
    };
  }

  repairTickets(recommendationId?: string): RepairTicket[] {
    const inRound = new Set(
      this.d.clusters
        .filter((c) => recommendationId === undefined || c.recommendation_ref === recommendationId)
        .map((c) => c.cluster_ref),
    );
    return this.d.repairTickets
      .filter((t) => inRound.has(t.cluster_ref))
      .map((t) => ({
        id: `rt_${t.cluster_ref}`,
        cluster_id: t.cluster_ref,
        diagnosis: t.diagnosis as ClusterDiagnosis,
        title: t.title,
        detail: t.detail,
        status: t.status as RepairTicket["status"],
        rebaseline_required: t.rebaseline_required,
        origin: ORIGIN,
      }));
  }

  /** v_fix_rate. The mock has no closed round, so no kind has events yet. */
  fixRates(): FixRate[] {
    return [];
  }

  // ============================================================== M6

  private evaluationRaw(id: string, role: UserRole): RawEvaluation | null {
    const ev = this.d.evaluations.find((e) => e.evaluation_ref === id);
    if (!ev || !canSee(ev, role, this.now())) return null;
    return ev;
  }

  /** v_eval_summary. */
  evaluations(role: UserRole): EvaluationSummary[] {
    return this.d.evaluations
      .filter((ev) => canSee(ev, role, this.now()))
      .map((ev) => this.evaluationSummary(ev));
  }

  evaluation(id: string, role: UserRole): EvaluationSummary | null {
    const ev = this.evaluationRaw(id, role);
    return ev ? this.evaluationSummary(ev) : null;
  }

  private evaluationSummary(ev: RawEvaluation): EvaluationSummary {
    const scored = ev.total_episodes - ev.infra_failed_count;
    const episodes = this.d.evalEpisodes.filter(
      (e) => e.evaluation_ref === ev.evaluation_ref && e.infra_status === "ok",
    );
    const simRate = scored > 0 ? round(ev.success_count / scored) : null;
    // Without episode rows the scorer verdicts are unknown, not zero.
    const scorerRate =
      scored > 0 && episodes.length > 0
        ? round(episodes.filter((e) => e.scorer_success === true).length / scored)
        : null;
    const ckpt = this.d.checkpoints.find((c) => c.checkpoint_ref === ev.checkpoint_ref);
    const exp = this.d.experiments.find((x) => x.experiment_code === ckpt?.experiment_code);
    const names =
      episodes[0]?.details.step_names ??
      this.d.evalEpisodes.find((e) => e.details.step_names)?.details.step_names ??
      [];
    return {
      evaluation_id: ev.evaluation_ref,
      task_id: ev.task_id,
      checkpoint_id: ev.checkpoint_ref,
      branch: exp?.branch ?? null,
      split: ev.split,
      level: ev.level,
      renderer: ev.renderer,
      eval_mode: ev.eval_mode,
      scorer_version: ev.scorer_version,
      total_episodes: ev.total_episodes,
      infra_failed_count: ev.infra_failed_count,
      success_count: ev.success_count,
      sim_success_rate: simRate,
      scorer_success_rate: scorerRate,
      sim_scorer_gap:
        simRate !== null && scorerRate !== null ? round(Math.abs(simRate - scorerRate)) : null,
      step_names: names,
      started_at: ev.started_at,
      finished_at: ev.finished_at,
      sealed_until: ev.sealed_until,
      is_sealed: isSealed(ev, this.now()),
      origin: ORIGIN,
    };
  }

  evalEpisodes(id: string, role: UserRole): EvalEpisodeRow[] | null {
    if (!this.evaluationRaw(id, role)) return null;
    return this.d.evalEpisodes
      .filter((e) => e.evaluation_ref === id)
      .map((e) => ({
        id: e.eval_episode_ref,
        evaluation_id: e.evaluation_ref,
        episode_index: e.episode_index,
        level: e.level,
        condition_id: e.condition_id,
        episode_seed: e.episode_seed,
        rollout_seed: e.rollout_seed,
        infra_status: e.infra_status as InfraStatus,
        sim_success: e.sim_success,
        scorer_success: e.scorer_success,
        step_status: e.step_status as StepStatus[],
        first_failed_step: e.first_failed_step,
        failure_code: e.failure_code,
        failure_class: e.failure_class as FailureClass | null,
        failure_time_s: e.failure_time_s,
        video_uri: e.video_uri,
        trajectory_log_uri: e.trajectory_log_uri,
        origin: ORIGIN,
      }));
  }

  /** v_eval_funnel: infra-clean episodes only, one row per (episode level, step). */
  funnel(id: string, role: UserRole): FunnelRow[] | null {
    const ev = this.evaluationRaw(id, role);
    if (!ev) return null;
    const groups = new Map<string, FunnelRow>();
    for (const e of this.d.evalEpisodes) {
      if (e.evaluation_ref !== id || e.infra_status !== "ok") continue;
      e.step_status.forEach((status, index) => {
        const key = `${e.level}:${index + 1}`;
        let row = groups.get(key);
        if (!row) {
          row = {
            evaluation_id: id, task_id: ev.task_id, split: ev.split, eval_level: ev.level,
            renderer: ev.renderer, eval_mode: ev.eval_mode, episode_level: e.level,
            step_no: index + 1, reached_or_beyond: 0, step_pass: 0, step_fail: 0,
            step_not_attempted: 0, step_unknown: 0, is_sealed: isSealed(ev, this.now()),
            origin: ORIGIN,
          };
          groups.set(key, row);
        }
        row.reached_or_beyond += 1;
        if (status === "pass") row.step_pass += 1;
        else if (status === "fail") row.step_fail += 1;
        else if (status === "not_attempted") row.step_not_attempted += 1;
        else row.step_unknown += 1;
      });
    }
    return [...groups.values()].sort(
      (a, b) => a.episode_level - b.episode_level || a.step_no - b.step_no,
    );
  }

  /** v_system_check. */
  private systemCheckRow(s: RawSystemDiagnosis): SystemCheckRow | null {
    const e = this.d.evalEpisodes.find((x) => x.eval_episode_ref === s.eval_episode_ref);
    const ev = e && this.d.evaluations.find((x) => x.evaluation_ref === e.evaluation_ref);
    if (!e || !ev) return null;
    return {
      id: `sd_${s.eval_episode_ref}`,
      eval_episode_id: s.eval_episode_ref,
      evaluation_id: e.evaluation_ref,
      task_id: ev.task_id,
      episode_index: e.episode_index,
      level: e.level,
      diagnosis: s.diagnosis as SystemDiagnosis,
      config_sha256: s.config_sha256,
      trace_sha256: s.trace_sha256,
      infra_status: s.infra_status as InfraStatus,
      fired_codes: s.findings.map((f) => f.code).sort(),
      skipped_codes: s.skipped.map((k) => k.code).sort(),
      finding_count: s.findings.length,
      skipped_count: s.skipped.length,
      findings: s.findings,
      skipped: s.skipped,
      measurements: s.measurements,
      // Unknown mode stays null, never sync (FR21); the lists default empty.
      timing: s.timing ?? null,
      recorded: s.recorded ?? [],
      recorded_skipped: s.recorded_skipped ?? [],
      usable_as_policy_evidence: s.diagnosis === "clean",
      is_sealed: isSealed(ev, this.now()),
      origin: ORIGIN,
    };
  }

  systemChecks(id: string, role: UserRole): SystemCheckRow[] | null {
    if (!this.evaluationRaw(id, role)) return null;
    const refs = new Set(
      this.d.evalEpisodes.filter((e) => e.evaluation_ref === id).map((e) => e.eval_episode_ref),
    );
    return this.d.systemDiagnoses
      .filter((s) => refs.has(s.eval_episode_ref))
      .map((s) => this.systemCheckRow(s))
      .filter((row): row is SystemCheckRow => row !== null);
  }

  /** The five signal families of the failure table (design 27/10 §10). */
  failures(id: string, role: UserRole): FailureBoard | null {
    const ev = this.evaluationRaw(id, role);
    if (!ev) return null;
    const counts = (codes: string[]): FailureFamilyRow[] => {
      const m = new Map<string, number>();
      for (const code of codes) m.set(code, (m.get(code) ?? 0) + 1);
      return [...m.entries()].sort().map(([code, count]) => ({ code, count, detail: null }));
    };
    const notRun = (family: FailureFamilyBlock["family"]): FailureFamilyBlock => ({
      family, status: "not_run", rows: [], skipped: [],
    });

    // F-DATA: QA of the release the checkpoint was trained on.
    const ckpt = this.d.checkpoints.find((c) => c.checkpoint_ref === ev.checkpoint_ref);
    const releaseEpisodes = new Set(
      this.d.releaseItems
        .filter((ri) => ri.release_ref === ckpt?.release_ref && !ri.excluded)
        .map((ri) => ri.episode_ref),
    );
    const qa = this.d.qaReports.filter((q) => releaseEpisodes.has(q.episode_id));
    const fData: FailureFamilyBlock = qa.length === 0 ? notRun("F-DATA") : {
      family: "F-DATA",
      status: "ok",
      rows: counts(qa.filter((q) => q.decision !== "pass")
        .flatMap((q) => q.checks.filter((c) => !c.passed).map((c) => c.name))),
      skipped: [],
    };

    // F-TRAIN and F-OFF: the train diagnosis of the checkpoint (T1–T8, O1–O4).
    const td = this.d.trainDiagnoses.find((t) => t.checkpoint_id === ev.checkpoint_ref);
    const trainFamily = (family: "F-TRAIN" | "F-OFF", prefix: "T" | "O"): FailureFamilyBlock =>
      !td ? notRun(family) : {
        family,
        status: "ok",
        rows: counts(td.findings.filter((f) => f.code.startsWith(prefix)).map((f) => f.code)),
        skipped: td.skipped.filter((k) => k.code.startsWith(prefix)).map((k) => ({
          source: "train_diagnosis" as const, code: k.code, reason: k.reason, eval_episode_id: null,
        })),
      };

    // F-CL: closed-loop failure codes of the infra-clean failed episodes.
    const episodes = this.d.evalEpisodes.filter(
      (e) => e.evaluation_ref === id && e.infra_status === "ok",
    );
    const fCl: FailureFamilyBlock = episodes.length === 0 ? notRun("F-CL") : {
      family: "F-CL",
      status: "ok",
      rows: counts(episodes.filter((e) => e.sim_success === false && e.failure_code)
        .map((e) => e.failure_code as string)),
      skipped: [],
    };

    // F-SYS: v_system_check. Codes that could not be scored stay separate.
    const sys = this.systemChecks(id, role) ?? [];
    const fSys: FailureFamilyBlock = sys.length === 0 ? notRun("F-SYS") : {
      family: "F-SYS",
      status: "ok",
      rows: counts(sys.flatMap((s) => s.fired_codes)),
      skipped: sys.flatMap((s) => s.skipped.map((k) => ({
        source: "system_check" as const, code: k.code, reason: k.reason,
        eval_episode_id: s.eval_episode_id,
      }))),
    };

    return {
      evaluation_id: id,
      families: [fData, trainFamily("F-TRAIN", "T"), trainFamily("F-OFF", "O"), fCl, fSys],
    };
  }

  // ============================================================== M2

  datasets(): DatasetRow[] {
    return this.d.datasets.map((ds) => ({
      id: ds.dataset_code,
      dataset_code: ds.dataset_code,
      source_id: ds.source_ref,
      source_kind: ds.source_kind as SourceKind,
      source_detail: ds.source_detail,
      data_class: ds.data_class as DataClass,
      license: ds.license,
      episode_count: ds.episode_count,
      has_seeded_faults: ds.has_seeded_faults,
      status: ds.status,
      note: ds.note,
      origin: ORIGIN,
    }));
  }

  dataset(id: string): DatasetRow | null {
    return this.datasets().find((ds) => ds.id === id) ?? null;
  }

  /** v_pipeline_current plus every attempt. */
  stages(id: string): PipelineView | null {
    if (!this.dataset(id)) return null;
    const runs = this.d.stageRuns.filter((r) => r.dataset_code === id);
    const attempts: StageRunRow[] = runs
      .map((r) => ({
        id: `${r.dataset_code}:${r.stage_number}:${r.attempt_no}`,
        dataset_id: r.dataset_code,
        stage_number: r.stage_number,
        attempt_no: r.attempt_no,
        is_current: r.is_current,
        status: r.status as StageRunStatus,
        qa_code_decision: r.qa_code_decision as QaDecision | null,
        qa_agent_verdict: r.qa_agent_verdict as QaAgentVerdict | null,
        started_at: r.started_at,
        finished_at: r.finished_at,
        log_uri: r.log_uri,
        origin: ORIGIN,
      }))
      .sort((a, b) => a.stage_number - b.stage_number || a.attempt_no - b.attempt_no);
    const stages: StageRow[] = pipelineStage.map((code, index) => {
      const current = attempts.find((a) => a.stage_number === index + 1 && a.is_current);
      return {
        dataset_id: id,
        stage_number: index + 1,
        stage_code: code,
        stage_run_id: current?.id ?? null,
        attempt_no: current?.attempt_no ?? null,
        status: current?.status ?? null,
        qa_code_decision: current?.qa_code_decision ?? null,
        qa_agent_verdict: current?.qa_agent_verdict ?? null,
        started_at: current?.started_at ?? null,
        finished_at: current?.finished_at ?? null,
        log_uri: current?.log_uri ?? null,
        origin: current ? ORIGIN : null,
      };
    });
    return { stages, attempts };
  }

  /** Episodes of a dataset, resolved the way fwsync does (W12): by source, then intervention. */
  private datasetEpisodes(id: string) {
    const ds = this.d.datasets.find((x) => x.dataset_code === id);
    if (!ds) return null;
    return this.d.episodes.filter((e) => e.source_id !== null && e.source_id === ds.source_ref);
  }

  episodes(id: string): EpisodeRow[] | null {
    const eps = this.datasetEpisodes(id);
    if (!eps) return null;
    const qa = new Map(this.d.qaReports.map((q) => [q.episode_id, q]));
    return eps.map((e) => ({
      id: e.episode_id,
      dataset_id: id,
      source_kind: e.source_kind as SourceKind,
      kind: e.kind,
      split: e.split as Split,
      deid_status: e.deid_status as DeidStatus,
      data_class: e.data_class as DataClass,
      operator_kind: e.operator_kind,
      is_root: e.is_root,
      action_quality: e.action_quality,
      qa_decision: (qa.get(e.episode_id)?.decision ?? null) as QaDecision | null,
      qa_reasons: qa.get(e.episode_id)?.reasons ?? [],
      origin: ORIGIN,
    }));
  }

  /** v_dataset_report plus the per-check breakdown. */
  report(id: string): DatasetReport | null {
    const eps = this.datasetEpisodes(id);
    if (!eps) return null;
    const qa = new Map(this.d.qaReports.map((q) => [q.episode_id, q]));
    const groups = new Map<string, DatasetReportRow>();
    for (const e of eps) {
      const tier = e.meta.synthetic_tier ?? null;
      const key = `${e.source_kind}:${tier}`;
      let row = groups.get(key);
      if (!row) {
        row = {
          dataset_id: id, source_kind: e.source_kind as SourceKind, synthetic_tier: tier,
          episode_count: 0, root_human_count: 0, qa_pass: 0, qa_flag: 0, qa_quarantine: 0,
          qa_reject: 0, qa_not_run: 0, egocentric_raw: 0, mean_duration_s: null, origin: ORIGIN,
        };
        groups.set(key, row);
      }
      row.episode_count += 1;
      if (e.is_root && e.operator_kind === "human") row.root_human_count += 1;
      if (e.source_kind === "egocentric" && e.deid_status === "raw") row.egocentric_raw += 1;
      const decision = qa.get(e.episode_id)?.decision;
      if (decision === "pass") row.qa_pass += 1;
      else if (decision === "flag") row.qa_flag += 1;
      else if (decision === "quarantine") row.qa_quarantine += 1;
      else if (decision === "reject") row.qa_reject += 1;
      else row.qa_not_run += 1;
    }
    const checks = new Map<string, { passed: number; failed: number }>();
    for (const e of eps) {
      for (const c of qa.get(e.episode_id)?.checks ?? []) {
        const entry = checks.get(c.name) ?? { passed: 0, failed: 0 };
        if (c.passed) entry.passed += 1;
        else entry.failed += 1;
        checks.set(c.name, entry);
      }
    }
    return {
      rows: [...groups.values()],
      by_check: [...checks.entries()].map(([name, v]) => ({ name, ...v })),
    };
  }

  // ============================================================== M9

  private bestCheckpointOf(experimentCode: string) {
    return this.d.checkpoints.find((c) => c.experiment_code === experimentCode && c.is_best);
  }

  private ledgerOfExperiment(code: string): RawLedger[] {
    return this.d.ledger.filter((l) => l.experiment_code === code);
  }

  /** v_branch_comparison: latest unsealed dev eval of each branch's best checkpoint. */
  branches(taskId: string): BranchComparisonRow[] {
    const rows: BranchComparisonRow[] = [];
    // HE points share one branch; they have their own view (v_he_curve).
    const branchExperiments = this.d.experiments.filter(
      (e) => e.task_id === taskId && e.hypothesis !== "HE" && e.hypothesis !== "HE_T",
    );
    for (const x of branchExperiments) {
      const ckpt = this.bestCheckpointOf(x.experiment_code);
      if (!ckpt) continue;
      const evs = this.d.evaluations
        .filter((ev) => ev.checkpoint_ref === ckpt.checkpoint_ref && ev.split === "dev"
          && !isSealed(ev, this.now()))
        .sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? ""));
      const ev = evs[0];
      if (!ev) continue;
      const ledger = this.ledgerOfExperiment(x.experiment_code);
      const scored = ev.total_episodes - ev.infra_failed_count;
      rows.push({
        task_id: x.task_id, branch: x.branch, method: x.method, experiment_id: x.experiment_code,
        evaluation_id: ev.evaluation_ref, level: ev.level,
        sim_success_rate: scored > 0 ? round(ev.success_count / scored) : null,
        total_episodes: ev.total_episodes, infra_failed_count: ev.infra_failed_count,
        measured_usd: sumOrNull(ledger.map((l) => l.measured_usd)),
        measured_human_minutes: sumOrNull(ledger.map((l) => l.measured_human_minutes)),
        measured_gpu_hours: sumOrNull(ledger.map((l) => l.measured_gpu_hours)),
        estimated_usd: sumOrNull(ledger.map((l) => l.estimated_usd)),
        origin: ORIGIN,
      });
    }
    return rows;
  }

  /** Human root demos in the releases an experiment trained on (v_he_curve, v_r_demo). */
  private humanRootEpisodes(experimentCode: string): Set<string> {
    const releases = new Set(
      this.d.experimentDatasets.filter((ed) => ed.experiment_code === experimentCode)
        .map((ed) => ed.release_ref),
    );
    const roots = new Set(
      this.d.episodes.filter((e) => e.is_root && e.operator_kind === "human").map((e) => e.episode_id),
    );
    return new Set(
      this.d.releaseItems
        .filter((ri) => releases.has(ri.release_ref) && !ri.excluded && roots.has(ri.episode_ref))
        .map((ri) => ri.episode_ref),
    );
  }

  /** v_he_curve. Sealed points are kept and flagged; the API drops them for non-ADMIN. */
  heCurve(role: UserRole): HeCurvePoint[] {
    const points: HeCurvePoint[] = [];
    for (const x of this.d.experiments.filter((e) => e.hypothesis === "HE" || e.hypothesis === "HE_T")) {
      const ckpt = this.bestCheckpointOf(x.experiment_code);
      if (!ckpt) continue;
      for (const ev of this.d.evaluations.filter((e) => e.checkpoint_ref === ckpt.checkpoint_ref)) {
        if (!canSee(ev, role, this.now())) continue;
        const scored = ev.total_episodes - ev.infra_failed_count;
        points.push({
          task_id: x.task_id, branch: x.branch, hypothesis: x.hypothesis,
          he_variant: (x.hyperparams.he_variant ?? null) as HeVariant | null,
          n_demos: this.humanRootEpisodes(x.experiment_code).size, train_seed: x.train_seed,
          level: ev.level, sim_success_rate: scored > 0 ? round(ev.success_count / scored) : null,
          n_scored: scored, is_sealed: isSealed(ev, this.now()), origin: ORIGIN,
        });
      }
    }
    return points;
  }

  /** E1 has not run in the mock; an empty list renders EmptyState, never a 0% curve. */
  e1Curve(): E1CurvePoint[] {
    return [];
  }

  // ============================================================== M8

  ledger(): LedgerRow[] {
    return this.d.ledger.map((l) => ({
      id: l.entry_ref,
      entry_kind: l.entry_kind,
      activity: l.activity,
      resource_type: l.resource_type,
      quantity: l.quantity,
      unit: l.unit,
      price_book_name: l.price_book_name,
      branch: l.branch ?? null,
      experiment_id: l.experiment_code ?? null,
      evaluation_id: l.evaluation_ref ?? null,
      dataset_id: l.dataset_code ?? null,
      recommendation_id: l.recommendation_ref ?? null,
      cluster_id: l.cluster_ref ?? null,
      intervention_id: l.intervention_ref ?? null,
      estimated_usd: l.estimated_usd ?? null,
      estimated_human_minutes: l.estimated_human_minutes ?? null,
      estimated_gpu_hours: l.estimated_gpu_hours ?? null,
      measured_usd: l.measured_usd ?? null,
      measured_human_minutes: l.measured_human_minutes ?? null,
      measured_gpu_hours: l.measured_gpu_hours ?? null,
      reverses_entry_id: l.reverses_entry_ref,
      note: l.note ?? null,
      origin: ORIGIN,
    }));
  }

  /** v_cost_by_branch: task from the experiment, else the evaluation, else the round. */
  private ledgerTask(l: RawLedger): TaskId | null {
    if (l.experiment_code) {
      const x = this.d.experiments.find((e) => e.experiment_code === l.experiment_code);
      if (x) return x.task_id;
    }
    if (l.evaluation_ref) {
      const ev = this.d.evaluations.find((e) => e.evaluation_ref === l.evaluation_ref);
      if (ev) return ev.task_id;
    }
    if (l.recommendation_ref && this.d.recommendation.recommendation_ref === l.recommendation_ref) {
      return this.d.recommendation.task_id;
    }
    return null;
  }

  /** v_cost_by_branch, v_r_demo and v_cost_data_allocation (BR-05). */
  costByBranch(): CostByBranch {
    const groups = new Map<string, { row: CostByBranchRow; entries: RawLedger[] }>();
    for (const l of this.d.ledger) {
      const branch = l.branch ?? null;
      const task = this.ledgerTask(l);
      const key = `${branch}:${task}:${l.price_book_name}`;
      let g = groups.get(key);
      if (!g) {
        g = {
          row: {
            branch, task_id: task, price_book_name: l.price_book_name, entry_count: 0,
            estimated_usd: null, measured_usd: null, usd_forecast_error: null, forecast_pairs: 0,
            estimated_human_minutes: null, measured_human_minutes: null,
            estimated_gpu_hours: null, measured_gpu_hours: null, reversal_count: 0, origin: ORIGIN,
          },
          entries: [],
        };
        groups.set(key, g);
      }
      g.entries.push(l);
    }
    const rows = [...groups.values()].map(({ row, entries }) => {
      // Forecast error only on rows carrying both an estimate and a measurement.
      const paired = entries.filter(
        (l) => l.measured_usd != null && l.estimated_usd != null,
      );
      return {
        ...row,
        entry_count: entries.length,
        estimated_usd: sumOrNull(entries.map((l) => l.estimated_usd)),
        measured_usd: sumOrNull(entries.map((l) => l.measured_usd)),
        usd_forecast_error: sumOrNull(paired.map((l) => (l.measured_usd as number) - (l.estimated_usd as number))),
        forecast_pairs: paired.length,
        estimated_human_minutes: sumOrNull(entries.map((l) => l.estimated_human_minutes)),
        measured_human_minutes: sumOrNull(entries.map((l) => l.measured_human_minutes)),
        estimated_gpu_hours: sumOrNull(entries.map((l) => l.estimated_gpu_hours)),
        measured_gpu_hours: sumOrNull(entries.map((l) => l.measured_gpu_hours)),
        reversal_count: entries.filter((l) => l.entry_kind === "REVERSAL").length,
      };
    });
    // v_r_demo: one row per (task, branch, method); HE points live in v_he_curve.
    const demoGroups = new Map<string, RDemoRow & { seen: Set<string> }>();
    for (const x of this.d.experiments) {
      if (x.hypothesis === "HE" || x.hypothesis === "HE_T") continue;
      const key = `${x.task_id}:${x.branch}:${x.method}`;
      const g = demoGroups.get(key) ?? {
        task_id: x.task_id, branch: x.branch, method: x.method, human_root_episodes: 0,
        origin: ORIGIN, seen: new Set<string>(),
      };
      for (const e of this.humanRootEpisodes(x.experiment_code)) g.seen.add(e);
      demoGroups.set(key, g);
    }
    const rDemo: RDemoRow[] = [...demoGroups.values()]
      .filter((g) => g.seen.size > 0)
      .map(({ seen, ...g }) => ({ ...g, human_root_episodes: seen.size }));
    return { rows, r_demo: rDemo, data_allocation: this.dataAllocation() };
  }

  /** v_cost_data_allocation: each dataset's measured cost, shared by episodes used. */
  private dataAllocation(): DataAllocationRow[] {
    type Cost = { usd: number | null; human_minutes: number | null; gpu_hours: number | null };
    const cost = new Map<string, Cost>();
    for (const l of this.d.ledger) {
      if (!l.dataset_code) continue;
      const c = cost.get(l.dataset_code) ?? { usd: null, human_minutes: null, gpu_hours: null };
      if (l.measured_usd != null) c.usd = (c.usd ?? 0) + l.measured_usd;
      if (l.measured_human_minutes != null) c.human_minutes = (c.human_minutes ?? 0) + l.measured_human_minutes;
      if (l.measured_gpu_hours != null) c.gpu_hours = (c.gpu_hours ?? 0) + l.measured_gpu_hours;
      cost.set(l.dataset_code, c);
    }
    // Episode → dataset the way fwsync resolves it (W12): by source.
    const bySource = new Map(this.d.datasets.map((d) => [d.source_ref, d.dataset_code]));
    const datasetOf = new Map(
      this.d.episodes.map((e) => [e.episode_id, e.source_id ? (bySource.get(e.source_id) ?? null) : null]),
    );
    const out: DataAllocationRow[] = [];
    for (const x of this.d.experiments) {
      const releases = new Set(
        this.d.experimentDatasets.filter((ed) => ed.experiment_code === x.experiment_code)
          .map((ed) => ed.release_ref),
      );
      const used = new Map<string, Set<string>>();
      for (const ri of this.d.releaseItems) {
        if (!releases.has(ri.release_ref) || ri.excluded) continue;
        const code = datasetOf.get(ri.episode_ref);
        if (!code) continue;
        const set = used.get(code) ?? new Set<string>();
        set.add(ri.episode_ref);
        used.set(code, set);
      }
      for (const d of this.d.datasets) {
        const eps = used.get(d.dataset_code);
        if (!eps) continue;
        const n = eps.size;
        const total = d.episode_count;
        const c = cost.get(d.dataset_code) ?? { usd: null, human_minutes: null, gpu_hours: null };
        const part = (v: number | null) => (v !== null && total ? (v * n) / total : null);
        out.push({
          experiment_id: x.experiment_code, task_id: x.task_id, branch: x.branch,
          method: x.method, hypothesis: x.hypothesis, dataset_id: d.dataset_code,
          episodes_used: n, dataset_episodes: total, share: total ? n / total : null,
          allocated_usd: part(c.usd), allocated_human_minutes: part(c.human_minutes),
          allocated_gpu_hours: part(c.gpu_hours), origin: ORIGIN,
        });
      }
    }
    return out;
  }

  /**
   * The ledger repriced under each price book. Pricing is linear, so each
   * entry's dollars scale by (new rate / rate of the book it was booked under).
   */
  sensitivity(priceBook?: string): SensitivityRow[] {
    const books = new Map(this.d.priceBooks.map((b) => [b.name, b]));
    return this.d.priceBooks
      .filter((b) => priceBook === undefined || b.name === priceBook)
      .map((book) => {
        const byBranch = new Map<string | null, number>();
        for (const l of this.d.ledger) {
          const base = l.price_book_name ? books.get(l.price_book_name) : undefined;
          const usd = l.measured_usd ?? l.estimated_usd ?? 0;
          const baseRate = base?.rates[l.resource_type]?.usd_per_unit;
          const newRate = book.rates[l.resource_type]?.usd_per_unit;
          const repriced = baseRate && newRate !== undefined ? (usd * newRate) / baseRate : usd;
          const branch = l.branch ?? null;
          byBranch.set(branch, (byBranch.get(branch) ?? 0) + repriced);
        }
        const by = [...byBranch.entries()].map(([branch, usd]) => ({ branch, usd: round(usd, 2) }));
        return {
          price_book_name: book.name,
          sha256: book.sha256,
          note: book.note,
          rates: book.rates,
          by_branch: by,
          total_usd: round(sum(by.map((b) => b.usd)), 2),
        };
      });
  }
}
