// M1 · Tổng quan (DESIGN.md §6.2): six cards, one per part of the 17/11 demo
// (design 27/10 §11), each with a status, its key number and a link to the
// screen that shows it; a system strip; one summary line. Built only from the
// read endpoints the other screens use, so it cannot say anything they do not.
// A part with nothing behind it says "chưa có", never a zero.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  useActions,
  useClusters,
  useDatasets,
  useDefectScoreboard,
  useEvaluations,
  useHeCurve,
  useRecommendations,
  useReleases,
  useSyncRuns,
} from "../api/hooks";
import { role } from "../api/role";
import { heVariant } from "../contracts/enums";
import { fmt, fmtTime } from "../ui/labels";
import { n50 } from "./HeCurve";

export type PartStatus = "ok" | "partial" | "none" | "loading";

const statusWord: Record<PartStatus, string> = {
  ok: "có số đo", partial: "một phần", none: "chưa có", loading: "đang tải",
};
const statusTone: Record<PartStatus, string> = {
  ok: "bg-emerald-50 text-emerald-800 ring-emerald-300",
  partial: "bg-amber-50 text-amber-900 ring-amber-300",
  none: "bg-slate-100 text-slate-600 ring-slate-300",
  loading: "bg-slate-50 text-slate-400 ring-slate-200",
};
const statusIcon: Record<PartStatus, string> = { ok: "✓", partial: "◐", none: "○", loading: "…" };

/** "4/6 phần có số đo · 1 một phần · 1 chưa có". */
export function summaryLine(statuses: PartStatus[]): string {
  const n = (s: PartStatus) => statuses.filter((x) => x === s).length;
  const parts = [`${n("ok")}/${statuses.length} phần có số đo`];
  if (n("partial")) parts.push(`${n("partial")} một phần`);
  if (n("none")) parts.push(`${n("none")} chưa có`);
  if (n("loading")) parts.push(`${n("loading")} đang tải`);
  return parts.join(" · ");
}

interface CardProps {
  no: number;
  title: string;
  status: PartStatus;
  to: string;
  screen: string;
  children: ReactNode;
}

function Card({ no, title, status, to, screen, children }: CardProps) {
  return (
    <section className="flex flex-col rounded-md border border-slate-200 bg-white p-4" data-testid={`part-${no}`}>
      <header className="mb-2 flex items-start justify-between gap-2">
        <h2 className="text-sm font-semibold"><span className="mr-1 text-slate-400">{no}</span>{title}</h2>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs ring-1 ${statusTone[status]}`} data-testid={`status-${no}`}>
          {statusIcon[status]} {statusWord[status]}
        </span>
      </header>
      <div className="flex-1 text-sm">{children}</div>
      <Link to={to} className="mt-3 self-start text-xs text-sky-800 underline">Mở {screen} →</Link>
    </section>
  );
}

export function Overview() {
  const datasets = useDatasets();
  const releases = useReleases();
  const evaluations = useEvaluations();
  const board = useDefectScoreboard();
  const he = useHeCurve();
  const recs = useRecommendations();
  const rec = recs.data?.[0] ?? null;
  const clusters = useClusters(rec?.id ?? null);
  const runs = useSyncRuns();
  const actions = useActions();

  // 1 · Ψ₀ reproduction: an evaluation of a checkpoint no branch trained.
  const evals = evaluations.data?.items ?? [];
  const repro = evals.filter((e) => e.branch === null && !e.is_sealed);
  const s1: PartStatus = evaluations.isLoading ? "loading" : repro.length ? "ok" : "none";

  // 2 · three kinds of data, the seeded benchmark copy left out.
  const real = (datasets.data?.items ?? []).filter((d) => !d.has_seeded_faults);
  const kinds = (["teleop", "synthetic", "egocentric"] as const).map((k) => ({
    kind: k, episodes: real.filter((d) => d.source_kind === k).reduce((a, d) => a + d.episode_count, 0),
  }));
  const s2: PartStatus = datasets.isLoading ? "loading"
    : kinds.every((k) => k.episodes > 0) ? "ok" : kinds.some((k) => k.episodes > 0) ? "partial" : "none";

  // 3 · pipeline: lots ready for training, frozen releases.
  const ready = real.filter((d) => d.status === "READY_FOR_TRAINING").length;
  const paused = real.filter((d) => d.status === "PAUSED_FOR_REVIEW").length;
  const rel = releases.data?.items ?? [];
  const frozen = rel.filter((r) => r.status === "frozen").length;
  const s3: PartStatus = datasets.isLoading || releases.isLoading ? "loading"
    : ready && frozen ? "ok" : ready || frozen || real.length ? "partial" : "none";

  // 4 · Agent QA/QC on injected defects.
  const b = board.data;
  const s4: PartStatus = board.isLoading ? "loading" : b?.result_sha256 ? "ok" : "none";

  // 5 · HE-1 curve.
  const points = (he.data ?? []).filter((p) => !p.is_sealed && p.sim_success_rate !== null);
  const variants = heVariant.filter((v) => points.some((p) => p.he_variant === v));
  const s5: PartStatus = he.isLoading ? "loading" : variants.length >= 2 ? "ok" : points.length ? "partial" : "none";

  // 6 · one Failure → Data round.
  const cl = clusters.data ?? [];
  const s6: PartStatus = recs.isLoading || (rec !== null && clusters.isLoading) ? "loading"
    : rec === null ? "none" : cl.length ? "ok" : "partial";

  const lastRun = runs.data?.[runs.data.length - 1];
  const pending = (actions.data?.items ?? []).filter((a) => a.sync_status === "PENDING" || a.sync_status === "EXPORTED").length;
  // BR-10: only ADMIN is served sealed evaluations, so anyone else cannot count them.
  const sealed = role() === "ADMIN" ? `${evals.filter((e) => e.is_sealed).length} lượt eval` : "chỉ ADMIN thấy (BR-10)";
  const statuses = [s1, s2, s3, s4, s5, s6];

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Tổng quan · demo 17/11</h1>
        <p className="text-base" data-testid="summary">{summaryLine(statuses)}</p>
      </header>

      <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-md border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600" data-testid="system-strip">
        <span>Đồng bộ gần nhất: {lastRun ? `${lastRun.status} · ${fmtTime(lastRun.finished_at)}` : "chưa chạy lượt nào"}</span>
        <span>Hành động chưa áp dụng: {pending}</span>
        <span data-testid="sealed">Holdout niêm phong: {sealed}</span>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card no={1} title="Tái tạo Ψ₀" status={s1} to="/danh-gia" screen="Đánh giá">
          {repro.length ? (
            <ul>{repro.map((e) => <li key={e.evaluation_id}>{e.evaluation_id}: {fmt((e.sim_success_rate ?? 0) * 100, 1)}% trên {e.total_episodes - e.infra_failed_count} episode</li>)}</ul>
          ) : (
            <p className="text-slate-500">Chưa có lượt eval nào của checkpoint tác giả được nạp vào web; bảng so với 7/5/6 chưa có.</p>
          )}
        </Card>

        <Card no={2} title="Thu dữ liệu ba loại" status={s2} to="/du-lieu" screen="Dữ liệu">
          <ul data-testid="kinds">
            {kinds.map((k) => <li key={k.kind}>{k.kind}: {k.episodes ? `${k.episodes} episode` : "chưa có"}</li>)}
          </ul>
        </Card>

        <Card no={3} title="Pipeline 6 tầng" status={s3} to="/du-lieu" screen="Dữ liệu">
          <p>{ready}/{real.length} lô sẵn sàng train{paused ? ` · ${paused} chờ duyệt` : ""}</p>
          <p>{frozen} release đóng băng, {rel.length - frozen} nháp · <Link to="/release" className="underline">Release</Link></p>
        </Card>

        <Card no={4} title="Agent QA/QC" status={s4} to="/agent-qa" screen="Agent QA/QC">
          {b?.result_sha256 ? (
            <p data-testid="qa-line">Trên lỗi cấy: code bắt {b.totals.by_code}/{b.totals.injected}, agent thêm {b.totals.agent_adds}.</p>
          ) : <p className="text-slate-500">Chưa có lần chấm nào của DA-31.</p>}
        </Card>

        <Card no={5} title="HE-1" status={s5} to="/ket-qua" screen="Kết quả">
          {variants.length ? (
            <ul data-testid="he-line">
              {variants.map((v) => {
                const reach = n50(points.filter((p) => p.he_variant === v));
                return <li key={v}>{v}: N₅₀ = {reach ?? "chưa tới 50%"}</li>;
              })}
            </ul>
          ) : <p className="text-slate-500">Chưa có điểm HE nào.</p>}
        </Card>

        <Card no={6} title="Một vòng Failure → Data" status={s6} to="/failure-to-data" screen="Failure→Data">
          {rec ? (
            <div data-testid="fd-line">
              <p>Lượt {rec.round_no} ({rec.task_id}), {rec.status}: {cl.length} cụm lỗi.</p>
              <p>{cl.filter((c) => c.consumes_data_budget).length} cụm cần thu dữ liệu; {cl.filter((c) => !c.consumes_data_budget).length} cụm không tốn ngân sách dữ liệu ({cl.filter((c) => c.is_system_fault).length} lỗi hệ thống).</p>
            </div>
          ) : <p className="text-slate-500">Chưa có lượt Failure → Data nào.</p>}
        </Card>
      </div>
    </div>
  );
}
