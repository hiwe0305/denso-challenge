/* Process view (brief 2 · T2): the six stages of the system and the cost ledger share one page template with tabs kept
   in the URL (?tab=result|how|log|runs|try): Kết quả · Cách làm · Log · Lần chạy · Chạy thử. Also the overview #/home
   (one row per stage for the selected task and round), the round report shell (#/report, #/follow, #/base, #/design)
   and the "Chạy thử" panels, built from GET /api/kinds (T3), never from a typed list.
   Stage numbers: 1 data · 2 checks · 3 training · 4 test and scoring · 5 diagnosis · 6 failure → data · 0 ledger.
   What runs where: tasks.json (TASK.process(n)) and /api/kinds. Numbers: the EXPLAIN readers (index, cited.yaml), with
   their origin mark. A stage or task without data shows the empty state, never zeros. Text lives in i18n (pr.*). */
"use strict";
const PROC = (() => {
  const P = {};
  /* process stage of a runnable kind (/api/kinds "stage", a job's "process_stage") → stage number */
  const STAGE_OF = { data: 1, qa: 2, train: 3, eval: 4, diagnose: 5, loop: 6 };
  P.ORDER = [1, 2, 3, 4, 5, 6, 0];
  P.TABS = ["result", "how", "log", "runs", "try"];
  /* app.js state (const ST, let STORY) is script-scoped, not on window */
  const S = () => (typeof ST !== "undefined" && ST) || {};
  const L = o => o == null ? "" : typeof o === "object" ? (o[UI.lang] || o.vi || "") : String(o);
  P.name = n => t("pr." + n + ".name");
  P.sub = n => t("pr." + n + ".sub");
  P.href = (n, tab, extra) => { const b = EXPLAIN.href(n), q = [tab && tab !== "result" ? "tab=" + tab : null, extra || null].filter(Boolean).join("&");
    return q ? b + (b.indexOf("?") < 0 ? "?" : "&") + q : b; };
  P.tabOf = qs => P.TABS.includes(qs.tab) ? qs.tab : "result";
  const when = iso => iso ? UI.fmt(iso, "date") + " " + UI.fmt(iso, "time") : "—";
  const active = j => j.state === "running" || j.state === "queued";
  const jdur = j => j.seconds != null ? j.seconds : j.started && j.ended ? (new Date(j.ended) - new Date(j.started)) / 1000 : null;
  const sec = (title, kids, cls) => h("section", { class: "pr-card" + (cls ? " " + cls : "") }, [title ? h("h3", { class: "pr-h3", text: title }) : null, ...[].concat(kids)]);
  const copy = s => h("button", { class: "u-btn sm", text: t("pr.copy"), onclick: e => { UI.copy(s); e.target.textContent = t("pr.copied"); setTimeout(() => { e.target.textContent = t("pr.copy"); }, 1200); } });
  /* DOM replaceChildren() writes a null child as the text "null"; h() skips it, so this does too */
  const put = (el, ...kids) => el.replaceChildren(...kids.filter(x => x != null));
  const code = s => h("div", { class: "pr-code" }, [h("code", { text: UI.redact(s) }), copy(UI.redact(s))]);

  /* ---------- data: runnable kinds and console jobs ---------- */
  let K = null, KT = 0, KP = null;
  P.kinds = () => {
    if (K && Date.now() - KT < 20000) return Promise.resolve(K);
    return KP || (KP = fetch("/api/kinds").then(r => r.ok ? r.json() : null).catch(() => null).then(d => { K = d && d.kinds ? d : { kinds: [], remote: [] }; K.remote = K.remote || []; KT = Date.now(); KP = null; return K; }));
  };
  P.jobs = () => fetch("/api/jobs?limit=200").then(r => r.ok ? r.json() : []).catch(() => []);
  const kindOf = id => ((K && K.kinds) || []).find(k => k.kind === id) || null;
  P.kindTitle = j => L((kindOf(j.kind) || {}).title) || j.kind;
  P.stageOfJob = j => { const s = j.process_stage || (kindOf(j.kind) || {}).stage; return s in STAGE_OF ? STAGE_OF[s] : null; };
  /* a job of this task, or one not tied to any task (the egocentric pipeline is shared by every task) */
  const ofTask = j => !j.task || j.task === "unknown" || j.task === TASK.id;
  P.stageJobs = (jobs, n) => (jobs || []).filter(j => P.stageOfJob(j) === n && ofTask(j));
  const kindsOf = n => ((K && K.kinds) || []).filter(k => STAGE_OF[k.stage] === n);
  const remoteOf = n => ((K && K.remote) || []).filter(k => STAGE_OF[k.stage] === n);
  /* a training run's last update, from /api/status (stage "train", runs[].age_min) for this task */
  const trainLive = branch => {
    const s = (S().stages || []).find(x => x.id === "train" && (!x.task || x.task === TASK.id)); if (!s || !s.runs) return null;
    const r = s.runs.find(x => x.branch === branch), base = S().status && S().status.time ? Date.parse(S().status.time) : Date.now();
    return r ? { running: !!r.running, at: r.age_min != null ? new Date(base - r.age_min * 60 * 1000).toISOString() : null } : null;
  };
  const demo = () => (STORY && STORY.demo) || {};
  const resource = id => ((demo().design || {}).resource || []).find(x => x.id === id) || null;
  const sumCu = r => { const ids = TASK.runs().filter(id => r && r.per_model_cu && r.per_model_cu[id] != null); return ids.length ? { cu: ids.reduce((a, id) => a + r.per_model_cu[id], 0), k: ids.length } : null; };

  /* ---------- state chips ---------- */
  const SCLS = { done: "ok", ok: "ok", run: "run", running: "run", queued: "run", none: "idle", failed: "bad", cancelled: "idle", remote: "rem" };
  P.chip = (s, label) => h("span", { class: "pr-chip " + (SCLS[s] || "idle"), text: label || t("pr.s." + s) });

  /* ---------- the stage page: head, tabs ---------- */
  P.head = function (n) {
    const p = TASK.process(n) || {};
    return h("header", { class: "pr-head" }, [
      h("div", { class: "pr-kick" }, [h("span", { text: n ? t("pr.kick", { n }) : t("pr.kick0") }), h("span", { class: "dim", text: " · " + TASK.name() })]),
      h("div", { class: "pr-title" }, [h("span", { class: "pr-sn" + (n ? "" : " cost"), text: n ? String(n) : "$" }), h("h1", { text: P.name(n) }),
        h("span", { class: "pr-where" }, [h("small", { text: t("pr.where") }), p.remote || t("pr.laptop")]),
        TASK.round() ? h("a", { class: "pr-rep", href: "#/report?s=" + n, text: t("pr.toReport") }) : null]),
      h("p", { class: "pr-sub", text: P.sub(n) })]);
  };
  P.tabs = (n, cur) => h("nav", { class: "pr-tabs" }, P.TABS.map(k => h("a", { class: k === cur ? "on" : "", href: P.href(n, k), text: t("tab." + k) })));
  /* sub-pages of a stage (one dataset, one episode, the sim library): a breadcrumb back to the stage */
  P.crumb = n => h("nav", { class: "pr-crumb" }, [h("a", { href: "#/home", text: t("pr.proc") }), h("i", { text: "›" }), h("a", { href: EXPLAIN.href(n), text: n + " · " + P.name(n) })]);

  /* ---------- Kết quả: summary strip, the stage figure where it is operational, then the page body ---------- */
  const FIG = new Set([1, 2, 5, 0]);
  P.summary = function (n, has) {
    const stats = EXPLAIN.stats(n);
    return h("section", { class: "pr-sum" }, [
      h("div", { class: "pr-qa" }, [h("b", { text: t("st." + n + ".q") }), h("p", { text: EXPLAIN.answer(n) }),
        has ? h("p", { class: "pr-risk" }, [h("b", { text: t("xb.risk") + ": " }), EXPLAIN.risk(n)]) : null]),
      stats.length ? h("div", { class: "pr-nums" }, stats.map(EXPLAIN.stat)) : null]);
  };
  P.result = function (n, body) {
    /* stage 6 of a round whose retest is not presented: the data order figure stands in for the old loop page,
       which is built around the retest and would otherwise say "no data" */
    const held6 = n === 6 && TASK.withheld().length > 0;
    const has = TASK.hasData(n), fig = FIG.has(n) || !TASK.round() || held6 ? EXPLAIN.safe(EXPLAIN.spec(n).fig, null) : null;
    const out = [P.summary(n, has)];
    if (fig) out.push(h("section", { class: "pr-card pr-fig" }, fig));
    if ((has && !held6) || !fig) out.push(h("div", { class: "pr-body" }, body));
    return out;
  };

  /* ---------- Cách làm ---------- */
  P.how = async function (n) {
    const p = TASK.process(n) || {}, how = p.how || [];
    await P.kinds();
    const ks = kindsOf(n), rm = remoteOf(n), by = k => how.filter(x => x.kind === k);
    const ref = x => h("li", null, [h("code", { text: x.path + (x.section ? " §" + x.section : "") }), x.note ? h("span", { class: "dim", text: " · " + x.note }) : null]);
    const list = (title, xs) => xs.length ? sec(title, h("ul", { class: "pr-refs" }, xs.map(ref))) : null;
    const loc = x => x.fw ? "fwdata/" + x.fw : x.index ? "index/" + x.index : x.cited ? "seed/cited.yaml · " + x.cited : x.doc || "";
    const files = [...(p.logs || []).map(x => [t("tab.log"), x]), ...(p.results || []).map(x => [t("tab.result"), x])];
    const left = [
      by("cmd").length ? sec(t("pr.how.cmd"), by("cmd").map(x => code(x.text))) : null,
      ks.length ? sec(t("pr.how.kinds"), ks.map(k => h("div", { class: "pr-kind" }, [h("div", null, [h("b", { text: L(k.title) }), h("span", { class: "dim", text: " · " + k.kind })]), code(k.command),
        (k.configs || []).length ? h("div", { class: "dim" }, [t("pr.how.cfg") + ": ", ...k.configs.map(c => h("code", { text: c + " " }))]) : null,
        h("a", { href: P.href(n, "try", "kind=" + k.kind), text: t("tab.try") + " →" })]))) : null,
      !by("cmd").length && !ks.length ? UI.empty({ tag: t("pr.how.nocmd.tag"), title: t("pr.how.nocmd"), missing: L(p.missing) }) : null];
    const right = [
      sec(t("pr.how.where"), [h("p", null, [h("b", { text: p.remote || t("pr.laptop") })]),
        ...rm.map(r => h("p", { class: "pr-rm" }, [h("b", { text: L(r.title) + ": " }), L(r.where), h("br"), h("span", { class: "dim", text: L(r.why) })]))]),
      (p.needs || []).length ? sec(t("pr.how.needs"), [h("ul", { class: "pr-refs" }, p.needs.map(k => h("li", null, [h("code", { text: k }), " ", P.chip(TASK.has(k) ? "done" : "none", t(TASK.has(k) ? "pr.how.have" : "pr.how.lack"))]))),
        L(p.missing) ? h("p", { class: "dim", text: t("empty.missing") + " " + L(p.missing) }) : null]) : null,
      list(t("pr.how.cfg"), by("config")), list(t("pr.how.mod"), by("module")), list(t("pr.how.doc"), by("doc")),
      files.length ? sec(t("pr.how.out"), h("ul", { class: "pr-refs" }, files.map(([k, x]) => h("li", null, [h("span", { class: "dim", text: k + " · " + (x.label || "") + ": " }), h("code", { text: loc(x) })])))) : null];
    return [h("div", { class: "pr-cols" }, [h("div", { class: "pr-col" }, left), h("div", { class: "pr-col" }, right)])];
  };

  /* ---------- Log ---------- */
  P.log = async function (n, qs) {
    const p = TASK.process(n) || {}, [jobs] = await Promise.all([P.jobs(), P.kinds()]), js = P.stageJobs(jobs, n), out = [];
    if (js.length) {
      let cur = js.find(j => j.id === qs.job) || js[0];
      const view = UI.Log({ jobId: cur.id }), head = h("div", { class: "pr-loghead" }), list = h("div", { class: "pr-jl" });
      const paint = () => {
        put(head, h("b", { text: P.kindTitle(cur) }), P.chip(cur.state === "ok" ? "ok" : active(cur) ? "running" : cur.state), h("span", { class: "dim", text: when(cur.started || cur.created) + " · " + (cur.host || "laptop") + (jdur(cur) != null ? " · " + UI.fmt(jdur(cur), "dur") : "") }),
          h("a", { href: "#/jobs?job=" + cur.id, text: t("pr.try.openJob") }));
        put(list, ...js.slice(0, 40).map(j => h("a", { class: "pr-jr" + (j === cur ? " on" : ""), href: "javascript:void 0", title: j.id, onclick: () => { cur = j; view.setJob(j.id); UI.setQs({ job: j.id }); paint(); } },
          [P.chip(j.state === "ok" ? "ok" : active(j) ? "running" : j.state), h("span", { class: "nm", text: (j.chain_id ? "↳ " : "") + P.kindTitle(j) }), h("span", { class: "dim", text: when(j.started || j.created) })])));
      };
      paint();
      out.push(sec(t("pr.log.jobs", { n: js.length }), h("div", { class: "pr-logs" }, [list, h("div", { class: "pr-logv" }, [head, view])])));
    }
    const tail = n === 3 && STORY && STORY.train_log_tail;
    if (tail && tail.length) {
      const run = (TASK.round() || {}).log_run, live = trainLive(run);
      out.push(sec(t("pr.log.remote", { m: p.remote || "—" }), [h("p", { class: "dim" }, [t("pr.log.run", { r: EXPLAIN.runName(run) }), live && live.at ? " · " + t("pr.log.at", { d: when(live.at) }) : null, UI.origin("file", "story.json · train_log_tail")]),
        h("div", { class: "pr-logv tall" }, UI.Log({ text: tail.join("\n"), follow: true }))]));
    }
    if ((p.logs || []).length) out.push(sec(t("pr.log.files"), h("ul", { class: "pr-refs" }, p.logs.map(x => h("li", null, [h("span", { class: "dim", text: (x.label || "") + ": " }), h("code", { text: "fwdata/" + (x.fw || "") })])))));
    if (!js.length && !(tail && tail.length)) out.unshift(UI.empty({ tag: t("pr.log.tag"), title: t("pr.log.none"), where: p.remote, how: p.how }));
    return out;
  };

  /* ---------- Lần chạy: console jobs and the remote runs the index knows ---------- */
  const OUTK = ["findings", "skipped", "episodes", "passed", "failed", "clusters"];
  const jobRes = j => { const o = j.outputs || {}; return OUTK.filter(k => typeof o[k] === "number").map(k => t("pr.out." + k, { n: o[k] })).join(" · ") || null; };
  function remoteRuns(n) {
    const p = TASK.process(n) || {}, R = EXPLAIN.read, rows = [], m = p.remote || "—";
    if (n === 3 && TASK.has("story.runs")) {
      const tr = resource("train_cu") || {};
      ((STORY && STORY.runs) || []).filter(r => !/\.attempt/.test(r.branch || "")).forEach(r => { const live = trainLive(r.branch), c = (tr.per_model_cu || {})[r.branch];
        rows.push({ name: EXPLAIN.runName(r.branch), tip: r.branch + " · " + r.job, mach: m, state: live && live.running ? "running" : "ok", when: live && live.at, res: t("pr.runs.steps", { s: UI.fmt(r.step, "int"), m: UI.fmt(r.max_steps, "int") }) + (c != null ? " · " + t("pr.runs.cu", { cu: UI.fmt(c, "float1") }) : ""), origin: "file", src: "story.json · runs" + (c != null ? "; " + tr.source : ""), link: "#/runs?sel=" + encodeURIComponent(r.branch), lk: t("tab.result") }); });
    }
    if (n === 4 && TASK.has("story.pair")) (R.pair().runs || []).forEach(r => rows.push({ name: EXPLAIN.runName(r.run), tip: r.run, mach: m, state: "ok", res: t("pr.runs.eval", { k: r.successes, n: r.n }), origin: "file", src: R.pair().source, link: "#/eval", lk: t("tab.result") }));
    if (n === 4 && !TASK.round()) ((TASK.cur() || {}).evals || []).filter(e => e.n != null).forEach(e => rows.push({ name: L(e.label) || e.id, tip: e.id, mach: m, state: "ok", res: t("pr.runs.eval", { k: e.successes, n: e.n }), origin: e.origin || "file", src: e.source, link: EXPLAIN.href(4), lk: t("tab.result") }));
    const dg = demo().diagnose, rd = TASK.round();
    if (n === 5 && rd && dg) { const nd = (dg.to_data || []).length, nt = Object.values(dg.tickets || {}).reduce((s, x) => s + x.length, 0);
      rows.push({ name: t("pr.runs.diag", { r: rd.number }), tip: dg.source, mach: t("pr.runs.hand"), state: "ok", res: t("pr.runs.groups", { d: nd, m: nd + nt }), origin: "cited", src: dg.source, link: EXPLAIN.href(5), lk: t("tab.result") }); }
    if (n === 6 && rd && TASK.has("story.round")) rows.push({ name: L(rd.title), tip: rd.id + " · " + (rd.doc || ""), mach: m === "—" ? t("pr.runs.many") : m, state: "ok", res: EXPLAIN.roundLine(), origin: "file", src: (R.pair().source || "story.json · pair"), link: EXPLAIN.href(6), lk: t("tab.result") });
    if (n === 0 && TASK.has("story.ledger")) ((STORY && STORY.ledger) || []).forEach(r => rows.push({ name: r[0], tip: "docs/g0/ledger/" + r[0] + ".csv", mach: "—", state: r[2] ? "ok" : "none", res: t("pr.runs.led", { e: UI.fmt(r[1], "float1"), m: r[2] ? UI.fmt(r[2], "float1") : "—" }), origin: "file", src: "story.json · ledger (docs/g0/ledger/*.csv)" }));
    return rows;
  }
  P.runs = async function (n) {
    const [jobs] = await Promise.all([P.jobs(), P.kinds()]), p = TASK.process(n) || {};
    const rows = P.stageJobs(jobs, n).map(j => ({ name: (j.chain_id ? "↳ " : "") + P.kindTitle(j), tip: j.id + " · " + j.kind, task: j.task && j.task !== "unknown" ? TASK.name(j.task) || j.task : t("pr.runs.shared"),
      mach: j.host || "laptop", state: j.state === "ok" ? "ok" : active(j) ? "running" : j.state, when: j.started || j.created, dur: jdur(j), res: jobRes(j), link: P.href(n, "log", "job=" + j.id), lk: t("tab.log") }));
    const rem = remoteRuns(n).map(r => Object.assign({ task: TASK.name() }, r));
    if (!rows.length && !rem.length) return [UI.empty({ tag: t("pr.runs.tag"), title: t("pr.runs.none"), where: p.remote, missing: L(p.missing), how: p.how })];
    const COLS = ["name", "task", "mach", "state", "when", "dur", "res", "open"];
    const tb = (rs, title) => sec(title, h("div", { class: "pr-tscroll" }, h("table", { class: "pr-tbl" }, [h("thead", null, h("tr", null, COLS.map(c => h("th", { class: c === "dur" ? "r" : "", text: t("pr.c." + c) })))),
      h("tbody", null, rs.map(r => h("tr", null, [h("td", { title: r.tip }, h("b", { text: r.name })), h("td", { text: r.task || "—" }), h("td", { text: r.mach }), h("td", null, P.chip(r.state)), h("td", { class: "mono", text: r.when ? when(r.when) : "—" }),
        h("td", { class: "r mono", text: r.dur != null ? UI.fmt(r.dur, "dur") : "—" }), h("td", { title: r.src || null }, [r.res || "—", r.res && r.origin ? UI.origin(r.origin, r.src) : null]),
        h("td", null, r.link ? h("a", { href: r.link, text: r.lk || "→" }) : "—")])))])));
    return [rem.length ? tb(rem, t("pr.runs.remote", { m: p.remote || t("pr.runs.index") })) : null, rows.length ? tb(rows, t("pr.runs.console", { n: rows.length })) : null].filter(Boolean);
  };

  /* ---------- Chạy thử: kinds of this stage from /api/kinds, ready-made samples, the run and its log ---------- */
  P.lockNote = () => h("div", { class: "pr-lock" }, [h("b", { text: "🔒 " + t("pr.try.locked") }), h("span", { text: t("pr.try.unlock") }), code("fw console serve")]);
  /* the kind's command is a display template: "--flag <name>" or "--flag …" takes the sample's value for that flag,
     a bare <name> the value of that name; <job> stays (the id exists once the job starts) */
  const cmdOf = (k, s) => { const P0 = (s && s.params) || {}, val = a => P0[a] != null && typeof P0[a] !== "object" ? String(P0[a]) : null;
    return String(k.command || "").replace(/--([\w-]+) (<\w+>|…)/g, (m, f) => { const v = val(f.replace(/-/g, "_")); return v != null ? "--" + f + " " + v : m; })
      .replace(/<(\w+)>/g, (m, a) => val(a) != null ? val(a) : m); };
  function kindCard(n, k, qs) {
    const order = s => (s.available === false ? 4 : 0) + (s.task === TASK.id ? 0 : !s.task ? 1 : 2);
    const ss = (k.samples || []).map((s, i) => Object.assign({ i }, s)).sort((a, b) => order(a) - order(b) || a.i - b.i);
    const card = h("section", { class: "pr-card pr-kcard", id: "k-" + k.kind.replace(/\./g, "-") });
    let pick = ss.find(s => qs.kind === k.kind && String(s.i) === qs.sample) || ss.find(s => s.available !== false && (s.task === TASK.id || !s.task)) || ss.find(s => s.available !== false) || null, more = false;
    const listBox = h("div", { class: "pr-samples" }), detail = h("div", { class: "pr-detail" }), runArea = h("div", { class: "pr-runarea" });
    const tags = s => [s.fixture ? h("span", { class: "pr-tag fx", text: t("pr.try.fixture") }) : null, s.task && s.task !== TASK.id ? h("span", { class: "pr-tag", text: t("pr.try.other", { t: TASK.name(s.task) || s.task }) }) : null,
      s.available === false ? h("span", { class: "pr-tag no", title: L(s.reason), text: t("pr.try.na") }) : null];
    const paintList = () => { const shown = more ? ss : ss.slice(0, 6);
      put(listBox, ...shown.map(s => h("button", { class: "pr-sample" + (s === pick ? " on" : ""), disabled: s.available === false, title: s.available === false ? t("pr.try.unavail", { r: L(s.reason) }) : null,
        onclick: () => { pick = s; UI.setQs({ kind: k.kind, sample: s.i }); paintList(); paintDetail(); } }, [h("span", { class: "nm", text: UI.redact(L(s.label)) }), ...tags(s)])),
        ss.length > 6 && !more ? h("button", { class: "u-btn sm", text: t("pr.try.more", { n: ss.length - 6 }), onclick: () => { more = true; paintList(); } }) : null); };
    const paintDetail = () => {
      if (!pick) { put(detail, h("p", { class: "dim", text: ss.length ? t("pr.try.pick") : t("pr.try.nosample") })); return; }
      const typ = pick.last_seconds != null ? pick.last_seconds : k.typical_seconds, ok = k.available !== false && pick.available !== false;
      const btn = h("button", { class: "u-btn pri wbtn pr-run", disabled: !ok, text: "▶ " + t("pr.try.run"), onclick: () => run(n, k, pick, runArea, btn) });
      put(detail, h("div", { class: "pr-dl" }, [h("small", { text: t("pr.try.cmd") }), code(cmdOf(k, pick))]),
        h("table", { class: "pr-kv" }, h("tbody", null, Object.keys(pick.params || {}).map(key => h("tr", null, [h("th", { text: key }), h("td", { class: "mono", text: UI.redact(typeof pick.params[key] === "object" ? JSON.stringify(pick.params[key]) : String(pick.params[key])) })])))),
        h("div", { class: "pr-meta" }, [h("span", { text: typ != null ? t("pr.try.typ", { d: UI.fmt(typ, "dur") }) : t("pr.try.typNone") }), k.n_ok_runs ? h("span", { class: "dim", text: t("pr.try.nok", { n: k.n_ok_runs }) }) : null,
          (k.chain || []).length ? h("span", { class: "dim", text: t("pr.try.chain", { c: k.chain.join(" → ") }) }) : null]),
        L(k.outputs) ? h("p", { class: "dim", text: t("pr.try.outputs") + ": " + UI.redact(L(k.outputs)) }) : null,
        h("div", { class: "pr-acts" }, [btn, k.available === false ? h("span", { class: "dim", text: t("pr.try.unavail", { r: L(k.reason) }) }) : null]));
    };
    card.append(h("div", { class: "pr-khead" }, [h("h3", { class: "pr-h3", text: L(k.title) }), h("code", { class: "dim", text: k.kind }), h("span", { class: "pr-where" }, [h("small", { text: t("pr.where") }), String(k.runs_on || "laptop")])]),
      h("div", { class: "pr-kbody" }, [h("div", null, [h("small", { class: "pr-lab", text: t("pr.try.samples", { n: ss.length }) }), listBox]), h("div", null, [detail])]), runArea);
    paintList(); paintDetail();
    return card;
  }
  async function run(n, k, s, area, btn) {
    if (!UI.canWrite(L(k.title) + " · " + UI.redact(L(s.label)))) return;
    btn.disabled = true; put(area, h("p", { class: "dim", text: t("pr.try.starting") }));
    try {
      const r = await fetch("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: k.kind, params: s.params || {} }) });
      const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || "HTTP " + r.status);
      follow(n, d.id, area, btn);
    } catch (e) { btn.disabled = false; put(area, h("p", { class: "c-bad", text: "✕ " + e.message })); }
  }
  function follow(n, id, area, btn) {
    const st = h("div", { class: "pr-runst" }), main = UI.Log({ jobId: id }), childBox = h("div"), res = h("div");
    let child = null, childLog = null;
    put(area, st, h("div", { class: "pr-logv" }, main), childBox, res);
    const tick = async () => {
      if (!area.isConnected) { clearInterval(tm); return; }
      const j = await fetch("/api/jobs/" + id).then(r => r.ok ? r.json() : null).catch(() => null); if (!j) return;
      put(st, P.chip(j.state === "ok" ? "ok" : active(j) ? "running" : j.state), h("b", { text: P.kindTitle(j) }), h("span", { class: "dim mono", text: j.id }), jdur(j) != null ? h("span", { class: "dim", text: UI.fmt(jdur(j), "dur") }) : null);
      const cur = (j.outputs || {}).current;
      if (cur && cur !== child) { child = cur; if (!childLog) { childLog = UI.Log({ jobId: cur }); put(childBox, h("small", { class: "pr-lab", text: t("pr.try.child") }), h("div", { class: "pr-logv" }, childLog)); } else childLog.setJob(cur); }
      if (!active(j)) {
        clearInterval(tm); btn.disabled = false; K = null;   /* durations and samples change after a run */
        const o = j.outputs || {}, keys = Object.keys(o).filter(x => x !== "children" && x !== "current" && o[x] != null && typeof o[x] !== "object");
        put(res, sec(j.state === "ok" ? t("pr.try.done", { d: UI.fmt(jdur(j), "dur") }) : t("pr.try.failed", { rc: j.rc == null ? "—" : j.rc }), [
          keys.length ? h("table", { class: "pr-kv" }, h("tbody", null, keys.map(x => h("tr", null, [h("th", { text: x }), h("td", { class: "mono", text: UI.redact(String(o[x])) })])))) : null,
          h("div", { class: "pr-acts" }, [h("a", { href: P.href(n, "runs"), text: t("pr.try.seeRuns") + " →" }), h("a", { href: "#/jobs?job=" + j.id, text: t("pr.try.openJob") + " →" })])], j.state === "ok" ? "ok" : "bad"));
      }
    };
    const tm = setInterval(tick, 1000); tick();
  }
  const remoteCard = r => h("div", { class: "pr-rcard" }, [h("b", { text: L(r.title) }),
    h("p", null, [h("small", { text: t("pr.try.where") }), L(r.where)]), h("p", null, [h("small", { text: t("pr.try.why") }), L(r.why)]), h("p", null, [h("small", { text: t("pr.try.observe") }), UI.redact(L(r.observe))]),
    (r.docs || []).length ? h("p", { class: "dim" }, r.docs.map(d => h("code", { text: d + " " }))) : null]);
  P.try = async function (n, qs) {
    await P.kinds();
    const ks = kindsOf(n), rm = remoteOf(n), out = [];
    if (UI.locked) out.push(P.lockNote());
    if (!ks.length) out.push(UI.empty({ tag: t("pr.try.tag"), title: t("pr.try.none"), where: (TASK.process(n) || {}).remote }));
    ks.forEach(k => out.push(kindCard(n, k, qs)));
    if (rm.length) out.push(sec(t("pr.try.remote"), h("div", { class: "pr-rgrid" }, rm.map(remoteCard))));
    if (qs.kind) setTimeout(() => { const el = document.getElementById("k-" + qs.kind.replace(/\./g, "-")); if (el) el.scrollIntoView({ block: "start" }); }, 50);
    return out;
  };
  P.tab = (n, tab, qs) => tab === "how" ? P.how(n) : tab === "log" ? P.log(n, qs) : tab === "runs" ? P.runs(n) : P.try(n, qs);

  /* ---------- #/home · overview of the process for the selected task and round ---------- */
  const STATUS_STAGE = { collect: 1, process: 1, release: 1, train: 3, eval: 4, loop: 6 };
  function costOf(n) {
    if (!TASK.has("story.demo")) return null;
    const D = demo();
    if (n === 3) { const s = sumCu(resource("train_cu")); return s ? { v: t("pr.home.cost.train", { cu: UI.fmt(s.cu, "int"), k: s.k }), o: "file", src: resource("train_cu").source } : null; }
    if (n === 4) { const s = sumCu(resource("test_cu")); return s ? { v: t("pr.home.cost.test", { cu: UI.fmt(s.cu, "int"), k: s.k }), o: "file", src: resource("test_cu").source } : null; }
    if (n === 5 && D.diagnose && D.diagnose.cost_cu) return { v: t("pr.runs.cu", { cu: D.diagnose.cost_cu.value }), o: "cited", src: D.diagnose.cost_cu.source };
    if (n === 6) { const g = resource("gen_cu"), mh = resource("gen_machine_hours"); return g ? { v: t("pr.home.cost.gen", { cu: g.value, h: mh ? UI.fmt(mh.value, "float1") : "—" }), o: "cited", src: g.source } : null; }
    if (n === 0 && D.round_cost && D.round_cost.total_cu != null) return { v: t("pr.home.cost.round", { cu: UI.fmt(D.round_cost.total_cu, "float1"), r: (TASK.round() || {}).number }), o: "cited", src: D.round_cost.source };
    return null;
  }
  P.costOf = costOf;
  function waitOf(n, js) {
    const w = [];
    const ag = S().agent, runJobs = new Set(((STORY && STORY.runs) || []).map(r => r.job));
    if (n === 2 && ag && ag.findings && (ag.runs || []).some(r => runJobs.has(r.input))) w.push(t("pr.home.wait.findings", { n: ag.findings }));
    const failed = js.filter(j => j.state === "failed" && !js.some(o => o.kind === j.kind && o.state === "ok" && o.created > j.created));
    if (failed.length) w.push(t("pr.home.wait.failed", { n: failed.length }));
    (S().stages || []).filter(s => STATUS_STAGE[s.id] === n && s.state === "waiting" && (!s.task || s.task === TASK.id)).forEach(s => w.push(s.now || s.label));
    return w;
  }
  P.home = async function (body) {
    const [jobs] = await Promise.all([P.jobs(), P.kinds()]), c = TASK.cur() || {}, rd = TASK.round();
    document.title = t("nav.overview") + " · " + TASK.name();
    body.appendChild(h("header", { class: "pr-head home" }, [h("div", { class: "pr-kick", text: t("nav.overview") }),
      h("div", { class: "pr-title" }, [h("h1", { text: TASK.name() }), h("span", { class: "pr-where" }, [h("small", { text: t("task.round") }), rd ? L(rd.title) : t("task.noround")]),
        rd ? h("a", { class: "pr-rep", href: "#/report", text: t("pr.toReport") }) : null]),
      h("p", { class: "pr-lead", text: t("pr.home.lead") }),
      h("p", { class: "pr-sub" }, [L(c.description), " ", h("span", { class: "dim", text: [c.robot, c.model, c.simulator].filter(Boolean).join(" · ") })])]));
    if (window.TASKS) body.appendChild(TASKS.hero());
    const head = ["step", "state", "last", "num", "cost", "wait"].map(k => h("th", { text: t("pr.home.c." + k) }));
    const rows = P.ORDER.map(n => {
      const js = P.stageJobs(jobs, n), p = TASK.process(n) || {}, node = EXPLAIN.node(n), live = n === 3 ? TASK.runs().map(trainLive).filter(Boolean) : [];
      const running = js.some(active) || live.some(x => x.running), done = !!node || js.some(j => j.state === "ok" && j.task === TASK.id) || ((p.needs || []).length > 0 && TASK.hasData(n));
      const lastJob = js[0], lastRemote = live.map(x => x.at).filter(Boolean).sort().pop();
      const lastAt = [lastJob && (lastJob.ended || lastJob.started || lastJob.created), lastRemote].filter(Boolean).sort().pop();
      const lastM = lastAt && lastJob && lastAt === (lastJob.ended || lastJob.started || lastJob.created) ? (lastJob.host || "laptop") : p.remote;
      const cost = costOf(n), wait = waitOf(n, js);
      return h("tr", { class: "lnk", onclick: e => { if (!e.target.closest("a")) location.hash = EXPLAIN.href(n); } }, [
        h("td", null, h("a", { class: "pr-step", href: EXPLAIN.href(n) }, [h("span", { class: "pr-sn sm" + (n ? "" : " cost"), text: n ? String(n) : "$" }), h("span", null, [h("b", { text: P.name(n) }), h("small", { text: P.sub(n) })])])),
        h("td", null, [P.chip(running ? "run" : done ? "done" : "none"), p.remote ? P.chip("remote", p.remote) : null]),
        h("td", { class: "mono" }, lastAt ? [when(lastAt), h("small", { text: lastM || "" })] : h("span", { class: "dim", text: p.remote && !done ? t("pr.home.remoteOnly", { m: p.remote }) : "—" })),
        h("td", { title: node && node.src ? t("xb.src") + ": " + node.src : null }, node ? [h("b", { class: "pr-num", text: node.v }), UI.origin(node.origin, node.src)] : h("span", { class: "dim", text: "—" })),
        h("td", null, cost ? [cost.v, UI.origin(cost.o, cost.src)] : h("span", { class: "dim", text: "—" })),
        h("td", null, wait.length ? wait.map(x => h("div", { class: "pr-wait", text: x })) : h("span", { class: "dim", text: "—" }))]);
    });
    body.appendChild(sec(t("tk.detail"), h("div", { class: "pr-tscroll" }, h("table", { class: "pr-tbl pr-ov" }, [h("thead", null, h("tr", null, head)), h("tbody", null, rows)]))));
    /* what is running now, and what this machine can run now */
    const run = jobs.filter(active), live = TASK.runs().map(id => [id, trainLive(id)]).filter(([, x]) => x && x.running);
    const runList = run.length || live.length ? h("div", { class: "pr-list" }, [
      ...run.map(j => { const n = P.stageOfJob(j); return h("a", { class: "pr-li", href: n != null ? P.href(n, "log", "job=" + j.id) : "#/jobs?job=" + j.id }, [P.chip("running"), h("b", { text: P.kindTitle(j) }), h("span", { class: "dim", text: (n != null ? n + " · " + P.name(n) + " · " : "") + when(j.started || j.created) })]); }),
      ...live.map(([id]) => h("a", { class: "pr-li", href: P.href(3, "log") }, [P.chip("running"), h("b", { text: EXPLAIN.runName(id) }), h("span", { class: "dim", text: "3 · " + P.name(3) + " · " + ((TASK.process(3) || {}).remote || "") })]))])
      : h("p", { class: "dim", text: t("pr.home.runNone") });
    /* in lock mode every kind is "unavailable: read-only": list what this laptop could run, under the lock note */
    const can = ((K && K.kinds) || []).filter(k => k.stage in STAGE_OF && (k.available !== false || K.locked)).map(k => [k, (k.samples || []).filter(s => s.available !== false && (!s.task || s.task === TASK.id)).length]).filter(([, m]) => m > 0);
    const canList = can.length ? h("div", { class: "pr-list" }, can.map(([k, m]) => { const n = STAGE_OF[k.stage];
      return h("a", { class: "pr-li", href: P.href(n, "try", "kind=" + k.kind) }, [h("span", { class: "pr-sn sm", text: String(n) }), h("b", { text: L(k.title) }), h("span", { class: "dim", text: t("pr.home.canN", { n: m }) + (k.typical_seconds != null ? " · " + t("pr.try.typ", { d: UI.fmt(k.typical_seconds, "dur") }) : "") })]); }))
      : h("p", { class: "dim", text: t("pr.home.canNone") });
    body.appendChild(h("div", { class: "pr-cols" }, [sec(t("pr.home.running"), runList), sec(t("pr.home.can"), [UI.locked ? h("p", { class: "pr-locksm", text: "🔒 " + t("pr.try.locked") }) : null, canList])]));
  };

  /* ---------- the round report: sub-navigation, link back to the process ---------- */
  P.REPORT = [["report", "pr.rep.wheel"], ["follow", "fol.title"], ["base", "sb.base.nav"], ["design", "sb.de.nav"]];
  P.reportHead = function (page, qs) {
    const rd = TASK.round(), s = page === "report" && qs.s != null && qs.s !== "" ? Math.min(6, Math.max(0, Math.round(+qs.s) || 0)) : null;
    const back = page === "report" ? (s != null ? EXPLAIN.href(s) : "#/home") : page === "follow" ? EXPLAIN.href(6) : "#/home";
    return h("header", { class: "pr-head rep" }, [h("div", { class: "pr-kick" }, [h("span", { text: t("nav.report") }), h("span", { class: "dim", text: " · " + TASK.name() })]),
      h("div", { class: "pr-title" }, [h("h1", { text: rd ? L(rd.title) : t("nav.report") }), h("a", { class: "pr-rep", href: back, text: t("pr.toProc"), onclick: e => { if (page !== "report") return;   /* the wheel changes ?s= without a re-render */
        const v = UI.qs().s; if (v != null && v !== "") { e.preventDefault(); location.hash = EXPLAIN.href(Math.min(6, Math.max(0, Math.round(+v) || 0))); } } })]),
      h("nav", { class: "pr-tabs" }, P.REPORT.map(([id, k]) => h("a", { class: id === page ? "on" : "", href: "#/" + id, text: t(k) })))]);
  };
  P.noRound = () => { const p6 = TASK.process(6) || {};
    return UI.empty({ tag: t("empty.noround.tag"), title: t("empty.noround", { t: TASK.name() }), missing: L(p6.missing) || t("pr.rep.needs"), how: p6.how }); };
  return P;
})();
window.PROC = PROC;
