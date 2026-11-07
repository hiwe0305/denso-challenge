// M5 · experiment draft form (DESIGN.md §6.2, §7.2): compose a draft without
// touching group P, save it, submit it. Submitting records EXPERIMENT_SUBMIT
// and the screen then waits for the core (§6.4, no optimistic update). The
// server checks BR-01 / C7 at submit and says which rule failed.
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { apiAction, apiWrite, newIdempotencyKey } from "../api/client";
import { useDrafts, useReleases } from "../api/hooks";
import type { DraftBody, ExperimentDraft } from "../api/types";
import { branchTray, branchTwoTable, method as methods, type TaskId } from "../contracts/enums";
import { ActionStatus, EmptyState, ErrorBox, Panel } from "../ui/components";
import { fmtTime } from "../ui/labels";

const BRANCHES: Record<TaskId, readonly string[]> = { two_table: branchTwoTable, tray: branchTray };

function SubmitButton({ d }: { d: ExperimentDraft }) {
  const key = useRef<string | null>(null);
  const client = useQueryClient();
  const [err, setErr] = useState<unknown>(null);
  if (d.submit_action_id) return <ActionStatus actionId={d.submit_action_id} />;
  return (
    <div className="space-y-1">
      <button type="button" className="rounded bg-slate-900 px-2 py-1 text-xs text-white"
        onClick={async () => {
          key.current ??= newIdempotencyKey();
          try {
            setErr(null);
            await apiAction(`/experiment-drafts/${d.id}/submit`, {}, key.current);
            await client.invalidateQueries({ queryKey: ["/experiment-drafts?limit=500"] });
          } catch (error) {
            key.current = null; // a refused submit recorded nothing; the next try is a new click
            setErr(error);
          }
        }}>
        Nộp {d.id}
      </button>
      {err ? <ErrorBox error={err} /> : null}
    </div>
  );
}

export function DraftPanel() {
  const drafts = useDrafts();
  const releases = useReleases();
  const client = useQueryClient();
  const [task, setTask] = useState<TaskId>("two_table");
  const [branch, setBranch] = useState<string>("B_PLUS");
  const [meth, setMeth] = useState<string>("PSI0");
  const [hypothesis, setHypothesis] = useState("HT");
  const [base, setBase] = useState("src_psi0_ckpt");
  const [lr, setLr] = useState("0.0001");
  const [steps, setSteps] = useState("2000");
  const [mix, setMix] = useState<Record<string, number>>({});
  const [err, setErr] = useState<unknown>(null);
  const frozen = (releases.data?.items ?? []).filter((r) => r.status === "frozen");
  const rows = drafts.data?.items ?? [];

  async function save() {
    try {
      setErr(null);
      await apiWrite<ExperimentDraft>("/experiment-drafts", {
        task_id: task, branch, method: meth, hypothesis: hypothesis || null, base_checkpoint_ref: base,
        hyperparams: { lr: Number(lr), steps: Number(steps) },
        release_mix: Object.entries(mix).map(([release_id, mix_weight]) => ({ release_id, mix_weight })),
      } satisfies DraftBody);
      await client.invalidateQueries({ queryKey: ["/experiment-drafts?limit=500"] });
    } catch (error) {
      setErr(error);
    }
  }

  const input = "rounded border border-slate-300 px-1.5 py-0.5 text-xs";
  return (
    <Panel title="Bản nháp thí nghiệm">
      <div className="grid gap-4 lg:grid-cols-2">
        <form className="space-y-2 text-xs" aria-label="bản nháp" onSubmit={(e) => { e.preventDefault(); void save(); }}>
          <div className="flex flex-wrap gap-2">
            <label>Task <select aria-label="task" className={input} value={task} onChange={(e) => {
              const t = e.target.value as TaskId;
              setTask(t);
              setBranch(BRANCHES[t][0] ?? "");
            }}>{(["two_table", "tray"] as const).map((t) => <option key={t}>{t}</option>)}</select></label>
            <label>Nhánh <select aria-label="nhánh" className={input} value={branch} onChange={(e) => setBranch(e.target.value)}>
              {BRANCHES[task].map((b) => <option key={b}>{b}</option>)}</select></label>
            <label>Method <select aria-label="method" className={input} value={meth} onChange={(e) => setMeth(e.target.value)}>
              {methods.map((m) => <option key={m}>{m}</option>)}</select></label>
            <label>Giả thuyết <input aria-label="giả thuyết" className={`${input} w-16`} value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} /></label>
          </div>
          <div className="flex flex-wrap gap-2">
            <label>Checkpoint gốc <input aria-label="checkpoint gốc" className={`${input} font-mono`} value={base} onChange={(e) => setBase(e.target.value)} /></label>
            <label>lr <input aria-label="lr" className={`${input} w-20`} value={lr} onChange={(e) => setLr(e.target.value)} /></label>
            <label>steps <input aria-label="steps" className={`${input} w-16`} value={steps} onChange={(e) => setSteps(e.target.value)} /></label>
          </div>
          <fieldset className="max-h-32 overflow-auto rounded border border-slate-200 p-1">
            <legend className="px-1 text-slate-500">Release (chỉ release đóng băng mới nộp được, BR-01)</legend>
            {frozen.map((r) => (
              <label key={r.release_id} className="mr-3 inline-flex items-center gap-1">
                <input type="checkbox" aria-label={r.release_id} checked={r.release_id in mix} onChange={(e) => {
                  const next = { ...mix };
                  if (e.target.checked) next[r.release_id] = 1; else delete next[r.release_id];
                  setMix(next);
                }} />
                <span className="font-mono">{r.release_id}</span>
              </label>
            ))}
          </fieldset>
          <button type="submit" className="rounded border border-slate-400 px-2 py-1">Lưu nháp</button>
          {err ? <ErrorBox error={err} /> : null}
        </form>
        <div>
          {rows.length === 0 ? <EmptyState title="Chưa có bản nháp nào">Bản nháp chỉ nằm ở web (nhóm W) tới khi nộp.</EmptyState> : (
            <ul className="space-y-2 text-xs" data-testid="drafts">
              {rows.map((d) => (
                <li key={d.id} className="rounded border border-slate-200 p-2" data-testid={`draft-${d.id}`}>
                  <p className="flex flex-wrap gap-2">
                    <span className="font-mono">{d.id}</span><span>{d.task_id} · {d.branch} · {d.method}</span>
                    <span className="text-slate-500">{d.status} · {fmtTime(d.updated_at)}</span>
                  </p>
                  <p className="text-slate-600">release: {d.release_mix.map((m) => m.release_id).join(", ") || "chưa chọn"} · gốc {d.base_checkpoint_ref}</p>
                  <div className="mt-1"><SubmitButton d={d} /></div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Panel>
  );
}
