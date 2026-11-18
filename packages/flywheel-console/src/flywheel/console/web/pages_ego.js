/* #/egoflow: how a raw first-person video becomes a labelled episode (text + two tracked hands).
   Seven steps of `fw egocentric …`, each with the tool or model that does it and where it runs; the counts come from
   story.json (h1m: the export's own summary), the clip on the right is the /ego/ viewer of one exported episode.
   Which models are, and are not, in this path: configs/data/egocentric.yaml and docs/g0/egocentric.md. Text: i18n (eg.*). */
"use strict";
UI.route("egoflow", async body => {
  document.title = "FW · " + t("eg.title");
  const ego = await EGOP().catch(() => null), H = (STORY_RAW || {}).h1m || null, N = v => v == null ? null : UI.fmt(v, "int");
  const d = (H && H.decisions) || {}, q = (H && H.qa) || {};
  /* step → the count the export's summary gives for it (null: no number, the step shows its text only) */
  const num = [H ? [N(H.clips), t("eg.u.clips")] : null, null, H && H.hands_visible_ge_95 != null ? [UI.fmt(H.hands_visible_ge_95, "pct"), t("eg.u.hands")] : null, null,
    q.pass != null ? [N(q.pass) + " · " + N(q.flag) + " · " + N(q.reject), t("eg.u.qa")] : null, d.excluded != null ? [N(d.excluded), t("eg.u.excl")] : null, d.exported != null ? [N(d.exported), t("eg.u.out")] : null];
  const CMD = ["ingest", "deid", "pose", "annotate", "qa", "review", "human1m"];
  body.appendChild(h("header", { class: "pr-head" }, [h("div", { class: "pr-kick", text: t("eg.kick") }), h("div", { class: "pr-title" }, [h("h1", { text: t("eg.title") }),
    h("a", { class: "pr-rep", href: "#/jobs?view=pipeline", text: t("eg.run") + " →" })]), h("p", { class: "pr-lead", text: t("eg.lead") })]));
  body.appendChild(h("div", { class: "eg-steps" }, CMD.map((c, i) => h("div", { class: "eg-step" }, [
    h("div", { class: "tk-sth" }, [h("span", { class: "pr-sn sm", text: String(i + 1) }), h("span", { text: t("eg." + (i + 1) + ".t") })]),
    num[i] ? h("b", null, [num[i][0], UI.origin("file", "story.json · h1m")]) : null, num[i] ? h("small", { text: num[i][1] }) : null,
    h("p", { text: t("eg." + (i + 1) + ".d") }), h("div", { class: "eg-tool" }, [h("small", { text: t("eg.by") }), t("eg." + (i + 1) + ".m")]),
    h("code", { text: "fw egocentric " + c })]))));
  const ep = ego && (ego.episodes || [])[0];
  body.appendChild(h("div", { class: "eg-cols" }, [
    h("section", { class: "pr-card" }, [h("h3", { class: "pr-h3", text: t("eg.models") }), h("table", { class: "pr-tbl" }, h("tbody", null, [1, 2, 3, 4, 5].map(i =>
      h("tr", null, [h("td", null, h("b", { text: t("eg.m" + i + ".n") })), h("td", null, h("span", { class: "pr-chip " + (i < 3 ? "ok" : "idle"), text: t(i < 3 ? "eg.used" : i === 5 ? "eg.other" : "eg.trial") })), h("td", { text: t("eg.m" + i + ".d") })])))),
      h("p", { class: "dim", text: t("eg.src") })]),
    h("section", { class: "pr-card" }, [h("h3", { class: "pr-h3", text: t("eg.result") }), ep ? h("iframe", { class: "eg-frame", src: "/ego/index.html#/ep/" + ep.id, title: "viewer" }) : UI.empty({ title: t("eg.noviewer") }),
      h("a", { href: "/ego/", target: "_blank", text: t("eg.all", { n: ego ? (ego.episodes || []).length : 0 }) + " ↗" })])]));
});
