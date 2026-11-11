/* Flywheel ring: demo intro slide only (v5). ringIssues is kept for unconverted v4 pages. */
"use strict";
const RING = { order: ["collect", "process", "release", "train", "eval", "loop"], short: { collect: "Collect", process: "Process", release: "Release", train: "Train", eval: "Eval", loop: "Failure → Data" } };

function ringIssues(model) {
  const S = STORY, r70 = S.runs.find(r => r.branch === "C_70") || S.runs[0], h1 = S.h1m, rr = h1.qa_reasons || {};
  return [
    { stage: "loop", problem: "L-PLACE-POSE " + S.loop_chain[1] + "/" + S.loop_chain[0], cause: "", action: "", status: "", st: "waiting", link: "#/loop" },
    { stage: "process", problem: `${h1.qa.flag}/${h1.clips} clips flagged`, cause: `segment_ambiguous ${rr.segment_ambiguous}, hand_pose_nan ${rr.hand_pose_nan}`, action: "", status: "", st: "waiting", link: "#/qa" },
    { stage: "train", problem: "B_ALL stopped", cause: "", action: "", status: `C_70 ${fmt(r70.step)}/${fmt(r70.max_steps)}`, st: "running", link: "#/runs" },
  ];
}

/* full-screen intro: six stages around an ellipse, live state from /api/status when available. onDone() runs on click, Enter or Space. */
function ringIntro(onDone) {
  const W = 800, H = 380, cx = 400, cy = 190, rx = 300, ry = 128, ang = [-90, -30, 30, 90, 150, 210];
  const el = h("div", { id: "intro" });
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}` });
  const P = d => { const a = d * Math.PI / 180; return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)]; };
  const stateOf = {}; if (typeof ST !== "undefined" && ST.stages) ST.stages.forEach(s => stateOf[s.id] = s.state);
  RING.order.forEach((id, i) => { const [x0, y0] = P(ang[i] + 22), [x1, y1] = P(ang[(i + 1) % 6] - 22), s = stateOf[id] || "idle";
    svg.appendChild(svgEl("path", { class: "arc " + s, d: `M${x0.toFixed(1)} ${y0.toFixed(1)} A${rx} ${ry} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}` })); });
  RING.order.forEach((id, i) => { const [x, y] = P(ang[i]), s = stateOf[id] || "idle"; const g = svgEl("g", { class: "node", transform: `translate(${x - 62},${y - 22})` }, [svgEl("rect", { width: 124, height: 44, rx: 4 })]);
    const t1 = svgEl("text", { x: 12, y: 19 }); t1.textContent = RING.short[id]; const t2 = svgEl("text", { x: 12, y: 36, class: "s" }); t2.textContent = (UI.glyph(s)) + " " + s; g.appendChild(t1); g.appendChild(t2); svg.appendChild(g); });
  el.appendChild(svg); el.appendChild(h("div", { class: "go", text: "Enter" }));
  const done = () => { document.removeEventListener("keydown", kd, true); el.remove(); if (onDone) onDone(); };
  const kd = e => { if (e.key === "Enter" || e.key === " " || e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); done(); } };
  el.addEventListener("click", done); document.addEventListener("keydown", kd, true);
  document.body.appendChild(el); return el;
}
