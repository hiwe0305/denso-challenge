// M9 · Kết quả và so sánh nhánh (DESIGN.md §6.1).
//
// Success rate beside cost, per branch, always with its task. Level 1 and
// Level 2 are reported apart against the 70% bar. Only dev results show here;
// a sealed holdout stays locked (BR-10). A curve nobody has run is EmptyState,
// never a line at 0%.
import { useMemo, useState } from "react";
import { useBranches, useE1Curve, useEvalEpisodes, useHeCurve } from "../api/hooks";
import type { BranchComparisonRow, EvalEpisodeRow } from "../api/types";
import { taskId as taskIds, type TaskId } from "../contracts/enums";
import { EmptyState, ErrorBox, Loading, MockBadge, Panel, SealedLock } from "../ui/components";
import { fmt } from "../ui/labels";

/** Target of the demo: Level 1 and Level 2 each at or above 70% (design 27/10). */
export const LEVEL_TARGET = 0.7;

const taskLabel: Record<TaskId, string> = { two_table: "Hai bàn", tray: "Bê khay" };
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${fmt(v * 100, 1)}%`);

export interface LevelRate {
  level: number;
  scored: number;
  success: number;
  rate: number | null;
}

/** Simulator-flag success per episode level, infra failures out of the denominator. */
export function ratesByLevel(episodes: EvalEpisodeRow[]): LevelRate[] {
  const by = new Map<number, LevelRate>();
  for (const e of episodes) {
    if (e.infra_status !== "ok") continue;
    const r = by.get(e.level) ?? { level: e.level, scored: 0, success: 0, rate: null };
    r.scored += 1;
    if (e.sim_success === true) r.success += 1;
    by.set(e.level, r);
  }
  return [...by.values()]
    .sort((a, b) => a.level - b.level)
    .map((r) => ({ ...r, rate: r.scored > 0 ? r.success / r.scored : null }));
}

export function Results() {
  const [task, setTask] = useState<TaskId>("two_table");
  const branches = useBranches(task);
  const rows = branches.data ?? [];
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="mr-2 text-xl font-semibold">Kết quả và so sánh nhánh</h1>
        <div className="flex rounded border border-slate-300 bg-white p-0.5" role="group" aria-label="task">
          {taskIds.map((t) => (
            <button key={t} type="button" onClick={() => setTask(t)}
              className={`rounded px-2 py-1 text-sm ${t === task ? "bg-slate-900 text-white" : "text-slate-600"}`}>
              {taskLabel[t]}
            </button>
          ))}
        </div>
        <span className="rounded bg-sky-100 px-2 py-0.5 text-xs text-sky-800">tập dev</span>
        <span className="flex items-center gap-1 text-xs text-slate-500">
          holdout <SealedLock until={null} /> chỉ hiện sau khi mở niêm phong
        </span>
      </header>

      <Panel title="So sánh nhánh: tỉ lệ thành công cạnh chi phí">
        {branches.isLoading ? <Loading /> : branches.error ? <ErrorBox error={branches.error} /> : rows.length === 0 ? (
          <EmptyState title={`Chưa nhánh nào của task ${task} có lượt eval dev`} />
        ) : <BranchTable rows={rows} />}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title={`Theo mức, so với mốc ${LEVEL_TARGET * 100}%`}>
          {rows.length === 0 ? <EmptyState title="Chưa có lượt eval" /> : (
            <div className="space-y-4" data-testid="level-report">
              {rows.map((r) => <LevelReport key={r.evaluation_id} row={r} />)}
            </div>
          )}
        </Panel>
        <Curves />
      </div>
    </div>
  );
}

function BranchTable({ rows }: { rows: BranchComparisonRow[] }) {
  const best = Math.max(...rows.map((r) => r.sim_success_rate ?? 0));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="branch-table">
        <thead className="text-left text-xs text-slate-500">
          <tr>
            <th className="py-1">Nhánh</th><th>Phương pháp</th><th>Lượt eval</th>
            <th className="w-1/4">Thành công (cờ sim)</th><th className="text-right">Chấm được</th>
            <th className="text-right">$ thực đo</th><th className="text-right">GPU-giờ</th><th className="text-right">Phút người</th>
            <th className="text-right" title="Chi phí thực đo cho mỗi điểm %">$ / điểm %</th><th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const perPoint = r.measured_usd !== null && r.sim_success_rate ? r.measured_usd / (r.sim_success_rate * 100) : null;
            return (
              <tr key={`${r.branch}-${r.method}-${r.level}`} className="border-t border-slate-100">
                <td className="py-1.5 font-semibold">{r.branch}</td>
                <td className="text-xs">{r.method}</td>
                <td className="font-mono text-xs">{r.evaluation_id}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="h-2.5 flex-1 overflow-hidden rounded bg-slate-200">
                      <div className={`h-full ${r.sim_success_rate === best ? "bg-emerald-600" : "bg-slate-500"}`}
                        style={{ width: `${(r.sim_success_rate ?? 0) * 100}%` }} />
                    </div>
                    <span className="w-14 text-right tabular-nums">{pct(r.sim_success_rate)}</span>
                  </div>
                </td>
                <td className="text-right tabular-nums">{r.total_episodes - r.infra_failed_count}/{r.total_episodes}</td>
                <td className="text-right tabular-nums">{fmt(r.measured_usd)}</td>
                <td className="text-right tabular-nums">{fmt(r.measured_gpu_hours)}</td>
                <td className="text-right tabular-nums">{fmt(r.measured_human_minutes, 0)}</td>
                <td className="text-right tabular-nums">{fmt(perPoint, 2)}</td>
                <td><MockBadge origin={r.origin} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">
        Chỉ nhánh có lượt eval dev chưa niêm phong mới hiện. Chi phí là tổng bút toán thực đo của thí nghiệm, kể cả bút toán đảo.
      </p>
    </div>
  );
}

function LevelReport({ row }: { row: BranchComparisonRow }) {
  const episodes = useEvalEpisodes(row.evaluation_id);
  const levels = useMemo(() => ratesByLevel(episodes.data?.items ?? []), [episodes.data]);
  return (
    <div>
      <p className="text-sm font-semibold">Nhánh {row.branch}</p>
      {episodes.isLoading ? <Loading /> : levels.length === 0 ? <EmptyState title="Không có episode để tách theo mức" /> : (
        <ul className="mt-1 space-y-1 text-sm">
          {levels.map((l) => {
            const reported = l.level >= 1;
            const ok = l.rate !== null && l.rate >= LEVEL_TARGET;
            return (
              <li key={l.level} className="flex items-center gap-2" data-testid={`level-${row.branch}-${l.level}`}>
                <span className="w-14 text-xs">mức {l.level}</span>
                <div className="relative h-2.5 flex-1 rounded bg-slate-200">
                  <div className={`h-full rounded ${reported ? (ok ? "bg-emerald-600" : "bg-rose-500") : "bg-slate-400"}`}
                    style={{ width: `${(l.rate ?? 0) * 100}%` }} />
                  <div className="absolute inset-y-[-3px] w-px bg-slate-900" style={{ left: `${LEVEL_TARGET * 100}%` }}
                    title="mốc 70%" />
                </div>
                <span className="w-24 text-right tabular-nums">{pct(l.rate)} <span className="text-xs text-slate-500">({l.success}/{l.scored})</span></span>
                <span className={`w-16 text-xs ${reported ? (ok ? "text-emerald-700" : "text-rose-700") : "text-slate-400"}`}>
                  {reported ? (ok ? "đạt" : "chưa đạt") : "không xét"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Curves() {
  const he = useHeCurve();
  const e1 = useE1Curve();
  return (
    <Panel title="Đường cong E1 và HE">
      <div className="space-y-3" data-testid="curves">
        {e1.isLoading ? <Loading /> : (e1.data?.length ?? 0) === 0 ? (
          <EmptyState title="E1 chưa chạy">Đường cong theo số demo và phương pháp, đánh dấu D*, sẽ hiện khi có lượt eval.</EmptyState>
        ) : <p className="text-sm">{e1.data?.length} điểm E1</p>}
        {he.isLoading ? <Loading /> : he.error ? <ErrorBox error={he.error} /> : (he.data?.length ?? 0) === 0 ? (
          <EmptyState title="HE chưa có điểm nào được đánh giá">
            V-EGO, V-EGO10, V-NOEGO theo N ∈ {"{10, 20, 40, 80}"} sẽ hiện khi checkpoint của các điểm HE có lượt eval.
          </EmptyState>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500"><tr><th>Nhánh</th><th className="text-right">N demo</th><th className="text-right">Thành công</th><th /></tr></thead>
            <tbody>
              {he.data?.map((p, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td>{p.branch} · {p.hypothesis}</td><td className="text-right">{p.n_demos}</td>
                  <td className="text-right">{pct(p.sim_success_rate)}</td><td>{p.is_sealed ? <SealedLock until={null} /> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Panel>
  );
}
