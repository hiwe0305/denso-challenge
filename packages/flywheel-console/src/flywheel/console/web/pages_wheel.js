/* Home = the data wheel (flywheel v0.3 design 5.1, deck slide 8): six numbered steps clockwise, the cost
   ledger in the centre, a panel for the selected step, the round-1 result strip, "Follow one failure".
   Step text and numbers come from the EXPLAIN registry (explain.js), so the wheel and the step pages agree.
   URL: #/home?s=<0..6> selects a step (0 = ledger); #/home?tour=1 advances every few seconds (for recording).
   Also: a placeholder #/diagnose (step 5) registered only when no other file registered that route. */
"use strict";

const WH = { cx: 380, cy: 345, R: 215, r: 44 };
const whAng = i => (-90 + 60 * i) * Math.PI / 180;
const whPos = i => [WH.cx + WH.R * Math.cos(whAng(i)), WH.cy + WH.R * Math.sin(whAng(i))];
/* a step name on at most two lines: split at the space nearest the middle when it is long */
function whLines(s) {
  if (s.length <= 15) return [s];
  const mid = s.length / 2; let at = -1;
  for (let i = 0; i < s.length; i++) if (s[i] === " " && (at < 0 || Math.abs(i - mid) < Math.abs(at - mid))) at = i;
  return at < 0 ? [s] : [s.slice(0, at), s.slice(at + 1)];
}

function wheelSvg(sel, onPick) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "-50 0 860 700"); svg.setAttribute("class", "wh-svg"); svg.setAttribute("role", "img");
  const el = (n, a, p, txt) => { const x = document.createElementNS(NS, n); Object.entries(a || {}).forEach(([k, v]) => x.setAttribute(k, v)); if (txt != null) x.textContent = txt; (p || svg).appendChild(x); return x; };
  const defs = el("defs");
  const mk = el("marker", { id: "wh-ar", viewBox: "0 0 10 10", refX: 6, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto" }, defs);
  el("path", { d: "M0 0L10 5L0 10z", class: "wh-arhead" }, mk);
  const { cx, cy, R, r } = WH;
  el("circle", { cx, cy, r: R, class: "wh-track" });
  /* arrows between neighbouring steps, clockwise; step 6 closes the loop back to step 1 */
  const gap = (r + 10) / R;
  for (let i = 0; i < 6; i++) {
    const a1 = whAng(i) + gap, a2 = whAng(i + 1) - gap;
    el("path", { d: `M${cx + R * Math.cos(a1)} ${cy + R * Math.sin(a1)} A${R} ${R} 0 0 1 ${cx + R * Math.cos(a2)} ${cy + R * Math.sin(a2)}`, class: "wh-arc", "marker-end": "url(#wh-ar)" });
  }
  /* a small marker travelling the ring (skipped when the viewer prefers reduced motion) */
  if (!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    const dot = el("circle", { r: 7, class: "wh-dot" });
    el("animateMotion", { dur: "14s", repeatCount: "indefinite", path: `M${cx} ${cy - R} A${R} ${R} 0 1 1 ${cx - 0.01} ${cy - R}` }, dot);
  }
  /* centre: the cost ledger */
  const c0 = el("g", { class: "wh-node wh-centre" + (sel === 0 ? " on" : ""), tabindex: 0 });
  el("circle", { cx, cy, r: 108, class: "wh-cbg" }, c0);
  el("circle", { cx, cy: cy - 50, r: 24, class: "wh-cbadge" }, c0);
  el("text", { x: cx, y: cy - 42, class: "wh-cdollar" }, c0, "$");
  el("text", { x: cx, y: cy + 4, class: "wh-ctitle" }, c0, EXPLAIN.name(0));
  const n0 = EXPLAIN.node(0);
  if (n0) el("text", { x: cx, y: cy + 32, class: "wh-csub" }, c0, n0.v);
  el("text", { x: cx, y: cy + 58, class: "wh-csub2" }, c0, t("wh.centre"));
  c0.addEventListener("click", () => onPick(0)); c0.addEventListener("keydown", e => { if (e.key === "Enter") onPick(0); });
  /* six steps */
  EXPLAIN.STEPS.forEach((n, i) => {
    const [x, y] = whPos(i), g = el("g", { class: "wh-node" + (n === sel ? " on" : "") + (n === EXPLAIN.KEEP ? " keep" : ""), tabindex: 0 });
    const tip = el("title", null, g, EXPLAIN.name(n));
    const nd = EXPLAIN.node(n); if (nd && nd.src) tip.textContent += " · " + t("xb.src") + ": " + nd.src;
    el("circle", { cx: x, cy: y, r: r + 7, class: "wh-ring" }, g);
    el("circle", { cx: x, cy: y, r, class: "wh-bg" }, g);
    el("text", { x, y: y + 10, class: "wh-num" }, g, String(n));
    const c = Math.cos(whAng(i)), side = Math.abs(c) > 0.3, lines = whLines(EXPLAIN.name(n));
    const anchor = side ? (c > 0 ? "start" : "end") : "middle", lx = side ? x + (c > 0 ? r + 14 : -(r + 14)) : x;
    const LH = 27, block = lines.length * LH + 32;
    /* top node: text above; bottom node: text below; side nodes: text beside, centred on the node */
    let y0 = side ? y - block / 2 + 18 : y < cy ? y - r - 14 - block + 18 : y + r + 30;
    lines.forEach((s, k) => el("text", { x: lx, y: y0 + k * LH, "text-anchor": anchor, class: "wh-name" }, g, s));
    if (nd && nd.v) el("text", { x: lx, y: y0 + lines.length * LH + 8, "text-anchor": anchor, class: "wh-val" + (nd.tone ? " " + nd.tone : "") }, g, nd.v);
    g.addEventListener("click", () => onPick(n)); g.addEventListener("keydown", e => { if (e.key === "Enter") onPick(n); });
  });
  return svg;
}

/* right panel for the selected step: question, answer, in → does → out, numbers, risk, button */
function wheelPanel(n) {
  const R = EXPLAIN.spec(n), stats = EXPLAIN.stats(n), vars = EXPLAIN.safe(R.vars, null);
  return h("div", { class: "wh-det" }, [
    h("div", { class: "xb-st", text: EXPLAIN.kicker(n) }),
    h("h2", null, [EXPLAIN.name(n), n === EXPLAIN.KEEP ? h("span", { class: "wh-tag", text: t("wh.keep") }) : null]),
    h("p", { class: "wh-q" }, [h("b", { text: t("st." + n + ".q") + " " }), t("st." + n + ".a", vars)]),
    EXPLAIN.io(n),
    stats.length ? h("div", { class: "xb-stats" }, stats.map(EXPLAIN.stat)) : null,
    h("p", { class: "xb-risk" }, [h("b", { text: t("xb.risk") + ": " }), t("st." + n + ".risk")]),
    h("a", { class: "wh-go", href: EXPLAIN.href(n), text: n ? t("wh.open", { n }) : t("wh.open0") + " →" })]);
}

/* the round-1 result, always under the title (brief 6): numbers and verdict from the index */
function resultStrip() {
  const R = EXPLAIN.read, a = R.run("C_70"), b = R.run("C70_R1"), d = R.decision();
  if (!a || !b) return null;
  return h("a", { class: "wh-result", href: EXPLAIN.href(6) }, [h("span", { class: "wh-rmark", text: "6" }),
    h("span", null, [h("b", { text: t("wh.result", { a: a.successes, b: b.successes, n: a.n }) }), " ", d === "F" ? t("wh.rule") : "", " ", h("span", { class: "dim", text: t("wh.prelim") })]),
    h("span", { class: "wh-rgo", text: t("wh.rgo") })]);
}

UI.route("home", async (body, params, qs) => {
  await SIMP(); document.title = "Humanoid Data Flywheel";
  const clamp = v => Math.min(6, Math.max(0, Math.round(+v)));
  let sel = qs.s != null && qs.s !== "" ? clamp(qs.s) : 1; if (Number.isNaN(sel)) sel = 1;
  const tour = qs.tour === "1";
  body.appendChild(h("div", { class: "wh-hero" }, [h("h1", { text: t("start.title") }), h("p", { text: t("start.lead") })]));
  const strip = resultStrip(); if (strip) body.appendChild(strip);
  const wheelBox = h("div", { class: "wh-card wh-wheel" }), detBox = h("div", { class: "wh-card" });
  let timer = null;
  /* fit the viewBox to what was drawn (label widths differ by language), so the text is as large as the column allows */
  const fit = (svg, k) => { if (!svg.isConnected) { if ((k || 0) < 120) requestAnimationFrame(() => fit(svg, (k || 0) + 1)); return; }
    try { const b = svg.getBBox(); if (b.width) svg.setAttribute("viewBox", [b.x - 8, b.y - 8, b.width + 16, b.height + 16].map(Math.round).join(" ")); } catch (e) { /* not rendered */ } };
  const draw = () => { const svg = wheelSvg(sel, pick); wheelBox.replaceChildren(svg); fit(svg); detBox.replaceChildren(wheelPanel(sel)); };
  const setUrl = () => { const q = "s=" + sel + (timer ? "&tour=1" : ""); history.replaceState(null, "", "#/home?" + q); };
  function pick(n, fromTour) { if (!fromTour && timer) { clearInterval(timer); timer = null; } sel = n; draw(); setUrl(); }
  /* ←/→ walk the six steps; from the centre → goes to 1 and ← to 6 */
  UI.keys.bind({ ArrowRight: () => pick(sel >= 6 ? 1 : sel + 1), ArrowLeft: () => pick(sel <= 1 ? 6 : sel - 1) }, "page");
  body.appendChild(h("div", { class: "wh-hub" }, [wheelBox, detBox]));
  draw();
  if (tour) {
    const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    timer = setInterval(() => { if (!body.isConnected) { clearInterval(timer); timer = null; return; } pick(sel >= 6 ? 0 : sel + 1, true); }, reduce ? 12000 : 7000);
  }
  /* follow one failure */
  const F = EXPLAIN.read.follow(), c70 = F.runs && F.runs.C_70;
  if (c70) body.appendChild(h("a", { class: "st-follow", href: "#/follow" }, [h("div", null, [failRing(c70, F.tol, false), h("div", { class: "dim fr-cap", text: t("fol.ring") })]),
    h("div", null, [h("b", { text: t("start.follow.t") }), h("p", { text: t("start.follow.d", { lv: F.level, seed: String(F.seed), d: fmtCm(c70.distance_m), y: fmtDeg(c70.yaw_error_deg) }) }), h("span", { class: "btnlike", text: t("start.follow.go") })])]));
  /* the team's operational view, never on the demo laptop */
  if (!UI.locked) {
    body.appendChild(h("h2", { class: "st-today", text: t("start.today") }));
    const today = h("div"); body.appendChild(today);
    await pageHome(today);
  }
  document.title = "Humanoid Data Flywheel";
});

/* ---------- #/diagnose placeholder (step 5). The step-5 page replaces it: register UI.route("diagnose", fn)
   in your own file; this one is added only when nothing else registered "diagnose" by page load. ---------- */
function diagnosePlaceholder(body) {
  /* the cluster cards are the step figure (EXPLAIN step 5); the technical part only names the source for now */
  body.appendChild(h("p", { class: "dim", text: t("xb.src") + ": " + (((STORY && STORY.round) || {}).source || "story.json · round.clusters") }));
}
document.addEventListener("DOMContentLoaded", () => { if (!UI.routes().includes("diagnose")) UI.route("diagnose", diagnosePlaceholder); });
