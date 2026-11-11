// M6 · Đánh giá và bảng lỗi (DESIGN.md §6.1).
//
// Task first, then the evaluation; the funnel has exactly the task's steps.
// The simulator flag is the headline (ADR-14), the scorer sits beside it and
// a gap above 5 points is a warning. Infra failures leave the denominator.
// A failure family nobody produced is "chưa chạy", never "không lỗi" (BR-12).
import { useFocus } from "../api/focus";
import { useMemo, useState } from "react";
import {
  useEvalEpisodes,
  useEvaluations,
  useFailures,
  useFunnel,
  useSystemChecks,
} from "../api/hooks";
import type {
  EvalEpisodeRow,
  EvaluationSummary,
  FailureFamily,
  FailureFamilyBlock,
  FunnelRow,
  SystemCheckRow,
} from "../api/types";
import { taskId as taskIds, type TaskId } from "../contracts/enums";
import {
  EmptyState,
  ErrorBox,
  Loading,
  MockBadge,
  Panel,
  SealedLock,
  SkippedList,
  SystemVerdictChip,
} from "../ui/components";
import { fmt, rolloutTimingLabel } from "../ui/labels";

/** Scorer disagreeing with the simulator by more than this means the scorer is broken. */
export const SCORER_GAP_WARNING = 0.05;

const taskLabel: Record<TaskId, string> = { two_table: "Hai bàn (6 bước)", tray: "Bê khay (7 bước)" };

const familyLabel: Record<FailureFamily, string> = {
  "F-DATA": "Dữ liệu",
  "F-TRAIN": "Huấn luyện",
  "F-OFF": "Offline",
  "F-CL": "Closed-loop",
  "F-SYS": "Hệ thống",
};

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${fmt(v * 100, 1)}%`);

export interface FunnelStep {
  step_no: number;
  reached: number;
  pass: number;
  fail: number;
  unknown: number;
  /** pass / every scored episode: share that got through this step. */
  absolute: number | null;
  /** pass / episodes that reached the step; unknown stays out of both. */
  conditional: number | null;
}

/**
 * Sums v_eval_funnel rows over the chosen levels. `unknown` is its own column:
 * a missing signal is neither a pass nor a fail (spec §5.1).
 */
export function funnelSteps(rows: FunnelRow[], levels: number[] | null): FunnelStep[] {
  const picked = rows.filter((r) => levels === null || levels.includes(r.episode_level));
  const byStep = new Map<number, FunnelStep>();
  for (const r of picked) {
    const s = byStep.get(r.step_no) ?? {
      step_no: r.step_no, reached: 0, pass: 0, fail: 0, unknown: 0, absolute: null, conditional: null,
    };
    s.reached += r.step_pass + r.step_fail + r.step_unknown;
    s.pass += r.step_pass;
    s.fail += r.step_fail;
    s.unknown += r.step_unknown;
    byStep.set(r.step_no, s);
  }
  const total = picked.filter((r) => r.step_no === 1).reduce((a, r) => a + r.reached_or_beyond, 0);
  return [...byStep.values()]
    .sort((a, b) => a.step_no - b.step_no)
    .map((s) => ({
      ...s,
      absolute: total > 0 ? s.pass / total : null,
      conditional: s.pass + s.fail > 0 ? s.pass / (s.pass + s.fail) : null,
    }));
}

export function Evaluation() {
  const list = useEvaluations();
  const [task, setTask] = useState<TaskId>("two_table");
  const [renderer, setRenderer] = useState<string>("all");
  const [mode, setMode] = useState<string>("all");
  const [split, setSplit] = useState<string>("all");
  const [chosen, setChosen] = useState<string | null>(null);
  const [level, setLevel] = useState<number | null>(null);

  const evaluations = useMemo(
    () => (list.data?.items ?? []).filter((e) =>
      e.task_id === task
      && (renderer === "all" || e.renderer === renderer)
      && (mode === "all" || e.eval_mode === mode)
      && (split === "all" || e.split === split)),
    [list.data, task, renderer, mode, split],
  );
  const current = evaluations.find((e) => e.evaluation_id === chosen) ?? evaluations[0] ?? null;
  useFocus({ evaluation_id: current?.evaluation_id ?? null });

  if (list.isLoading) return <Loading />;
  if (list.error) return <ErrorBox error={list.error} />;

  const select = "rounded border border-slate-300 bg-white px-2 py-1 text-sm";
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="mr-2 text-xl font-semibold">Đánh giá</h1>
        <div className="flex rounded border border-slate-300 bg-white p-0.5" role="group" aria-label="task">
          {taskIds.map((t) => (
            <button key={t} type="button" onClick={() => { setTask(t); setChosen(null); }}
              className={`rounded px-2 py-1 text-sm ${t === task ? "bg-slate-900 text-white" : "text-slate-600"}`}>
              {taskLabel[t]}
            </button>
          ))}
        </div>
        <select className={select} aria-label="renderer" value={renderer} onChange={(e) => setRenderer(e.target.value)}>
          <option value="all">mọi renderer</option><option value="mujoco">mujoco</option><option value="isaac">isaac</option>
        </select>
        <select className={select} aria-label="chế độ" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="all">đồng bộ và bất đồng bộ</option><option value="sync">đồng bộ</option><option value="async">bất đồng bộ</option>
        </select>
        <select className={select} aria-label="tập" value={split} onChange={(e) => setSplit(e.target.value)}>
          <option value="all">dev và holdout</option><option value="dev">dev</option><option value="holdout">holdout</option>
        </select>
      </header>

      {evaluations.length === 0 ? (
        <EmptyState title={`Chưa có lượt eval nào cho task ${task} với bộ lọc này`}>
          Holdout còn niêm phong không hiện với vai của bạn (BR-10).
        </EmptyState>
      ) : (
        <>
          <label className="flex flex-wrap items-center gap-2 text-sm">
            Lượt eval
            <select className={`${select} min-w-[22rem]`} data-testid="evaluation-picker" aria-label="lượt eval"
              value={current?.evaluation_id ?? ""} onChange={(e) => setChosen(e.target.value)}>
              {evaluations.map((e) => (
                <option key={e.evaluation_id} value={e.evaluation_id}>
                  {e.evaluation_id} · nhánh {e.branch ?? "—"} · {e.split} · {e.renderer} · {e.eval_mode}
                  {e.is_sealed ? " · niêm phong" : ""}
                </option>
              ))}
            </select>
            <span className="text-xs text-slate-500">{evaluations.length} lượt</span>
          </label>
          {current ? <EvaluationDetail ev={current} level={level} setLevel={setLevel} /> : null}
        </>
      )}
    </div>
  );
}

function EvaluationDetail({ ev, level, setLevel }: {
  ev: EvaluationSummary;
  level: number | null;
  setLevel: (l: number | null) => void;
}) {
  const funnel = useFunnel(ev.evaluation_id);
  const levels = useMemo(
    () => [...new Set((funnel.data ?? []).map((r) => r.episode_level))].sort(),
    [funnel.data],
  );
  return (
    <div className="space-y-4">
      <Headline ev={ev} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title={`Phễu ${ev.step_names.length} bước`} aside={
          <div className="flex gap-1 text-xs" role="group" aria-label="mức">
            {[null, ...levels].map((l) => (
              <button key={String(l)} type="button" onClick={() => setLevel(l)}
                className={`rounded px-2 py-0.5 ${l === level ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>
                {l === null ? "mọi mức" : `mức ${l}`}
              </button>
            ))}
          </div>
        }>
          {funnel.isLoading ? <Loading /> : funnel.error ? <ErrorBox error={funnel.error} /> : (
            <StepFunnel steps={funnelSteps(funnel.data ?? [], level === null ? null : [level])}
              names={ev.step_names} />
          )}
        </Panel>
        <FailureTable evaluationId={ev.evaluation_id} />
      </div>
      <FailedEpisodes evaluationId={ev.evaluation_id} level={level} />
    </div>
  );
}

function Headline({ ev }: { ev: EvaluationSummary }) {
  const gapTooBig = ev.sim_scorer_gap !== null && ev.sim_scorer_gap > SCORER_GAP_WARNING;
  const scored = ev.total_episodes - ev.infra_failed_count;
  return (
    <div className="grid gap-3 sm:grid-cols-4" data-testid="eval-headline">
      <Stat label="Tỉ lệ thành công · cờ simulator" value={pct(ev.sim_success_rate)} strong
        note={`${ev.success_count}/${scored} episode chấm được`} />
      <Stat label="Kết luận scorer (đối chiếu)" value={pct(ev.scorer_success_rate)}
        note={ev.scorer_success_rate === null ? "chưa có episode để đối chiếu" : `lệch ${pct(ev.sim_scorer_gap)}`}
        warn={gapTooBig ? "Lệch quá 5%: scorer có thể hỏng" : undefined} />
      <Stat label="Loại vì lỗi hạ tầng" value={String(ev.infra_failed_count)}
        note="không tính vào mẫu số" />
      <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600">
        <p>checkpoint <span className="font-mono">{ev.checkpoint_id}</span></p>
        <p>scorer {ev.scorer_version} · {ev.renderer} · {ev.eval_mode}</p>
        <p className="mt-1 flex items-center gap-1">tập {ev.split} <MockBadge origin={ev.origin} />
          {ev.is_sealed ? <SealedLock until={ev.sealed_until} /> : null}</p>
      </div>
    </div>
  );
}

function Stat({ label, value, note, strong, warn }: {
  label: string; value: string; note?: string; strong?: boolean; warn?: string;
}) {
  return (
    <div className={`rounded-lg border bg-white p-3 ${warn ? "border-rose-400" : "border-slate-200"}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`${strong ? "text-3xl" : "text-2xl"} font-semibold tabular-nums`}>{value}</p>
      {note ? <p className="text-xs text-slate-500">{note}</p> : null}
      {warn ? <p className="mt-1 text-xs font-semibold text-rose-700" role="alert">{warn}</p> : null}
    </div>
  );
}

/** §6.3 StepFunnel: absolute and conditional rate per step of the task. */
export function StepFunnel({ steps, names }: { steps: FunnelStep[]; names: string[] }) {
  if (steps.length === 0) return <EmptyState title="Chưa có episode chấm được" />;
  return (
    <table className="w-full text-sm" data-testid="step-funnel">
      <thead className="text-left text-xs text-slate-500">
        <tr>
          <th className="py-1">Bước</th>
          <th className="w-2/5">Qua bước (trên tổng)</th>
          <th className="text-right">Có điều kiện</th>
          <th className="text-right">Trượt</th>
          <th className="text-right" title="Không có tín hiệu: không tính là qua, không tính là trượt">Chưa rõ</th>
        </tr>
      </thead>
      <tbody>
        {steps.map((s) => (
          <tr key={s.step_no} className="border-t border-slate-100">
            <td className="py-1.5 pr-2"><span className="text-slate-400">{s.step_no}.</span> {names[s.step_no - 1] ?? ""}</td>
            <td className="pr-2">
              <div className="flex items-center gap-2">
                <div className="h-2.5 flex-1 overflow-hidden rounded bg-slate-200">
                  <div className="h-full bg-emerald-600" style={{ width: `${(s.absolute ?? 0) * 100}%` }} />
                </div>
                <span className="w-12 text-right tabular-nums">{pct(s.absolute)}</span>
              </div>
            </td>
            <td className="text-right tabular-nums">{pct(s.conditional)}</td>
            <td className="text-right tabular-nums">{s.fail}</td>
            <td className={`text-right tabular-nums ${s.unknown > 0 ? "font-semibold text-amber-700" : "text-slate-400"}`}>{s.unknown}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FailureTable({ evaluationId }: { evaluationId: string }) {
  const board = useFailures(evaluationId);
  return (
    <Panel title="Bảng lỗi 5 họ">
      {board.isLoading ? <Loading /> : board.error ? <ErrorBox error={board.error} /> : (
        <div className="space-y-2" data-testid="failure-table">
          {(board.data?.families ?? []).map((f) => <FamilyBlock key={f.family} block={f} />)}
        </div>
      )}
    </Panel>
  );
}

function FamilyBlock({ block }: { block: FailureFamilyBlock }) {
  const head = (
    <span className="font-medium">
      <span className="font-mono text-xs text-slate-500">{block.family}</span> {familyLabel[block.family]}
    </span>
  );
  if (block.status === "not_run") {
    return (
      <div className="rounded border border-dashed border-slate-300 p-2 text-sm" data-testid={`family-${block.family}`}>
        {head} <span className="ml-2 text-xs text-slate-500">chưa chạy · không phải "không lỗi"</span>
      </div>
    );
  }
  return (
    <div className="rounded border border-slate-200 p-2 text-sm" data-testid={`family-${block.family}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {head}
        {block.rows.length === 0 ? (
          <span className="text-xs text-emerald-700">
            đã chấm, không mã nào nổ{block.skipped.length > 0 ? " (trừ các mã không chấm được bên dưới)" : ""}
          </span>
        ) : block.rows.map((r) => (
          <span key={r.code} className="rounded bg-rose-50 px-1.5 py-0.5 font-mono text-xs text-rose-800 ring-1 ring-rose-200">
            {r.code} × {r.count}
          </span>
        ))}
      </div>
      {block.skipped.length > 0 ? <div className="mt-2"><SkippedList items={block.skipped} /></div> : null}
    </div>
  );
}

function FailedEpisodes({ evaluationId, level }: { evaluationId: string; level: number | null }) {
  const episodes = useEvalEpisodes(evaluationId);
  const checks = useSystemChecks(evaluationId);
  const [open, setOpen] = useState<string | null>(null);
  const byEpisode = useMemo(
    () => new Map((checks.data ?? []).map((c) => [c.eval_episode_id, c])),
    [checks.data],
  );
  const rows = (episodes.data?.items ?? []).filter((e) => level === null || e.level === level);
  const failed = rows.filter((e) => e.infra_status === "ok" && e.sim_success === false);
  const infra = rows.filter((e) => e.infra_status !== "ok");
  const selected = failed.find((e) => e.id === open) ?? null;

  return (
    <Panel title={`Episode lỗi (${failed.length})`} aside={
      infra.length > 0 ? (
        <span className="text-xs text-slate-500" data-testid="infra-excluded">
          {infra.length} episode lỗi hạ tầng bị loại: {infra.map((e) => `${e.id} (${e.infra_status})`).join(", ")}
        </span>
      ) : null
    }>
      {episodes.isLoading ? <Loading /> : episodes.error ? <ErrorBox error={episodes.error} /> : failed.length === 0 ? (
        <EmptyState title="Không có episode lỗi ở mức này" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm" data-testid="failed-episodes">
              <thead className="sticky top-0 bg-white text-left text-xs text-slate-500">
                <tr><th className="py-1">Episode</th><th>Mức</th><th>Bước hỏng</th><th>Mã lỗi</th><th>t (s)</th><th>Kiểm hệ thống</th></tr>
              </thead>
              <tbody>
                {failed.map((e) => (
                  <tr key={e.id} onClick={() => setOpen(e.id)} aria-selected={e.id === open}
                    className={`cursor-pointer border-t border-slate-100 ${e.id === open ? "bg-sky-50" : "hover:bg-slate-50"}`}>
                    <td className="py-1 font-mono text-xs">{e.id}</td>
                    <td>{e.level}</td>
                    <td>{e.first_failed_step ?? "—"}</td>
                    <td className="font-mono text-xs">{e.failure_code ?? "—"}</td>
                    <td className="tabular-nums">{fmt(e.failure_time_s, 1)}</td>
                    <td><SystemVerdictChip diagnosis={byEpisode.get(e.id)?.diagnosis ?? null} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selected ? <EpisodeDetail episode={selected} check={byEpisode.get(selected.id) ?? null} />
            : <EmptyState title="Chọn một episode để xem clip, log và kiểm hệ thống" />}
        </div>
      )}
    </Panel>
  );
}

function EpisodeDetail({ episode, check }: { episode: EvalEpisodeRow; check: SystemCheckRow | null }) {
  const m = (check?.measurements ?? {}) as {
    tracking_error_p99?: Record<string, number>;
    latency_p99_s?: number;
    sync_offset_max_s?: number;
  };
  const mockMedia = (uri: string | null) => !uri || uri.startsWith("mock://");
  return (
    <div className="space-y-3 text-sm" data-testid="episode-detail">
      <p className="font-mono text-xs">{episode.id} · seed {episode.episode_seed}/{episode.rollout_seed}</p>
      {mockMedia(episode.video_uri) ? (
        <div className="flex aspect-video items-center justify-center rounded bg-slate-200 text-xs text-slate-500">
          clip mock · {episode.video_uri ?? "không có video"}
        </div>
      ) : (
        <video className="w-full rounded" controls src={episode.video_uri ?? undefined} />
      )}
      <p className="text-xs">
        Log quỹ đạo:{" "}
        {mockMedia(episode.trajectory_log_uri)
          ? <span className="text-slate-500">{episode.trajectory_log_uri ?? "—"}</span>
          : <a className="text-blue-700 underline" href={episode.trajectory_log_uri ?? "#"}>mở</a>}
      </p>
      <div className="flex gap-1" aria-label="các bước">
        {episode.step_status.map((s, i) => (
          <span key={i} title={`bước ${i + 1}: ${s}`} className={`h-2 flex-1 rounded ${
            s === "pass" ? "bg-emerald-500" : s === "fail" ? "bg-rose-500" : s === "unknown" ? "bg-amber-400" : "bg-slate-200"}`} />
        ))}
      </div>
      {check === null ? (
        <EmptyState title="Chưa kiểm hệ thống episode này" />
      ) : (
        <div className="space-y-2">
          <p className="flex items-center gap-2 text-xs">Kiểm hệ thống <SystemVerdictChip diagnosis={check.diagnosis} />
            {check.fired_codes.length > 0 ? <span className="font-mono text-rose-700">{check.fired_codes.join(", ")}</span> : null}
          </p>
          <table className="w-full text-xs">
            <tbody>
              {Object.entries(m.tracking_error_p99 ?? {}).map(([part, v]) => (
                <tr key={part}><td className="text-slate-500">sai số bám lệnh p99 · {part === "upper" ? "thân trên" : part === "lower" ? "thân dưới" : part}</td><td className="text-right tabular-nums">{fmt(v, 3)}</td></tr>
              ))}
              <tr><td className="text-slate-500">độ trễ p99 (s)</td><td className="text-right tabular-nums">{fmt(m.latency_p99_s, 3)}</td></tr>
              <tr><td className="text-slate-500">lệch đồng bộ lớn nhất (s)</td><td className="text-right tabular-nums">{fmt(m.sync_offset_max_s, 3)}</td></tr>
            </tbody>
          </table>
          <SkippedList items={check.skipped.map((k) => ({
            source: "system_check" as const, code: k.code, reason: k.reason, eval_episode_id: null,
          }))} />
          <p className="text-xs text-slate-500" data-testid="rollout-timing">
            Rollout: {rolloutTimingLabel[check.timing ?? "unknown"]}
          </p>
          {check.recorded.length + check.recorded_skipped.length > 0 ? (
            // Decision (a) of 5/11/2026: shown so the latency is not lost, but
            // apart from the verdict, because it decides nothing.
            <div className="rounded border border-slate-200 bg-slate-50 p-2 text-xs" data-testid="recorded-checks">
              <p className="font-semibold text-slate-600">Ghi nhận, không quy lỗi</p>
              <ul className="mt-1 space-y-0.5">
                {check.recorded.map((f, i) => {
                  const r = f as { code: string; value?: number; threshold?: number | null };
                  return (
                    <li key={`r${i}`}>
                      <span className="font-mono">{r.code}</span>{" "}
                      <span className="tabular-nums">{fmt(r.value, 3)}</span>
                      {r.threshold != null ? <span className="text-slate-500"> / ngưỡng {fmt(r.threshold, 3)}</span> : null}
                    </li>
                  );
                })}
                {check.recorded_skipped.map((k) => (
                  <li key={`s${k.code}`}>
                    <span className="font-mono">{k.code}</span> <span className="text-slate-500">không đo được: {k.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
