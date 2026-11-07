// M4 · Release, minimal version (DESIGN.md §6.2): the releases with hash,
// draft or frozen, parent, merged licence and item count; the lineage tree;
// the split guard; the items with excluded ones and why; the freeze request
// button. The web refuses a freeze request while the guard fails, and the core
// checks again when it freezes. LeRobot export is a core job not run yet.
import { useRef, useState } from "react";
import { apiAction, newIdempotencyKey } from "../api/client";
import { useReleaseItems, useReleases } from "../api/hooks";
import type { GuardCheckName, ReleaseRow, SplitGuard } from "../api/types";
import { ActionStatus, EmptyState, ErrorBox, HashBadge, Loading, MockBadge, Panel } from "../ui/components";
import { fmtTime } from "../ui/labels";

const guardLabel: Record<GuardCheckName, string> = {
  split: "Chỉ episode của tập train",
  benchmark_copy: "Không episode của bản sao chấm (BR-01)",
  raw_egocentric: "Không egocentric chưa che danh tính (BR-09)",
  qa_not_pass: "Không episode QA quarantine hay reject",
  near_duplicate: "Không episode gần trùng (phép kiểm dedup)",
};
const guardTone = { ok: "text-emerald-700", fail: "text-rose-700", not_run: "text-slate-500" } as const;
const guardIcon = { ok: "✓", fail: "✕", not_run: "○" } as const;
const guardWord = { ok: "qua", fail: "không qua", not_run: "chưa kiểm được" } as const;

/** Releases as a forest: roots first, each child under its parent, in load order. */
export function lineage(rows: ReleaseRow[]): Array<{ row: ReleaseRow; depth: number }> {
  const ids = new Set(rows.map((r) => r.release_id));
  const out: Array<{ row: ReleaseRow; depth: number }> = [];
  const walk = (parent: string | null, depth: number) => {
    for (const r of rows) {
      const p = r.parent_release_id && ids.has(r.parent_release_id) ? r.parent_release_id : null;
      if (p === parent) {
        out.push({ row: r, depth });
        walk(r.release_id, depth + 1);
      }
    }
  };
  walk(null, 0);
  return out;
}

function StatusChip({ status }: { status: ReleaseRow["status"] }) {
  return status === "frozen"
    ? <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-white">đóng băng</span>
    : <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">nháp</span>;
}

function Guard({ guard }: { guard: SplitGuard }) {
  return (
    <ul className="space-y-1 text-sm" data-testid="split-guard">
      {guard.checks.map((c) => (
        <li key={c.name} className={guardTone[c.status]} data-testid={`guard-${c.name}`}>
          {guardIcon[c.status]} {guardLabel[c.name]}: {guardWord[c.status]}
          {c.count ? <span className="text-xs"> · {c.count} episode: <span className="font-mono">{c.examples.join(", ")}</span>{c.count > c.examples.length ? "…" : ""}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function FreezeButton({ r }: { r: ReleaseRow }) {
  const key = useRef<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  if (r.status === "frozen") {
    return <p className="text-xs text-slate-500">Đã đóng băng lúc {fmtTime(r.frozen_at)}; đóng băng là bất biến.</p>;
  }
  if (actionId) return <ActionStatus actionId={actionId} />;
  return (
    <div className="space-y-2">
      <button type="button" disabled={!r.guard.ok}
        className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-40"
        title={r.guard.ok ? "gửi yêu cầu đóng băng cho lõi" : "guard chia tập chưa qua"}
        onClick={async () => {
          key.current ??= newIdempotencyKey();
          try {
            setErr(null);
            const res = await apiAction(`/releases/${r.release_id}/freeze-request`, {}, key.current);
            setActionId(res.action_id);
          } catch (error) {
            setErr(error);
          }
        }}>
        Yêu cầu đóng băng
      </button>
      {!r.guard.ok ? (
        <p className="text-xs text-rose-700" data-testid="freeze-blocked">
          Chưa gửi được: guard chia tập chưa qua. Bỏ các episode bị nêu khỏi bản nháp rồi gửi lại.
        </p>
      ) : null}
      {err ? <ErrorBox error={err} /> : null}
    </div>
  );
}

function ReleaseDetail({ r }: { r: ReleaseRow }) {
  const items = useReleaseItems(r.release_id);
  // Items the guard names come first, so they are seen without scrolling 166 rows.
  const rows = [...(items.data?.items ?? [])].sort(
    (a, b) => Number(b.split !== "train" && !b.excluded) - Number(a.split !== "train" && !a.excluded));
  const excluded = rows.filter((i) => i.excluded);
  return (
    <div className="space-y-4" data-testid={`release-${r.release_id}`}>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={`Manifest · ${r.name}`} aside={<StatusChip status={r.status} />}>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs" data-testid="manifest-card">
            <dt className="text-slate-500">Mã</dt><dd className="font-mono">{r.release_id}</dd>
            <dt className="text-slate-500">Hash manifest</dt><dd>{r.manifest_sha256 ? <HashBadge value={r.manifest_sha256} /> : "chưa có (bản nháp chưa đóng băng)"}</dd>
            <dt className="text-slate-500">Kế hoạch chia tập</dt><dd>{r.split_plan_sha256 ? <HashBadge value={r.split_plan_sha256} /> : "—"}</dd>
            <dt className="text-slate-500">Release cha</dt><dd className="font-mono">{r.parent_release_id ?? "—"}</dd>
            <dt className="text-slate-500">Giấy phép gộp</dt><dd>{r.license_summary ?? "—"}</dd>
            <dt className="text-slate-500">Item</dt><dd>{r.item_count} giữ, {r.excluded_count} loại · {Object.entries(r.by_source).map(([k, n]) => `${k} ${n}`).join(", ")}</dd>
            <dt className="text-slate-500">Thí nghiệm dùng</dt><dd className="font-mono">{r.used_by.join(", ") || "chưa có"}</dd>
            <dt className="text-slate-500">Export LeRobot</dt><dd data-testid="export">chưa có: v2.1 / v3 là job của lõi, chưa chạy cho release này</dd>
          </dl>
        </Panel>
        <Panel title="Guard chia tập" aside={r.guard.ok ? <span className="text-xs text-emerald-700">qua</span> : <span className="text-xs text-rose-700">chưa qua</span>}>
          <div className="space-y-3">
            <Guard guard={r.guard} />
            <FreezeButton key={r.release_id} r={r} />
          </div>
        </Panel>
      </div>
      <Panel title={`Item (${rows.length})`}>
        {items.isLoading ? <Loading /> : items.error ? <ErrorBox error={items.error} /> : rows.length === 0 ? (
          <EmptyState title="Release chưa có item nào" />
        ) : (
          <div className="space-y-2">
            {excluded.length ? (
              <ul className="text-xs text-slate-600" data-testid="excluded">
                {excluded.map((i) => <li key={i.episode_id}>loại <span className="font-mono">{i.episode_id}</span>: {i.exclude_reason}</li>)}
              </ul>
            ) : null}
            <div className="max-h-72 overflow-auto">
              <table className="w-full text-xs" data-testid="release-items">
                <thead className="sticky top-0 bg-white text-left text-slate-500">
                  <tr><th className="py-1">Episode</th><th>Lô</th><th>Nguồn</th><th>Tập</th><th>QA</th><th>Trọng số</th></tr>
                </thead>
                <tbody>
                  {rows.map((i) => (
                    <tr key={i.episode_id} className={`border-t border-slate-100 ${i.excluded ? "text-slate-400 line-through" : i.split !== "train" ? "bg-rose-50" : ""}`}>
                      <td className="py-0.5 font-mono">{i.episode_id}</td>
                      <td className="font-mono">{i.dataset_id ?? "—"}</td>
                      <td>{i.source_kind ?? "—"}</td>
                      <td className={i.split !== "train" ? "font-semibold text-rose-700" : ""}>{i.split ?? "—"}</td>
                      <td>{i.qa_decision ?? "chưa QA"}</td>
                      <td className="tabular-nums">{i.sample_weight}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

export function Release() {
  const releases = useReleases();
  const [picked, setPicked] = useState<string | null>(null);
  if (releases.isLoading) return <Loading />;
  if (releases.error) return <ErrorBox error={releases.error} />;
  const rows = releases.data?.items ?? [];
  if (!rows.length) return <EmptyState title="Chưa có release nào" />;
  const current = rows.find((r) => r.release_id === picked) ?? rows.find((r) => r.status === "draft") ?? rows[0]!;
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Release</h1>
        <span className="text-xs text-slate-500">
          {rows.filter((r) => r.status === "frozen").length} đóng băng, {rows.filter((r) => r.status === "draft").length} nháp
        </span>
      </header>
      <Panel title="Cây lineage">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="lineage">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="py-1">Release</th><th>Trạng thái</th><th>Hash</th><th>Item</th><th>Giấy phép</th><th>Guard</th><th>Dùng bởi</th><th /></tr>
            </thead>
            <tbody>
              {lineage(rows).map(({ row: r, depth }) => (
                <tr key={r.release_id} className={`border-t border-slate-100 ${r.release_id === current.release_id ? "bg-slate-100" : "hover:bg-slate-50"}`}>
                  <td className="py-1" style={{ paddingLeft: `${depth * 1.25}rem` }}>
                    {depth ? <span className="mr-1 text-slate-400">└</span> : null}
                    <button type="button" className="text-left underline decoration-dotted" onClick={() => setPicked(r.release_id)}>{r.name}</button>
                    <span className="ml-2 font-mono text-xs text-slate-500">{r.release_id}</span>
                  </td>
                  <td><StatusChip status={r.status} /></td>
                  <td>{r.manifest_sha256 ? <HashBadge value={r.manifest_sha256} /> : <span className="text-xs text-slate-400">—</span>}</td>
                  <td className="text-xs tabular-nums">{r.item_count}{r.excluded_count ? ` (+${r.excluded_count} loại)` : ""}</td>
                  <td className="text-xs">{r.license_summary ?? "—"}</td>
                  <td className={`text-xs ${r.guard.ok ? "text-emerald-700" : "text-rose-700"}`} data-testid={`guard-line-${r.release_id}`}>{r.guard.ok ? "✓ qua" : "✕ chưa qua"}</td>
                  <td className="font-mono text-xs">{r.used_by.join(", ") || "—"}</td>
                  <td><MockBadge origin={r.origin} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <ReleaseDetail key={current.release_id} r={current} />
    </div>
  );
}
