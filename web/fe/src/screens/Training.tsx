// M5 · Huấn luyện, minimal version (DESIGN.md §6.2): the experiments, the
// RunPlan card each is pinned to, train and val loss (one y axis; LR on its
// own chart), loss per action group, the twelve train-diagnosis codes with
// the skipped ones and why, the probes against the parent checkpoint.
//
// Colours: categorical slots 1–2 of the dataviz reference palette (the same
// two HeCurve validated on white), train = slot 1, val = slot 2, fixed per
// series. Both lines are direct-labelled and the table under the chart holds
// the same numbers, so identity never rests on colour alone.
import { useState } from "react";
import {
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  useCheckpoints,
  useExperiments,
  useMetrics,
  useProbes,
  useTrainDiagnoses,
} from "../api/hooks";
import type {
  DiagnosisSummary,
  ExperimentRow,
  ProbeRow,
  TrainCodeStatus,
  TrainDiagnosisView,
  TrainingMetricRow,
} from "../api/types";
import { EmptyState, ErrorBox, HashBadge, Loading, MockBadge, Panel } from "../ui/components";
import { fmt, fmtTime } from "../ui/labels";
import { DraftPanel } from "./DraftPanel";

const SPLIT_COLOR = { train: "#2a78d6", val: "#eb6834" } as const;
const SPLIT_LABEL = { train: "train", val: "val" } as const;
const INK = { muted: "#898781", axis: "#c9c8c2", grid: "#e7e6e2", label: "#52514e" };

const statusLabel: Record<TrainCodeStatus, string> = {
  fired: "nổ",
  clean: "không thấy lỗi",
  skipped: "bỏ qua",
  partial: "bỏ qua một phần",
  not_run: "chưa chạy",
};
const statusTone: Record<TrainCodeStatus, string> = {
  fired: "bg-rose-100 text-rose-800",
  clean: "bg-emerald-50 text-emerald-800",
  skipped: "bg-amber-100 text-amber-900",
  partial: "bg-amber-50 text-amber-900",
  not_run: "bg-slate-100 text-slate-600",
};
const statusIcon: Record<TrainCodeStatus, string> = {
  fired: "✕", clean: "✓", skipped: "–", partial: "◐", not_run: "○",
};

/** One line under an experiment: "1 nổ · 1 bỏ qua", or "chưa chạy chẩn đoán", never green by default. */
export function diagnosisLine(s: DiagnosisSummary | null): string {
  if (!s || !s.ran) return "chưa chạy chẩn đoán";
  const parts = [
    s.fired ? `${s.fired} nổ` : null,
    s.skipped ? `${s.skipped} bỏ qua` : null,
    s.partial ? `${s.partial} bỏ qua một phần` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "12 mã không thấy lỗi";
}

/** Rows of the loss chart: one per step, train and val side by side (null where a split has no row). */
export function lossSeries(rows: TrainingMetricRow[]) {
  const steps = [...new Set(rows.map((r) => r.step))].sort((a, b) => a - b);
  return steps.map((step) => ({
    step,
    train: rows.find((r) => r.step === step && r.split === "train")?.loss ?? null,
    val: rows.find((r) => r.step === step && r.split === "val")?.loss ?? null,
    lr: rows.find((r) => r.step === step && r.split === "train")?.lr ?? null,
  }));
}

function LossChart({ rows, marks }: { rows: TrainingMetricRow[]; marks: Array<{ code: string; step: number }> }) {
  const data = lossSeries(rows);
  // Each line is labelled at its own last point: val is logged less often than
  // train, so the last step of the chart may carry no val value.
  const lastOf = (split: "train" | "val") => [...data].reverse().find((d) => d[split] !== null)?.step;
  const nonFinite = rows.filter((r) => r.loss_nonfinite !== null);
  return (
    <div className="space-y-2" data-testid="loss-chart">
      <div className="h-64" role="img" aria-label="Loss train và val theo step">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 24, right: 56, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={INK.grid} vertical={false} />
            <XAxis dataKey="step" type="number" domain={["dataMin", "dataMax"]} tick={{ fill: INK.muted, fontSize: 12 }} stroke={INK.axis}
              label={{ value: "step", position: "insideBottomRight", offset: -4, fill: INK.muted, fontSize: 11 }} />
            <YAxis width={44} tick={{ fill: INK.muted, fontSize: 12 }} stroke={INK.axis} />
            {marks.map((m) => (
              <ReferenceLine key={`${m.code}-${m.step}`} x={m.step} stroke={INK.muted} strokeDasharray="4 4"
                label={{ value: m.code, position: "top", fill: INK.label, fontSize: 11 }} />
            ))}
            <Tooltip formatter={(value, name) => [value === null ? "—" : fmt(Number(value), 4), String(name)]}
              labelFormatter={(step) => `step ${step}`} />
            <Legend />
            {(["train", "val"] as const).map((split) => (
              <Line key={split} type="monotone" dataKey={split} name={SPLIT_LABEL[split]} stroke={SPLIT_COLOR[split]}
                strokeWidth={2} dot={false} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls>
                <LabelList dataKey={split} content={({ x, y, index }) =>
                  data[Number(index)]?.step === lastOf(split) ? (
                    <text x={Number(x) + 8} y={Number(y) + 4} fontSize={12} fill={INK.label}>{SPLIT_LABEL[split]}</text>
                  ) : null} />
              </Line>
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {nonFinite.length ? (
        <p className="text-xs text-rose-700" data-testid="loss-nonfinite">
          {nonFinite.length} dòng loss không hữu hạn (không vẽ): {nonFinite.slice(0, 3).map((r) => `step ${r.step} ${r.split} = ${r.loss_nonfinite}`).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

function LrChart({ rows }: { rows: TrainingMetricRow[] }) {
  const data = lossSeries(rows).filter((d) => d.lr !== null);
  if (!data.length) return null;
  return (
    <div className="h-28" role="img" aria-label="Learning rate theo step" data-testid="lr-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 56, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={INK.grid} vertical={false} />
          <XAxis dataKey="step" type="number" domain={["dataMin", "dataMax"]} tick={{ fill: INK.muted, fontSize: 11 }} stroke={INK.axis} />
          <YAxis width={56} tick={{ fill: INK.muted, fontSize: 11 }} stroke={INK.axis} tickFormatter={(v: number) => v.toExponential(0)} />
          <Tooltip formatter={(value) => [Number(value).toExponential(2), "LR"]} labelFormatter={(step) => `step ${step}`} />
          <Line type="monotone" dataKey="lr" name="LR" stroke={INK.label} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function GroupLoss({ rows }: { rows: TrainingMetricRow[] }) {
  const val = rows.filter((r) => r.split === "val" && Object.keys(r.loss_by_group).length > 0);
  if (!val.length) return <EmptyState title="Chưa có loss theo nhóm action">Chỉ dòng val của metrics.jsonl mang loss_by_group.</EmptyState>;
  const first = val[0]!;
  const last = val[val.length - 1]!;
  const groups = Object.keys(last.loss_by_group).sort();
  return (
    <table className="w-full text-xs" data-testid="group-loss">
      <thead className="text-left text-slate-500">
        <tr><th className="py-1">Nhóm action</th><th className="text-right">val step {first.step}</th><th className="text-right">val step {last.step}</th></tr>
      </thead>
      <tbody>
        {groups.map((g) => (
          <tr key={g} className="border-t border-slate-100">
            <td className="py-1 font-mono">{g}</td>
            <td className="text-right tabular-nums">{fmt(first.loss_by_group[g] ?? null, 4)}</td>
            <td className="text-right tabular-nums">{fmt(last.loss_by_group[g] ?? null, 4)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Resources({ rows }: { rows: TrainingMetricRow[] }) {
  const train = rows.filter((r) => r.split === "train");
  const last = train[train.length - 1];
  const vram = train.map((r) => r.vram_gb).filter((v): v is number => v !== null);
  const tput = train.map((r) => r.throughput).filter((v): v is number => v !== null);
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4" data-testid="resources">
      <dt className="text-slate-500">VRAM tối đa</dt><dd className="tabular-nums">{vram.length ? `${fmt(Math.max(...vram), 1)} GB` : "chưa đo"}</dd>
      <dt className="text-slate-500">Thông lượng</dt><dd className="tabular-nums">{tput.length ? `${fmt(tput[tput.length - 1] ?? null, 1)} mẫu/s` : "chưa đo"}</dd>
      <dt className="text-slate-500">Grad norm action (cuối)</dt><dd className="tabular-nums">{fmt(last?.grad_norm_action ?? null, 3)}</dd>
      <dt className="text-slate-500">Thời gian train</dt><dd className="tabular-nums">{last ? `${fmt(last.wall_time_s / 3600, 2)} giờ` : "—"}</dd>
    </dl>
  );
}

function DiagnosisTable({ view }: { view: TrainDiagnosisView }) {
  return (
    <div className="space-y-2">
      {!view.summary.ran ? (
        <p className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600" data-testid="diag-not-run">
          Chưa có lần chẩn đoán nào cho thí nghiệm này (<span className="font-mono">fw eval diag-train</span>). Mười hai mã dưới là
          <b> chưa chạy</b>, không phải không có lỗi.
        </p>
      ) : (
        <p className="text-xs text-slate-500">
          Cấu hình {view.config_sha256.map((h) => <HashBadge key={h} value={h} />)} · checkpoint {view.checkpoint_ids.join(", ")}
        </p>
      )}
      <table className="w-full text-sm" data-testid="diag-table">
        <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Mã</th><th>Họ</th><th>Kết quả</th><th>Chi tiết</th></tr></thead>
        <tbody>
          {view.codes.map((c) => (
            <tr key={c.code} className="border-t border-slate-100" data-testid={`diag-${c.code}`}>
              <td className="py-1 font-mono text-xs">{c.code}</td>
              <td className="text-xs text-slate-500">{c.family}</td>
              <td><span className={`rounded px-1.5 py-0.5 text-xs ${statusTone[c.status]}`}>{statusIcon[c.status]} {statusLabel[c.status]}</span></td>
              <td className="text-xs">
                {c.findings.map((f, i) => (
                  <span key={i} className="mr-2">
                    từ step {f.start_step}{f.group ? ` · nhóm ${f.group}` : ""}{f.dim !== null ? ` · chiều ${f.dim}` : ""}
                    {" · "}giá trị {f.value_nonfinite ?? fmt(f.value, 3)}{f.threshold !== null ? ` (ngưỡng ${fmt(f.threshold, 3)})` : ""}
                    {f.stop_job ? " · dừng job" : ""}
                  </span>
                ))}
                {c.skipped.map((k) => <span key={k.code} className="text-amber-900">{k.code !== c.code ? `${k.code}: ` : ""}{k.reason}</span>)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function probeSummary(p: ProbeRow): string {
  const body = p.payload;
  const pairs = (o: unknown) => Object.entries((o ?? {}) as Record<string, number>).map(([k, v]) => `${k} ${fmt(v, 3)}`).join(", ");
  if (p.probe === "P1") return `độ chính xác theo loại câu hỏi: ${pairs(body.accuracy_by_question_type)}`;
  if (p.probe === "P3") return `sai số theo nhóm: ${pairs(body.error_by_group)}`;
  if (p.probe === "P4") return `so với checkpoint cha ${p.parent_checkpoint_id ?? "—"}`;
  return Object.keys(body).filter((k) => !["probe", "checkpoint_id", "dataset_sha256"].includes(k)).join(", ");
}

function Probes({ probes }: { probes: ProbeRow[] }) {
  if (!probes.length) return <EmptyState title="Chưa chạy probe nào">P1–P4 chạy trên checkpoint sau khi train xong.</EmptyState>;
  return (
    <ul className="space-y-1 text-xs" data-testid="probes">
      {probes.map((p, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-2">
          <span className="font-mono font-semibold">{p.probe}</span>
          <span className="font-mono text-slate-500">{p.checkpoint_id}</span>
          <span>{probeSummary(p)}</span>
        </li>
      ))}
    </ul>
  );
}

function ExperimentDetail({ x }: { x: ExperimentRow }) {
  const metrics = useMetrics(x.experiment_id);
  const diag = useTrainDiagnoses(x.experiment_id);
  const probes = useProbes(x.experiment_id);
  const ckpts = useCheckpoints(x.experiment_id);
  const marks = (diag.data?.codes ?? []).flatMap((c) => c.findings.map((f) => ({ code: c.code, step: f.start_step })));
  const rows = metrics.data ?? [];
  return (
    <div className="space-y-4" data-testid={`experiment-${x.experiment_id}`}>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="RunPlan">
          {x.run_plan ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs" data-testid="runplan-card">
              <dt className="text-slate-500">Mã</dt><dd className="font-mono">{x.run_plan.id}</dd>
              <dt className="text-slate-500">Mục đích</dt><dd>{x.run_plan.purpose}</dd>
              <dt className="text-slate-500">Hash cấu hình</dt><dd><HashBadge value={x.run_plan.config_sha256} /></dd>
              <dt className="text-slate-500">Đóng băng</dt><dd>{fmtTime(x.run_plan.frozen_at)}</dd>
              <dt className="text-slate-500">Dải seed eval</dt><dd className="font-mono">{x.run_plan.seed_range ?? "—"}</dd>
              <dt className="text-slate-500">Lock</dt><dd className="break-all font-mono">{x.run_plan.lock_uri}</dd>
            </dl>
          ) : <EmptyState title="Thí nghiệm không trỏ RunPlan nào" />}
        </Panel>
        <Panel title="Dữ liệu và checkpoint">
          <ul className="space-y-1 text-xs">
            {x.releases.map((r) => (
              <li key={r.release_id}>release <span className="font-mono">{r.release_id}</span> · trọng số {fmt(r.mix_weight, 2)} · {r.episodes_used ?? "—"} episode</li>
            ))}
            {(ckpts.data ?? []).map((c) => (
              <li key={c.checkpoint_id} data-testid="checkpoint">
                checkpoint <span className="font-mono">{c.checkpoint_id}</span> · step {c.step ?? "—"}
                {c.is_best ? " · tốt nhất" : ""}{c.parent_checkpoint_id ? ` · cha ${c.parent_checkpoint_id}` : ""} · <HashBadge value={c.weights_sha256} />
              </li>
            ))}
            <li className="text-slate-500">seed train {x.train_seed ?? "—"} · {Object.entries(x.hyperparams).map(([k, v]) => `${k}=${String(v)}`).join(", ") || "không có siêu tham số"}</li>
          </ul>
        </Panel>
      </div>

      <Panel title="Loss train và val">
        {metrics.isLoading ? <Loading /> : metrics.error ? <ErrorBox error={metrics.error} /> : rows.length === 0 ? (
          <EmptyState title="Chưa có telemetry">Thí nghiệm này chưa có dòng nào trong metrics.jsonl được nạp; không vẽ đường trống.</EmptyState>
        ) : (
          <div className="space-y-3">
            <LossChart rows={rows} marks={marks} />
            <LrChart rows={rows} />
            <Resources rows={rows} />
            <GroupLoss rows={rows} />
          </div>
        )}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
        <Panel title="Chẩn đoán train · T1–T8, O1–O4">
          {diag.isLoading ? <Loading /> : diag.error ? <ErrorBox error={diag.error} /> : diag.data ? <DiagnosisTable view={diag.data} /> : null}
        </Panel>
        <Panel title="Probe P1–P4">
          {probes.isLoading ? <Loading /> : <Probes probes={probes.data ?? []} />}
        </Panel>
      </div>
    </div>
  );
}

export function Training() {
  const experiments = useExperiments();
  const items = experiments.data?.items ?? [];
  const [picked, setPicked] = useState<string | null>(null);
  if (experiments.isLoading) return <Loading />;
  if (experiments.error) return <ErrorBox error={experiments.error} />;
  if (!items.length) return <EmptyState title="Chưa có thí nghiệm nào" />;
  const current = items.find((x) => x.experiment_id === picked) ?? items.find((x) => x.metric_rows > 0) ?? items[0]!;
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Huấn luyện</h1>
        <span className="text-xs text-slate-500">{items.length} thí nghiệm · bản nháp mới ở cuối trang</span>
      </header>
      <Panel title="Thí nghiệm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="experiments">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="py-1">Thí nghiệm</th><th>Nhánh</th><th>Giả thuyết</th><th>Trạng thái</th><th>RunPlan</th><th>Telemetry</th><th>Chẩn đoán</th><th /></tr>
            </thead>
            <tbody>
              {items.map((x) => (
                <tr key={x.experiment_id} onClick={() => setPicked(x.experiment_id)}
                  className={`cursor-pointer border-t border-slate-100 ${x.experiment_id === current.experiment_id ? "bg-slate-100" : "hover:bg-slate-50"}`}>
                  <td className="py-1 font-mono text-xs">
                    <button type="button" className="text-left underline decoration-dotted" onClick={() => setPicked(x.experiment_id)}>{x.experiment_id}</button>
                  </td>
                  <td className="text-xs">{x.branch}</td>
                  <td className="text-xs">{x.hypothesis ?? "—"}</td>
                  <td className="text-xs">{x.status}</td>
                  <td className="font-mono text-xs">{x.run_plan?.id ?? "—"}</td>
                  <td className="text-xs tabular-nums">{x.metric_rows ? `${x.metric_rows} dòng` : "chưa có"}</td>
                  <td className={`text-xs ${x.diagnosis?.fired ? "text-rose-700" : ""}`} data-testid={`diag-line-${x.experiment_id}`}>{diagnosisLine(x.diagnosis)}</td>
                  <td><MockBadge origin={x.origin} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <ExperimentDetail key={current.experiment_id} x={current} />
      <DraftPanel />
    </div>
  );
}
