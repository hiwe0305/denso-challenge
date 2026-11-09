// MSW handlers for exactly the endpoints of DESIGN.md §7 (§6.4: mock at the
// network layer). Components always call the real paths; turning MSW off
// switches the FE to the backend with no code change.
import { http, HttpResponse, type DefaultBodyType } from "msw";
import { API_BASE } from "../api/client";
import type {
  ActionAccepted,
  ActionStatusRow,
  ApiError,
  ChatFocus,
  ChatMessage,
  ChatSession,
  ExperimentDraft,
  Page,
  SyncRunRow,
} from "../api/types";
import {
  clusterDiagnosis,
  interventionDecision,
  method,
  taskId,
  type TaskId,
  syncStatus,
  userRole,
  type UserRole,
} from "../contracts/enums";
import { loadMockData } from "./data";
import { MockViews } from "./views";

const url = (path: string) => `${API_BASE}${path}`;

const DRAFT_FIELDS = ["task_id", "branch", "method", "hypothesis", "base_checkpoint_ref", "run_plan_ref", "hyperparams", "release_mix"];

/** Shape check of a draft body, as `check_body` in web/api/drafts.py; domain rules wait for submit. */
function checkDraft(body: Record<string, unknown>, partial: boolean): string | null {
  const unknown = Object.keys(body).filter((k) => !DRAFT_FIELDS.includes(k)).sort();
  if (unknown.length) return `trường không sửa được: ${JSON.stringify(unknown)}`;
  if (!partial) {
    const missing = ["task_id", "branch", "method", "base_checkpoint_ref"].filter((k) => !body[k]);
    if (missing.length) return `thiếu ${JSON.stringify(missing)}`;
  }
  if ("task_id" in body && !(taskId as readonly unknown[]).includes(body.task_id)) return `task_id ${String(body.task_id)} không có`;
  if ("method" in body && !(method as readonly unknown[]).includes(body.method)) return `method ${String(body.method)} không có`;
  if ("release_mix" in body) {
    const mix = body.release_mix;
    const ok = Array.isArray(mix) && mix.every((m: { release_id?: unknown; mix_weight?: unknown }) =>
      typeof m?.release_id === "string" && typeof m?.mix_weight === "number" && m.mix_weight > 0 && m.mix_weight <= 1);
    if (!ok) return "release_mix là [{release_id, mix_weight ∈ (0, 1]}]";
  }
  return null;
}

function error(status: number, code: string, message: string, hint: string | null = null) {
  const body: ApiError = { code, message, hint, ref: null };
  return HttpResponse.json(body, { status });
}

const notFound = (what: string) => error(404, "NOT_FOUND", `${what} không tồn tại hoặc bạn không được xem`);

/** The viewer's role. Header `X-Fw-Role` until sessions exist (§3.1); default ML_ENGINEER. */
function roleOf(request: Request): UserRole {
  const header = request.headers.get("x-fw-role");
  return header && (userRole as readonly string[]).includes(header)
    ? (header as UserRole)
    : "ML_ENGINEER";
}

/** §7.3 pagination: opaque cursor (an offset here), `limit` capped at 500. */
function page<T>(items: T[], request: Request): Page<T> {
  const params = new URL(request.url).searchParams;
  const limit = Math.min(Number(params.get("limit") ?? 100) || 100, 500);
  const offset = Number(params.get("cursor") ?? 0) || 0;
  const next = offset + limit < items.length ? String(offset + limit) : null;
  return { items: items.slice(offset, offset + limit), next_cursor: next, total: items.length };
}

const json = <T extends DefaultBodyType>(body: T | null, what: string) =>
  body === null ? notFound(what) : HttpResponse.json(body);

/**
 * In-memory `human_actions`. Same Idempotency-Key → same action_id (C16).
 * Nothing here applies the action: the status stays PENDING until a core
 * (or `fwsync fake-core`) answers, exactly as §6.4 asks the FE to expect.
 */
class ActionStore {
  private byKey = new Map<string, string>();
  private rows = new Map<string, ActionStatusRow>();
  private seq = 0;

  record(key: string, kind: string, targetKind: string, targetId: string, reason: string | null) {
    const existing = this.byKey.get(key);
    if (existing) return this.rows.get(existing) as ActionStatusRow;
    this.seq += 1;
    const row: ActionStatusRow = {
      action_id: `act_${String(this.seq).padStart(4, "0")}`,
      action_kind: kind,
      target_kind: targetKind,
      target_id: targetId,
      sync_status: "PENDING",
      reason,
      reject_reason: null,
      created_at: new Date().toISOString(),
      exported_at: null,
      applied_at: null,
    };
    this.byKey.set(key, row.action_id);
    this.rows.set(row.action_id, row);
    return row;
  }

  get(id: string) {
    return this.rows.get(id) ?? null;
  }

  findByKey(key: string) {
    const id = this.byKey.get(key);
    return id ? (this.rows.get(id) ?? null) : null;
  }

  /** Newest first, like the API. */
  list(syncStatus: string | null) {
    const rows = [...this.rows.values()].reverse();
    return syncStatus ? rows.filter((r) => r.sync_status === syncStatus) : rows;
  }

  /**
   * One pass of `POST /sync/run` with the fake core: every PENDING action is
   * exported and answered at once, so it ends APPLIED, as in sink mode.
   */
  cycle(): SyncRunRow {
    const at = new Date().toISOString();
    const moved = [...this.rows.values()].filter((r) => r.sync_status === "PENDING");
    for (const r of moved) {
      r.sync_status = "APPLIED";
      r.exported_at = at;
      r.applied_at = at;
    }
    const ids = moved.map((r) => r.action_id);
    const run: SyncRunRow = {
      id: `sync_${String(this.runs.length + 1).padStart(4, "0")}`, direction: "cycle", status: "ok",
      started_at: at, finished_at: at, exported: ids, applied: ids, fake_core: true, errors: [],
    };
    this.runs.unshift(run);
    return run;
  }

  runs: SyncRunRow[] = [];
}

interface DecisionItem {
  intervention_id: string;
  decision: string;
  approved_quantity?: number;
  reason?: string;
}

const CHAT_SCREENS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"];
const CHAT_FOCUS_KEYS = ["dataset_id", "experiment_id", "evaluation_id", "recommendation_id", "cluster_id"] as const;
const CHAT_KINDS: Record<(typeof CHAT_FOCUS_KEYS)[number], string> = {
  dataset_id: "dataset", experiment_id: "experiment", evaluation_id: "evaluation",
  recommendation_id: "recommendation", cluster_id: "cluster_card",
};

/** A sha256-shaped stand-in: MSW has no model and no prompt, only the shape of a turn. */
const fakeSha = (n: number) => n.toString(16).padStart(8, "0").repeat(8);

export function createHandlers(views = new MockViews(loadMockData())) {
  const actions = new ActionStore();
  const drafts: ExperimentDraft[] = [];
  // Chat, read-only minimum (web/api/chat.py). MSW has no model: the answer
  // says so and lists what the API would load, so the pane can be built and tested.
  const chatSessions: ChatSession[] = [];
  let chatMessageCount = 0;

  const accepted = (row: ActionStatusRow) =>
    HttpResponse.json<ActionAccepted>(
      { action_id: row.action_id, sync_status: row.sync_status },
      { status: 202 },
    );

  return [
    // ------------------------------------------------------------ M7
    // M4
    http.get(url("/releases"), ({ request }) => HttpResponse.json(page(views.releases(), request))),
    http.get(url("/releases/:id/items"), ({ params, request }) => {
      const rows = views.releaseItems(String(params.id));
      return rows === null ? notFound("release") : HttpResponse.json(page(rows, request));
    }),
    http.post(url("/releases/:id/freeze-request"), async ({ params, request }) => {
      const key = request.headers.get("idempotency-key");
      if (!key) return error(400, "IDEMPOTENCY_KEY_REQUIRED", "thiếu header Idempotency-Key (§7.3)");
      const release = views.releaseRow(String(params.id));
      if (!release) return notFound("release");
      if (release.status === "frozen") {
        return error(409, "ALREADY_FROZEN", "release đã đóng băng; đóng băng là bất biến");
      }
      if (!release.guard.ok) {
        const failed = release.guard.checks.filter((c) => c.status !== "ok").map((c) => c.name);
        return error(422, "SPLIT_GUARD", `guard chia tập chưa qua: ${failed.join(", ")}`,
          "bỏ các episode bị nêu khỏi bản nháp rồi gửi lại");
      }
      const body = (await request.json().catch(() => ({}))) as { reason?: string };
      const row = actions.record(key, "RELEASE_FREEZE_REQUEST", "releases", release.release_id, body.reason?.trim() || null);
      return accepted(row);
    }),

    // M5
    http.get(url("/experiments"), ({ request }) => HttpResponse.json(page(views.experiments(), request))),
    http.get(url("/experiment-drafts"), ({ request }) => HttpResponse.json(page([...drafts].reverse(), request))),
    http.post(url("/experiment-drafts"), async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      const bad = checkDraft(body, false);
      if (bad) return error(422, "BAD_DRAFT", bad);
      const now = new Date().toISOString();
      const row: ExperimentDraft = {
        id: `drf_${String(drafts.length + 1).padStart(4, "0")}`, task_id: body.task_id as TaskId,
        branch: String(body.branch), method: String(body.method), hypothesis: (body.hypothesis as string) ?? null,
        base_checkpoint_ref: String(body.base_checkpoint_ref), run_plan_ref: (body.run_plan_ref as string) ?? null,
        hyperparams: (body.hyperparams as Record<string, unknown>) ?? {},
        release_mix: (body.release_mix as ExperimentDraft["release_mix"]) ?? [],
        status: "DRAFT", submit_action_id: null, experiment_id: null, reject_reason: null,
        created_by: roleOf(request), created_at: now, updated_at: now,
      };
      drafts.push(row);
      return HttpResponse.json(row, { status: 201 });
    }),
    http.patch(url("/experiment-drafts/:id"), async ({ params, request }) => {
      const row = drafts.find((d) => d.id === params.id);
      if (!row) return notFound("bản nháp");
      const body = (await request.json()) as Record<string, unknown>;
      const bad = checkDraft(body, true);
      if (bad) return error(422, "BAD_DRAFT", bad);
      if (row.status !== "DRAFT") return error(409, "ALREADY_SUBMITTED", "bản nháp đã nộp; không sửa được nữa");
      Object.assign(row, body, { updated_at: new Date().toISOString() });
      return HttpResponse.json(row);
    }),
    http.post(url("/experiment-drafts/:id/submit"), ({ params, request }) => {
      const key = request.headers.get("idempotency-key");
      if (!key) return error(400, "IDEMPOTENCY_KEY_REQUIRED", "thiếu header Idempotency-Key (§7.3)");
      const row = drafts.find((d) => d.id === params.id);
      if (!row) return notFound("bản nháp");
      if (row.status !== "DRAFT") {
        const previous = actions.findByKey(key);
        if (previous && previous.action_id === row.submit_action_id) return accepted(previous);
        return error(409, "ALREADY_SUBMITTED", "bản nháp đã nộp");
      }
      const problems = views.submitProblems(row);
      if (problems.length) return error(422, "BR-01", problems.join("; "), "sửa bản nháp rồi nộp lại");
      const action = actions.record(key, "EXPERIMENT_SUBMIT", "experiment_drafts", row.id, null);
      Object.assign(row, { status: "SUBMITTED", submit_action_id: action.action_id, updated_at: new Date().toISOString() });
      return accepted(action);
    }),
    http.get(url("/experiments/:id/metrics"), ({ params, request }) => {
      const q = new URL(request.url).searchParams;
      const split = q.get("split");
      if (split !== null && split !== "train" && split !== "val") {
        return error(422, "BAD_SPLIT", `split ${split} không hợp lệ; chỉ train, val`);
      }
      const every = q.get("every") === null ? null : Number(q.get("every"));
      if (every !== null && !(every >= 1)) return error(422, "BAD_EVERY", "every phải >= 1");
      return json(views.metrics(String(params.id), split, every), "thí nghiệm");
    }),
    http.get(url("/experiments/:id/diagnoses"), ({ params }) =>
      json(views.diagnoses(String(params.id)), "thí nghiệm")),
    http.get(url("/experiments/:id/probes"), ({ params }) =>
      json(views.probes(String(params.id)), "thí nghiệm")),
    http.get(url("/experiments/:id/checkpoints"), ({ params }) =>
      json(views.checkpoints(String(params.id)), "thí nghiệm")),

    // M3
    http.get(url("/defects/scoreboard"), () => HttpResponse.json(views.defectScoreboard())),
    http.get(url("/defects/scores"), ({ request }) => HttpResponse.json(page(views.defectScores(), request))),

    http.get(url("/recommendations"), () => HttpResponse.json(views.recommendations())),
    http.get(url("/recommendations/:id"), ({ params }) =>
      json(views.recommendation(String(params.id)), "đề xuất")),
    http.get(url("/recommendations/:id/steps"), ({ params }) =>
      HttpResponse.json(views.steps(String(params.id)))),
    http.get(url("/recommendations/:id/clusters"), ({ params }) =>
      HttpResponse.json(views.clusters(String(params.id)))),
    http.get(url("/clusters/:id/card"), ({ params }) =>
      json(views.card(String(params.id)), "cụm")),
    http.get(url("/repair-tickets"), ({ request }) => {
      const rec = new URL(request.url).searchParams.get("recommendation_id") ?? undefined;
      return HttpResponse.json(views.repairTickets(rec));
    }),
    http.get(url("/fix-rates"), () => HttpResponse.json(views.fixRates())),

    // ------------------------------------------------------------ M6
    http.get(url("/evaluations"), ({ request }) =>
      HttpResponse.json(page(views.evaluations(roleOf(request)), request))),
    http.get(url("/evaluations/:id"), ({ params, request }) =>
      json(views.evaluation(String(params.id), roleOf(request)), "lượt eval")),
    http.get(url("/evaluations/:id/episodes"), ({ params, request }) => {
      const rows = views.evalEpisodes(String(params.id), roleOf(request));
      return rows === null ? notFound("lượt eval") : HttpResponse.json(page(rows, request));
    }),
    http.get(url("/evaluations/:id/funnel"), ({ params, request }) =>
      json(views.funnel(String(params.id), roleOf(request)), "lượt eval")),
    http.get(url("/evaluations/:id/failures"), ({ params, request }) =>
      json(views.failures(String(params.id), roleOf(request)), "lượt eval")),
    http.get(url("/evaluations/:id/system-checks"), ({ params, request }) =>
      json(views.systemChecks(String(params.id), roleOf(request)), "lượt eval")),

    // ------------------------------------------------------------ M2
    http.get(url("/datasets"), ({ request }) => HttpResponse.json(page(views.datasets(), request))),
    http.get(url("/datasets/:id"), ({ params }) => json(views.dataset(String(params.id)), "lô")),
    http.get(url("/datasets/:id/stages"), ({ params }) =>
      json(views.stages(String(params.id)), "lô")),
    http.get(url("/datasets/:id/episodes"), ({ params, request }) => {
      const rows = views.episodes(String(params.id));
      return rows === null ? notFound("lô") : HttpResponse.json(page(rows, request));
    }),
    http.get(url("/datasets/:id/report"), ({ params }) =>
      json(views.report(String(params.id)), "lô")),
    // No intake has been filed in the mock.
    http.get(url("/intakes"), ({ request }) => HttpResponse.json(page([], request))),

    // ------------------------------------------------------------ M9
    http.get(url("/results/branches"), ({ request }) => {
      const task = new URL(request.url).searchParams.get("task_id");
      if (!task) return error(400, "TASK_REQUIRED", "nhánh luôn đi kèm task_id (§6.4)");
      return HttpResponse.json(views.branches(task));
    }),
    http.get(url("/results/he-curve"), ({ request }) =>
      HttpResponse.json(views.heCurve(roleOf(request)))),
    http.get(url("/results/e1-curve"), () => HttpResponse.json(views.e1Curve())),

    // ------------------------------------------------------------ M8
    http.get(url("/cost/ledger"), ({ request }) => HttpResponse.json(page(views.ledger(), request))),
    http.get(url("/cost/by-branch"), () => HttpResponse.json(views.costByBranch())),
    http.get(url("/cost/by-intervention"), () => {
      const rec = views.recommendations()[0];
      return HttpResponse.json(rec ? (views.recommendation(rec.id)?.interventions ?? []) : []);
    }),
    http.get(url("/cost/sensitivity"), ({ request }) => {
      const book = new URL(request.url).searchParams.get("price_book") ?? undefined;
      return HttpResponse.json(views.sensitivity(book));
    }),

    // ------------------------------------------------------------ actions
    http.get(url("/actions"), ({ request }) => {
      const status = new URL(request.url).searchParams.get("sync_status");
      if (status !== null && !(syncStatus as readonly string[]).includes(status)) {
        return error(422, "BAD_SYNC_STATUS", `sync_status ${status} không hợp lệ`);
      }
      return HttpResponse.json(page(actions.list(status), request));
    }),
    http.get(url("/actions/:id"), ({ params }) =>
      json(actions.get(String(params.id)), "hành động")),
    http.get(url("/decisions"), ({ request }) => HttpResponse.json(page(views.decisions(), request))),
    http.get(url("/sync/runs"), () => HttpResponse.json(actions.runs)),

    // ------------------------------------------------------------ chat
    http.post(url("/chat/sessions"), async ({ request }) => {
      const body = (await request.json()) as { screen?: string; focus?: unknown; title?: string };
      if (!body.screen || !CHAT_SCREENS.includes(body.screen)) {
        return error(422, "BAD_SCREEN", `screen ${String(body.screen)} không có`);
      }
      const focus = (body.focus ?? {}) as Record<string, unknown>;
      if (typeof focus !== "object" || Array.isArray(focus)) return error(422, "BAD_FOCUS", "focus phải là đối tượng");
      const unknown = Object.keys(focus).filter((k) => !(CHAT_FOCUS_KEYS as readonly string[]).includes(k));
      if (unknown.length) return error(422, "BAD_FOCUS", `focus không nhận ${JSON.stringify(unknown.sort())}`);
      const pick = (k: keyof ChatFocus) => (typeof focus[k] === "string" && focus[k] ? (focus[k] as string) : null);
      const row: ChatSession = {
        id: `chs_${String(chatSessions.length + 1).padStart(4, "0")}`,
        user_role: roleOf(request), title: body.title?.trim() || null, screen: body.screen,
        context_dataset_id: pick("dataset_id"), context_experiment_id: pick("experiment_id"),
        context_evaluation_id: pick("evaluation_id"), context_recommendation_id: pick("recommendation_id"),
        context_cluster_id: pick("cluster_id"),
        created_at: new Date().toISOString(), closed_at: null, messages: [],
      };
      chatSessions.push(row);
      return HttpResponse.json(row, { status: 201 });
    }),
    http.get(url("/chat/sessions/:id"), ({ params }) => {
      const row = chatSessions.find((c) => c.id === params.id);
      return row ? HttpResponse.json(row) : notFound("phiên chat");
    }),
    http.post(url("/chat/sessions/:id/messages"), async ({ params, request }) => {
      const session = chatSessions.find((c) => c.id === params.id);
      if (!session) return error(404, "NOT_FOUND", "phiên chat không tồn tại");
      const content = String(((await request.json()) as { content?: unknown }).content ?? "").trim();
      if (!content) return error(422, "EMPTY_MESSAGE", "câu hỏi rỗng");
      if (content.length > 4000) return error(422, "MESSAGE_TOO_LONG", "câu hỏi dài quá 4000 ký tự");
      const loaded: Array<{ kind: string; id: string | null }> = [];
      const missing: Array<{ kind: string; id: string | null }> = [];
      if (session.screen !== "M3") {
        for (const k of CHAT_FOCUS_KEYS) {
          const id = session[`context_${k}`];
          if (!id) continue;
          // As agent_ro: a sealed evaluation is not visible, whoever asks (BR-10).
          const visible = k !== "evaluation_id" || views.evaluation(id, "JUDGE_VIEWER") !== null;
          (visible ? loaded : missing).push({ kind: CHAT_KINDS[k], id });
        }
      }
      const base = { session_id: session.id, attachments: [], proposed_action: null, confirmed_action_id: null,
        created_at: new Date().toISOString() };
      const user: ChatMessage = { ...base, id: ++chatMessageCount, role: "user", content, context_snapshot: {},
        prompt_sha256: null, model: null };
      const read = loaded.map((x) => `${x.kind} ${x.id}`).join(", ") || "danh sách của màn hình";
      const assistant: ChatMessage = {
        ...base, id: ++chatMessageCount, role: "assistant",
        content: `(mock) MSW không có model. API thật sẽ đọc ${session.screen}: ${read}.`,
        context_snapshot: { screen: session.screen, loaded, withheld: [], missing, truncated: false },
        prompt_sha256: fakeSha(chatMessageCount), model: "msw-mock",
      };
      session.messages.push(user, assistant);
      return HttpResponse.json({ user, assistant }, { status: 201 });
    }),
    http.post(url("/sync/run"), ({ request }) => {
      const role = roleOf(request);
      if (role !== "ADMIN" && role !== "LEAD") {
        return error(403, "ROLE", "chỉ ADMIN và LEAD được chạy đồng bộ (§7.2)");
      }
      return HttpResponse.json(actions.cycle());
    }),

    http.post(url("/recommendations/:id/decision"), async ({ params, request }) => {
      const key = request.headers.get("idempotency-key");
      if (!key) return error(400, "IDEMPOTENCY_KEY_REQUIRED", "thiếu header Idempotency-Key (§7.3)");
      const rec = views.recommendation(String(params.id));
      if (!rec) return notFound("đề xuất");
      const body = (await request.json()) as { items?: DecisionItem[] };
      const items = body.items ?? [];
      const known = new Map(rec.interventions.map((iv) => [iv.id, iv]));
      for (const item of items) {
        if (!known.has(item.intervention_id)) {
          return error(422, "UNKNOWN_INTERVENTION", `can thiệp ${item.intervention_id} không thuộc đề xuất này`);
        }
        if (!(interventionDecision as readonly string[]).includes(item.decision)) {
          return error(422, "BAD_DECISION", `quyết định ${item.decision} không hợp lệ`);
        }
        if (item.decision !== "APPROVE" && !item.reason?.trim()) {
          return error(422, "REASON_REQUIRED", "duyệt có sửa và từ chối phải ghi lý do");
        }
        if (item.decision === "APPROVE_EDITED" && !(Number(item.approved_quantity) > 0)) {
          return error(422, "QUANTITY_REQUIRED", "duyệt có sửa phải có số lượng > 0");
        }
      }
      // BR-07: approval may not push any of the three ceilings below zero.
      const used = new Map(rec.budget.map((b) => [b.resource, b.used]));
      const approved = { usd: 0, human_minutes: 0, gpu_hours: 0 };
      for (const item of items) {
        if (item.decision === "REJECT") continue;
        const iv = known.get(item.intervention_id);
        if (!iv) continue;
        const qty = item.decision === "APPROVE_EDITED" ? Number(item.approved_quantity) : iv.target_quantity;
        const f = qty / iv.target_quantity;
        approved.usd += iv.estimated_usd * f;
        approved.human_minutes += iv.estimated_human_minutes * f;
        approved.gpu_hours += iv.estimated_gpu_hours * f;
      }
      for (const line of rec.budget) {
        if ((used.get(line.resource) ?? 0) + approved[line.resource] > line.cap + 1e-9) {
          return error(422, "BR-07", `vượt trần ${line.resource}`, "giảm số lượng hoặc từ chối bớt can thiệp");
        }
      }
      const row = actions.record(key, "RECOMMENDATION_DECISION", "flywheel_recommendations", rec.id, null);
      return accepted(row);
    }),

    http.post(url("/clusters/:id/diagnosis-override"), async ({ params, request }) => {
      const key = request.headers.get("idempotency-key");
      if (!key) return error(400, "IDEMPOTENCY_KEY_REQUIRED", "thiếu header Idempotency-Key (§7.3)");
      const card = views.card(String(params.id));
      if (!card) return notFound("cụm");
      const body = (await request.json()) as { diagnosis?: string; reason?: string };
      if (!body.diagnosis || !(clusterDiagnosis as readonly string[]).includes(body.diagnosis)) {
        return error(422, "BAD_DIAGNOSIS", "chẩn đoán không thuộc 11 giá trị của spec §6.9");
      }
      if (!body.reason?.trim()) {
        return error(422, "REASON_REQUIRED", "ghi đè chẩn đoán bắt buộc ghi lý do");
      }
      const row = actions.record(key, "DIAGNOSIS_OVERRIDE", "failure_clusters", card.cluster.cluster_id, body.reason);
      return accepted(row);
    }),
  ];
}
