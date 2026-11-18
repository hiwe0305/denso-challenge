/* Step detail pages (workstream B, flywheel v0.3): #/base (the base scoreboard, closing screen of the video),
   #/design (deck slide 9: input, output, environment, devices, resource around the six steps), #/diagnose (step 5),
   and the figures of steps 0 (ledger), 2, 3, 4, 6 added to the EXPLAIN registry (specs merge, see explain.js).
   Every number is read from STORY.demo (story.json · demo, built by the indexer from fwdata and seed/cited.yaml),
   STORY.pair / round / follow / ledger or CAT; tooltips carry the cited source and quote. Text lives in i18n (sb.*). */
"use strict";
const SB = (() => {
  const S = {}, E = EXPLAIN, R = EXPLAIN.read;
  const D = () => (STORY && STORY.demo) || {};
  const N = v => v == null ? null : UI.fmt(v, "int");
  const num = (v, d) => v == null ? "–" : Number(v).toLocaleString(loc(), { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
  const cu = v => v == null ? "–" : Number(v).toLocaleString(loc(), { maximumFractionDigits: 2 });
  const rate = () => (D().round_cost || {}).usd_per_cu;
  const usd = v => v == null || rate() == null ? "–" : num(v * rate(), v * rate() >= 10 ? 1 : 2);
  const pc = v => Math.round(v * 100);
  const frac = (a, n) => a == null || n == null ? "–" : a + "/" + n;
  /* the cited source of one item: "source · “quote”" (bare, for xb-stat src) and with the "Nguồn:" label (for title) */
  const srcq = c => c && c.source ? c.source + (c.quote ? " · “" + c.quote + "”" : "") : null;
  const tip = c => { const s = srcq(c); return s ? t("xb.src") + ": " + s : null; };
  const TAG = { measured: "sb.tag.m", estimated: "sb.tag.e", proposed: "sb.tag.p", goal: "sb.tag.g" };
  const tag = k => TAG[k] ? h("span", { class: "sb-tag " + k, text: t(TAG[k]) }) : null;
  const byId = (xs, id) => (xs || []).find(x => x.id === id) || null;
  S.tip = tip;

  /* ---------- shared figures ---------- */
  /* the relaxed-tolerance ladder: rows from "tray on table B" down to the 5 cm standard, five models, round 1 last */
  S.ladder = function () {
    const L = D().ladder; if (!L || !L.runs) return null;
    const ids = TASK.runs().filter(id => L.runs[id]), n = L.n, R1 = TASK.after();
    const val = (id, row) => { const r = L.runs[id]; return row === "on_table_b" ? r.on_table_b : row === "success" ? r.success : (r.relaxed || {})[row]; };
    const label = row => row === "on_table_b" ? [t("sb.lad.tb"), " ", h("span", { class: "sb-tag sb-sec", text: t("sb.lad.sec") })]
      : row === "success" ? t("sb.lad.ok", { d: Number(L.standard_cm) }) : t("sb.lad.cm", { d: Number(row) });
    const cell = (id, row) => { const v = val(id, row);
      return h("td", { class: id === R1 ? "r1" : "" }, h("div", { class: "sb-lc" }, [h("b", { text: v == null ? "–" : v + "/" + n }), h("i", null, h("span", { style: { width: (v == null ? 0 : v / n * 100) + "%" } }))])); };
    const tb = ids.map(id => L.runs[id].on_table_b), ok = ids.map(id => L.runs[id].success);
    return h("div", { class: "sb-lad" }, [
      h("div", { class: "xb-cap", text: t("sb.lad.t", { y: L.yaw_tol_deg }) }),
      h("table", { class: "xb-tbl sb-ladt", title: t("xb.src") + ": " + L.source }, [
        h("thead", null, h("tr", null, [h("th"), ...ids.map(id => h("th", { class: id === R1 ? "r1" : "" }, E.runLabel(id)))])),
        h("tbody", null, (L.rows || []).map(row => h("tr", { class: row === "success" ? "sb-rstd" : row === "on_table_b" ? "sb-rsec" : "", title: row === "on_table_b" ? tip(L.on_table_b) : null },
          [h("th", null, label(row)), ...ids.map(id => cell(id, row))])))]),
      h("p", { class: "sb-read", text: t("sb.lad.read", { a: Math.min(...tb), b: Math.max(...tb), c: Math.min(...ok), d: Math.max(...ok), n }) })]);
  };
  /* round 1 read from measurements: more narrow misses (5 cm < error ≤ next ladder step) and more tilt at place */
  S.near = function () {
    const L = D().ladder, A = TASK.baseline(), B = TASK.after(); if (!L || !L.runs || !L.runs[A] || !L.runs[B]) return null;
    const std = Number(L.standard_cm), up = (L.relaxed_cm || []).map(Number).filter(x => x > std).sort((a, b) => a - b)[0];
    if (up == null) return null;
    const key = (L.relaxed_cm || []).find(x => Number(x) === up), m = id => { const r = L.runs[id], a = (r.relaxed || {})[key]; return a == null ? null : a - r.success; };
    return { lo: std, hi: up, a: m(A), b: m(B) };
  };
  S.twoSides = function () {
    const nr = S.near(), Q = D().round1_reading || {}, tl = (Q.tilt_at_place || {}).value || {}, A = TASK.baseline(), B = TASK.after();
    if (!nr) return null;
    const side = (title, a, b, k, src) => h("div", { class: "sb-side", title: src }, [h("div", { class: "sb-side-t", text: title }),
      h("div", { class: "sb-ab" }, [h("b", { text: N(a) }), h("i", { text: "→" }), h("b", { class: "after", text: N(b) })]), h("span", { text: k })]);
    return h("div", { class: "sb-two" }, [
      h("div", { class: "sb-pair dim", text: t("sb.np.pair", { a: E.runName(A), b: E.runName(B) }) }),
      h("div", { class: "sb-sides" }, [
        side(t("sb.np.near"), nr.a, nr.b, t("sb.np.near.k", { lo: nr.lo, hi: nr.hi }), t("xb.src") + ": " + (D().ladder || {}).source + " · relaxed − success"),
        tl[A] != null ? side(t("sb.np.tilt"), tl[A], tl[B], t("sb.np.tilt.k"), tip(Q.tilt_at_place)) : null]),
      h("p", { class: "sb-cause", title: tip(Q.not_a_cause), text: t("sb.np.cause") })]);
  };
  /* the pre-written rule and its outcome, framed as Jidoka */
  S.rule = function () {
    const Q = D().round1_reading || {}, r1 = (Q.rule_r1 || {}).value; if (!r1) return null;
    return h("div", { class: "sb-jidoka", title: tip(Q.rule_r1) }, [h("b", { text: t("sb.np.rule", { k: r1.episodes }) }), h("span", { text: t("sb.np.jidoka") })]);
  };
  const resultBig = () => { const a = R.base(), b = R.after(); return a && b ? frac(a.successes, a.n) + " → " + frac(b.successes, b.n) : null; };
  const pairSrc = () => (R.pair().source || "story.json · pair");

  /* ---------- #/base · the base scoreboard ---------- */
  function proven() {
    const out = [], Q = D().qa_bench || {}, cl = Q.code_layer, fs = D().fail_share, dg = D().diagnose || {}, L = D().ladder || {}, tb = (L.on_table_b || {}).value || {};
    const pf = (big, k, sub, src, extra, cls, org) => h("div", { class: "sb-pf" + (cls ? " " + cls : ""), title: src }, [h("b", { text: big }), h("p", null, [k, UI.origin(org, src)]), sub ? h("small", { text: sub }) : null, extra || null]);
    if (cl) out.push(pf(cl.caught + "/" + cl.planted, t("sb.pv.qa.k", { f: cl.false_alarms, c: cl.clean_units }), t("sb.pv.qa.s", { d: cl.date }), t("xb.src") + ": " + Q.source + " · " + ((cl.cites || [])[2] || {}).quote, null, "", "cited"));
    if (fs && fs.min != null) out.push(pf(pc(fs.min) + "–" + pc(fs.max) + " %", t("sb.pv.score.k"), t("sb.pv.score.s", { n: Object.keys(fs.runs || {}).length }), t("xb.src") + ": " + fs.source, null, "", "file"));
    const nt = Object.values(dg.tickets || {}).reduce((s, x) => s + x.length, 0), nd = (dg.to_data || []).length;
    if (nt) out.push(pf(nt + "/" + (nt + nd), t("sb.pv.diag.k"), dg.cost_cu ? t("sb.pv.diag.s", { cu: dg.cost_cu.value }) : null, t("xb.src") + ": " + dg.source, null, "", "cited"));
    /* less data: the baseline against the same recipe on the largest set, and the human-video pair at both sizes */
    const A = TASK.baseline(), B = R.like(A, { episodes: "max" }), C = R.like(A, { human_video: true }), Dd = C && R.like(C, { episodes: "max" }), a = R.run(A), b = R.run(B);
    if (a && b) out.push(pf(frac(a.successes, a.n), t("sb.pv.less.k", { b: frac(b.successes, b.n) }), null, t("xb.src") + ": " + pairSrc() + " · " + A + ", " + B,
      tb[A] != null ? h("div", { class: "sb-sub", title: tip(L.on_table_b) }, [t("sb.pv.less.tb", { a: tb[A], b: tb[B], c: tb[C], d: tb[Dd], n: L.n }), " ", h("span", { class: "sb-tag sb-sec", text: t("sb.pv.less.tag") })]) : null, "neu", "file"));
    const led = (STORY && STORY.ledger) || [];
    if (led.length) out.push(pf(N(led.length), t("sb.pv.led.k"), null, t("xb.src") + ": story.json · ledger", null, "", "file"));
    return out;
  }
  function notYet() {
    const dg = D().diagnose || {}, nt = Object.values(dg.tickets || {}).reduce((s, x) => s + x.length, 0), std = (D().ladder || {}).standard_cm;
    return [
      resultBig() ? h("div", { class: "sb-pf nb", title: t("xb.src") + ": " + pairSrc() + " · " + TASK.baseline() + ", " + TASK.after() }, [h("b", { text: resultBig() }), h("p", null, [t("sb.np.r1.k", { d: std != null ? Number(std) : "–" }), UI.origin("file", pairSrc())])])
        : h("div", { class: "sb-pf nb" }, [h("b", { class: "sm", text: t("sb.np.open") }), h("p", { text: t("wh.withheld") })]),
      S.twoSides() ? h("div", { class: "sb-why" }, [h("span", { class: "sb-mark", text: "C" }), h("div", null, [h("div", { class: "sb-h4", text: t("sb.np.two") }), S.twoSides()])]) : null,
      S.rule(),
      h("div", { class: "sb-why sm" }, [h("span", { class: "sb-mark", text: "A" }), h("span", { text: t("sb.np.once") })]),
      nt ? h("div", { class: "sb-why sm", title: t("xb.src") + ": " + dg.source }, [h("span", { class: "sb-mark", text: "B" }), h("span", { text: t("sb.np.sys", { n: nt }) })]) : null];
  }
  function nextSteps() {
    const nx = (k, s, mark) => h("div", { class: "sb-nx" }, [h("div", { class: "sb-nx-h" }, [tag("proposed"), h("span", { class: "sb-because" }, [t("sb.nx.why") + " ", h("span", { class: "sb-mark", text: mark })])]),
      h("b", { text: t(k) }), s ? h("small", { text: t(s) }) : null]);
    return [nx("sb.nx.1", "sb.nx.1s", "A"), nx("sb.nx.2", "sb.nx.2s", "B"), nx("sb.nx.3", "sb.nx.3s", "C")];
  }
  function roadmap() {
    const ms = (when, k, goal, now) => h("div", { class: "sb-ms" + (now ? " now" : "") }, [h("span", { class: "sb-dot" }), h("b", { text: t(when) }), h("p", { text: t(k) }),
      goal ? h("div", { class: "sb-goal" }, [tag("goal"), " ", t(goal)]) : null]);
    return h("div", { class: "sb-road" }, [
      h("div", { class: "sb-rm" }, [h("div", { class: "sb-h3", text: t("sb.rm.t") }), h("div", { class: "sb-ms-row" }, [ms("sb.rm.1h", "sb.rm.1", null, true), ms("sb.rm.2h", "sb.rm.2", "sb.rm.2g"), ms("sb.rm.3h", "sb.rm.3")])]),
      h("div", { class: "sb-scale" }, [h("div", { class: "sb-h3", text: t("sb.sc.t") }), h("ol", null, ["sb.sc.1", "sb.sc.2", "sb.sc.3", "sb.sc.4"].map(k => h("li", { text: t(k) })))])]);
  }
  function fixes() {
    const rc = D().round_cost || {}, dv = (D().design || {}).devices, tr = (byId(dv, "colab_train_gpu") || {}).value || {}, sv = (byId(dv, "colab_serve_gpu") || {}).value || {};
    const s1 = R.tot("s1"), s2 = R.tot("s2");
    const row = (o, nw, src, org) => h("tr", { title: src }, [h("td", { class: "old", text: t(o) }), h("td", { class: "arrow", text: "→" }), h("td", null, [nw, org ? UI.origin(org, src) : null])]);
    return h("div", { class: "sb-fix" }, [h("div", { class: "sb-h3", text: t("sb.fix.t") }), h("table", null, h("tbody", null, [
      s1 != null ? row("sb.fix.1o", t("sb.fix.1n", { a: s1, b: s1 + (s2 || 0) }), t("xb.src") + ": catalog.json · totals.s1, totals.s2", "file") : null,
      rc.total_cu != null ? row("sb.fix.2o", t("sb.fix.2n", { usd: usd(rc.total_cu), cu: cu(rc.total_cu) }), t("xb.src") + ": " + rc.source, "cited") : null,
      row("sb.fix.3o", t("sb.fix.3n"), null),
      tr.gpu ? row("sb.fix.4o", t("sb.fix.4n", { a: tr.gpu, b: sv.gpu || "–" }), tip(byId(dv, "colab_train_gpu")), "cited") : null]))]);
  }
  UI.route("base", async body => {
    document.title = t("sb.base.nav") + " · Humanoid Data Flywheel";
    const col = (cls, k, kids) => h("section", { class: "sb-col " + cls }, [h("div", { class: "sb-colh", text: t(k) }), ...kids]);
    body.appendChild(h("div", { class: "sb-page" }, [
      h("div", { class: "sb-hero" }, [h("span", { class: "xb-st", text: t("sb.base.kick") }), h("h1", { text: t("sb.base.title") }), h("p", null, [t("sb.base.lead"), " ", h("span", { class: "dim", text: t("wh.prelim") })])]),
      h("div", { class: "sb-cols" }, [col("pv", "sb.base.c1", proven()), col("ny", "sb.base.c2", notYet()), col("nx", "sb.base.c3", nextSteps())]),
      roadmap(), fixes()]));
  });

  /* ---------- #/design · deck slide 9 ---------- */
  function designPage() {
    const G = D().design || {}, L = D().ladder || {}, F = R.follow().tol || {};
    const it = (k, vars, item, kind, org) => ({ text: t(k, vars), src: tip(item), kind: kind || (item && item.kind), origin: item ? (org || (item.source ? "cited" : null)) : null });
    const I = id => byId(G.input, id), O = id => byId(G.output, id), V = id => byId(G.environment, id), W = id => byId(G.devices, id), X = id => byId(G.resource, id);
    const v = (x, k) => x && x.value && typeof x.value === "object" ? x.value[k] : x ? x.value : null;
    const tr = X("train_cu") || {}, te = X("train_cu_estimate"), ts = X("test_cu") || {}, gm = X("gen_machine_hours"), gc = X("gen_cu"), rr = (D().round_cost || {}).usd_rate;
    const steps = v(O("step_scores"), "steps"), models = v(O("trained_model"), "models");
    const blocks = {
      in: [it("sb.de.task", { s: steps, d: L.standard_cm != null ? Number(L.standard_cm) : F.distance_m * 100, y: L.yaw_tol_deg }, I("task"), "description"),
        it("sb.de.station", null, I("station")),
        it("sb.de.sim", { n: v(I("sim_episodes"), "episodes") }, I("sim_episodes"), null, "file"),
        it("sb.de.human", { n: v(I("human_clips"), "clips"), e: v(I("human_clips"), "exported") }, I("human_clips"), null, "file"),
        it("sb.de.teleop", null, I("keyboard_teleop"))],
      out: [it("sb.de.model", { n: models ? models.length : "–" }, O("trained_model")), it("sb.de.scores", { n: steps }, O("step_scores")),
        it("sb.de.reco", null, O("recommendation")), it("sb.de.cmp", null, O("comparison"))],
      env: [it("sb.de.sim1", null, V("sim_stack")), it("sb.de.isaac", null, V("sim_stack")),
        it("sb.de.robot", { r: v(V("robot_model"), "robot"), m: v(V("robot_model"), "model") }, V("robot_model")), it("sb.de.fmt", { v: v(V("lerobot")) }, V("lerobot"))],
      dev: [it("sb.de.laptop", null, W("laptop")), it("sb.de.3060", { h: v(W("rtx3060"), "hours") }, W("rtx3060")),
        it("sb.de.train", { g: v(W("colab_train_gpu"), "gpu"), s: v(W("colab_train_gpu"), "steps") }, W("colab_train_gpu")),
        it("sb.de.serve", { g: v(W("colab_serve_gpu"), "gpu") }, W("colab_serve_gpu")), it("sb.de.cam", null, W("head_camera"))],
      res: [tr.min_cu != null ? { text: t("sb.de.rtrain", { lo: num(tr.min_cu), hi: num(tr.max_cu), ulo: usd(tr.min_cu), uhi: usd(tr.max_cu) }), src: t("xb.src") + ": " + tr.source, kind: "measured", origin: "file" } : null,
        te ? it("sb.de.rtrainE", { lo: v(te, "low"), hi: v(te, "high") }, te) : null,
        ts.min_cu != null ? { text: t("sb.de.rtest", { n: L.n, lo: num(ts.min_cu, 1), hi: num(ts.max_cu, 1) }), src: t("xb.src") + ": " + ts.source + " · " + (ts.note || ""), kind: "measured", origin: "file" } : null,
        gm ? it("sb.de.rgen", { k: R.round().selected, h: num(gm.value, 1), cu: gc ? gc.value : "–" }, gm) : null,
        it("sb.de.rdeid", null, X("deid_first")),
        rr ? { text: t("sb.de.rate", { u: num(rate(), 2), cu: rr.value.cu, usd: num(rr.value.usd, 2) }), src: tip(rr), kind: "rate", origin: rr.source ? "cited" : null } : null] };
    const HK = { in: "sb.de.h.in", out: "sb.de.h.out", env: "sb.de.h.env", dev: "sb.de.h.dev", res: "sb.de.h.res" };
    const blk = (k, cls) => h("section", { class: "sb-blk " + cls }, [h("h3", { text: t(HK[k]) }),
      h("ul", null, blocks[k].filter(Boolean).map(x => h("li", { title: x.src }, [h("span", { text: x.text }), tag(x.kind), x.origin ? UI.origin(x.origin, x.src) : null])))]);
    const fw = h("section", { class: "sb-fw" }, [h("h3", { text: t("sb.de.h.fw") }),
      h("div", { class: "sb-fw-steps" }, E.STEPS.map(n => h("a", { class: "sb-fw-chip" + (n === E.KEEP ? " keep" : ""), href: E.href(n) }, [h("span", { class: "sn", text: String(n) }), h("span", null, [E.name(n), n === E.KEEP ? h("small", { text: t("wh.keep") }) : null])]))),
      h("a", { class: "sb-fw-led", href: E.href(0) }, [h("span", { class: "sn", text: "$" }), h("span", { text: t("sb.de.ledger") })]),
      h("p", { class: "sb-fw-flow", text: t("sb.de.flow") })]);
    return h("div", { class: "sb-page sb-design" }, [
      h("div", { class: "sb-hero tight" }, [h("span", { class: "xb-st", text: t("sb.de.nav") }), h("h1", { text: t("sb.de.title") })]),
      h("div", { class: "sb-de-top" }, [blk("in", "in"), h("i", { class: "sb-arr", text: "➜" }), fw, h("i", { class: "sb-arr", text: "➜" }), blk("out", "out")]),
      h("div", { class: "sb-de-bot" }, [blk("env", "env"), blk("dev", "dev"), blk("res", "res")]),
      h("div", { class: "sb-de-key dim" }, [tag("measured"), " " + t("sb.de.keym") + "   ", tag("estimated"), " " + t("sb.de.keye")])]);
  }
  UI.route("design", async body => { document.title = t("sb.de.nav") + " · Humanoid Data Flywheel"; body.appendChild(designPage()); });

  /* ---------- step 2 · QA bench from the index (the wheel node reads stats()[0]) ---------- */
  const prev2 = E.registered(2).stats;
  E.register(2, {
    stats: () => { const Q = D().qa_bench || {}, q = Q.code_layer; if (!q) return E.safe(prev2, []);
      const m = (STORY && STORY.h1m) || {}, d = m.decisions || {}, c = q.cites || [];
      return [{ v: q.caught + "/" + q.planted, k: t("sb.s2.k1", { d: q.date }), src: srcq(c[2]) || Q.source, tone: "good", origin: "cited" },
        { v: q.false_alarms + "/" + q.clean_units, k: t("sb.s2.k2"), src: srcq(c[3]) || Q.source, origin: "cited" },
        { v: d.exported != null ? N(d.exported) + "/" + N(m.clips) : null, k: t("st.2.k1"), src: "story.json · h1m.decisions", origin: "file" }]; },
    note: () => { const a = (D().qa_bench || {}).agent_layer_nemotron; if (!a || !a.value) return null;
      const x = a.value; return t("sb.s2.agent", { c: x.caught, p: x.planted, f: x.false_alarms, n: x.clean_units, d: x.date }); },
  });

  /* ---------- step 3 · plain model names, measured training cost, the step kept as-is ---------- */
  E.register(3, {
    note: () => t("sb.s3.keep"),
    fig: () => {
      const tr = byId((D().design || {}).resource, "train_cu") || {}, pm = tr.per_model_cu || {};
      const cell = id => { const r = R.run(id), c = pm[id];
        return h("div", { class: "xb-cell sb-cell", title: id + (c != null ? " · " + t("xb.src") + ": " + tr.source : "") }, [h("b", { text: E.runName(id) }),
          h("span", { text: r ? r.successes + "/" + r.n : TASK.withheld().includes(id) ? "" : "–" }),
          h("small", { class: "dim", text: c != null ? t("sb.s3.cost", { cu: num(c), u: usd(c) }) : t("sb.s3.nocost") })]); };
      return E.grid(cell);
    },
  });

  /* ---------- step 4 · seven-step bar, success clip, tolerance ladder ---------- */
  const fig4 = E.registered(4).fig;
  S.clip = function () {
    const c = D().success_clip; if (!c || !c.path) return null;
    const v = h("video", { src: "/demomedia/" + String(c.path).split("/").pop(), preload: "metadata", playsinline: true, muted: true, loop: true });
    v.muted = true;
    const box = h("div", { class: "sb-clip", title: c.deck_caption || null }, [v, h("span", { class: "sb-play", text: "▶ " + t("sb.s4.play") })]);
    box.addEventListener("click", () => { if (v.paused) { v.play().catch(() => {}); box.classList.add("on"); } else { v.pause(); box.classList.remove("on"); } });
    return h("figure", { class: "sb-clipf" }, [h("div", { class: "xb-cap", text: t("sb.s4.clip", { run: E.runName(c.model) }) }), box,
      h("small", { class: "dim", title: t("xb.src") + ": " + (c.deck_file || "") + " · " + (c.deck_member || ""), text: t("sb.s4.prov", { s: c.deck_slide }) })]);
  };
  E.register(4, {
    note: () => t("st.4.note") + " " + t("sb.s4.two"),
    fig: () => h("div", null, [h("div", { class: "sb-s4" }, [h("div", null, [E.safe(fig4, null), h("small", { class: "dim sb-s4n", text: t("sb.s4.bar") })]), S.clip()]), S.ladder()]),
  });

  /* ---------- step 5 · #/diagnose: system checks first, then the eight groups of similar failed runs ---------- */
  const CHK = { H1: "sb.s5.h1", H2: "sb.s5.h2", H3: "sb.s5.h3", delay_sync_camera: "sb.s5.dsc" };
  const TCK = { "DA-37": "sb.s5.t37", "DA-38": "sb.s5.t38" };
  S.checks = function () {
    const G = D().diagnose; if (!G || !G.checks) return null;
    const st = c => { const x = c.value || {}; return x.result === "pass" ? ["ok", "✓", t("sb.s5.pass")] : x.goes_to === "data" ? ["pol", "→", t("sb.s5.policy")] : ["unc", "?", t("sb.s5.unclear", { id: x.ticket || "–" })]; };
    return h("div", { class: "sb-chk" }, [h("div", { class: "xb-cap", text: t("sb.s5.checks") }),
      ...G.checks.filter(c => CHK[c.id]).map(c => { const [cls, ic, lab] = st(c), cl = (c.value || {}).clusters;
        return h("div", { class: "sb-chkr " + cls, title: tip(c) + (Array.isArray(cl) ? " · " + cl.join(", ") : "") }, [h("span", { class: "ic", text: ic }), h("span", { class: "q", text: t(CHK[c.id]) }), h("span", { class: "r", text: lab })]); })]);
  };
  S.groups = function () {
    const G = D().diagnose, C = (STORY && STORY.round && STORY.round.clusters) || []; if (!G || !C.length) return null;
    const cl = id => C.find(c => c.id === id) || { id }, h2 = ((G.checks || []).find(c => c.id === "H2") || {}).value || {}, inH2 = id => (h2.clusters || []).includes(id);
    const stage = c => c.stage && c.stage !== "—" ? TASK.stageName(c.stage) : t("sb.s5.nostep");
    const card = (c, why, go) => h("div", { class: "sb-cc", title: c.id + " · " + String(c.diagnosis || "") + " · " + String(c.intervention || "") }, [
      h("b", { text: stage(c) }), h("span", { text: why }), c.failures != null ? h("span", { class: "n", text: t("sb.s5.fails", { n: c.failures }) }) : null, h("span", { class: "go", text: go })]);
    const data = (G.to_data || []).map(cl), tk = Object.entries(G.tickets || {}), nt = tk.reduce((s, [, x]) => s + x.length, 0), m = data.length + nt;
    return h("div", { class: "wh-cls sb-grp", title: t("xb.src") + ": " + G.source }, [
      h("div", { class: "wh-cl data" }, [h("div", { class: "xb-cap", text: t("sb.s5.gdata", { n: data.length, m }) }), ...data.map(c => card(c, t(inH2(c.id) ? "sb.s5.h2s" : "sb.s5.weak"), "→ " + t("sb.s5.gen")))]),
      h("div", { class: "wh-cl sys" }, [h("div", { class: "xb-cap", text: t("sb.s5.gsys", { n: nt, m }) }),
        ...tk.flatMap(([id, xs]) => xs.map(x => card(cl(x), TCK[id] ? t(TCK[id]) : id, "→ " + t("sb.s5.ticket", { id }))))])]);
  };
  E.register(5, {
    stats: () => { const G = D().diagnose; if (!G) return [];
      const nd = (G.to_data || []).length, nt = Object.values(G.tickets || {}).reduce((s, x) => s + x.length, 0), m = nd + nt;
      return [{ v: nd + "/" + m, k: t("sb.s5.k1"), src: G.source, origin: "cited" }, { v: nt + "/" + m, k: t("sb.s5.k2"), src: G.source, origin: "cited" },
        G.cost_cu ? { v: G.cost_cu.value + " CU", k: t("sb.s5.cost"), src: srcq(G.cost_cu), tone: "good", origin: "cited" } : null]; },
    note: () => t("sb.s5.what"),
    fig: () => h("div", { class: "sb-s5" }, [S.checks(), S.groups()]),
  });
  UI.route("diagnose", async body => {
    const G = D().diagnose || {};
    body.appendChild(h("table", { class: "xb-tbl sb-quotes" }, h("tbody", null, (G.checks || []).map(c => h("tr", null, [h("td", { text: c.id }), h("td", { class: "dim", text: c.source }), h("td", { text: c.quote || "" })])))));
  });

  /* ---------- step 6 · the filter chain beside the robot's result, the 23/37 table, the stop ---------- */
  const prev6 = E.registered(6).stats;
  E.register(6, {
    /* the third tile was "23 → 181", which reads as progress (brief 6): show the count added, labelled as not a result */
    stats: () => { const s = E.safe(prev6, []), c = R.round();
      return c.selected != null ? [...s.slice(0, 2), { v: N(c.selected), k: t("sb.s6.k3"), src: "story.json · round.chain", origin: "cited" }] : s; },
    fig: () => { const c = R.round();
      const chain = E.chain(t("sb.s6.chain"), [["sb.s6.targets", c.targets], ["fig.c.generated", c.generated], ["fig.c.recorded", c.recorded], ["fig.c.qa", c.qa_pass], ["fig.c.quality", c.quality], ["fig.c.selected", c.selected, "ok"]]);
      const res = h("div", { class: "sb-res" }, [h("div", { class: "xb-cap", text: t("sb.s6.res") }),
        resultBig() ? h("div", { class: "sb-pf nb", title: t("xb.src") + ": " + pairSrc() + " · " + TASK.baseline() + ", " + TASK.after() }, [h("b", { text: resultBig() }), h("p", null, [t("sb.np.r1.k", { d: (D().ladder || {}).standard_cm != null ? Number(D().ladder.standard_cm) : "–" }), UI.origin("file", pairSrc())])])
          : h("div", { class: "sb-pf nb" }, [h("p", { text: t("wh.withheld") })]),
        S.twoSides()]);
      return h("div", null, [h("div", { class: "sb-s6" }, [chain, res]), h("div", { class: "sb-s6t" }, [E.r3Table(), E.verdict()]), S.rule()]); },
    links: () => [["sb.base.link", "#/base"], ["sb.de.link", "#/design"]],
  });

  /* ---------- centre · cost ledger: round 1 measured, n jobs with a line; one total only (the round's own) ---------- */
  const prev0 = E.registered(0).stats;
  const LINE = { train_1: "sb.s0.tr1", train_2: "sb.s0.tr2", serve: "sb.s0.serve" };
  E.register(0, {
    stats: () => { const s = E.safe(prev0, []), rc = D().round_cost || {};
      return rc.total_cu != null ? [...s.slice(0, 2), { v: "≈ " + usd(rc.total_cu) + " USD", k: t("sb.s0.k3", { cu: cu(rc.total_cu) }), src: rc.source + " · " + (rc.total_note || ""), origin: "cited" }] : s; },
    fig: () => { const rc = D().round_cost; if (!rc || !rc.lines) return null;
      const w = rc.serve_waste, ec = rc.eval_client;
      const row = (k, v, src, cls, vars) => h("tr", { class: cls || "", title: src }, [h("td", { text: t(k, vars) }), h("td", { text: (cls === "tot" ? "≈ " : "") + usd(v) + " USD" }), h("td", { class: "dim", text: "(" + cu(v) + " CU)" })]);
      return h("div", { class: "sb-cost" }, [h("div", { class: "xb-cap" }, [t("sb.s0.t") + " ", tag("measured")]),
        h("table", { class: "xb-tbl" }, h("tbody", null, [
          ...rc.lines.map(l => row(LINE[l.id] || l.id, l.value, tip(l), "", { w: w ? w.value : "–" })),
          row("sb.s0.tot", rc.total_cu, t("xb.src") + ": " + rc.source + " · " + (rc.total_note || ""), "tot")])),
        h("p", { class: "dim sb-cost-n" }, [ec && ec.value ? h("span", { title: tip(ec), text: t("sb.s0.client", { h: num(ec.value.hours, 1), cu: ec.value.cu }) + " " }) : null,
          rc.usd_rate ? h("span", { title: tip(rc.usd_rate), text: t("sb.s0.rate", { cu: rc.usd_rate.value.cu, usd: num(rc.usd_rate.value.usd, 2) }) }) : null])]); },
    links: () => [["sb.base.link", "#/base"], ["sb.de.link", "#/design"]],
  });
  return S;
})();
