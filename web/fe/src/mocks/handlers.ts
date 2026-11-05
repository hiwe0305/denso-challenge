// MSW handlers for exactly the endpoints of DESIGN.md §7 (§6.4: mock at the
// network layer). Components always call the real paths; turning MSW off
// switches the FE to the backend with no code change.
import { http, HttpResponse, type DefaultBodyType } from "msw";
import { API_BASE } from "../api/client";
import type {
  ActionAccepted,
  ActionStatusRow,
  ApiError,
  Page,
  SyncRunRow,
} from "../api/types";
import {
  clusterDiagnosis,
  interventionDecision,
  syncStatus,
  userRole,
  type UserRole,
} from "../contracts/enums";
import { loadMockData } from "./data";
import { MockViews } from "./views";

const url = (path: string) => `${API_BASE}${path}`;

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

export function createHandlers(views = new MockViews(loadMockData())) {
  const actions = new ActionStore();

  const accepted = (row: ActionStatusRow) =>
    HttpResponse.json<ActionAccepted>(
      { action_id: row.action_id, sync_status: row.sync_status },
      { status: 202 },
    );

  return [
    // ------------------------------------------------------------ M7
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
