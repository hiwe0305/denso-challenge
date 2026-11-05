// HE curve (DESIGN.md §6.1, M9): success rate by number of robot demos N,
// one line per variant, a Wilson 95% interval per point, N50 marked.
//
// Colours: categorical slots 1–3 of the dataviz reference palette, in fixed
// order per variant (never by rank), validated with validate_palette.js on a
// white surface. Slot 3 sits below 3:1 contrast, so every line is also
// direct-labelled and the same numbers are in the table under the chart.
import {
  CartesianGrid,
  ErrorBar,
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
import type { HeCurvePoint } from "../api/types";
import { heVariant, type HeVariant } from "../contracts/enums";
import { SealedLock } from "../ui/components";
import { fmt } from "../ui/labels";

const VARIANT_COLOR: Record<HeVariant, string> = {
  V_EGO: "#2a78d6",
  V_EGO10: "#eb6834",
  V_NOEGO: "#1baf7a",
};
const VARIANT_LABEL: Record<HeVariant, string> = {
  V_EGO: "V-EGO",
  V_EGO10: "V-EGO10",
  V_NOEGO: "V-NOEGO",
};

/** Wilson score interval, 95%. Returns null when nothing was scored. */
export function wilson(rate: number | null, n: number, z = 1.96): [number, number] | null {
  if (rate === null || n <= 0) return null;
  const denom = 1 + (z * z) / n;
  const centre = (rate + (z * z) / (2 * n)) / denom;
  const half = (z * Math.sqrt((rate * (1 - rate)) / n + (z * z) / (4 * n * n))) / denom;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

/** Smallest N whose success rate reaches 50%; null when no point does. */
export function n50(points: HeCurvePoint[]): number | null {
  const reached = points
    .filter((p) => p.sim_success_rate !== null && p.sim_success_rate >= 0.5)
    .map((p) => p.n_demos);
  return reached.length > 0 ? Math.min(...reached) : null;
}

export function HeCurve({ points }: { points: HeCurvePoint[] }) {
  const visible = points.filter((p) => !p.is_sealed);
  const variants = heVariant.filter((v) => visible.some((p) => p.he_variant === v));
  const sizes = [...new Set(visible.map((p) => p.n_demos))].sort((a, b) => a - b);
  const data = sizes.map((n) => {
    const row: Record<string, number | [number, number] | null> = { n };
    for (const v of variants) {
      const p = visible.find((x) => x.he_variant === v && x.n_demos === n);
      const rate = p?.sim_success_rate ?? null;
      const ci = p ? wilson(rate, p.n_scored) : null;
      row[v] = rate === null ? null : rate * 100;
      row[`${v}_err`] = rate !== null && ci ? [(rate - ci[0]) * 100, (ci[1] - rate) * 100] : null;
    }
    return row;
  });
  const lastN = sizes[sizes.length - 1];

  return (
    <div className="space-y-2" data-testid="he-curve">
      <div className="h-72" role="img" aria-label="Đường cong HE: tỉ lệ thành công theo số demo">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 72, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="#e7e6e2" vertical={false} />
            <XAxis dataKey="n" tick={{ fill: "#898781", fontSize: 12 }} stroke="#c9c8c2"
              label={{ value: "N demo robot", position: "insideBottomRight", offset: -4, fill: "#898781", fontSize: 11 }} />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" width={44}
              tick={{ fill: "#898781", fontSize: 12 }} stroke="#c9c8c2" />
            <ReferenceLine y={50} stroke="#898781" strokeDasharray="4 4"
              label={{ value: "50%", position: "left", fill: "#898781", fontSize: 11 }} />
            <Tooltip
              formatter={(value, name) => [`${fmt(Number(value), 1)}%`, VARIANT_LABEL[name as HeVariant] ?? String(name)]}
              labelFormatter={(n) => `N = ${n}`} />
            <Legend formatter={(v) => VARIANT_LABEL[v as HeVariant] ?? v} />
            {variants.map((v) => (
              <Line key={v} type="monotone" dataKey={v} stroke={VARIANT_COLOR[v]} strokeWidth={2}
                dot={{ r: 4, strokeWidth: 2, stroke: "#ffffff", fill: VARIANT_COLOR[v] }}
                activeDot={{ r: 6 }} isAnimationActive={false} connectNulls={false}>
                <ErrorBar dataKey={`${v}_err`} width={6} strokeWidth={1.5} stroke={VARIANT_COLOR[v]} direction="y" />
                <LabelList dataKey={v} content={({ x, y, index }) =>
                  data[Number(index)]?.n === lastN ? (
                    <text x={Number(x) + 10} y={Number(y) + 4} fontSize={12} fill="#52514e">{VARIANT_LABEL[v]}</text>
                  ) : null} />
              </Line>
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <table className="w-full text-xs" data-testid="he-table">
        <thead className="text-left text-slate-500">
          <tr><th>Biến thể</th>{sizes.map((n) => <th key={n} className="text-right">N={n}</th>)}<th className="text-right">N₅₀</th></tr>
        </thead>
        <tbody>
          {variants.map((v) => {
            const own = visible.filter((p) => p.he_variant === v);
            const reach = n50(own);
            return (
              <tr key={v} className="border-t border-slate-100">
                <td className="py-1"><span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: VARIANT_COLOR[v] }} />{VARIANT_LABEL[v]}</td>
                {sizes.map((n) => {
                  const p = own.find((x) => x.n_demos === n);
                  const ci = p ? wilson(p.sim_success_rate, p.n_scored) : null;
                  return (
                    <td key={n} className="text-right tabular-nums" title={ci ? `KTC 95%: ${fmt(ci[0] * 100, 1)}–${fmt(ci[1] * 100, 1)}%` : undefined}>
                      {p?.sim_success_rate == null ? "—" : `${fmt(p.sim_success_rate * 100, 1)}%`}
                    </td>
                  );
                })}
                <td className="text-right font-semibold tabular-nums" data-testid={`n50-${v}`}>{reach ?? "chưa tới"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {points.some((p) => p.is_sealed) ? (
        <p className="flex items-center gap-1 text-xs text-slate-500"><SealedLock until={null} /> có điểm holdout còn niêm phong, không vẽ</p>
      ) : null}
      <p className="text-xs text-slate-500">
        N đếm từ release của từng điểm (demo gốc do người làm), không nhập tay. Thanh dọc là khoảng tin cậy Wilson 95%.
      </p>
    </div>
  );
}
