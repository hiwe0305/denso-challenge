// M0 acceptance: "MSW trả được mock M7" (DESIGN.md §9.2), plus the shapes of
// the other four core screens and the rules the read API must keep.
import { describe, expect, it } from "vitest";
import type {
  ActionAccepted,
  ApiError,
  ClusterBoardRow,
  ClusterCard,
  CostByBranch,
  DatasetReport,
  EvaluationSummary,
  FailureBoard,
  FunnelRow,
  Page,
  PipelineView,
  Recommendation,
  SensitivityRow,
} from "../api/types";
import { dataBudgetDiagnosis } from "../contracts/enums";
import { loadMockData } from "./data";
import { MockViews } from "./views";

const get = async <T>(path: string, role?: string) => {
  const response = await fetch(`/api${path}`, role ? { headers: { "X-Fw-Role": role } } : {});
  return { status: response.status, body: (await response.json()) as T };
};

const post = async <T>(path: string, body: unknown, key: string | null) => {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (key) headers["Idempotency-Key"] = key;
  const response = await fetch(`/api${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as T };
};

describe("M7 · Failure → Data on MSW", () => {
  it("serves the round with its three ceilings and proposals sorted by g/c", async () => {
    const { status, body } = await get<Recommendation>("/recommendations/rec_round1");
    expect(status).toBe(200);
    expect(body.status).toBe("AWAITING_REVIEW");
    expect(body.budget.map((b) => b.resource)).toEqual(["usd", "human_minutes", "gpu_hours"]);
    const usd = body.budget.find((b) => b.resource === "usd");
    // used = the diagnostic rollouts in the ledger; proposed = the four interventions.
    expect(usd).toMatchObject({ cap: 400, used: 1.11, proposed: 175.6 });
    expect(usd?.remaining).toBeCloseTo(400 - 1.11 - 175.6, 6);
    const gc = body.interventions.map((iv) => iv.gain_pp_per_100usd ?? -1);
    expect(gc).toEqual([...gc].sort((a, b) => b - a));
    expect(body.interventions[0]?.id).toBe("iv_1");
  });

  it("serves 12 steps, the last one still pending", async () => {
    const { body } = await get<Array<{ step_no: number; status: string }>>(
      "/recommendations/rec_round1/steps",
    );
    expect(body.map((s) => s.step_no)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expect(body[11]?.status).toBe("pending");
  });

  it("serves four clusters; only the three data diagnoses consume the data budget", async () => {
    const { body } = await get<ClusterBoardRow[]>("/recommendations/rec_round1/clusters");
    expect(body).toHaveLength(4);
    for (const c of body) {
      const spends = (dataBudgetDiagnosis as readonly string[]).includes(c.diagnosis ?? "");
      expect(c.consumes_data_budget).toBe(spends);
      expect(c.is_system_fault).toBe((c.diagnosis ?? "").startsWith("HE_THONG"));
      expect(c.origin).toBe("mock");
    }
    expect(body.filter((c) => c.consumes_data_budget).map((c) => c.cluster_id)).toEqual([
      "clu_3",
      "clu_4",
    ]);
  });

  it("member_count equals the failed episodes carrying the cluster key", () => {
    const views = new MockViews(loadMockData());
    for (const c of views.clusters("rec_round1")) {
      expect(views.clusterMembers(c.cluster_id)).toHaveLength(c.member_count);
    }
  });

  it("lists the codes that could not be scored, with reasons (BR-12)", async () => {
    const { body } = await get<ClusterCard>("/clusters/clu_3/card");
    const sys = body.skipped.filter((s) => s.source === "system_check");
    expect(sys.map((s) => s.code).sort()).toEqual(["R1", "R1", "R2", "R2"]);
    expect(sys.every((s) => s.reason.length > 0 && s.eval_episode_id !== null)).toBe(true);
    // The two `unknown` episodes are not counted as clean.
    const unknown = body.system_checks.filter((s) => s.diagnosis === "unknown");
    expect(unknown).toHaveLength(2);
    expect(unknown.every((s) => !s.usable_as_policy_evidence && s.fired_codes.length === 0)).toBe(true);

    const clu2 = (await get<ClusterCard>("/clusters/clu_2/card")).body;
    expect(clu2.skipped).toContainEqual(
      expect.objectContaining({ source: "diagnostic_run", code: "localize" }),
    );
    const clu1 = (await get<ClusterCard>("/clusters/clu_1/card")).body;
    expect(clu1.repair_tickets).toHaveLength(1);
    expect(clu1.repair_tickets[0]?.rebaseline_required).toBe(true);
    expect(clu1.interventions).toHaveLength(0);
  });

  it("answers 404 in the one error shape", async () => {
    const { status, body } = await get<ApiError>("/clusters/nope/card");
    expect(status).toBe(404);
    expect(Object.keys(body).sort()).toEqual(["code", "hint", "message", "ref"]);
  });
});

describe("M7 · write actions", () => {
  const approveAll = { items: ["iv_1", "iv_2", "iv_3", "iv_4"].map((id) => ({ intervention_id: id, decision: "APPROVE" })) };

  it("needs an Idempotency-Key and returns the same action for the same key", async () => {
    expect((await post("/recommendations/rec_round1/decision", approveAll, null)).status).toBe(400);
    const a = await post<ActionAccepted>("/recommendations/rec_round1/decision", approveAll, "k-1");
    const b = await post<ActionAccepted>("/recommendations/rec_round1/decision", approveAll, "k-1");
    expect(a.status).toBe(202);
    expect(a.body.sync_status).toBe("PENDING");
    expect(b.body.action_id).toBe(a.body.action_id);
  });

  it("refuses an edit or rejection without a reason, and an approval over a ceiling (BR-07)", async () => {
    const noReason = await post<ApiError>("/recommendations/rec_round1/decision",
      { items: [{ intervention_id: "iv_2", decision: "REJECT" }] }, "k-2");
    expect(noReason.status).toBe(422);
    expect(noReason.body.code).toBe("REASON_REQUIRED");
    const over = await post<ApiError>("/recommendations/rec_round1/decision",
      { items: [{ intervention_id: "iv_2", decision: "APPROVE_EDITED", approved_quantity: 80, reason: "x" }] },
      "k-3");
    expect(over.status).toBe(422);
    expect(over.body.code).toBe("BR-07");
  });

  it("refuses a diagnosis override without a reason", async () => {
    const r = await post<ApiError>("/clusters/clu_2/diagnosis-override", { diagnosis: "KY_NANG_YEU" }, "k-4");
    expect(r.status).toBe(422);
    const ok = await post<ActionAccepted>("/clusters/clu_2/diagnosis-override",
      { diagnosis: "KY_NANG_YEU", reason: "xem video, không phải ngoài miền" }, "k-5");
    expect(ok.status).toBe(202);
  });
});

describe("M6 · evaluation", () => {
  it("hides the sealed holdout from every role but ADMIN (BR-10)", async () => {
    const eng = await get<Page<EvaluationSummary>>("/evaluations");
    expect(eng.body.items.map((e) => e.evaluation_id)).not.toContain("ev_B_holdout");
    expect((await get("/evaluations/ev_B_holdout")).status).toBe(404);
    const admin = await get<Page<EvaluationSummary>>("/evaluations", "ADMIN");
    const holdout = admin.body.items.find((e) => e.evaluation_id === "ev_B_holdout");
    expect(holdout?.is_sealed).toBe(true);
    // No episode rows: the scorer rate is unknown, not 0.
    expect(holdout?.scorer_success_rate).toBeNull();
  });

  it("builds a funnel with exactly the task's step count, infra failures excluded", async () => {
    const ev = (await get<EvaluationSummary>("/evaluations/ev_B_dev")).body;
    expect(ev.step_names).toHaveLength(6);
    const rows = (await get<FunnelRow[]>("/evaluations/ev_B_dev/funnel")).body;
    expect(new Set(rows.map((r) => r.step_no))).toEqual(new Set([1, 2, 3, 4, 5, 6]));
    const perLevel = rows.filter((r) => r.step_no === 1).reduce((a, r) => a + r.reached_or_beyond, 0);
    expect(perLevel).toBe(ev.total_episodes - ev.infra_failed_count);
  });

  it("marks a family nobody produced as not_run, never as zero faults", async () => {
    const a = (await get<FailureBoard>("/evaluations/ev_A_dev/failures")).body;
    expect(a.families.find((f) => f.family === "F-SYS")?.status).toBe("not_run");
    const b = (await get<FailureBoard>("/evaluations/ev_B_dev/failures")).body;
    const sys = b.families.find((f) => f.family === "F-SYS");
    expect(sys?.status).toBe("ok");
    expect(sys?.skipped.length).toBeGreaterThan(0);
    expect(b.families.map((f) => f.family)).toEqual(["F-DATA", "F-TRAIN", "F-OFF", "F-CL", "F-SYS"]);
  });
});

describe("M2 · data and the 6-stage pipeline", () => {
  it("serves six stages per dataset and every attempt", async () => {
    const p = (await get<PipelineView>("/datasets/ds_kbd_teleop/stages")).body;
    expect(p.stages).toHaveLength(6);
    expect(p.attempts.filter((a) => a.stage_number === 4)).toHaveLength(2);
  });

  it("keeps QA-not-run apart from pass, and counts raw egocentric", async () => {
    const r = (await get<DatasetReport>("/datasets/ds_egodex/report")).body;
    const row = r.rows[0];
    expect(row?.egocentric_raw).toBe(10);
    expect(row?.qa_not_run).toBeGreaterThanOrEqual(10);
  });
});

describe("M9 and M8", () => {
  it("requires task_id with every branch query", async () => {
    expect((await get("/results/branches")).status).toBe(400);
    const rows = (await get<Array<{ branch: string }>>("/results/branches?task_id=two_table")).body;
    expect(rows.map((r) => r.branch)).toEqual(expect.arrayContaining(["A", "B"]));
  });

  it("serves E1 as an empty list, not a zero curve", async () => {
    expect((await get<unknown[]>("/results/e1-curve")).body).toEqual([]);
  });

  it("keeps the reversal visible and nets it out", async () => {
    const c = (await get<CostByBranch>("/cost/by-branch")).body;
    const a = c.rows.find((r) => r.branch === "A");
    expect(a?.reversal_count).toBe(1);
    expect(a?.measured_usd).toBe(20);
    expect(c.r_demo.length).toBeGreaterThan(0);
  });

  it("reprices the ledger under each of the four price books", async () => {
    const rows = (await get<SensitivityRow[]>("/cost/sensitivity")).body;
    expect(rows).toHaveLength(4);
    const base = rows.find((r) => r.price_book_name === "pitch_v10");
    const ledger = loadMockData().ledger;
    const booked = ledger.reduce((a, l) => a + (l.measured_usd ?? l.estimated_usd ?? 0), 0);
    expect(base?.total_usd).toBeCloseTo(booked, 2);
  });
});
