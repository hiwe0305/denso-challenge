// M8 · Sổ chi phí và kinh tế (DESIGN.md §6.1).
//
// Estimate and measurement are two entries, the measured one naming the
// estimate it measures (R5); a reversal is shown as such, never hidden (BR-06). Human minutes and GPU hours are two separate constraints,
// never folded into dollars. A branch carries its direct entries plus its
// BR-05 share of the data it trained on. An indicator with no data behind it
// says so instead of showing 0.
import { useMemo, useState } from "react";
import { useBranches, useCostByBranch, useHeCurve, useLedger, useSensitivity } from "../api/hooks";
import type { BranchComparisonRow, CostByBranch, LedgerRow } from "../api/types";
import { EmptyState, ErrorBox, Loading, MockBadge, Panel } from "../ui/components";
import { fmt } from "../ui/labels";
import { n50 } from "./HeCurve";

const TASK = "two_table";
const HE = new Set(["HE", "HE_T"]);

// `LedgerEntry.activity` of the contract; anything else shows its raw name.
const activityLabel: Record<string, string> = {
  data_download: "tải dữ liệu",
  teleop_session: "teleop",
  data_generation: "sinh dữ liệu",
  pipeline: "pipeline",
  qa: "QA",
  agent_qa: "Agent QA/QC",
  train: "train",
  probe: "probe",
  eval: "eval",
  diagnosis: "chẩn đoán",
  holdout: "holdout",
  storage: "lưu trữ",
  review: "review",
  other: "khác",
};

export interface BranchCost {
  branch: string;
  direct_usd: number | null;
  data_usd: number | null;
  human_minutes: number | null;
  gpu_hours: number | null;
  total_usd: number | null;
  human_demos: number | null;
  rate: number | null;
}

const add = (...v: Array<number | null | undefined>): number | null => {
  const present = v.filter((x): x is number => x !== null && x !== undefined);
  return present.length ? present.reduce((a, b) => a + b, 0) : null;
};

/**
 * Per branch of the task: measured direct entries, plus the BR-05 share of the
 * data each of its experiments trained on. HE points are not branches.
 */
export function branchCosts(cost: CostByBranch, rates: BranchComparisonRow[], task: string): BranchCost[] {
  const branches = new Set<string>();
  for (const r of cost.rows) if (r.branch && r.task_id === task) branches.add(r.branch);
  for (const a of cost.data_allocation) if (a.task_id === task && !HE.has(a.hypothesis)) branches.add(a.branch);
  return [...branches].sort().map((branch) => {
    const direct = cost.rows.filter((r) => r.branch === branch && r.task_id === task);
    const alloc = cost.data_allocation.filter((a) => a.branch === branch && a.task_id === task && !HE.has(a.hypothesis));
    const direct_usd = add(...direct.map((r) => r.measured_usd));
    const data_usd = add(...alloc.map((a) => a.allocated_usd));
    return {
      branch,
      direct_usd,
      data_usd,
      human_minutes: add(...direct.map((r) => r.measured_human_minutes), ...alloc.map((a) => a.allocated_human_minutes)),
      gpu_hours: add(...direct.map((r) => r.measured_gpu_hours), ...alloc.map((a) => a.allocated_gpu_hours)),
      total_usd: add(direct_usd, data_usd),
      human_demos: cost.r_demo.find((d) => d.branch === branch && d.task_id === task)?.human_root_episodes ?? null,
      rate: rates.find((r) => r.branch === branch)?.sim_success_rate ?? null,
    };
  });
}

/** Per percentage point of success; null when either side is missing or the rate is 0. */
export const perPoint = (value: number | null, rate: number | null) =>
  value !== null && rate ? value / (rate * 100) : null;

export function Cost() {
  const cost = useCostByBranch();
  const rates = useBranches(TASK);
  const he = useHeCurve();
  const branches = useMemo(
    () => (cost.data && rates.data ? branchCosts(cost.data, rates.data, TASK) : []),
    [cost.data, rates.data],
  );
  if (cost.isLoading || rates.isLoading) return <Loading />;
  if (cost.error) return <ErrorBox error={cost.error} />;

  const pairs = (cost.data?.rows ?? []).reduce((a, r) => a + r.forecast_pairs, 0);
  const forecastError = add(...(cost.data?.rows ?? []).map((r) => r.usd_forecast_error));
  const heVisible = (he.data ?? []).filter((p) => !p.is_sealed);
  const reach = [...new Set(heVisible.map((p) => p.he_variant))]
    .map((v) => ({ variant: v, n: n50(heVisible.filter((p) => p.he_variant === v)) }))
    .filter((x): x is { variant: typeof x.variant; n: number } => x.n !== null)
    .sort((a, b) => a.n - b.n)[0];
  const b = branches.find((x) => x.branch === "B");
  const c = branches.find((x) => x.branch === "C");

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Sổ chi phí và kinh tế</h1>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="cost-indicators">
        <Indicator label="Demo người để đạt 50%" testId="ind-demos"
          value={reach ? `N = ${reach.n}` : null}
          note={reach ? `nhỏ nhất trên đường cong HE, biến thể ${reach.variant}` : "chưa điểm HE nào chạm 50%"} />
        <Indicator label="Phút operator mỗi điểm % · nhánh B" testId="ind-minutes"
          value={b ? fmt(perPoint(b.human_minutes, b.rate), 2) : null}
          note={b?.human_minutes != null ? `${fmt(b.human_minutes, 0)} phút / ${fmt((b.rate ?? 0) * 100, 1)} điểm` : "chưa có phút người gắn nhánh B"} />
        <Indicator label="$ mỗi điểm % của C so với B" testId="ind-c-vs-b"
          value={b && c ? fmt(perPoint(c.total_usd, c.rate) !== null && perPoint(b.total_usd, b.rate) !== null
            ? (perPoint(c.total_usd, c.rate) as number) - (perPoint(b.total_usd, b.rate) as number) : null, 2) : null}
          note={c ? "chênh $/điểm, C trừ B" : "nhánh C chưa có lượt eval dev"} />
        <Indicator label="Sai số dự báo chi phí" testId="ind-forecast"
          value={pairs > 0 ? `${fmt(forecastError, 2)} $` : null}
          note={pairs > 0 ? `trên ${pairs} cặp ước tính → thực đo` : "chưa job nào có cả dòng ước tính lẫn dòng thực đo"} />
      </div>

      <Panel title="Chi phí theo nhánh · thực đo, kèm phần dữ liệu chia theo BR-05">
        {branches.length === 0 ? <EmptyState title="Chưa có bút toán nào gắn nhánh" /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="branch-cost">
              <thead className="text-left text-xs text-slate-500">
                <tr>
                  <th className="py-1">Nhánh</th><th className="text-right">Thành công</th>
                  <th className="text-right">$ trực tiếp</th><th className="text-right">$ dữ liệu (BR-05)</th>
                  <th className="text-right">$ tổng</th><th className="text-right">$ / điểm %</th>
                  <th className="text-right" title="Ràng buộc riêng, không quy ra $">Phút người</th>
                  <th className="text-right" title="Ràng buộc riêng, không quy ra $">GPU-giờ</th>
                  <th className="text-right" title="Episode gốc do người làm trong release của nhánh">r_demo</th>
                </tr>
              </thead>
              <tbody>
                {branches.map((x) => (
                  <tr key={x.branch} className="border-t border-slate-100 tabular-nums">
                    <td className="py-1.5 font-semibold">{x.branch}</td>
                    <td className="text-right">{x.rate === null ? "—" : `${fmt(x.rate * 100, 1)}%`}</td>
                    <td className="text-right">{fmt(x.direct_usd)}</td>
                    <td className="text-right">{fmt(x.data_usd)}</td>
                    <td className="text-right font-semibold">{fmt(x.total_usd)}</td>
                    <td className="text-right">{fmt(perPoint(x.total_usd, x.rate), 2)}</td>
                    <td className="text-right">{fmt(x.human_minutes, 0)}</td>
                    <td className="text-right">{fmt(x.gpu_hours, 2)}</td>
                    <td className="text-right">{x.human_demos ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">
              Phần dữ liệu = chi phí thực đo của lô × (episode nhánh dùng ÷ episode của lô). Một lô dùng chung được chia cho
              mọi nhánh dùng nó, nên cộng cột này qua các nhánh sẽ lớn hơn chi phí dữ liệu thật.
            </p>
          </div>
        )}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <LedgerTable />
        <Sensitivity />
      </div>
    </div>
  );
}

function Indicator({ label, value, note, testId }: { label: string; value: string | null; note: string; testId: string }) {
  return (
    <div className={`rounded-lg border bg-white p-3 ${value === null ? "border-dashed border-slate-300" : "border-slate-200"}`} data-testid={testId}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums ${value === null ? "text-slate-400" : ""}`}>{value ?? "chưa có"}</p>
      <p className="text-xs text-slate-500">{note}</p>
    </div>
  );
}

function LedgerTable() {
  const ledger = useLedger();
  const [branch, setBranch] = useState("all");
  const [activity, setActivity] = useState("all");
  const [resource, setResource] = useState("all");
  const rows = ledger.data?.items ?? [];
  const reversed = new Set(rows.map((r) => r.reverses_entry_id).filter(Boolean));
  const options = (pick: (r: LedgerRow) => string | null) => [...new Set(rows.map(pick).map((v) => v ?? "—"))].sort();
  const shown = rows.filter((r) =>
    (branch === "all" || (r.branch ?? "—") === branch)
    && (activity === "all" || r.activity === activity)
    && (resource === "all" || r.resource_type === resource));
  const select = "rounded border border-slate-300 bg-white px-1.5 py-0.5 text-xs";

  return (
    <Panel title={`Sổ chi phí (${rows.length} bút toán, chỉ thêm)`} aside={
      <div className="flex flex-wrap gap-1">
        <select className={select} aria-label="nhánh" value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="all">mọi nhánh</option>{options((r) => r.branch).map((v) => <option key={v}>{v}</option>)}
        </select>
        <select className={select} aria-label="hoạt động" value={activity} onChange={(e) => setActivity(e.target.value)}>
          <option value="all">mọi hoạt động</option>{options((r) => r.activity).map((v) => <option key={v} value={v}>{activityLabel[v] ?? v}</option>)}
        </select>
        <select className={select} aria-label="nguồn lực" value={resource} onChange={(e) => setResource(e.target.value)}>
          <option value="all">mọi nguồn lực</option>{options((r) => r.resource_type).map((v) => <option key={v}>{v}</option>)}
        </select>
      </div>
    }>
      {ledger.isLoading ? <Loading /> : ledger.error ? <ErrorBox error={ledger.error} /> : (
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full text-xs" data-testid="ledger">
            <thead className="sticky top-0 bg-white text-left text-slate-500">
              <tr>
                <th className="py-1">Bút toán</th><th>Hoạt động</th><th>Gắn với</th><th className="text-right">Lượng</th>
                <th className="text-right">$ ước tính</th><th className="text-right">$ thực đo</th>
                <th className="text-right">phút</th><th className="text-right">GPU-giờ</th><th />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const isReversal = r.entry_kind === "REVERSAL";
                const wasReversed = reversed.has(r.id);
                return (
                  <tr key={r.id} data-testid={`ledger-${r.id}`}
                    className={`border-t border-slate-100 tabular-nums ${isReversal ? "bg-amber-50" : ""} ${wasReversed ? "text-slate-400 line-through" : ""}`}>
                    <td className="py-1 font-mono">{r.id}</td>
                    <td>{activityLabel[r.activity] ?? r.activity}</td>
                    <td className="text-slate-600">
                      {r.branch ? `nhánh ${r.branch}` : r.dataset_id ?? r.intervention_id ?? r.recommendation_id ?? r.run_plan_id ?? "—"}
                    </td>
                    <td className="text-right">{fmt(r.quantity)} {r.unit}</td>
                    <td className="text-right">{r.measure_kind === "estimated" ? fmt(r.usd_amount) : null}</td>
                    <td className="text-right">{r.measure_kind === "measured" ? fmt(r.usd_amount) : null}</td>
                    <td className="text-right">{fmt(r.human_minutes, 0)}</td>
                    <td className="text-right">{fmt(r.gpu_hours, 2)}</td>
                    <td className="no-underline">
                      {r.estimate_entry_id ? <span className="rounded bg-sky-100 px-1 text-[10px] text-sky-900" data-testid={`measures-${r.id}`}>đo {r.estimate_entry_id}</span> : null}
                      {isReversal ? <span className="rounded bg-amber-200 px-1 text-[10px] text-amber-900" title={r.note ?? ""}>đảo {r.reverses_entry_id}</span> : null}
                      {wasReversed ? <span className="rounded bg-slate-200 px-1 text-[10px] text-slate-600">đã bị đảo</span> : null}
                      <MockBadge origin={r.origin} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Sensitivity() {
  const sens = useSensitivity();
  const rows = sens.data ?? [];
  const branches = [...new Set(rows.flatMap((r) => r.by_branch.map((b) => b.branch ?? "chung")))];
  return (
    <Panel title="Độ nhạy theo 4 bảng giá">
      {sens.isLoading ? <Loading /> : sens.error ? <ErrorBox error={sens.error} /> : rows.length === 0 ? (
        <EmptyState title="Chưa có bảng giá" />
      ) : (
        <div className="space-y-2">
          <table className="w-full text-xs" data-testid="sensitivity">
            <thead className="text-left text-slate-500">
              <tr><th className="py-1">Bảng giá</th>{branches.map((b) => <th key={b} className="text-right">{b}</th>)}<th className="text-right">Tổng $</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.price_book_name} className="border-t border-slate-100 tabular-nums">
                  <td className="py-1" title={`GPU ${r.rates.gpu_hours?.usd_per_unit ?? "—"} $/giờ · operator ${r.rates.operator_minutes?.usd_per_unit ?? "—"} $/phút`}>
                    {r.price_book_name}
                  </td>
                  {branches.map((b) => (
                    <td key={b} className="text-right">{fmt(r.by_branch.find((x) => (x.branch ?? "chung") === b)?.usd ?? null)}</td>
                  ))}
                  <td className="text-right font-semibold">{fmt(r.total_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500">
            Mỗi bút toán định giá lại theo tỉ lệ giá của bảng mới so với bảng đã ghi. Cột "chung" là chi phí dữ liệu, chẩn đoán và
            ước tính can thiệp chưa gắn nhánh. {rows[0]?.note ?? ""}
          </p>
        </div>
      )}
    </Panel>
  );
}
