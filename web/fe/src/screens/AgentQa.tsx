// M3 · Agent QA/QC (DESIGN.md §6.2): DA-31's score of the injected defects.
// Every number is measured on defects DA-27 seeded into copies of the data,
// and the screen says so before anything else; the false alarm on the clean
// copy is an upper bound. Code and agent stand side by side so the agent is
// never credited with what code already caught (design 27/10 §9.2).
import { useDefectScoreboard } from "../api/hooks";
import type { AgentModelUse, BenchLayer, DefectBenchGroup, DefectFinding, DefectRate } from "../api/types";
import { EmptyState, ErrorBox, HashBadge, Loading, MockBadge, Panel } from "../ui/components";
import { fmtTime } from "../ui/labels";

const layerLabel: Record<BenchLayer, string> = { code: "Code", agent: "Agent" };
const groupLabel: Record<string, string> = { data: "Dữ liệu", logs: "Log train" };
const findingLabel: Record<DefectFinding["label"], string> = {
  hit: "đúng lỗi cấy",
  false: "báo sai",
  natural: "lỗi tự nhiên",
  clean: "trên bản sạch",
};
const reviewLabel: Record<DefectFinding["review"], string> = {
  agree: "kỹ sư đồng ý",
  override: "kỹ sư bác",
  unreviewed: "chưa duyệt",
};

/** "1/2 · 50%"; a rate with nothing to divide by is "—", never 0%. */
export function fmtRate(r: DefectRate): string {
  if (r.value === null) return "—";
  return `${r.hit}/${r.total} · ${Math.round(r.value * 100)}%`;
}

function fmtSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return "chưa đo";
  return value < 120 ? `${value.toFixed(1)} s` : `${(value / 60).toFixed(1)} phút`;
}

function RateCell({ rate, testId }: { rate: DefectRate; testId?: string }) {
  const tone = rate.value === null ? "text-slate-400" : rate.value === 1 ? "text-emerald-700" : rate.value === 0 ? "text-rose-700" : "";
  return <td className={`text-xs tabular-nums ${tone}`} data-testid={testId}>{fmtRate(rate)}</td>;
}

function GroupBlock({ g }: { g: DefectBenchGroup }) {
  const masked = g.kinds.some((k) => k.masked.code + k.masked.agent > 0);
  const injectedFindings = g.agent_findings.filter((f) => f.copy === g.injected_copy);
  const cleanFindings = g.agent_findings.filter((f) => f.copy !== g.injected_copy);
  return (
    <Panel title={`${groupLabel[g.group_name] ?? g.group_name} · ${g.injected_copy}`}
      aside={<span className="text-xs text-slate-500">bản sạch đối chứng: <span className="font-mono">{g.clean_copy}</span></span>}>
      <div className="space-y-4" data-testid={`bench-group-${g.group_name}`}>
        <p className="text-sm">
          {g.defects} lỗi cấy. Code bắt <b>{g.totals.by_code}</b>, agent bắt thêm <b>{g.totals.agent_adds}</b>,
          cùng nhau <b>{g.totals.together}/{g.totals.injected}</b>.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid={`kinds-${g.group_name}`}>
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="py-1">Loại lỗi</th><th>Mã</th><th>Cấy</th><th>Code bắt</th><th>Agent thêm</th>
                <th>Cùng nhau</th><th>Recall code</th><th>Recall agent</th>{masked ? <th>Bị che</th> : null}
              </tr>
            </thead>
            <tbody>
              {g.kinds.map((k) => (
                <tr key={k.kind} className="border-t border-slate-100">
                  <td className="py-1 font-mono text-xs">{k.kind}</td>
                  <td className="font-mono text-xs">{k.code}</td>
                  <td className="text-xs tabular-nums">{k.injected}</td>
                  <td className="text-xs tabular-nums">{k.by_code}</td>
                  <td className={`text-xs tabular-nums ${k.agent_adds ? "font-semibold text-sky-800" : ""}`}>{k.agent_adds ? `+${k.agent_adds}` : "0"}</td>
                  <td className="text-xs tabular-nums">{k.together}</td>
                  <RateCell rate={k.recall.code} />
                  <RateCell rate={k.recall.agent} />
                  {masked ? <td className="text-xs tabular-nums">{k.masked.code}/{k.masked.agent}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase text-slate-500">Precision theo mã báo</h3>
            <table className="w-full text-sm" data-testid={`codes-${g.group_name}`}>
              <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Mã</th><th>Code</th><th>Agent</th></tr></thead>
              <tbody>
                {g.codes.map((c) => (
                  <tr key={c.code} className="border-t border-slate-100">
                    <td className="py-1 font-mono text-xs">{c.code}</td>
                    <RateCell rate={c.precision.code} />
                    <RateCell rate={c.precision.agent} />
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-slate-500">"—": lớp đó không báo mã này lần nào, không phải 0%.</p>
          </div>
          <div className="space-y-3">
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-slate-500">Báo nhầm trên bản sạch · cận trên</h3>
              <ul className="text-sm" data-testid={`false-alarm-${g.group_name}`}>
                {(["code", "agent"] as const).map((l) => (
                  <li key={l}>
                    {layerLabel[l]}: <span className="tabular-nums">{fmtRate(g.false_alarm[l])}</span> đơn vị
                    {g.clean_reports[l].length ? (
                      <span className="text-xs text-slate-500"> · {g.clean_reports[l].map(([t, c]) => `${c} trên ${t}`).join(", ")}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-slate-500">Thời gian tới khi có báo cáo</h3>
              <table className="w-full text-xs" data-testid={`latency-${g.group_name}`}>
                <thead className="text-left text-slate-500"><tr><th className="py-1">Lớp</th><th>Bản có lỗi</th><th>Bản sạch</th></tr></thead>
                <tbody>
                  {(["code", "agent"] as const).map((l) => (
                    <tr key={l} className="border-t border-slate-100">
                      <td className="py-1">{layerLabel[l]}</td>
                      <td className="tabular-nums">{fmtSeconds(g.seconds_to_report[l][g.injected_copy])}</td>
                      <td className="tabular-nums">{fmtSeconds(g.seconds_to_report[l][g.clean_copy])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {g.natural.code.length + g.natural.agent.length > 0 ? (
              <p className="text-xs text-slate-600">
                Lỗi tự nhiên của dữ liệu thật (không tính vào precision): {[...g.natural.code, ...g.natural.agent].map(([t, c]) => `${c} trên ${t}`).join(", ")}
              </p>
            ) : null}
          </div>
        </div>

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase text-slate-500">Báo cáo của agent</h3>
          {injectedFindings.length + cleanFindings.length === 0 ? (
            <EmptyState title="Agent không báo gì trên cặp bản sao này" />
          ) : (
            <>
              <p className="mb-1 text-sm" data-testid={`ranking-${g.group_name}`}>
                Thứ hạng: phát hiện đúng đứng trên phát hiện sai ở <span className="tabular-nums">{fmtRate(g.agent_ranking)}</span> cặp.
              </p>
              <table className="w-full text-xs" data-testid={`findings-${g.group_name}`}>
                <thead className="text-left text-slate-500">
                  <tr><th className="py-1">Hạng</th><th>Bản</th><th>Đích</th><th>Mã</th><th>So với đáp án</th><th>Kỹ sư</th></tr>
                </thead>
                <tbody>
                  {[...injectedFindings, ...cleanFindings].map((f) => (
                    <tr key={`${f.report_id}/${f.finding_id}`} className="border-t border-slate-100">
                      <td className="py-1 tabular-nums">{f.rank}</td>
                      <td>{f.copy === g.injected_copy ? "có lỗi" : "sạch"}</td>
                      <td className="font-mono">{f.target}</td>
                      <td className="font-mono">{f.code}</td>
                      <td className={f.label === "hit" ? "text-emerald-700" : f.label === "natural" ? "text-slate-600" : "text-rose-700"}>{findingLabel[f.label]}</td>
                      <td>{reviewLabel[f.review]}{f.reason ? ` · ${f.reason}` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
        <GroupModels g={g} />
      </div>
    </Panel>
  );
}

/** "name revision · t=0.2"; the model as the agent column depends on it. */
function modelLabel(m: AgentModelUse): string {
  return `${m.name} ${m.revision} · t=${m.temperature}`;
}

/** The key of a model a number can be rerun with: everything but the copy and the count. */
function modelKey(m: AgentModelUse): string {
  return `${m.name}\u0000${m.revision}\u0000${m.temperature}\u0000${m.prompt_sha256}`;
}

/** Whether both copies were read by the same set of models (recall and false alarm from one agent). */
export function sameModels(g: DefectBenchGroup): boolean {
  const keys = (copy: string) => [...new Set((g.agent_models ?? []).filter((m) => m.copy === copy).map(modelKey))].sort().join("|");
  return keys(g.injected_copy) === keys(g.clean_copy);
}

/** Header line: the models behind the agent column, or why there are none (W14). */
function BenchModels({ groups, version }: { groups: DefectBenchGroup[]; version: string | null }) {
  if (groups.every((g) => g.agent_models === null)) {
    return (
      <p className="text-xs text-slate-500" data-testid="bench-model">
        Model và hash prompt của agent: chưa có — kết quả <span className="font-mono">{version}</span> chưa mang hai trường này
        (có từ <span className="font-mono">da31-3</span>, W14).
      </p>
    );
  }
  const seen = new Map<string, AgentModelUse>();
  for (const m of groups.flatMap((g) => g.agent_models ?? [])) seen.set(modelKey(m), m);
  const models = [...seen.values()];
  return (
    <p className="text-xs text-slate-500" data-testid="bench-model">
      Model của agent:{" "}
      {models.length === 0 ? "không có báo cáo agent nào" : models.map((m, i) => (
        <span key={modelKey(m)}>
          {i > 0 ? "; " : ""}<span className="font-mono">{modelLabel(m)}</span>, prompt <HashBadge value={m.prompt_sha256} />
        </span>
      ))}
    </p>
  );
}

/** Per group: which model read which copy, and a warning when the two copies differ. */
function GroupModels({ g }: { g: DefectBenchGroup }) {
  if (g.agent_models === null) return null;
  const rows = [...g.agent_models].sort((a, b) =>
    a.copy === b.copy ? modelKey(a).localeCompare(modelKey(b)) : a.copy === g.injected_copy ? -1 : 1);
  return (
    <div>
      <h3 className="mb-1 text-xs font-semibold uppercase text-slate-500">Model của agent theo bản sao</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-500">Không bản nào có báo cáo agent.</p>
      ) : (
        <table className="w-full text-xs" data-testid={`models-${g.group_name}`}>
          <thead className="text-left text-slate-500">
            <tr><th className="py-1">Bản</th><th>Model</th><th>Hash prompt</th><th>Số báo cáo</th></tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={`${m.copy}/${modelKey(m)}`} className="border-t border-slate-100">
                <td className="py-1">{m.copy === g.injected_copy ? "có lỗi" : "sạch"}</td>
                <td className="font-mono">{modelLabel(m)}</td>
                <td><HashBadge value={m.prompt_sha256} /></td>
                <td className="tabular-nums">{m.reports}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {sameModels(g) ? null : (
        <p className="mt-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900" data-testid={`models-differ-${g.group_name}`}>
          Hai bản sao không do cùng model hoặc prompt đọc: recall (bản có lỗi) và báo nhầm (bản sạch) của cột agent không đến từ một agent.
        </p>
      )}
    </div>
  );
}

export function AgentQa() {
  const board = useDefectScoreboard();
  if (board.isLoading) return <Loading />;
  if (board.error) return <ErrorBox error={board.error} />;
  const b = board.data;
  if (!b || b.result_sha256 === null) {
    return (
      <EmptyState title="Chưa có lần chấm nào">
        Chạy bộ chấm DA-31 (<span className="font-mono">python -m flywheel.eval.agentqa.bench</span>) rồi nạp
        <span className="font-mono"> bench_result.json</span> bằng <span className="font-mono">fwsync import</span>.
      </EmptyState>
    );
  }
  const t = b.totals;
  return (
    <div className="space-y-4">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">Agent QA/QC · trên lỗi cấy</h1>
          <MockBadge origin={b.origin} />
          <HashBadge value={b.result_sha256} />
          <span className="text-xs text-slate-500">{b.bench_version} · chấm lúc {fmtTime(b.created_at)}</span>
        </div>
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="bench-banner">
          Mọi số ở đây đo trên lỗi DA-27 cấy vào bản sao của dữ liệu thật, đáp án niêm phong trước khi chạy
          ({b.measured_on}). Nó nói các phép kiểm bắt <b>những lỗi này</b> tốt đến đâu, không phải tỉ lệ trên lỗi tự nhiên.
          Báo nhầm trên bản sạch là <b>cận trên</b>: bản sạch vẫn mang lỗi tự nhiên của dữ liệu thật.
        </p>
        <p className="text-base" data-testid="bench-summary">
          Code bắt <b>{t.by_code}/{t.injected}</b> lỗi cấy; agent bắt thêm <b>{t.agent_adds}</b>; cùng nhau <b>{t.together}/{t.injected}</b>.
        </p>
        <BenchModels groups={b.groups} version={b.bench_version} />
      </header>
      {b.groups.map((g) => <GroupBlock key={g.group_name} g={g} />)}
    </div>
  );
}
