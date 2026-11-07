// M2 · Dữ liệu và pipeline 6 tầng (DESIGN.md §6.1).
//
// Each stage carries two labels side by side: the code check (the gate) and
// the agent's reading (advice only, §1 rule 7). QA not run is its own count,
// never folded into pass. Raw egocentric episodes lock every split action (BR-09).
import { useState } from "react";
import {
  useDatasetEpisodes,
  useDatasetReport,
  useDatasets,
  useIntakes,
  useStages,
} from "../api/hooks";
import type { DatasetRow, StageRow, StageRunRow } from "../api/types";
import type { PipelineStage, QaAgentVerdict, QaDecision, StageRunStatus } from "../contracts/enums";
import { EmptyState, ErrorBox, Loading, MockBadge, Panel } from "../ui/components";
import { fmt, fmtTime } from "../ui/labels";

const stageLabel: Record<PipelineStage, string> = {
  INGEST: "Nạp",
  NORMALIZE: "Chuẩn hoá",
  ANNOTATE: "Gán nhãn",
  QA: "Kiểm QA",
  RELEASE: "Release",
  EXPORT: "Xuất",
};

const statusLabel: Record<StageRunStatus, string> = {
  PENDING: "chờ",
  RUNNING: "đang chạy",
  QA_EVALUATING: "đang chấm",
  PASSED: "qua",
  PAUSED_FOR_REVIEW: "dừng chờ duyệt",
  OVERRIDDEN: "kỹ sư cho qua",
  FAILED: "hỏng",
  ABORTED: "huỷ",
};

const statusTone: Record<StageRunStatus, string> = {
  PENDING: "border-slate-300 bg-white text-slate-500",
  RUNNING: "border-sky-400 bg-sky-50 text-sky-800",
  QA_EVALUATING: "border-sky-400 bg-sky-50 text-sky-800",
  PASSED: "border-emerald-400 bg-emerald-50 text-emerald-800",
  PAUSED_FOR_REVIEW: "border-amber-500 bg-amber-50 text-amber-900",
  OVERRIDDEN: "border-violet-400 bg-violet-50 text-violet-800",
  FAILED: "border-rose-400 bg-rose-50 text-rose-800",
  ABORTED: "border-slate-400 bg-slate-100 text-slate-600",
};

const codeTone: Record<QaDecision, string> = {
  pass: "text-emerald-700", flag: "text-amber-700", quarantine: "text-orange-700", reject: "text-rose-700",
};
const agentTone: Record<QaAgentVerdict, string> = {
  PASS: "text-emerald-700", WARNING: "text-amber-700", FAIL: "text-rose-700",
};

export function DataPipeline() {
  const datasets = useDatasets();
  const intakes = useIntakes();
  const [chosen, setChosen] = useState<string | null>(null);
  const items = datasets.data?.items ?? [];
  const current = items.find((d) => d.id === chosen) ?? items[0] ?? null;

  if (datasets.isLoading) return <Loading />;
  if (datasets.error) return <ErrorBox error={datasets.error} />;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Dữ liệu và pipeline 6 tầng</h1>
      <Panel title="Lô dữ liệu">
        {(intakes.data?.items.length ?? 0) > 0 ? (
          <p className="mb-2 rounded bg-sky-50 px-3 py-1.5 text-sm text-sky-800">
            {intakes.data?.items.length} phiếu nạp đang đồng bộ với lõi
          </p>
        ) : null}
        {items.length === 0 ? <EmptyState title="Chưa có lô nào" /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="dataset-list">
              <thead className="text-left text-xs text-slate-500">
                <tr><th className="py-1">Mã lô</th><th>Nguồn</th><th>Loại</th><th>data_class</th><th>Giấy phép</th>
                  <th className="text-right">Episode</th><th>Trạng thái</th><th /></tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id} onClick={() => setChosen(d.id)} aria-selected={d.id === current?.id}
                    className={`cursor-pointer border-t border-slate-100 ${d.id === current?.id ? "bg-sky-50" : "hover:bg-slate-50"}`}>
                    <td className="py-1.5 font-mono text-xs">{d.dataset_code}</td>
                    <td className="text-xs">{d.source_detail ?? d.source_id ?? "—"}</td>
                    <td>{d.source_kind}</td>
                    <td>{d.data_class}</td>
                    <td className="text-xs">{d.license}</td>
                    <td className="text-right tabular-nums">{d.episode_count}</td>
                    <td className="text-xs">{d.status}</td>
                    <td className="space-x-1">
                      {d.has_seeded_faults ? (
                        <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[11px] text-violet-800"
                          title="Bản sao chấm Agent QA/QC; không bao giờ vào release">có lỗi cấy</span>
                      ) : null}
                      <MockBadge origin={d.origin} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {current ? <DatasetDetail dataset={current} /> : null}
    </div>
  );
}

function DatasetDetail({ dataset }: { dataset: DatasetRow }) {
  const pipeline = useStages(dataset.id);
  return (
    <div className="space-y-4">
      <Panel title={`Pipeline · ${dataset.dataset_code}`}>
        {pipeline.isLoading ? <Loading /> : pipeline.error ? <ErrorBox error={pipeline.error} /> : pipeline.data ? (
          <>
            <Stepper stages={pipeline.data.stages} />
            <AttemptHistory attempts={pipeline.data.attempts} />
          </>
        ) : null}
      </Panel>
      <div className="grid gap-4 xl:grid-cols-2">
        <Report datasetId={dataset.id} />
        <Episodes datasetId={dataset.id} />
      </div>
    </div>
  );
}

export function Stepper({ stages }: { stages: StageRow[] }) {
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" data-testid="stepper">
      {stages.map((s) => {
        const status = s.status;
        return (
          <li key={s.stage_number} data-testid={`stage-${s.stage_number}`}
            className={`rounded-md border-2 p-2 text-sm ${status ? statusTone[status] : "border-dashed border-slate-300 text-slate-400"}`}>
            <p className="text-xs opacity-70">Tầng {s.stage_number}{s.attempt_no && s.attempt_no > 1 ? ` · lần ${s.attempt_no}` : ""}</p>
            <p className="font-semibold">{stageLabel[s.stage_code as PipelineStage] ?? s.stage_code}</p>
            <p className="text-xs">{status ? statusLabel[status] : "chưa chạy"}</p>
            {s.qa_code_decision || s.qa_agent_verdict ? (
              <div className="mt-1 space-y-0.5 border-t border-current/20 pt-1 text-[11px]">
                <p>code: <b className={s.qa_code_decision ? codeTone[s.qa_code_decision] : ""}>{s.qa_code_decision ?? "—"}</b></p>
                <p>agent: <b className={s.qa_agent_verdict ? agentTone[s.qa_agent_verdict] : ""}>{s.qa_agent_verdict ?? "—"}</b></p>
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function AttemptHistory({ attempts }: { attempts: StageRunRow[] }) {
  const retried = attempts.some((a) => a.attempt_no > 1);
  return (
    <details className="mt-3 text-sm" open={retried}>
      <summary className="cursor-pointer text-xs text-slate-600">
        Lịch sử attempt ({attempts.length}){retried ? " · có tầng chạy lại; attempt cũ giữ làm lịch sử (BR-02)" : ""}
      </summary>
      <table className="mt-2 w-full text-xs" data-testid="attempt-history">
        <thead className="text-left text-slate-500">
          <tr><th>Tầng</th><th>Lần</th><th>Trạng thái</th><th>code</th><th>agent</th><th>Bắt đầu</th><th>Xong</th><th>Hiện hành</th></tr>
        </thead>
        <tbody>
          {attempts.map((a) => (
            <tr key={a.id} className={`border-t border-slate-100 ${a.is_current ? "" : "text-slate-400"}`}>
              <td>{a.stage_number}</td><td>{a.attempt_no}</td><td>{statusLabel[a.status]}</td>
              <td>{a.qa_code_decision ?? "—"}</td><td>{a.qa_agent_verdict ?? "—"}</td>
              <td>{fmtTime(a.started_at)}</td><td>{fmtTime(a.finished_at)}</td><td>{a.is_current ? "✓" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function Report({ datasetId }: { datasetId: string }) {
  const report = useDatasetReport(datasetId);
  const rows = report.data?.rows ?? [];
  const raw = rows.reduce((a, r) => a + r.egocentric_raw, 0);
  return (
    <Panel title="Báo cáo dataset">
      {report.isLoading ? <Loading /> : report.error ? <ErrorBox error={report.error} /> : rows.length === 0 ? (
        <EmptyState title="Lô chưa có episode" />
      ) : (
        <div className="space-y-3" data-testid="dataset-report">
          {raw > 0 ? (
            <p className="rounded border border-amber-400 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
              🔒 {raw} episode egocentric còn <b>raw</b> (chưa che danh tính): khoá mọi thao tác chia tập và không vào release (BR-09).
            </p>
          ) : null}
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th>Nguồn</th><th className="text-right">Episode</th><th className="text-right">Demo người</th>
                <th className="text-right">pass</th><th className="text-right">flag</th><th className="text-right">cách ly</th>
                <th className="text-right">loại</th><th className="text-right" title="Chưa ai chấm: không phải pass">chưa chấm</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.source_kind}-${r.synthetic_tier}`} className="border-t border-slate-100 tabular-nums">
                  <td>{r.source_kind}{r.synthetic_tier ? ` · ${r.synthetic_tier}` : ""}</td>
                  <td className="text-right">{r.episode_count}</td>
                  <td className="text-right">{r.root_human_count}</td>
                  <td className="text-right text-emerald-700">{r.qa_pass}</td>
                  <td className="text-right text-amber-700">{r.qa_flag}</td>
                  <td className="text-right text-orange-700">{r.qa_quarantine}</td>
                  <td className="text-right text-rose-700">{r.qa_reject}</td>
                  <td className={`text-right ${r.qa_not_run > 0 ? "font-semibold text-slate-700" : "text-slate-400"}`}>{r.qa_not_run}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(report.data?.by_check.length ?? 0) > 0 ? (
            <div>
              <p className="text-xs font-semibold text-slate-600">Theo từng phép kiểm (7 phép bắt buộc)</p>
              <ul className="mt-1 space-y-1 text-xs" data-testid="qa-checks">
                {report.data?.by_check.map((c) => {
                  const total = c.passed + c.failed;
                  return (
                    <li key={c.name} className="flex items-center gap-2">
                      <span className="w-24 font-mono">{c.name}</span>
                      <div className="flex h-2 flex-1 overflow-hidden rounded bg-slate-200">
                        <div className="bg-emerald-500" style={{ width: `${total ? (c.passed / total) * 100 : 0}%` }} />
                        <div className="bg-rose-500" style={{ width: `${total ? (c.failed / total) * 100 : 0}%` }} />
                      </div>
                      <span className={`w-16 text-right ${c.failed ? "text-rose-700" : "text-slate-500"}`}>{c.failed} trượt</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <EmptyState title="QA chưa chạy trên lô này" />
          )}
          <p className="text-xs text-slate-500">
            Độ dài episode trung bình: {fmt(rows[0]?.mean_duration_s ?? null, 1)} s. Phân bố điều kiện, thống kê theo nhóm
            action và kết quả phát lại action chưa có trong artifact của lõi.
          </p>
        </div>
      )}
    </Panel>
  );
}

function Episodes({ datasetId }: { datasetId: string }) {
  const episodes = useDatasetEpisodes(datasetId);
  const [onlyProblems, setOnlyProblems] = useState(true);
  const all = episodes.data?.items ?? [];
  const rows = onlyProblems
    ? all.filter((e) => e.qa_decision !== "pass" || e.deid_status === "raw")
    : all;
  return (
    <Panel title={`Episode (${all.length})`} aside={
      <label className="text-xs text-slate-600">
        <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} /> chỉ episode có vấn đề
      </label>
    }>
      {episodes.isLoading ? <Loading /> : episodes.error ? <ErrorBox error={episodes.error} /> : rows.length === 0 ? (
        <EmptyState title={onlyProblems ? "Mọi episode đã qua QA" : "Lô chưa có episode"} />
      ) : (
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-xs" data-testid="episode-list">
            <thead className="sticky top-0 bg-white text-left text-slate-500">
              <tr><th className="py-1">Episode</th><th>Loại</th><th>Tập</th><th>deid</th><th>QA</th><th>Lý do</th></tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className="border-t border-slate-100">
                  <td className="py-1 font-mono">{e.id}</td>
                  <td>{e.kind}</td>
                  <td>{e.split}</td>
                  <td className={e.deid_status === "raw" ? "font-semibold text-amber-800" : ""}>
                    {e.source_kind === "egocentric" ? e.deid_status : "—"}
                  </td>
                  <td className={e.qa_decision ? codeTone[e.qa_decision] : "text-slate-500"}>{e.qa_decision ?? "chưa chấm"}</td>
                  <td className="text-slate-600">{e.qa_reasons.join("; ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
