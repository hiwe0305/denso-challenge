// M7 · Failure → Data (DESIGN.md §6.1): steps on the left, the cluster board
// with its evidence cards in the middle, proposals and budget on the right,
// repair tickets underneath.
import { useMemo, useRef, useState } from "react";
import { apiAction, newIdempotencyKey } from "../api/client";
import {
  useAlgoSteps,
  useClusterCard,
  useClusters,
  useFixRates,
  useRecommendation,
  useRecommendations,
  useRepairTickets,
} from "../api/hooks";
import type {
  AlgoStep,
  BudgetLine,
  ClusterBoardRow,
  InterventionRow,
  Recommendation,
} from "../api/types";
import { clusterDiagnosis, type ClusterDiagnosis, type SystemDiagnosis } from "../contracts/enums";
import {
  ActionStatus,
  BudgetBar,
  DiagnosisChip,
  EmptyState,
  ErrorBox,
  Loading,
  MockBadge,
  Panel,
  SkippedList,
  SystemVerdictChip,
} from "../ui/components";
import {
  algoStepStatusLabel,
  checkNameLabel,
  clusterDiagnosisLabel,
  fmt,
  fmtTime,
  interventionKindLabel,
} from "../ui/labels";

export function FailureToData() {
  const list = useRecommendations();
  const id = list.data?.[0]?.id ?? null;
  const rec = useRecommendation(id);

  if (list.isLoading) return <Loading />;
  if (list.error) return <ErrorBox error={list.error} />;
  if (!id) return <EmptyState title="Chưa có lượt Failure → Data nào">Chạy lượt đầu từ màn hình Đánh giá.</EmptyState>;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-xl font-semibold">Failure → Data</h1>
        {rec.data ? (
          <>
            <span className="text-sm text-slate-600">
              Vòng {rec.data.round_no} · task {rec.data.task_id} · checkpoint {rec.data.checkpoint_id} · eval{" "}
              {rec.data.evaluation_id}
            </span>
            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
              {rec.data.status === "AWAITING_REVIEW" ? "chờ duyệt" : rec.data.status}
            </span>
            <MockBadge origin={rec.data.origin} />
          </>
        ) : null}
      </header>
      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_340px]">
        <StepColumn recommendationId={id} />
        <ClusterColumn recommendationId={id} />
        {rec.isLoading ? <Loading /> : rec.error ? <ErrorBox error={rec.error} /> : rec.data ? (
          <ProposalColumn rec={rec.data} />
        ) : null}
      </div>
      <RepairTickets recommendationId={id} />
    </div>
  );
}

// ------------------------------------------------------------------ left

function StepColumn({ recommendationId }: { recommendationId: string }) {
  const steps = useAlgoSteps(recommendationId);
  const totalRollouts = (steps.data ?? []).reduce((a, s) => a + s.rollout_count, 0);
  return (
    <Panel title="Tiến trình 12 bước">
      {steps.isLoading ? <Loading /> : steps.error ? <ErrorBox error={steps.error} /> : (
        <>
          <ol className="space-y-1.5" data-testid="algo-steps">
            {(steps.data ?? []).map((s) => <StepItem key={s.step_no} step={s} />)}
          </ol>
          <p className="mt-3 text-xs text-slate-500">Tổng rollout chẩn đoán đã tốn: {fmt(totalRollouts, 0)}</p>
        </>
      )}
    </Panel>
  );
}

function StepItem({ step }: { step: AlgoStep }) {
  const dot = {
    done: "bg-emerald-500", running: "bg-sky-500 animate-pulse", pending: "bg-slate-300",
    skipped: "bg-amber-400", failed: "bg-rose-500",
  }[step.status];
  return (
    <li className="flex gap-2 text-sm">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot}`} />
      <div className="min-w-0">
        <p>
          <span className="text-slate-400">{step.step_no}.</span> {step.name}{" "}
          <span className="text-xs text-slate-500">· {algoStepStatusLabel[step.status]}</span>
        </p>
        <p className="text-xs text-slate-500">
          {step.started_at ? `${fmtTime(step.started_at)} → ${fmtTime(step.finished_at)}` : "chưa bắt đầu"}
          {step.rollout_count > 0 ? ` · ${step.rollout_count} rollout` : ""}
        </p>
        {step.status === "skipped" && step.skip_reason ? (
          <p className="text-xs text-amber-800">bỏ qua: {step.skip_reason}</p>
        ) : null}
      </div>
    </li>
  );
}

// ------------------------------------------------------------------ middle

function ClusterColumn({ recommendationId }: { recommendationId: string }) {
  const clusters = useClusters(recommendationId);
  const [open, setOpen] = useState<string | null>(null);
  const rows = clusters.data ?? [];
  const free = rows.filter((c) => !c.consumes_data_budget);
  return (
    <Panel
      title="Bảng cụm lỗi"
      aside={
        <span className="flex gap-1.5 text-[11px] text-slate-500">
          <DiagnosisChip diagnosis="HE_THONG_CONTROLLER" />
          <DiagnosisChip diagnosis="THIEU_VUNG_PHU" />
          <DiagnosisChip diagnosis="NGOAI_MIEN" />
        </span>
      }
    >
      {clusters.isLoading ? <Loading /> : clusters.error ? <ErrorBox error={clusters.error} /> : rows.length === 0 ? (
        <EmptyState title="Chưa gom cụm" />
      ) : (
        <>
          {free.length > 0 ? (
            <p className="mb-3 rounded bg-slate-100 px-3 py-2 text-sm text-slate-700" data-testid="free-clusters-note">
              {free.length} cụm là lỗi hệ thống hoặc không cần dữ liệu, <b>không tốn ngân sách dữ liệu</b>;
              chỉ {rows.length - free.length} cụm còn lại cần thu thêm.
            </p>
          ) : null}
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="cluster-board">
              <thead className="text-left text-xs text-slate-500">
                <tr>
                  <th className="py-1 pr-2">Cụm</th>
                  <th className="pr-2">Bước hỏng</th>
                  <th className="pr-2">Lỗi</th>
                  <th className="pr-2">Mức</th>
                  <th className="pr-2 text-right">TV</th>
                  <th className="pr-2">Chẩn đoán</th>
                  <th className="pr-2">Ngân sách dữ liệu</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <ClusterRows key={c.cluster_id} c={c} open={open === c.cluster_id}
                    toggle={() => setOpen(open === c.cluster_id ? null : c.cluster_id)} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  );
}

function ClusterRows({ c, open, toggle }: { c: ClusterBoardRow; open: boolean; toggle: () => void }) {
  return (
    <>
      <tr className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={toggle}
        aria-expanded={open} data-testid={`cluster-${c.cluster_id}`}>
        <td className="py-1.5 pr-2 font-mono text-xs">{open ? "▾" : "▸"} {c.cluster_id}</td>
        <td className="pr-2">{c.failed_step}</td>
        <td className="pr-2 font-mono text-xs">{c.failure_code}</td>
        <td className="pr-2">{c.level}</td>
        <td className="pr-2 text-right">{c.member_count}</td>
        <td className="pr-2">
          <DiagnosisChip diagnosis={c.diagnosis} />
          {c.diagnosis_source === "engineer_override" ? <span className="ml-1 text-xs text-slate-500">(ghi đè)</span> : null}
        </td>
        <td className="pr-2 text-xs">{c.consumes_data_budget ? "có" : "không"}</td>
      </tr>
      {open ? (
        <tr>
          <td colSpan={7} className="bg-slate-50 p-3">
            <EvidenceCard clusterId={c.cluster_id} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function EvidenceCard({ clusterId }: { clusterId: string }) {
  const card = useClusterCard(clusterId);
  if (card.isLoading) return <Loading />;
  if (card.error) return <ErrorBox error={card.error} />;
  const d = card.data;
  if (!d) return null;
  const coverage = d.cluster.checks.coverage as
    | { in_train_domain: boolean; knn_distance: number; threshold: number }
    | undefined;
  const byVerdict = new Map<SystemDiagnosis, number>();
  for (const s of d.system_checks) byVerdict.set(s.diagnosis, (byVerdict.get(s.diagnosis) ?? 0) + 1);

  return (
    <div className="space-y-3" data-testid="evidence-card">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">Evidence card · {clusterId}</span>
        <DiagnosisChip diagnosis={d.cluster.diagnosis} />
        <span className="text-xs text-slate-500">
          {d.cluster.diagnostic_run_count} phép kiểm · {d.cluster.diagnostic_rollouts} rollout
        </span>
      </div>

      <div>
        <p className="text-xs font-semibold text-slate-600">Kiểm hệ thống trên {d.system_checks.length} episode thành viên</p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {d.system_checks.length === 0 ? <span className="text-xs text-slate-500">chưa chạy</span> : null}
          {[...byVerdict.entries()].map(([verdict, n]) => (
            <span key={verdict} className="flex items-center gap-1 text-xs">
              <SystemVerdictChip diagnosis={verdict} /> × {n}
            </span>
          ))}
        </div>
        {d.system_checks.some((s) => s.fired_codes.length > 0) ? (
          <ul className="mt-1 text-xs text-slate-600">
            {d.system_checks.filter((s) => s.findings.length > 0).slice(0, 3).map((s) => (
              <li key={s.id}>
                {s.eval_episode_id}: {s.findings.map((f) =>
                  `${String(f.code)} = ${fmt(f.value as number)} (ngưỡng ${fmt(f.threshold as number)})`).join(", ")}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {coverage ? (
        <p className="text-xs text-slate-600">
          Vùng phủ: khoảng cách kNN {fmt(coverage.knn_distance)} so với ngưỡng {fmt(coverage.threshold)} →{" "}
          {coverage.in_train_domain ? "trong miền train" : <b>ngoài miền train</b>}
        </p>
      ) : null}

      {d.diagnostic_runs.length > 0 ? (
        <table className="w-full text-xs">
          <thead className="text-left text-slate-500">
            <tr><th>Bước</th><th>Phép kiểm</th><th className="text-right">Giá trị</th><th className="text-right">Ngưỡng</th><th>Kết quả</th><th className="text-right">Rollout</th></tr>
          </thead>
          <tbody>
            {d.diagnostic_runs.map((r) => (
              <tr key={`${r.step_no}-${r.check_name}`} className="border-t border-slate-200">
                <td>{r.step_no}</td>
                <td>{checkNameLabel[r.check_name] ?? r.check_name}</td>
                <td className="text-right">{fmt(r.value)}</td>
                <td className="text-right">{fmt(r.threshold)}</td>
                <td className={r.outcome === "failed" ? "text-rose-700" : r.outcome === "skipped" ? "text-amber-700" : "text-emerald-700"}>
                  {r.outcome === "passed" ? "đạt" : r.outcome === "failed" ? "không đạt" : "bỏ qua"}
                </td>
                <td className="text-right">{r.rollout_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyState title="Không có rollout chẩn đoán cho cụm này" />
      )}

      <SkippedList items={d.skipped} />

      <div>
        <p className="text-xs font-semibold text-slate-600">Episode đại diện</p>
        <ul className="mt-1 flex flex-wrap gap-2 text-xs">
          {d.representatives.map((r) => (
            <li key={r.eval_episode_id} className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1">
              <span className="font-mono">{r.eval_episode_id}</span>
              <SystemVerdictChip diagnosis={r.system_diagnosis} />
              {r.video_uri?.startsWith("mock://") ? (
                <span className="text-slate-400">video mock</span>
              ) : r.video_uri ? (
                <a className="text-blue-700 underline" href={r.video_uri}>video</a>
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      {d.interventions.length > 0 ? (
        <p className="text-xs text-slate-600">
          Can thiệp đề xuất:{" "}
          {d.interventions.map((iv) =>
            `${interventionKindLabel[iv.kind]} ×${iv.target_quantity} (lợi ích ${fmt(iv.expected_gain_pp)} điểm %, $${fmt(iv.estimated_usd)})`).join("; ")}
        </p>
      ) : (
        <p className="text-xs text-slate-600">Không đề xuất thu dữ liệu cho cụm này.</p>
      )}

      <OverrideForm clusterId={clusterId} current={d.cluster.diagnosis} />
    </div>
  );
}

function OverrideForm({ clusterId, current }: { clusterId: string; current: ClusterDiagnosis | null }) {
  const [open, setOpen] = useState(false);
  const [diagnosis, setDiagnosis] = useState<ClusterDiagnosis>(current ?? "CHUA_RO");
  const [reason, setReason] = useState("");
  const [actionId, setActionId] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const key = useRef<string | null>(null);

  if (actionId) return <ActionStatus actionId={actionId} />;
  if (!open) {
    return (
      <button type="button" className="text-xs text-blue-700 underline" onClick={() => setOpen(true)}>
        Ghi đè chẩn đoán…
      </button>
    );
  }
  return (
    <form
      className="space-y-2 rounded border border-slate-200 bg-white p-2"
      onSubmit={async (e) => {
        e.preventDefault();
        key.current ??= newIdempotencyKey();
        try {
          const r = await apiAction(`/clusters/${clusterId}/diagnosis-override`, { diagnosis, reason }, key.current);
          setActionId(r.action_id);
        } catch (error) {
          setErr(error);
        }
      }}
    >
      <label className="block text-xs">
        Chẩn đoán mới{" "}
        <select className="ml-1 rounded border px-1 py-0.5" value={diagnosis}
          onChange={(e) => setDiagnosis(e.target.value as ClusterDiagnosis)}>
          {clusterDiagnosis.map((d) => <option key={d} value={d}>{clusterDiagnosisLabel[d]}</option>)}
        </select>
      </label>
      <label className="block text-xs">
        Lý do (bắt buộc)
        <textarea className="mt-0.5 block w-full rounded border px-1 py-0.5" rows={2} value={reason}
          onChange={(e) => setReason(e.target.value)} />
      </label>
      {err ? <ErrorBox error={err} /> : null}
      <button type="submit" disabled={!reason.trim()}
        className="rounded bg-slate-800 px-2 py-1 text-xs text-white disabled:opacity-40">
        Gửi ghi đè
      </button>
    </form>
  );
}

// ------------------------------------------------------------------ right

interface Choice {
  quantity: number;
  rejected: boolean;
}

/** Budget recomputed from the engineer's edits, so the three bars move at once. */
export function liveBudget(rec: Recommendation, choices: Record<string, Choice>): BudgetLine[] {
  const proposed = { usd: 0, human_minutes: 0, gpu_hours: 0 };
  for (const iv of rec.interventions) {
    const c = choices[iv.id];
    if (!c || c.rejected) continue;
    const f = c.quantity / iv.target_quantity;
    proposed.usd += iv.estimated_usd * f;
    proposed.human_minutes += iv.estimated_human_minutes * f;
    proposed.gpu_hours += iv.estimated_gpu_hours * f;
  }
  return rec.budget.map((b) => ({
    ...b,
    proposed: proposed[b.resource],
    remaining: b.cap - b.used - proposed[b.resource],
  }));
}

function ProposalColumn({ rec }: { rec: Recommendation }) {
  const initial = useMemo(
    () => Object.fromEntries(rec.interventions.map((iv) => [iv.id, { quantity: iv.target_quantity, rejected: false }])),
    [rec.interventions],
  );
  const [choices, setChoices] = useState<Record<string, Choice>>(initial);
  const [reason, setReason] = useState("");
  const [actionId, setActionId] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const attempt = useRef<{ payload: string; key: string } | null>(null);
  const fixRates = useFixRates();

  const budget = liveBudget(rec, choices);
  const over = budget.some((b) => b.remaining < 0);
  const edited = rec.interventions.some((iv) => {
    const c = choices[iv.id];
    return c !== undefined && (c.rejected || c.quantity !== iv.target_quantity);
  });
  const reviewable = rec.status === "AWAITING_REVIEW" && actionId === null;

  async function submit(kind: "approve" | "edited" | "reject") {
    const items = rec.interventions.map((iv) => {
      const c = choices[iv.id] ?? { quantity: iv.target_quantity, rejected: false };
      if (kind === "reject" || c.rejected) return { intervention_id: iv.id, decision: "REJECT", reason };
      if (kind === "edited" && c.quantity !== iv.target_quantity) {
        return { intervention_id: iv.id, decision: "APPROVE_EDITED", approved_quantity: c.quantity, reason };
      }
      return { intervention_id: iv.id, decision: "APPROVE" };
    });
    const payload = JSON.stringify({ items });
    // Same payload as a failed attempt → same key, so a retry is not a second action (C16).
    if (attempt.current?.payload !== payload) attempt.current = { payload, key: newIdempotencyKey() };
    try {
      setErr(null);
      const r = await apiAction(`/recommendations/${rec.id}/decision`, { items }, attempt.current.key);
      setActionId(r.action_id);
    } catch (error) {
      setErr(error);
    }
  }

  return (
    <Panel title="Đề xuất và ngân sách">
      <div className="space-y-3">
        {budget.map((line) => <BudgetBar key={line.resource} line={line} />)}
        {over ? <p className="text-xs font-semibold text-rose-700">Vượt trần: không duyệt được (BR-07).</p> : null}
      </div>

      <ul className="mt-4 space-y-2" data-testid="interventions">
        {rec.interventions.length === 0 ? <EmptyState title="Không có can thiệp nào được đề xuất" /> : null}
        {rec.interventions.map((iv) => (
          <InterventionItem key={iv.id} iv={iv} threshold={rec.stop_threshold_pp_per_100usd}
            choice={choices[iv.id] ?? { quantity: iv.target_quantity, rejected: false }}
            disabled={!reviewable}
            onChange={(c) => setChoices({ ...choices, [iv.id]: c })} />
        ))}
      </ul>

      <p className="mt-3 text-xs text-slate-500" data-testid="fix-rate-note">
        {fixRates.data && fixRates.data.length > 0
          ? fixRates.data.map((f) => `${interventionKindLabel[f.intervention_kind]}: ${fmt(f.mean_fix_rate)} (${f.event_count} lượt)`).join(" · ")
          : "Tỉ lệ sửa được: prior Beta(1, 1) = 0,5 · chưa lượt nào khép lại"}
      </p>

      {actionId ? (
        <div className="mt-4"><ActionStatus actionId={actionId} /></div>
      ) : reviewable ? (
        <div className="mt-4 space-y-2">
          <textarea className="block w-full rounded border px-2 py-1 text-sm" rows={2}
            placeholder="Lý do (bắt buộc khi sửa hoặc từ chối)" value={reason}
            onChange={(e) => setReason(e.target.value)} />
          {err ? <ErrorBox error={err} /> : null}
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={edited || over} onClick={() => void submit("approve")}
              className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white disabled:opacity-40">Duyệt</button>
            <button type="button" disabled={!edited || over || !reason.trim()} onClick={() => void submit("edited")}
              className="rounded bg-blue-700 px-3 py-1.5 text-sm text-white disabled:opacity-40">Duyệt có sửa</button>
            <button type="button" disabled={!reason.trim()} onClick={() => void submit("reject")}
              className="rounded bg-rose-700 px-3 py-1.5 text-sm text-white disabled:opacity-40">Từ chối</button>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function InterventionItem(props: {
  iv: InterventionRow;
  choice: Choice;
  threshold: number;
  disabled: boolean;
  onChange: (c: Choice) => void;
}) {
  const { iv, choice, threshold, disabled, onChange } = props;
  const below = iv.gain_pp_per_100usd !== null && iv.gain_pp_per_100usd < threshold;
  return (
    <li className={`rounded border p-2 text-sm ${choice.rejected ? "border-slate-200 opacity-50" : "border-slate-300"}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-medium">{interventionKindLabel[iv.kind]}</span>
        <span className="font-mono text-xs text-slate-500">{iv.cluster_id} · {iv.id}</span>
      </div>
      <p className="text-xs text-slate-600">
        g/c = <b className={below ? "text-rose-700" : ""}>{fmt(iv.gain_pp_per_100usd)}</b> điểm %/$100 · lợi ích{" "}
        {fmt(iv.expected_gain_pp)} điểm % · ${fmt(iv.estimated_usd)} · {fmt(iv.estimated_human_minutes, 0)} phút ·{" "}
        {fmt(iv.estimated_gpu_hours)} GPU-giờ
      </p>
      <div className="mt-1 flex items-center gap-2 text-xs">
        <label>
          Số lượng{" "}
          <input type="number" min={1} className="w-16 rounded border px-1 py-0.5" value={choice.quantity}
            disabled={disabled || choice.rejected}
            aria-label={`số lượng ${iv.id}`}
            onChange={(e) => onChange({ ...choice, quantity: Math.max(1, Number(e.target.value) || 1) })} />{" "}
          / {iv.target_quantity} {iv.unit}
        </label>
        <label className="ml-auto">
          <input type="checkbox" checked={choice.rejected} disabled={disabled}
            onChange={(e) => onChange({ ...choice, rejected: e.target.checked })} /> từ chối
        </label>
      </div>
    </li>
  );
}

// ------------------------------------------------------------------ bottom

function RepairTickets({ recommendationId }: { recommendationId: string }) {
  const tickets = useRepairTickets(recommendationId);
  return (
    <Panel title="Phiếu sửa từ cụm lỗi hệ thống">
      {tickets.isLoading ? <Loading /> : tickets.error ? <ErrorBox error={tickets.error} /> :
        (tickets.data ?? []).length === 0 ? <EmptyState title="Không có phiếu sửa" /> : (
          <ul className="space-y-2" data-testid="repair-tickets">
            {(tickets.data ?? []).map((t) => (
              <li key={t.id} className="rounded border border-slate-300 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <DiagnosisChip diagnosis={t.diagnosis} />
                  <span className="font-medium">{t.title}</span>
                  <span className="text-xs text-slate-500">{t.cluster_id} · {t.status}</span>
                  <MockBadge origin={t.origin} />
                </div>
                {t.detail ? <p className="mt-1 text-slate-600">{t.detail}</p> : null}
                {t.rebaseline_required ? (
                  <p className="mt-1 text-xs font-semibold text-amber-800">
                    ⚠ Sửa xong phải đo lại baseline: mọi số đo trước đó không còn dùng được.
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
    </Panel>
  );
}

