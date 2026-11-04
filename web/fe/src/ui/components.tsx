// Shared components of DESIGN.md §6.3.
import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { apiGet, ApiRequestError } from "../api/client";
import type { ActionStatusRow, BudgetLine, SkippedItem } from "../api/types";
import {
  dataBudgetDiagnosis,
  type ClusterDiagnosis,
  type Origin,
  type SystemDiagnosis,
} from "../contracts/enums";
import {
  budgetLabel,
  checkNameLabel,
  clusterDiagnosisLabel,
  fmt,
  syncStatusLabel,
  systemDiagnosisLabel,
} from "./labels";

const chip = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset";

/**
 * Three colours from two flags, never from a group name (v_cluster_board):
 * grey = system fault, blue = data (spends the data budget), amber = record only.
 */
export function DiagnosisChip({ diagnosis }: { diagnosis: ClusterDiagnosis | null }) {
  if (diagnosis === null) {
    return <span className={`${chip} bg-white text-slate-500 ring-slate-300`}>chưa chẩn đoán</span>;
  }
  const tone = diagnosis.startsWith("HE_THONG")
    ? "bg-slate-200 text-slate-800 ring-slate-400"
    : (dataBudgetDiagnosis as readonly string[]).includes(diagnosis)
      ? "bg-blue-100 text-blue-800 ring-blue-300"
      : "bg-amber-100 text-amber-900 ring-amber-300";
  return (
    <span className={`${chip} ${tone}`} data-testid="diagnosis-chip" data-diagnosis={diagnosis}>
      {clusterDiagnosisLabel[diagnosis]}
    </span>
  );
}

/** Episode-level system verdict; `unknown` has its own dashed form (v0.3). */
export function SystemVerdictChip({ diagnosis }: { diagnosis: SystemDiagnosis | null }) {
  if (diagnosis === null) return <span className={`${chip} text-slate-500 ring-slate-300`}>—</span>;
  const tone =
    diagnosis === "clean"
      ? "bg-emerald-50 text-emerald-800 ring-emerald-300"
      : diagnosis === "unknown"
        ? "bg-white text-slate-600 ring-slate-400 ring-dashed border border-dashed border-slate-400"
        : "bg-rose-50 text-rose-800 ring-rose-300";
  return <span className={`${chip} ${tone}`}>{systemDiagnosisLabel[diagnosis]}</span>;
}

export function MockBadge({ origin }: { origin: Origin | null | undefined }) {
  if (origin !== "mock") return null;
  return (
    <span className={`${chip} bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-300`} title="Số bịa, không phải số đo">
      mock
    </span>
  );
}

export function SealedLock({ until }: { until: string | null }) {
  return (
    <span className={`${chip} bg-slate-800 text-white ring-slate-800`} title="Holdout niêm phong">
      🔒 niêm phong{until ? ` tới ${until.slice(0, 10)}` : ""}
    </span>
  );
}

export function HashBadge({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="font-mono text-xs text-slate-600 underline decoration-dotted"
      title={value}
      onClick={() => {
        void navigator.clipboard?.writeText(value);
        setCopied(true);
      }}
    >
      {copied ? "đã chép" : value.slice(0, 8)}
    </button>
  );
}

/** "Chưa chạy", never a 0 (§6.4). */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
      <p className="font-medium text-slate-600">{title}</p>
      {children ? <div className="mt-1">{children}</div> : null}
    </div>
  );
}

function skippedCode(item: SkippedItem): string {
  if (item.source === "algo_step") return `bước ${item.code}`;
  if (item.source === "diagnostic_run") return `kiểm ${checkNameLabel[item.code] ?? item.code}`;
  return item.code;
}

/** Codes that could not be scored, with reasons (BR-12). */
export function SkippedList({ items }: { items: SkippedItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3" data-testid="skipped-list">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
        Không chấm được ({items.length}) · không phải "không có lỗi"
      </p>
      <ul className="mt-1 space-y-0.5 text-sm text-amber-900">
        {items.map((item, i) => (
          <li key={`${item.source}-${item.code}-${item.eval_episode_id}-${i}`}>
            <span className="font-mono">{skippedCode(item)}</span>
            {item.eval_episode_id ? <span className="text-amber-700"> · {item.eval_episode_id}</span> : null}
            {" — "}
            {item.reason}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One ceiling: used, proposed, remaining (BR-07). */
export function BudgetBar({ line }: { line: BudgetLine }) {
  const { name, unit } = budgetLabel[line.resource];
  const pct = (v: number) => (line.cap > 0 ? Math.max(0, Math.min(100, (v / line.cap) * 100)) : 0);
  const over = line.remaining < 0;
  return (
    <div data-testid={`budget-${line.resource}`}>
      <div className="flex justify-between text-xs">
        <span className="font-medium">{name}</span>
        <span className={over ? "font-semibold text-rose-700" : "text-slate-600"}>
          còn {fmt(line.remaining)} / {fmt(line.cap)} {unit}
        </span>
      </div>
      <div className="mt-1 flex h-2.5 overflow-hidden rounded bg-slate-200">
        <div className="bg-slate-600" style={{ width: `${pct(line.used)}%` }} title={`đã dùng ${fmt(line.used)}`} />
        <div
          className={over ? "bg-rose-500" : "bg-blue-500"}
          style={{ width: `${pct(line.proposed)}%` }}
          title={`đề xuất ${fmt(line.proposed)}`}
        />
      </div>
      <div className="mt-0.5 flex gap-3 text-[11px] text-slate-500">
        <span>đã dùng {fmt(line.used)}</span>
        <span>đề xuất {fmt(line.proposed)}</span>
      </div>
    </div>
  );
}

/** Lifecycle label of a recorded action; waits for the core, no optimistic update (§6.4). */
export function ActionStatus({ actionId }: { actionId: string }) {
  const { data } = useQuery({
    queryKey: ["actions", actionId],
    queryFn: () => apiGet<ActionStatusRow>(`/actions/${actionId}`),
    refetchInterval: 5000,
  });
  const status = data?.sync_status ?? "PENDING";
  const tone =
    status === "APPLIED"
      ? "bg-emerald-50 text-emerald-800 ring-emerald-300"
      : status === "REJECTED"
        ? "bg-rose-50 text-rose-800 ring-rose-300"
        : "bg-sky-50 text-sky-800 ring-sky-300";
  return (
    <span className={`${chip} ${tone}`} data-testid="action-status">
      {syncStatusLabel[status]} · {actionId}
    </span>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const message =
    error instanceof ApiRequestError
      ? `${error.body.code}: ${error.body.message}${error.body.hint ? ` (${error.body.hint})` : ""}`
      : error instanceof Error
        ? error.message
        : String(error);
  return (
    <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
      {message}
    </div>
  );
}

export function Loading() {
  return <p className="text-sm text-slate-400">Đang tải…</p>;
}

export function Panel({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
