// The bell (DESIGN.md §6.2). Each notice is derived from data the API already
// serves, so the bell needs no table of its own: a stage paused for review, a
// recommendation awaiting review, a new repair ticket, an action the core
// rejected, an action still exported after 30 minutes (sync late), and an
// action the core just applied.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useActions, useDatasets, useRecommendations, useRepairTicketsAll } from "../api/hooks";
import type { ActionStatusRow, DatasetRow, RecommendationSummary, RepairTicket } from "../api/types";

/** §5.5: EXPORTED longer than this means the core has not picked the action up. */
export const LATE_MINUTES = 30;

export interface Notice {
  key: string;
  tone: "warn" | "info" | "bad" | "good";
  text: string;
  to: string;
}

export function notices(input: {
  recommendations: RecommendationSummary[];
  datasets: DatasetRow[];
  tickets: RepairTicket[];
  actions: ActionStatusRow[];
  now: Date;
}): Notice[] {
  const out: Notice[] = [];
  for (const r of input.recommendations) {
    if (r.status === "AWAITING_REVIEW") {
      out.push({ key: `rec-${r.id}`, tone: "warn", text: `Khuyến nghị vòng ${r.round_no} chờ duyệt`, to: "/failure-to-data" });
    }
  }
  for (const d of input.datasets) {
    if (d.status === "PAUSED_FOR_REVIEW") {
      out.push({ key: `ds-${d.id}`, tone: "warn", text: `Lô ${d.dataset_code} dừng chờ duyệt`, to: "/du-lieu" });
    }
  }
  for (const t of input.tickets) {
    if (t.status === "OPEN") {
      out.push({ key: `rt-${t.id}`, tone: "info", text: `Phiếu sửa mới: ${t.title}`, to: "/failure-to-data" });
    }
  }
  for (const a of input.actions) {
    if (a.sync_status === "REJECTED") {
      out.push({ key: `act-${a.action_id}`, tone: "bad", text: `Lõi từ chối ${a.action_id}: ${a.reject_reason ?? "không rõ lý do"}`, to: "/kiem-toan" });
    } else if (a.sync_status === "EXPORTED" && a.exported_at
      && input.now.getTime() - new Date(a.exported_at).getTime() > LATE_MINUTES * 60_000) {
      out.push({ key: `act-${a.action_id}`, tone: "bad", text: `Đồng bộ trễ: ${a.action_id} đã xuất quá ${LATE_MINUTES} phút`, to: "/kiem-toan" });
    } else if (a.sync_status === "APPLIED") {
      out.push({ key: `act-${a.action_id}`, tone: "good", text: `Lõi đã áp dụng ${a.action_id} (${a.action_kind})`, to: "/kiem-toan" });
    }
  }
  return out;
}

const toneDot: Record<Notice["tone"], string> = {
  warn: "bg-amber-500", info: "bg-sky-500", bad: "bg-rose-600", good: "bg-emerald-600",
};

export function Bell() {
  const [open, setOpen] = useState(false);
  const recommendations = useRecommendations();
  const datasets = useDatasets();
  const tickets = useRepairTicketsAll();
  const actions = useActions();
  const list = notices({
    recommendations: recommendations.data ?? [],
    datasets: datasets.data?.items ?? [],
    tickets: tickets.data ?? [],
    actions: actions.data?.items ?? [],
    now: new Date(),
  });
  const urgent = list.filter((n) => n.tone !== "good").length;
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-label={`thông báo, ${urgent} cần xem`}
        aria-expanded={open} className="relative rounded px-2 py-1 text-slate-600 hover:bg-slate-100">
        🔔
        {urgent > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white"
            data-testid="bell-count">{urgent}</span>
        ) : null}
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-1 w-80 rounded-md border border-slate-200 bg-white p-2 shadow-lg" data-testid="bell-panel">
          {list.length === 0 ? <p className="p-2 text-sm text-slate-500">Không có thông báo</p> : (
            <ul className="space-y-1">
              {list.map((n) => (
                <li key={n.key}>
                  <Link to={n.to} onClick={() => setOpen(false)}
                    className="flex items-start gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-50">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${toneDot[n.tone]}`} />
                    <span>{n.text}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
