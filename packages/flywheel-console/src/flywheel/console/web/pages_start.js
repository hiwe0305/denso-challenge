/* "Follow one failure" (one-site design 6.7) and the failure ring it shares with the home wheel (pages_wheel.js).
   Numbers: CAT (catalog.json), STORY (story.json: pair, round, follow, h1m), SIMD (sim.json). Text: t(). */
"use strict";

/* failure ring: the record keeps only how far and how much turned, never the direction (design 6.7) */
function failRing(r, tol, small, capM) {
  const NS = "http://www.w3.org/2000/svg", W = small ? 120 : 360, H = small ? 64 : 220, cx = small ? 32 : 115, cy = H / 2, R = small ? 28 : 92;
  const el = (n, a) => { const x = document.createElementNS(NS, n); Object.entries(a || {}).forEach(([k, v]) => x.setAttribute(k, v)); return x; };
  const txt = (x, y, s, cls) => { const n = el("text", { x, y, class: cls || "fr-l" }); n.textContent = s; return n; };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "failring" + (small ? " small" : "") });
  /* capM: one shared scale for a column of small rings; farther than capM is drawn at the edge with ▸ */
  const d = r.distance_m, td = tol.distance_m, s = R / (capM || Math.max(d || 0, td)), ok = !!r.success, over = capM && d > capM;
  svg.appendChild(el("circle", { cx, cy, r: td * s, class: "fr-tol" }));
  svg.appendChild(el("circle", { cx, cy, r: Math.max(2, Math.min(d, capM || d) * s), class: (ok ? "fr-at ok" : "fr-at") + (over ? " over" : "") }));
  if (over) svg.appendChild(txt(cx + R + 2, cy + 4, "▸", "fr-lbad"));
  svg.appendChild(el("line", { x1: cx - 6, y1: cy, x2: cx + 6, y2: cy, class: "fr-x" })); svg.appendChild(el("line", { x1: cx, y1: cy - 6, x2: cx, y2: cy + 6, class: "fr-x" }));
  if (!small) {
    svg.appendChild(txt(cx, cy - td * s + 14, t("fol.tol") + " " + UI.fmt(td * 100, "int") + " cm", "fr-lok"));
    svg.appendChild(txt(cx, cy + d * s + 16, UI.fmt(d * 100, "float1") + " cm", "fr-lbad"));
  }
  /* yaw dial: green wedge = allowed, line = measured */
  const gx = small ? 92 : 285, gy = small ? cy + 12 : cy + 30, gr = small ? 22 : 60, rad = a => (a - 90) * Math.PI / 180;
  const pt = a => [gx + gr * Math.cos(rad(a)), gy + gr * Math.sin(rad(a))];
  const [ax, ay] = pt(tol.yaw_error_deg), [bx, by] = pt(r.yaw_error_deg);
  svg.appendChild(el("path", { d: `M${gx} ${gy} L${gx} ${gy - gr} A${gr} ${gr} 0 0 1 ${ax} ${ay} Z`, class: "fr-wedge" }));
  svg.appendChild(el("line", { x1: gx, y1: gy, x2: gx, y2: gy - gr, class: "fr-zero" }));
  svg.appendChild(el("line", { x1: gx, y1: gy, x2: bx, y2: by, class: r.yaw_error_deg <= tol.yaw_error_deg ? "fr-yaw ok" : "fr-yaw" }));
  if (!small) { svg.appendChild(txt(gx, gy + 18, t("fol.yaw", { y: fmtDeg(r.yaw_error_deg), ty: fmtDeg(tol.yaw_error_deg) }).split(" (")[0])); svg.appendChild(txt(ax + 4, ay - 6, fmtDeg(tol.yaw_error_deg) + "°", "fr-lok")); }
  return svg;
}
const fmtCm = d => UI.fmt(d * 100, "float1"), fmtDeg = y => UI.fmt(y, "float1");

/* ---------- #/follow ---------- */
UI.route("follow", async (body, params, qs) => {
  await SIMP(); document.title = "FW · " + t("fol.title");
  /* without the retest result the story ends at the data order: three screens, not five */
  const F = EXPLAIN.read.follow(), R = EXPLAIN.read, MAX = TASK.withheld().length ? 3 : 5, S = Math.min(MAX, Math.max(1, Math.round(+qs.s) || 1));
  if (!F.runs || !F.runs[TASK.baseline()]) { body.appendChild(h("p", { class: "dim", text: t("sim.empty") })); return; }
  const go2 = s => go("follow?s=" + s);
  UI.keys.bind({ ArrowRight: () => S < MAX && go2(S + 1), ArrowLeft: () => S > 1 && go2(S - 1) }, "page");
  const steps = h("div", { class: "fol-steps" }, [1, 2, 3, 4, 5].slice(0, MAX).map(i => h("a", { class: i === S ? "on" : i < S ? "done" : "", href: "#/follow?s=" + i, text: t("fol.s" + i + ".t") })));
  body.appendChild(h("div", { class: "sim-head" }, [h("h1", { text: t("fol.title") }), h("span", { class: "dim", text: t("fol.case", { lv: F.level, seed: String(F.seed) }) }), steps]));
  const tol = F.tol, td = UI.fmt(tol.distance_m * 100, "int"), ty = UI.fmt(tol.yaw_error_deg, "int"), A = TASK.baseline(), B = TASK.after(), c70 = F.runs[A];
  const scr = h("div", { class: "fol-screen" }), link = n => h("div", { class: "fol-link" }, [h("span", { class: "sn", text: String(n) }), h("a", { href: EXPLAIN.href(n), text: t("fol.station", { n, name: EXPLAIN.name(n) }) })]);
  const cluster = SIMD.episodes.filter(e => e.for && e.for[0] === F.level && e.for[1] === F.seed);
  const prior = cluster.filter(e => e.label === "prev"), fresh = cluster.filter(e => e.label === "round");
  const vid = e => h("div", { class: "fol-vid" }, [hoverVideo(e.poster ? "/simmedia/" + e.poster : null, e.video ? "/simmedia/" + e.video : null), h("a", { href: "#/sim/" + e.i, text: t("sim.ep", { i: e.i }) })]);
  if (S === 1) {
    scr.append(failRing(c70, tol), h("div", null, [h("p", { class: "fol-a", text: t("fol.s1.a", { run: EXPLAIN.runName(A), d: fmtCm(c70.distance_m), y: fmtDeg(c70.yaw_error_deg), td, ty }) }),
      h("p", { class: "dim", text: "◌ " + t("fol.ring") }), h("p", { class: "dim", text: "◔ " + t("fol.yaw", { y: fmtDeg(c70.yaw_error_deg), ty }) }), link(4)]));
  } else if (S === 2) {
    const c1 = ((STORY.round || {}).clusters || []).find(c => c.id === "c1") || {};
    scr.append(h("div", { class: "fol-loop" }, [1, 2, 3].map(i => h("span", { class: "on", text: i + " " + t("fig.loop." + i) }))), h("div", null, [h("p", { class: "fol-a", text: t("fol.s2.a", { k: c1.n, m: c1.failures }) }),
      prior.length ? h("p", { text: t("fol.s2.b", { base: EXPLAIN.runName(A), ep: String(prior[0].i) }) }) : null, h("div", { class: "fol-vids one" }, prior.slice(0, 1).map(vid)), link(5)]));
  } else if (S === 3) {
    /* attempts per place failure come from the round plan (tray.md 20.14); the episodes shown are the ones selected into the cut */
    const per = ((STORY.round || {}).per_case || {}).place;
    scr.append(h("div", { class: "fol-wide" }, [h("p", { class: "fol-a", text: t("fol.s3.a", { n: per, k: fresh.length, after: EXPLAIN.runName(B) }) }), h("p", { class: "dim", text: t("fol.hover") }), h("div", { class: "fol-vids" }, fresh.map(vid)), MAX < 5 ? h("p", { class: "dim", text: t("wh.withheld") }) : null, link(6)]));
  } else if (S === 4) {
    const order = [A, B, ...TASK.controls()].filter(id => F.runs[id]), CAP = 0.15;   /* one scale for the column: 15 cm */
    const why = r => r.success ? "" : r.failure ? " · " + t("fail." + r.failure) : "";
    const tb = h("table", { class: "xb-tbl fol-tbl" }, [h("thead", null, h("tr", null, ["fol.col.run", "fol.col.res", "fol.col.d", "fol.col.y", "fol.col.data"].map(k => h("th", { text: t(k) })).concat([h("th")]))),
      h("tbody", null, order.map(id => { const r = F.runs[id]; return h("tr", { class: id === B ? "hot" : "" }, [h("td", { title: id }, h("b", { text: EXPLAIN.runName(id) })),
        h("td", { class: r.success ? "c-ok" : "c-bad", text: (r.success ? "✓ " + t("fol.pass") : "✕ " + t("fol.fail")) + why(r) }), h("td", { text: fmtCm(r.distance_m) }), h("td", { text: fmtDeg(r.yaw_error_deg) }),
        h("td", { text: id === B ? t("fol.yes") : t("fol.no") }), h("td", null, failRing(r, tol, true, CAP))]); }))]);
    /* the human-video model on the largest set: it passed without reaching table B (L-REACH-B), noted under the table */
    const bAllId = EXPLAIN.read.like(A, { episodes: "max", human_video: true }), bAll = F.runs[bAllId];
    scr.append(h("div", { class: "fol-wide" }, [h("p", { class: "fol-a", text: t("fol.s4.a") }), tb, bAll && bAll.success && bAll.reach_b === false ? h("p", { class: "dim", text: "⚠ " + t("fol.s4.note", { ctl: EXPLAIN.runName(bAllId) }) }) : null, h("p", { class: "dim", text: t("fol.ringScale", { c: Math.round(CAP * 100) }) }), link(4)]));
  } else {
    const a = R.base(), b = R.after();
    scr.append(h("div", { class: "fol-wide" }, [a && b ? h("p", { class: "fol-a", text: t("fol.s5.a", { a: a.successes, b: b.successes, n: a.n }) }) : null, h("p", { class: "dim", text: t("wh.prelim") }), EXPLAIN.r3Table(), EXPLAIN.verdict()]));
  }
  body.appendChild(scr);
  /* one obvious next action on every screen: the big "Next →" (on the last screen: step 6) */
  body.appendChild(h("div", { class: "fol-nav" }, [S > 1 ? h("button", { class: "fol-back", text: t("fol.prev"), onclick: () => go2(S - 1) }) : h("span"),
    h("span", { class: "dim fol-count", text: S + " / " + MAX }),
    S < MAX ? h("button", { class: "fol-go", text: t("fol.next"), onclick: () => go2(S + 1) }) : h("a", { class: "fol-go", href: EXPLAIN.href(6), text: t("fol.station", { n: 6, name: EXPLAIN.name(6) }) })]));
});
