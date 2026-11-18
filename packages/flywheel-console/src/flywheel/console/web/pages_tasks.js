/* Workspace (#/tasks): one card per task of the manifest, and what adding a task takes. Also the hero and the
   six-stage strip of the task overview (#/home, called from PROC.home).
   Every number is a stage's EXPLAIN.node, read with that task in scope (withTask), so a card never shows another
   task's numbers; a stage without data says "chưa chạy". Text: i18n (tk.*). */
"use strict";
const TASKS = (() => {
  const T = {}, STG = [1, 2, 3, 4, 5, 6];
  const L = o => o == null ? "" : typeof o === "object" ? (o[UI.lang] || o.vi || "") : String(o);
  const lab = nd => nd.l || nd.label || nd.k || "";
  /* run fn with task id as the (task, round) context, then restore: the EXPLAIN readers ask TASK, STORY and SIMD */
  function withTask(id, fn) {
    const k = [TASK.id, TASK.roundId], s = STORY, d = SIMD;
    try { TASK.set(id); STORY = TASK.scopeStory(STORY_RAW || {}); SIMD = TASK.scopeSim(SIMD_RAW || {}); return fn(); }
    finally { TASK.set(k[0], k[1]); STORY = s; SIMD = d; }
  }
  function media() {
    const c = ((STORY && STORY.demo) || {}).success_clip, e = ((SIMD && SIMD.teleop) || [])[0] || ((SIMD && SIMD.episodes) || [])[0];
    if (c && c.path) return { video: "/demomedia/" + String(c.path).split("/").pop() };
    return e ? { poster: e.poster ? "/simmedia/" + e.poster : null, video: e.video ? "/simmedia/" + e.video : null } : null;
  }
  T.summary = id => withTask(id, () => {
    const c = TASK.cur() || {}, rd = TASK.round(), nodes = {}, done = {};
    STG.forEach(n => { const p = TASK.process(n) || {}; nodes[n] = EXPLAIN.node(n); done[n] = !!nodes[n] || ((p.needs || []).length > 0 && TASK.hasData(n)); });
    const todo = STG.find(n => !done[n]);
    return { id, name: TASK.name(), desc: L(c.description), meta: [c.robot, c.model, t("tk.steps", { n: (c.stages || []).length })].filter(Boolean).join(" · "),
      nodes, done, media: media(), round: rd ? L(rd.title) : null, cost: PROC.costOf(0),
      next: todo ? t("tk.next", { s: PROC.name(todo) }) : t("tk.next.round"), open: !todo };
  });
  /* the clip: a poster that plays on hover, or the video's first frame when the index has no poster */
  function clip(m, cls) {
    if (!m || (!m.poster && !m.video)) return h("div", { class: "tk-clip none " + (cls || "") });
    if (m.poster) return hoverVideo(m.poster, m.video, "tk-clip " + (cls || ""));
    const v = h("video", { src: m.video, preload: "metadata", playsinline: true, muted: true, loop: true }); v.muted = true;
    const box = h("div", { class: "tk-clip " + (cls || "") }, [v, h("span", { class: "tk-play", text: "▶" })]);
    box.onmouseenter = () => { v.play().catch(() => {}); box.classList.add("on"); };
    box.onmouseleave = () => { v.pause(); box.classList.remove("on"); };
    return box;
  }
  const bar = s => h("div", { class: "tk-bar" }, STG.map(n => h("i", { class: s.done[n] ? "on" : "", title: n + " · " + PROC.name(n) + " · " + t(s.done[n] ? "pr.s.done" : "pr.s.none") })));
  const big = s => { const nd = s.nodes[4];
    return h("div", { class: "tk-big" }, nd ? [h("b", { text: nd.v }), h("span", { text: lab(nd) || t("tk.best") }), UI.origin(nd.origin, nd.src)] : [h("b", { class: "dim", text: "—" }), h("span", { text: t("tk.noeval") })]); };
  const facts = s => [s.round || t("task.noround"), s.nodes[1] ? t("tk.eps", { n: s.nodes[1].v }) : null, s.cost ? s.cost.v : null].filter(Boolean).join(" · ");
  const pick = id => { TASK.set(id); UI.pref("v5task", TASK.id); retask(); };

  function card(s) {
    const on = s.id === TASK.id;
    return h("a", { class: "tk-card" + (on ? " on" : ""), href: "#/home", onclick: () => { if (!on) pick(s.id); } }, [clip(s.media),
      h("div", { class: "tk-body" }, [h("div", { class: "tk-name" }, [h("b", { text: s.name }), on ? h("span", { class: "pr-chip run", text: t("tk.cur") }) : null]),
        h("div", { class: "tk-meta", text: s.meta }), big(s), bar(s), h("div", { class: "tk-meta", text: facts(s) }),
        h("div", { class: "tk-foot" }, [h("span", { class: "tk-next" + (s.open ? " ok" : ""), text: s.next }), h("span", { class: "tk-open", text: t("tk.open") + " →" })])])]);
  }
  /* every task against the six stages: the stage's number, or "chưa chạy" */
  function matrix(ss) {
    const cell = (s, n) => { const nd = s.nodes[n];
      return h("td", { class: nd ? "" : "dim", title: nd ? lab(nd) : null }, nd ? [h("b", { text: nd.v }), UI.origin(nd.origin, nd.src)] : t("pr.s.none")); };
    return h("section", { class: "tk-new" }, [h("div", { class: "tk-newh" }, [h("b", { text: t("tk.mx") }), h("span", { text: t("tk.mx.sub") })]),
      h("div", { class: "pr-tscroll" }, h("table", { class: "pr-tbl tk-mx" }, [
        h("thead", null, h("tr", null, [h("th", { text: t("pr.c.task") }), ...STG.map(n => h("th", null, [h("span", { class: "pr-sn sm", text: String(n) }), " " + PROC.name(n)])), h("th")])),
        h("tbody", null, ss.map(s => h("tr", { class: "lnk", onclick: () => { if (s.id !== TASK.id) pick(s.id); location.hash = "#/home"; } }, [h("td", null, h("b", { text: s.name })), ...STG.map(n => cell(s, n)),
          h("td", null, h("span", { class: "tk-next" + (s.open ? " ok" : ""), text: s.next }))])))]))]);
  }
  function newTask() {
    const ex = (TASK.list()[0] || {}).scorer_config || "", steps = [["seed/tasks.yaml"], [ex], ["fw data ingest", "fw data qa", "fw data release"], ["fw console index"]];
    return h("section", { class: "tk-new", id: "tk-new" }, [h("div", { class: "tk-newh" }, [h("b", { text: "＋ " + t("tk.new") }), h("span", { text: t("tk.new.sub") })]),
      h("div", { class: "tk-steps" }, steps.map((codes, i) => h("div", { class: "tk-step" }, [h("span", { class: "pr-sn sm", text: String(i + 1) }), h("b", { text: t("tk.new." + (i + 1) + ".t") }),
        h("p", { text: t("tk.new." + (i + 1) + ".d") }), ...codes.filter(Boolean).map(c => h("code", { text: c }))]))),
      h("p", { class: "tk-note", text: t("tk.new.note") })]);
  }
  UI.route("tasks", async body => {
    document.title = "FW · " + t("tk.title"); await PROC.kinds();
    const ss = TASK.list().map(x => T.summary(x.id));
    body.appendChild(h("header", { class: "pr-head" }, [h("div", { class: "pr-kick", text: t("tk.kick") }),
      h("div", { class: "pr-title" }, [h("h1", { text: t("tk.title") }), h("span", { class: "pr-where", text: t("tk.count", { n: ss.length }) })]), h("p", { class: "pr-lead", text: t("tk.lead") })]));
    body.appendChild(h("div", { class: "tk-grid" }, [...ss.map(card),
      h("a", { class: "tk-card add", href: "javascript:void 0", onclick: () => document.getElementById("tk-new").scrollIntoView({ block: "center" }) }, [h("span", { class: "tk-plus", text: "＋" }), h("b", { text: t("tk.new") }), h("span", { text: t("tk.new.sub") })])]));
    body.appendChild(matrix(ss));
    body.appendChild(newTask());
  });

  /* ---------- #/home: the clip and headline, then the six stages as one strip with their numbers ---------- */
  T.hero = function () {
    const s = T.summary(TASK.id);
    const tile = n => { const nd = s.nodes[n];
      return h("a", { class: "tk-st s" + n + (s.done[n] ? "" : " none"), href: EXPLAIN.href(n), title: nd && nd.src ? t("xb.src") + ": " + nd.src : null }, [
        h("div", { class: "tk-sth" }, [h("span", { class: "pr-sn sm", text: String(n) }), h("span", { text: PROC.name(n) })]),
        nd ? h("b", { text: nd.v }) : h("b", { class: "dim", text: t("pr.s.none") }),
        h("small", null, nd ? [lab(nd) || t("tk.u." + n), UI.origin(nd.origin, nd.src)] : [L((TASK.process(n) || {}).remote) || t("pr.laptop")])]); };
    return h("section", { class: "tk-hero" }, [
      h("div", { class: "tk-top" }, [clip(s.media, "lg"), h("div", { class: "tk-head" }, [big(s), h("p", { class: "tk-meta", text: facts(s) }), bar(s),
        h("div", { class: "tk-foot" }, [h("span", { class: "tk-next" + (s.open ? " ok" : ""), text: s.next }), TASK.round() ? h("a", { href: "#/report", text: t("pr.toReport") }) : null])])]),
      h("div", { class: "tk-strip" }, STG.map(tile)), h("div", { class: "tk-loop", text: "↺ " + t("tk.loop") })]);
  };
  return T;
})();
window.TASKS = TASKS;
