/* Simulation library (one-site design 7) and the step-1 face (workstream C: three kinds of data, latest training mix, real examples).
   Data: data/sim.json from index/sim.py; sampled media at /simmedia/; egocentric cards from the /ego/ viewer.
   Routes: #/sim (?tab=gallery|quality|all, ?tag=, ?lv=), #/sim/:i. */
"use strict";
var SIMD = null;
const SIMP = () => SIMD ? Promise.resolve(SIMD) : fetch("data/sim.json").then(r => r.ok ? r.json() : null).catch(() => null)
  .then(d => (SIMD = d || { episodes: [], teleop: [], parts: [], cuts: {}, batch: {} }));
let EGO = null;
const EGOP = () => EGO ? Promise.resolve(EGO) : fetch("/ego/data/index.js").then(r => r.ok ? r.text() : "").then(s => {
  try { return JSON.parse(s.slice(s.indexOf("=") + 1).trim().replace(/;\s*$/, "")); } catch (e) { return null; }
}).catch(() => null).then(d => (EGO = d || { episodes: [] }));

const SIM_TAGS = ["coverage", "prev", "round", "teleop"];
/* poster that plays its video while the mouse is over it */
function hoverVideo(poster, video, cls) {
  const box = h("div", { class: "hv " + (cls || "") }, [poster ? h("img", { src: poster, alt: "", loading: "lazy" }) : h("div", { class: "hv-none" })]);
  if (!video) return box;
  let v = null;
  box.onmouseenter = () => { if (!v) { v = h("video", { src: video, muted: true, loop: true, playsinline: true, preload: "none" }); v.muted = true; box.appendChild(v); } v.play().catch(() => {}); box.classList.add("on"); };
  box.onmouseleave = () => { if (v) v.pause(); box.classList.remove("on"); };
  return box;
}
const simSrc = rel => rel ? "/simmedia/" + rel : null;   /* a poster can be missing (unreadable video) */
const simItems = () => [...SIMD.episodes.filter(e => e.video), ...(SIMD.teleop || [])];

/* ---------- step 1 face (workstream C): three kinds side by side, what the latest training used, real examples ----------
   Counts come from catalog.json (CAT), story.json (STORY) and sim.json (SIMD). Clip media: the /ego/ export (built from
   de-identified clips only), index posters, and the existing /api/ego_strip filmstrip for a rejected clip (de-identified only). */
/* @budget-skip-start data values, not text */ const TEAM = "Team tray", PIPE = "pipeline source"; /* @budget-skip-end */
const GRP = { coverage: "d1.grp.coverage", prev: "d1.grp.prev", round: "d1.grp.round", teleop: "d1.grp.teleop" };
const GRPD = { coverage: "d1.grp.coverage.d", prev: "d1.grp.prev.d", round: "d1.grp.round.d" };
const simTag = l => h("span", { class: "lb lb-" + l, text: t(GRP[l] || GRP.coverage) });
/* a targeted episode names the failed step in its cluster id: "place-pose-L1-1000189" -> place-pose */
const FAIL = { "place-pose": "d1.fail.pose", place: "d1.fail.place", approach_a: "d1.fail.approach" };
const simStep = e => { const m = /^(.*)-L\d+-\d+$/.exec(e.cluster || ""); return m && FAIL[m[1]] ? t(FAIL[m[1]]) : null; };
/* one plain line per sim card: the "situation" (seed) it plays, or the failed test situation it re-plays */
const simLine = e => e.for && simStep(e) ? t("d1.redo", { s: String(e.for[1]), step: simStep(e) }) : t("d1.case", { s: String(e.seed == null ? "–" : e.seed), lv: e.level });
const D1 = (() => {
  const N = v => v == null ? null : UI.fmt(v, "int");
  const tot = g => CAT && CAT.totals && CAT.totals[g] ? CAT.totals[g].episodes : null;
  const rows = () => (CAT && CAT.rows) || [];
  const row = id => rows().find(r => r.id === id);
  const tip = s => t("xb.src") + ": " + s;
  const runs = () => (STORY && STORY.demo && STORY.demo.models && STORY.demo.models.runs) || {};
  const big = (n, unit, s) => h("div", { class: "d1-n", title: tip(s) }, [h("b", { text: N(n) }), h("span", { text: unit })]);
  /* person-hours per episode, a three-dot scale (qualitative, no number) */
  const meter = (k, lit) => h("div", { class: "d1-meter" }, [h("span", { text: t("d1.hours") }), h("i", null, [0, 1, 2].map(i => h("em", { class: i < lit ? "on" : "" }))), h("b", { text: t(k) })]);
  const autoVideo = (poster, video) => {
    if (!video) return h("div", { class: "hv" }, poster ? h("img", { src: poster, alt: "" }) : null);
    const v = h("video", { src: video, poster, muted: true, loop: true, autoplay: true, playsinline: true, preload: "metadata" });
    v.muted = true; return h("div", { class: "hv on" }, v);
  };

  /* ---- the three columns ---- */
  function columns() {
    const ego = (EGO && EGO.episodes) || [], R = runs(), ids = Object.keys(R);
    const egoTeam = ego.filter(e => e.source === TEAM), clip = egoTeam.filter(e => e.qa === "pass").slice(-1)[0] || egoTeam[0] || ego[0];
    const egodex = row("egodex-da30"), teamN = (tot("egocentric") || 0) - (egodex ? egodex.episodes : 0);
    /* the export the vision pre-training read (its child is the stage-1 run) */
    const vis = rows().find(r => r.group === "egocentric" && r.kind === "export" && r.status === "current" && (r.children || []).some(c => /stage1/.test(c)));
    const withVideo = ids.filter(id => R[id].human_video), sizes = [...new Set(ids.map(id => R[id].episodes))].sort((a, b) => b - a);
    const two = row("psi-two-table"), hug = row("psi-hug");
    const teleTray = rows().filter(r => r.group === "teleop" && r.unique && r.task === "tray").reduce((a, r) => a + (r.episodes || 0), 0);
    const sim = SIMD.episodes.find(e => e.video && e.label === "round") || SIMD.episodes.find(e => e.video), tel = (SIMD.teleop || [])[0];
    const K = { ego: ["d1.k.ego", "d1.k.ego.sub"], sim: ["d1.k.sim", "d1.k.sim.sub"], tele: ["d1.k.tele", "d1.k.tele.sub"] };
    const col = (k, media, n, unit, s, split, cost, lit, hk, use, extra, href) => h("div", { class: "d1-col d1-" + k }, [
      h("div", { class: "d1-kind" }, [h("b", { text: t(K[k][0]) }), h("span", { text: t(K[k][1]) })]),
      media, big(n, unit, s), h("div", { class: "d1-split", text: split }),
      h("div", { class: "d1-row" }, [h("small", { text: t("d1.cost") }), h("p", { text: cost }), meter(hk, lit)]),
      h("div", { class: "d1-row use" }, [h("small", { text: t("d1.use") }), extra, h("p", { text: use })]),
      h("a", { class: "d1-open", href, text: t("d1.open") })]);
    return h("div", { class: "d1-cols" }, [
      col("ego", autoVideo(clip ? "/ego/" + clip.poster : null, clip ? "/ego/media/" + clip.id + ".mp4" : null), tot("egocentric"), t("d1.unit.clip"), "catalog.json · totals.egocentric",
        t("d1.ego.split", { a: egodex ? egodex.episodes : null, b: teamN }), t("d1.ego.cost"), 1, "d1.hours.ego",
        t("d1.ego.use", { c: vis ? vis.episodes : null, m: withVideo.length, n: ids.length }), null, "/ego/"),
      col("sim", autoVideo(sim ? simSrc(sim.poster) : null, sim ? "/simmedia/" + sim.video : null), (tot("s1") || 0) + (tot("s2") || 0) || null, t("d1.unit.ep"), "catalog.json · totals.s1 + totals.s2",
        t("d1.sim.split", { a: tot("s1"), b: tot("s2") }), t("d1.sim.cost"), 0, "d1.hours.sim",
        t("d1.sim.use", { n: ids.length, a: sizes[0], b: sizes[sizes.length - 1] }), null, "#/sim"),
      col("tele", autoVideo(tel ? simSrc(tel.poster) : null, tel ? "/simmedia/" + tel.video : null), tot("teleop"), t("d1.unit.ep"), "catalog.json · totals.teleop",
        t("d1.tele.split", { a: two ? two.episodes : null, b: hug ? hug.episodes : null }), t("d1.tele.cost"), 3, "d1.hours.tele",
        t("d1.tele.use"), h("div", { class: "d1-zero", title: tip("catalog.json · teleop rows, task = tray") }, [h("b", { text: N(teleTray) }), h("span", { text: t("d1.tele.zero") })]), "#/sim?tag=teleop")]);
  }

  /* ---- what the latest training used: one bar, three parts ---- */
  function mix() {
    const parts = SIMD.parts || [], all = parts.reduce((a, p) => a + p.n, 0), r = runs().C70_R1;
    if (!all) return null;
    const tele = parts.filter(p => p.label === "teleop").reduce((a, p) => a + p.n, 0);
    return h("div", { class: "d1-mix" }, [
      h("div", { class: "d1-mix-head" }, [h("h3", { text: t("d1.mix.t") }), h("span", { class: "d1-mix-n", title: tip("sim.json · parts (C70_R1)") }, [h("b", { text: N(all) }), t("d1.mix.unit")])]),
      h("p", { class: "d1-mix-sub", text: t("d1.mix.sub", { v: r ? r.human_clips : null, p: tele }) }),
      h("div", { class: "d1-mix-bar" }, parts.map(p => h("div", { class: "lb-" + p.label, style: { flex: String(p.n) }, title: tip("sim.json · parts · " + p.release) }, [
        h("b", { text: N(p.n) }), h("span", { text: t(GRP[p.label] || GRP.coverage) }), h("small", { text: GRPD[p.label] ? t(GRPD[p.label]) : "" })])))]);
  }

  /* ---- human video examples: accepted, accepted with a note, rejected (with the plain reason) ---- */
  const ST = { pass: ["d1.st.pass", "ok"], flag: ["d1.st.flag", "note"], reject: ["d1.st.reject", "bad"] };
  const WHY = { hand_out_of_frame: "d1.why.out", segment_count: "d1.why.count", hand_pose_nan: "d1.why.nan", pose_low_confidence: "d1.why.conf", camera_jitter_deg_s: "d1.why.jitter", segment_ambiguous: "d1.why.amb", segments: "d1.why.count" };
  const ORDER = Object.keys(WHY), NOTE = { "d1.why.nan": "d1.why.nan.note" };
  const reasons = (xs, k) => [...new Set((xs || []).filter(x => WHY[x]).sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b)).map(x => WHY[x]))].slice(0, k);
  const pill = q => h("span", { class: "d1-pill " + (ST[q] || ST.flag)[1], text: t((ST[q] || ST.flag)[0]) });
  const egoCard = (e, why) => h("div", { class: "d1-ex" }, [hoverVideo("/ego/" + e.poster, "/ego/media/" + e.id + ".mp4"),
    h("div", { class: "d1-ex-b" }, [h("div", { class: "d1-ex-top" }, [pill(e.qa), h("span", { class: "dim", text: t(e.source === TEAM ? "d1.src.team" : "d1.src.egodex") })]),
      why.length ? h("p", { class: "d1-why", text: why.map(k => t(k)).join(" · ") }) : null,
      h("p", { class: "d1-en", lang: "en", text: String(e.title || "") })])]);
  /* no playable video for a rejected clip: hovering flips through six frames of the de-identified filmstrip */
  const rejCard = (e, work) => h("div", { class: "d1-ex rej", title: t("d1.ex.film") }, [h("div", { class: "hv" }, [e.poster ? h("img", { src: e.poster, alt: "", loading: "lazy" }) : null,
    h("div", { class: "d1-flip", style: { backgroundImage: "url(/api/ego_strip?work=" + encodeURIComponent(work) + "&ep=" + encodeURIComponent(e.id) + "&n=6)" } })]),
    h("div", { class: "d1-ex-b" }, [h("div", { class: "d1-ex-top" }, [pill("reject"), h("span", { class: "dim", text: t("d1.src.team") })]),
      h("p", { class: "d1-why", text: reasons(e.reasons, 2).map(k => t(k)).join(" · ") })])]);
  const jget = u => fetch(u).then(r => r.ok ? r.json() : null).catch(() => null);
  function egoExamples() {
    const m = (STORY && STORY.h1m) || {}, d = m.decisions || {}, ego = (EGO && EGO.episodes) || [];
    const pick = (src, q, k) => ego.filter(e => e.source === src && e.qa === q).slice(0, k);
    const ok = [...pick(TEAM, "pass", 2), ...pick("EgoDex", "pass", 1)], note = pick(TEAM, "flag", 1);
    const grid = h("div", { class: "d1-ex-grid" }, [...ok.map(e => egoCard(e, [])), ...note.map(e => egoCard(e, []))]);
    /* reasons of the flagged clip and the rejected clips come from the index (data/ds/<id>/episodes.json) */
    const exp = rows().find(r => r.group === "egocentric" && r.kind === "export" && r.view === "ego" && r.task === "tray" && r.status === "current");
    const srcRow = rows().find(r => r.group === "egocentric" && r.kind === PIPE && r.status === "current" && r.task === "tray" && r.qa_counts && r.qa_counts.reject);
    if (note.length && exp) jget("data/ds/" + exp.id + "/episodes.json").then(xs => { const x = (xs || []).find(y => y.id === note[0].id);
      if (x && grid.children[ok.length]) grid.replaceChild(egoCard(note[0], reasons(x.reasons, 1).map(k => NOTE[k]).filter(Boolean)), grid.children[ok.length]); });
    if (srcRow) jget("data/ds/" + srcRow.id + "/episodes.json").then(xs => {
      const rank = x => Math.min(99, ...(x.reasons || []).map(r => ORDER.indexOf(r)).filter(i => i >= 0));
      const rej = (xs || []).filter(x => x.qa === "reject" && x.poster).sort((a, b) => rank(a) - rank(b));
      rej.slice(0, 3).forEach(x => grid.appendChild(rejCard(x, srcRow.id))); });
    const parts = [[d.exported, "d1.qa.pass", "ok"], [d.rejected_qa, "d1.qa.rej", "bad"], [d.excluded, "d1.qa.exc", "ex"]].filter(x => x[0]);
    return h("div", { class: "d1-sec" }, [h("div", { class: "d1-sec-head" }, [h("h3", { text: t("d1.ex.ego") }), h("a", { href: "/ego/", text: t("d1.ex.all.ego", { n: d.exported }) })]),
      h("div", { class: "d1-qa", title: tip("story.json · h1m.decisions") }, [h("span", { class: "d1-qa-in", text: t("d1.qa.in", { n: m.clips }) }),
        h("div", { class: "d1-qa-r" }, [h("div", { class: "d1-qa-bar" }, parts.map(([n, , c]) => h("i", { class: c, style: { flex: String(n) } }))),
          h("div", { class: "d1-qa-key" }, parts.map(([n, k, c]) => h("span", { class: c }, [h("i"), h("b", { text: N(n) }), t(k)])))])]),
      grid]);
  }

  /* ---- simulation examples: four per group, posters step through the episode (index/sim.py) ---- */
  const simCard = e => h("a", { class: "d1-ex sim", href: "#/sim/" + e.i }, [hoverVideo(simSrc(e.poster), "/simmedia/" + e.video),
    h("div", { class: "d1-ex-b" }, [h("div", { class: "d1-ex-top" }, [h("b", { text: t("d1.ep", { i: e.i }) }), h("span", { class: "dim", text: t("sim.level", { lv: e.level }) })]),
      h("p", { class: "d1-why", title: e.cluster || null, text: simLine(e) })])]);
  /* four cards that differ: a new situation and a new poster position first, then any new situation, then the rest */
  const pick4 = eps => {
    const out = [], seen = new Set(), at = new Set(), pos = e => (/\.p(\d+)\.jpg$/.exec(e.poster || "") || [])[1];
    const pass = need => eps.forEach(e => { if (out.length < 4 && !out.includes(e) && need(e)) { out.push(e); seen.add(e.cluster || e.i); at.add(pos(e)); } });
    pass(e => !seen.has(e.cluster || e.i) && !at.has(pos(e))); pass(e => !seen.has(e.cluster || e.i)); pass(() => true);
    return out.sort((a, b) => a.i - b.i);
  };
  function simExamples() {
    const parts = SIMD.parts || [];
    return h("div", { class: "d1-sec" }, [h("div", { class: "d1-sec-head" }, [h("h3", { text: t("d1.ex.sim") }), h("a", { href: "#/sim", text: t("d1.ex.all.sim") })]),
      ...parts.map(p => { const xs = pick4(SIMD.episodes.filter(e => e.video && e.label === p.label));
        return xs.length ? h("div", { class: "d1-grp" }, [h("div", { class: "d1-grp-head" }, [simTag(p.label), h("span", { class: "dim", text: t("d1.grp.of", { n: p.n }) }), GRPD[p.label] ? h("span", { class: "dim", text: "· " + t(GRPD[p.label]) }) : null]),
          h("div", { class: "d1-ex-grid" }, xs.map(simCard))]) : null; })]);
  }
  function teleExamples() {
    const xs = (SIMD.teleop || []).slice(0, 4);
    return xs.length ? h("div", { class: "d1-sec" }, [h("div", { class: "d1-sec-head" }, [h("h3", { text: t("d1.ex.tele") }), h("a", { href: "#/sim?tag=teleop", text: t("d1.ex.all.tele") })]),
      h("div", { class: "d1-ex-grid" }, xs.map(e => h("div", { class: "d1-ex" }, [hoverVideo(simSrc(e.poster), "/simmedia/" + e.video), h("div", { class: "d1-ex-b" }, [h("p", { class: "d1-why", text: t("sim.teleop.task") })])])))]) : null;
  }
  return { columns, mix, egoExamples, simExamples, teleExamples, tot };
})();

EXPLAIN.register(1, {
  fig: () => h("div", { class: "d1" }, [
    h("div", { class: "d1-lead" }, [h("h3", { text: t("d1.kinds") }), h("span", { class: "dim", title: t("xb.src") + ": catalog.json · totals.all", text: t("d1.store", { n: D1.tot("all") }) })]),
    D1.columns(), D1.mix(),
    h("div", { class: "d1-lead ex" }, [h("h3", { text: t("d1.ex.t") }), h("span", { class: "dim", text: t("d1.hover") })]),
    D1.egoExamples(), D1.simExamples(), D1.teleExamples()]),
});

/* ---------- #/sim ---------- */
UI.route("sim", async (body, params, qs) => {
  await Promise.all([SIMP(), EGOP()]); document.title = "FW · " + t("sim.title");
  const tab = qs.tab || "gallery";
  const tabs = h("div", { class: "sim-tabs" }, ["gallery", "quality", "all"].map(k => h("a", { class: k === tab ? "on" : "", href: "#/sim?tab=" + k, text: t("sim.tab." + k) })));
  body.appendChild(h("div", { class: "sim-head" }, [h("h1", { text: t("sim.title") }), h("span", { class: "dim", title: "C70_R1" + (SIMD.sha8 ? " · sha256 " + SIMD.sha8 : ""), text: t("d1.lib.sub", { n: (SIMD.parts || []).reduce((a, p) => a + p.n, 0), v: SIMD.episodes.filter(e => e.video).length }) }), tabs]));
  if (!SIMD.episodes.length && !(SIMD.teleop || []).length) { body.appendChild(h("p", { class: "dim", text: t("sim.empty") })); return; }
  if (tab === "quality") return simQuality(body);
  if (tab === "all") return simAll(body);
  const tag = qs.tag || "", lv = qs.lv || "";
  const q = o => "#/sim?" + Object.entries(Object.assign({ tag, lv }, o)).filter(([, v]) => v).map(([k, v]) => k + "=" + v).join("&");
  const chip = (on, label, href) => h("a", { class: "chip" + (on ? " on" : ""), href, text: label });
  body.appendChild(h("div", { class: "sim-filter" }, [chip(!tag, t("sim.filter.tags"), q({ tag: "" })), ...SIM_TAGS.map(k => chip(tag === k, t(GRP[k]), q({ tag: k }))), h("span", { class: "sep" }),
    chip(!lv, t("sim.filter.levels"), q({ lv: "" })), chip(lv === "1", t("sim.level", { lv: 1 }), q({ lv: "1" })), chip(lv === "2", t("sim.level", { lv: 2 }), q({ lv: "2" }))]));
  const items = simItems().filter(e => (!tag || e.label === tag) && (!lv || String(e.level) === lv));
  body.appendChild(h("div", { class: "sim-grid" }, items.map(e => h(e.label === "teleop" ? "div" : "a", { class: "sim-card", href: e.label === "teleop" ? null : "#/sim/" + e.i }, [
    hoverVideo(simSrc(e.poster), "/simmedia/" + e.video), h("div", { class: "sim-cap" }, [simTag(e.label), e.label === "teleop" ? null : h("b", { text: t("d1.ep", { i: e.i }) }), e.level ? h("span", { class: "dim", text: t("sim.level", { lv: e.level }) }) : null]),
    h("div", { class: "dim", title: e.cluster || null, text: e.label === "teleop" ? t("sim.teleop.task") : simLine(e) })]))));
});

/* both panels describe the same batch: this round's targeted generation (tray.md 20.16, via cited.yaml) */
function simQuality(body) {
  const R = (STORY && STORY.round) || {}, c = R.chain || {}, pf = Object.entries(R.planner_failures || {}).sort((x, y) => y[1] - x[1]), lost = pf.reduce((a, x) => a + x[1], 0);
  body.appendChild(h("div", { class: "sim-two" }, [
    EXPLAIN.chain(t("sim.chain"), [["fig.c.generated", c.generated], ["fig.c.recorded", c.recorded], ["fig.c.qa", c.qa_pass], ["fig.c.quality", c.quality], ["fig.c.selected", c.selected, "ok"]]),
    lost ? h("div", { class: "xb-chain", title: t("xb.src") + ": " + (R.source || "story.json · round") }, [h("div", { class: "xb-cap", text: t("sim.planner", { n: lost }) }),
      ...pf.map(([k, v]) => h("div", { class: "xb-bar bad", title: k }, [h("i", { style: { width: Math.max(2, v / lost * 100) + "%" } }), h("b", { text: UI.fmt(v, "int") }), h("span", { text: t("fail." + k) })]))]) : null]));
}

function simAll(body) {
  const tb = h("table", { class: "xb-tbl sim-all" }, [h("thead", null, h("tr", null, ["sim.col.i", "sim.col.label", "sim.col.cluster", "sim.col.level", "sim.col.len"].map(k => h("th", { text: t(k) })).concat([h("th", { text: "▶" })])))]);
  const tbody = h("tbody");
  SIMD.episodes.forEach(e => tbody.appendChild(h("tr", { class: "click", onclick: () => go("sim/" + e.i) }, [h("td", { text: String(e.i) }), h("td", null, simTag(e.label)), h("td", { class: "mono", text: e.cluster || "" }), h("td", { text: e.level == null ? "" : String(e.level) }), h("td", { text: UI.fmt(e.len, "int") }), h("td", { text: e.video ? "▶" : "" })])));
  tb.appendChild(tbody); body.appendChild(tb);
}

/* ---------- #/sim/:i ---------- */
/* top view in metres: tray at start, target zone, robot spawn and heading (tray.sample) */
function simTopView(e) {
  const NS = "http://www.w3.org/2000/svg", W = 640, H = 220, sc = 220, cx = W / 2, cy = H / 2;
  const X = x => cx - x * sc, Y = y => cy - y * sc;   // table A (positive x) drawn on the left
  const el = (n, a, kids) => { const x = document.createElementNS(NS, n); Object.entries(a || {}).forEach(([k, v]) => x.setAttribute(k, v)); (kids || []).forEach(k => x.appendChild(k)); return x; };
  const txt = (x, y, s, cls) => { const n = el("text", { x, y, class: cls || "tv-l" }); n.textContent = s; return n; };
  const box = (p, cls, label) => { const g = el("g", { transform: `translate(${X(p.x)} ${Y(p.y)}) rotate(${-(p.yaw || 0) * 180 / Math.PI})` }, [el("rect", { x: -33, y: -24, width: 66, height: 48, rx: 4, class: cls })]);
    return el("g", null, [g, txt(X(p.x), Y(p.y) + 44, label)]); };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "topview" });
  if (e.tray) svg.appendChild(box(e.tray, "tv-tray", t("sim.tray")));
  if (e.target) svg.appendChild(box(e.target, "tv-target", t("fol.target")));
  if (e.spawn) { const s = e.spawn, a = (s.yaw || 0); svg.appendChild(el("circle", { cx: X(s.x), cy: Y(s.y), r: 12, class: "tv-robot" }));
    svg.appendChild(el("line", { x1: X(s.x), y1: Y(s.y), x2: X(s.x + 0.12 * Math.cos(a)), y2: Y(s.y + 0.12 * Math.sin(a)), class: "tv-head" })); svg.appendChild(txt(X(s.x), Y(s.y) - 18, t("sim.robot"))); }
  return svg;
}
UI.route("sim/:i", async (body, params) => {
  await SIMP();
  const i = +params.i, e = SIMD.episodes.find(x => x.i === i);
  if (!e) { body.appendChild(h("p", { class: "dim", text: SIMD.episodes.length ? t("sim.noep", { i: params.i }) : t("sim.empty") })); return; }
  const idx = SIMD.episodes.indexOf(e), prev = SIMD.episodes[idx - 1], next = SIMD.episodes[idx + 1];
  UI.keys.bind({ "[": () => prev && go("sim/" + prev.i), "]": () => next && go("sim/" + next.i) }, "page");
  const steps = (STORY && STORY.pair && STORY.pair.steps) || [];
  body.appendChild(h("div", { class: "sim-head" }, [h("a", { href: "#/sim", text: "← " + t("sim.title") }), h("h1", { text: t("d1.ep", { i }) }), simTag(e.label), h("span", { class: "dim", title: e.cluster || null, text: e.for ? (simStep(e) || "") : simLine(e) }),
    h("span", { class: "sep" }), prev ? h("a", { href: "#/sim/" + prev.i, text: "← " + prev.i }) : null, next ? h("a", { href: "#/sim/" + next.i, text: next.i + " →" }) : null]));
  const F = EXPLAIN.read.follow();
  if (e.for) body.appendChild(h("p", { class: "sim-for" }, [t("sim.made.for", { lv: e.for[0], seed: String(e.for[1]) }), e.for[0] === F.level && e.for[1] === F.seed ? [" · ", h("a", { href: "#/follow", text: t("sim.follow") })] : null]));
  body.appendChild(h("div", { class: "sim-ep" }, [
    e.video ? h("video", { src: "/simmedia/" + e.video, controls: true, muted: true, loop: true, autoplay: true, playsinline: true, poster: simSrc(e.poster), class: "sim-video" }) : h("p", { class: "dim", text: t("sim.novideo") }),
    h("div", null, [h("div", { class: "xb-cap", text: t("sim.top") }), simTopView(e), h("div", { class: "xb-cap", text: t("sim.steps") }),
      h("ol", { class: "sim-steps" }, (e.steps || []).map((ok, k) => h("li", { class: ok ? "ok" : "bad" }, [ok ? "✓ " : "✕ ", steps[k] ? t("fig.step." + steps[k]) : String(k + 1)])))])]));
});
