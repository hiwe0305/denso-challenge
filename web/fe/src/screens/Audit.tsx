// M10 · Kiểm toán, minimal version (DESIGN.md §6.2): the action log, the
// decisions, the sync history, and the button that runs one sync pass
// (ADMIN and LEAD only, §7.2). After a pass the screens re-read; nothing is
// updated optimistically (§6.4).
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiPost } from "../api/client";
import { useActions, useDecisions, useSyncRuns } from "../api/hooks";
import { role } from "../api/role";
import type { SyncRunRow } from "../api/types";
import { EmptyState, ErrorBox, Loading, MockBadge, Panel } from "../ui/components";
import { fmtTime, syncStatusLabel } from "../ui/labels";

const statusTone: Record<string, string> = {
  PENDING: "bg-slate-100 text-slate-700",
  EXPORTED: "bg-sky-100 text-sky-800",
  APPLIED: "bg-emerald-100 text-emerald-800",
  REJECTED: "bg-rose-100 text-rose-800",
};

export function Audit() {
  const actions = useActions();
  const decisions = useDecisions();
  const runs = useSyncRuns();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [last, setLast] = useState<SyncRunRow | null>(null);
  const allowed = role() === "ADMIN" || role() === "LEAD";

  async function runSync() {
    setBusy(true);
    setErr(null);
    try {
      setLast(await apiPost<SyncRunRow>("/sync/run"));
      await client.invalidateQueries();
    } catch (error) {
      setErr(error);
    } finally {
      setBusy(false);
    }
  }

  const items = actions.data?.items ?? [];
  const waiting = items.filter((a) => a.sync_status === "PENDING" || a.sync_status === "EXPORTED").length;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Kiểm toán</h1>
        <button type="button" onClick={() => void runSync()} disabled={!allowed || busy}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-40"
          title={allowed ? "export → lõi → import một lượt" : "chỉ ADMIN và LEAD (§7.2)"}>
          {busy ? "Đang đồng bộ…" : "Chạy đồng bộ"}
        </button>
        <span className="text-xs text-slate-500">
          {waiting} hành động chưa áp dụng{allowed ? "" : " · đổi vai sang ADMIN hoặc LEAD để chạy đồng bộ"}
        </span>
        {last ? (
          <span className="text-xs text-slate-600" data-testid="last-sync">
            Lượt {last.id}: xuất {last.exported.length}, áp dụng {last.applied.length}, {last.status}
          </span>
        ) : null}
      </header>
      {err ? <ErrorBox error={err} /> : null}

      <Panel title={`Nhật ký hành động (${items.length})`}>
        {actions.isLoading ? <Loading /> : actions.error ? <ErrorBox error={actions.error} /> : items.length === 0 ? (
          <EmptyState title="Chưa có hành động nào">Duyệt đề xuất ở màn Failure→Data sẽ ghi một hành động vào đây.</EmptyState>
        ) : (
          <table className="w-full text-sm" data-testid="action-log">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="py-1">Hành động</th><th>Loại</th><th>Đích</th><th>Trạng thái</th><th>Tạo</th><th>Xuất</th><th>Áp dụng</th></tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.action_id} className="border-t border-slate-100">
                  <td className="py-1 font-mono text-xs">{a.action_id}</td>
                  <td className="text-xs">{a.action_kind}</td>
                  <td className="text-xs">{a.target_id}</td>
                  <td><span className={`rounded px-1.5 py-0.5 text-xs ${statusTone[a.sync_status] ?? ""}`}>{syncStatusLabel[a.sync_status]}</span></td>
                  <td className="text-xs">{fmtTime(a.created_at)}</td>
                  <td className="text-xs">{fmtTime(a.exported_at)}</td>
                  <td className="text-xs">{fmtTime(a.applied_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Quyết định">
          {decisions.isLoading ? <Loading /> : (decisions.data?.items.length ?? 0) === 0 ? <EmptyState title="Chưa có quyết định" /> : (
            <ul className="space-y-2 text-sm" data-testid="decisions">
              {decisions.data?.items.map((d) => (
                <li key={d.id} className="rounded border border-slate-200 p-2">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs">{d.id}</span>
                    <span className="text-xs text-slate-500">{d.kind}</span>
                    {d.source_action_id ? <span className="rounded bg-emerald-50 px-1 text-xs text-emerald-800">trả lời {d.source_action_id}</span> : null}
                    <MockBadge origin={d.origin} />
                  </p>
                  <p>{d.conclusion ?? "—"}</p>
                  {d.reason ? <p className="text-xs text-slate-500">lý do: {d.reason}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Lịch sử đồng bộ">
          {runs.isLoading ? <Loading /> : (runs.data?.length ?? 0) === 0 ? <EmptyState title="Chưa chạy đồng bộ lần nào" /> : (
            <table className="w-full text-xs" data-testid="sync-runs">
              <thead className="text-left text-slate-500"><tr><th className="py-1">Lượt</th><th>Kết quả</th><th>Xuất</th><th>Áp dụng</th><th>Lõi giả</th><th>Xong</th></tr></thead>
              <tbody>
                {runs.data?.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100">
                    <td className="py-1 font-mono">{r.id}</td><td>{r.status}{r.errors.length ? ` · ${r.errors.length} lỗi` : ""}</td>
                    <td>{r.exported.length}</td><td>{r.applied.length}</td><td>{r.fake_core ? "có" : "không"}</td><td>{fmtTime(r.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}
