import {
  cleanLogLines,
  cls,
  compactPath,
  el,
  ensureStoryRaw,
  failureLabel,
  formatBytes,
  formatDateTime,
  formatNumber,
  formatPercent,
  getCurrentRound,
  getCurrentTask,
  getJSON,
  jigReadingLines,
  hasI18nKey,
  hasIndexAccess,
  pickLang,
  renderChartBlock,
  renderCrumbHeading,
  renderErrorBlock,
  renderLoadingView,
  renderProcessEmptyBlock,
  renderReportSubnav,
  renderRoundEmpty,
  renderSourceCitation,
  renderStatStrip,
  renderStateChip,
  scopeStoryForTask,
  scrubPath,
  setChildren,
  setSelection,
  shortHashId,
  stageLabel,
  state,
  t,
  taskSuccessText,
} from "./core.js";

const RUN_METRICS = ["loss", "val", "thr", "vram", "gn"];
const CHAIN_KEYS = ["targets", "generated", "recorded", "qa_pass", "quality", "selected"];

// Keep point estimates, uncertainty and exact values readable without a tooltip.
function comparisonPlot(title, rows, { bound, threshold, unit = "" } = {}) {
  const measured = rows.filter((row) => Number.isFinite(row.value));
  if (!measured.length) return null;
  const endpoints = measured.flatMap((row) => [row.value, ...(row.interval || [])]);
  if (Number.isFinite(threshold)) endpoints.push(threshold);
  const min = Math.min(0, ...endpoints);
  const max = Math.max(bound || 0, ...endpoints);
  const position = (value) => 100 * (value - min) / (max - min || 1);
  const label = (value) => formatNumber(value, { maximumFractionDigits: 4 }) + unit;

  return el("figure", { className: "comparison-plot" }, [
    el("figcaption", {}, [
      el("b", { text: title }),
      Number.isFinite(threshold)
        ? el("small", { text: t("visual.threshold", { value: label(threshold) }) })
        : null,
    ]),
    ...measured.map((row) => el("div", { className: "plot-row" }, [
      el("span", { text: row.name }),
      el("div", { className: "plot-track", "aria-hidden": "true" }, [
        row.interval ? el("i", { className: "plot-interval", style:
          `left:${position(row.interval[0])}%;width:${position(row.interval[1])-position(row.interval[0])}%` }) : null,
        Number.isFinite(threshold) ? el("i", { className: "plot-limit", style: `left:${position(threshold)}%` }) : null,
        el("i", { className: "plot-point", style: `left:${position(row.value)}%` }),
      ]),
      el("span", { className: "plot-value", text: row.label || label(row.value) }),
    ])),
    el("div", { className: "plot-row", "aria-hidden": "true" }, [
      el("span"), el("div", { className: "plot-axis" }, [
        el("span", { text: label(min) }), el("span", { text: label(max) }),
      ]),
    ]),
  ]);
}

function successPlot(runs) {
  return comparisonPlot(t("eval.colRate"), runs.map((run) => ({
    name: run.run,
    value: Number.isFinite(run.p) ? run.p * 100 : null,
    interval: Array.isArray(run.wilson) && run.wilson.length === 2 && run.wilson.every(Number.isFinite)
      ? run.wilson.map((value) => value * 100) : null,
    label: [
      `${formatPercent(run.p)} · ${formatNumber(run.successes)}/${formatNumber(run.n)}`,
      Array.isArray(run.wilson) && run.wilson.length === 2 && run.wilson.every(Number.isFinite)
        ? `${t("eval.colWilson")} ${formatPercent(run.wilson[0])}–${formatPercent(run.wilson[1])}`
        : "",
    ].filter(Boolean).join(" · "),
  })), { bound: 100, unit: "%" });
}

// Paired McNemar comparisons of round 1 (story.pair.comparisons). Only comparison (a′) decides
// stop or continue (docs/he/tray.md §20, rule of the round); (f), (g), (h) are descriptive
// (W4), so their outcome cell says "Chỉ mô tả" whatever the index wrote.
const DECIDING_TAG = "a";

function renderPairCompTable(pairComps) {
  return el("table", { className: "table" }, [
    el("thead", {}, [
      el("tr", {}, [
        el("th", { text: t("eval.colPair") }),
        el("th", { className: "num", text: "n" }),
        el("th", { className: "num", text: t("eval.colPairSucc") }),
        el("th", { className: "num", text: t("eval.colDiffCi") }),
        el("th", { className: "num", text: t("eval.colMcnemarP") }),
        el("th", { text: t("eval.colOutcome") }),
      ]),
    ]),
    el(
      "tbody",
      {},
      pairComps.map((c) =>
        el("tr", {}, [
          el("td", { className: "mono", text: `(${c.tag}) ${c.variant} · ${c.baseline}` }),
          el("td", { className: "num", text: formatNumber(c.n) }),
          el("td", { className: "num", text: `${c.variant_succ} · ${c.baseline_succ}` }),
          el("td", {
            className: "num",
            text: `${formatPercent(c.diff)} (${Array.isArray(c.ci) ? `${formatPercent(c.ci[0])} – ${formatPercent(c.ci[1])}` : "–"})`,
          }),
          el("td", {
            className: "num",
            text: formatNumber(c.mcnemar_p, { maximumFractionDigits: 3 }),
          }),
          el("td", {}, [
            c.tag === DECIDING_TAG
              ? renderStateChip(c.outcome)
              : el("span", { className: cls("chip", "neutral"), text: t("eval.descriptiveOnly") }),
          ]),
        ])
      )
    ),
  ]);
}

// Step-4 checks of round 1 (story.demo.diagnose.checks): ids H1–H3 are the hypotheses of
// tray.md §20.11 (not the spec's HS/HT/HD), shown with a Vietnamese title (W12).
function diagCheckTitle(id) {
  return hasI18nKey("diag.check." + id) ? t("diag.check." + id) : id;
}

function diagCheckText(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return formatVal(value);
  const word = (v) => {
    const slug = String(v).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    return hasI18nKey("diag.val." + slug) ? t("diag.val." + slug) : String(v);
  };
  return Object.entries(value)
    .map(([k, v]) => `${fieldLabel(k)}: ${Array.isArray(v) ? v.join(", ") : word(v)}`)
    .join(" · ");
}

// Outcome of one rollout (W1): "Thành công" / "Không thành công", never "Đạt".
function outcomeChip(success) {
  return el("span", {
    className: cls("chip", success ? "" : "danger"),
    text: t(success ? "outcome.ok" : "outcome.fail"),
  });
}

// "simple-tray-predicates@2" → "bộ chấm bản 2"; anything else as written.
function scorerLabel(raw) {
  if (raw === null || raw === undefined || raw === "") return "–";
  const m = String(raw).match(/@(\d+)$/) || String(raw).match(/^(\d+)$/);
  return m ? t("exp.scorerVersion", { v: m[1] }) : String(raw);
}

// Numbers inside a preformatted index string ("7.3–33.6") in the page's decimal style.
function localizeNumText(raw) {
  const str = String(raw);
  return state.lang === "vi" ? str.replace(/(\d)\.(\d)/g, "$1,$2") : str;
}

// A field name of an index object shown as a reader's word ("field.episodes" → "tập"),
// the raw name only when the dictionary has no entry.
function fieldLabel(k) {
  return hasI18nKey("field." + k) ? t("field." + k) : k;
}

function formatVal(val) {
  if (val === null || val === undefined) return t("state.na");
  if (typeof val === "number") return formatNumber(val, { maximumFractionDigits: 4 });
  if (typeof val === "boolean") return val ? t("common.yes") : t("common.no");
  if (Array.isArray(val)) return val.join(", ");
  if (typeof val === "object") {
    return Object.entries(val)
      .map(([k, v]) => `${fieldLabel(k)}: ${typeof v === "number" ? formatNumber(v, { maximumFractionDigits: 3 }) : v}`)
      .join(" · ");
  }
  return String(val);
}

// Design page rows (W12): a Vietnamese title per id; a translated description when the
// dictionary has one for that id (descriptions in the seed are English).
function designItemTitle(id) {
  return hasI18nKey("design.item." + id) ? t("design.item." + id) : id;
}

function designItemValue(item) {
  const raw = item.value ?? item.per_model_cu;
  if (typeof raw === "string" && hasI18nKey("design.desc." + item.id)) {
    return t("design.desc." + item.id);
  }
  return formatVal(raw);
}

function computeEmaPoints(pts, alpha = 0.14) {
  const out = [];
  let ema = null;
  for (const pt of pts) {
    if (!Array.isArray(pt) || pt[1] === null || !Number.isFinite(pt[1])) continue;
    ema = ema === null ? pt[1] : alpha * pt[1] + (1 - alpha) * ema;
    out.push([pt[0], Number(ema.toFixed(4))]);
  }
  return out;
}

// ============================================================================
// #/runs — Model Training
// ============================================================================
// Training speed (audit 02 A5): the index's thr_med is samples per second; newer indexes also
// carry samples_per_s and steps_per_s.
function runSpeedText(r) {
  if (!r) return null;
  const sps = Number.isFinite(r.samples_per_s) ? r.samples_per_s : r.thr_med;
  if (!Number.isFinite(sps)) return null;
  const main = t("runs.samplesPerS", { n: formatNumber(sps, { maximumFractionDigits: 1 }) });
  return Number.isFinite(r.steps_per_s)
    ? `${main} · ${t("runs.stepsPerS", { n: formatNumber(r.steps_per_s, { maximumFractionDigits: 2 }) })}`
    : main;
}

function formatDurationS(sec) {
  if (!Number.isFinite(sec)) return t("state.na");
  if (sec >= 3600) return t("unit.hours", { n: formatNumber(sec / 3600, { maximumFractionDigits: 1 }) });
  if (sec >= 60) return t("unit.minutes", { n: formatNumber(sec / 60, { maximumFractionDigits: 1 }) });
  return t("unit.seconds", { n: formatNumber(sec, { maximumFractionDigits: 0 }) });
}

function metricLabel(m) {
  return hasI18nKey("runs.metric." + m) ? t("runs.metric." + m) : m;
}

function phaseLabel(k) {
  if (k === "persist") return t("exp.phasePersist");
  if (String(k).startsWith("setup")) return t("runs.phase.setup");
  return hasI18nKey("runs.phase." + k) ? t("runs.phase." + k) : k;
}

export function renderRunsPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("runs.title")));
  let activeMetric = "loss";
  let useEma = true;
  let selectedBranch = null;

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const round = getCurrentRound();

      // The round's training runs: story.runs when the round lists it (tray-r1), else the runs of
      // the jig block (tray-jig-r1, which names a train folder per run). Never both.
      const topScope = hasIndexAccess("story.runs");
      const jigDoc = !topScope && hasIndexAccess("story.jig") && story.jig ? story.jig : null;
      if (!topScope && !jigDoc) {
        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("runs.title") }],
            title: t("runs.title"),
          }),
          renderProcessEmptyBlock(3, t("runs.title"))
        );
        return;
      }
      const src = topScope ? story : jigDoc;
      const roundLogTail = Array.isArray(src.train_log_tail) ? src.train_log_tail : [];
      const roundPhases = src.vm_phases && typeof src.vm_phases === "object" ? src.vm_phases : {};
      const logRun = topScope ? (round && round.log_run) || null : jigDoc.log_run || null;

      const rawRuns = Array.isArray(src.runs) ? src.runs : [];
      const validRuns = rawRuns.filter((r) => r && !String(r.branch || "").includes(".attempt"));
      const filteredRuns = validRuns;

      if (!selectedBranch || !validRuns.some((r) => r.branch === selectedBranch)) {
        selectedBranch =
          [logRun, round && round.baseline].find(
            (id) => id && validRuns.some((r) => r.branch === id)
          ) ||
          (validRuns[0] && validRuns[0].branch) ||
          null;
      }
      const selectedRun = validRuns.find((r) => r.branch === selectedBranch) || validRuns[0] || null;

      const chartSlot = el("div", {});

      const redrawCurve = () => {
        if (filteredRuns.length === 0) {
          setChildren(chartSlot, el("div", { className: "empty", text: t("state.empty") }));
          return;
        }
        const smoothActive = useEma && (activeMetric === "loss" || activeMetric === "gn");
        setChildren(
          chartSlot,
          renderChartBlock({
            title: `${t("runs.curvesTitle")} · ${metricLabel(activeMetric)}${smoothActive ? " (EMA)" : ""}`,
            height: 300,
            buildOption: ({ soft, line, colors }) => {
              const series = [];
              filteredRuns.forEach((r, idx) => {
                const col = colors[idx % colors.length];
                const rawPts = (r[activeMetric] || []).filter(
                  (pt) =>
                    Array.isArray(pt) &&
                    pt[1] !== null &&
                    (!(activeMetric === "loss") || pt[1] > 0)
                );
                if (smoothActive && rawPts.length > 6) {
                  series.push({
                    name: `${r.branch || r.job} (raw)`,
                    type: "line",
                    showSymbol: false,
                    silent: true,
                    tooltip: { show: false },
                    data: rawPts,
                    lineStyle: { width: 1, color: col, opacity: 0.18 },
                    itemStyle: { color: col, opacity: 0.18 },
                  });
                  series.push({
                    name: r.branch || r.job,
                    type: "line",
                    showSymbol: false,
                    data: computeEmaPoints(rawPts),
                    lineStyle: { width: 2.4, color: col },
                    itemStyle: { color: col },
                  });
                } else {
                  series.push({
                    name: r.branch || r.job,
                    type: "line",
                    showSymbol: activeMetric === "val",
                    symbolSize: 5,
                    data: rawPts,
                    lineStyle: { width: 2.2, color: col },
                    itemStyle: { color: col },
                  });
                }
              });
              return {
                grid: { left: 54, right: 20, top: 36, bottom: 32 },
                tooltip: { trigger: "axis" },
                legend: {
                  top: 0,
                  textStyle: { color: soft },
                  data: filteredRuns.map((r) => r.branch || r.job),
                },
                xAxis: {
                  type: "value",
                  name: t("runs.axisStep"),
                  axisLabel: { color: soft },
                  splitLine: { lineStyle: { color: line } },
                },
                yAxis: {
                  type: activeMetric === "loss" ? "log" : "value",
                  axisLabel: { color: soft },
                  splitLine: { lineStyle: { color: line } },
                },
                series,
              };
            },
            tableNode: el("table", { className: "table" }, [
              el("thead", {}, [
                el("tr", {}, [
                  el("th", { text: t("follow.colModel") }),
                  el("th", { text: t("runs.colJob") }),
                  el("th", { className: "num", text: t("runs.colStep") }),
                  el("th", { className: "num", text: t("runs.colLossLast") }),
                  el("th", { className: "num", text: t("runs.colValLast") }),
                ]),
              ]),
              el(
                "tbody",
                {},
                filteredRuns.map((r) =>
                  el("tr", {}, [
                    el("td", { className: "mono", text: r.branch }),
                    el("td", { className: "mono", text: r.job }),
                    el("td", {
                      className: "num",
                      text: `${formatNumber(r.ckpt_step || r.step)} / ${formatNumber(r.max_steps)}`,
                    }),
                    el("td", {
                      className: "num",
                      text: formatNumber(r.loss_last, { maximumFractionDigits: 4 }),
                    }),
                    el("td", {
                      className: "num",
                      text: formatNumber(r.val_last, { maximumFractionDigits: 4 }),
                    }),
                  ])
                )
              ),
            ]),
          })
        );
      };

      const roundRuns = round && Array.isArray(round.runs) ? round.runs : [];
      const roundIdsSet = new Set(roundRuns.map((rr) => rr.id));
      const extraRuns = validRuns
        .filter((r) => r && r.branch && !roundIdsSet.has(r.branch))
        .map((r) => ({
          id: r.branch,
          train_set: r.scene || "-",
          role: "current",
        }));
      const displayRoundRuns =
        roundRuns.length > 0
          ? [...extraRuns, ...roundRuns]
          : validRuns.map((r) => ({ id: r.branch, train_set: r.scene || "-", role: "info" }));

      const liveEvalList = jigDoc && Array.isArray(jigDoc.live_evals) ? jigDoc.live_evals : [];
      const modelRuns =
        story.demo && story.demo.models && story.demo.models.runs ? story.demo.models.runs : {};

      // The round-level log and phases belong to log_run only; another run shows its own or none.
      const ownLog = (r) => Boolean(r) && (r.branch === logRun || !logRun);
      const selPhasesObj =
        selectedRun && selectedRun.vm_phases && Object.keys(selectedRun.vm_phases).length > 0
          ? selectedRun.vm_phases
          : ownLog(selectedRun)
            ? roundPhases
            : {};
      const vmPhases = Object.entries(selPhasesObj);
      const logTail = cleanLogLines(
        selectedRun && Array.isArray(selectedRun.log_tail) && selectedRun.log_tail.length > 0
          ? selectedRun.log_tail
          : ownLog(selectedRun)
            ? roundLogTail
            : []
      );

      const groupsFirst = (selectedRun && selectedRun.groups_first) || {};
      const groupsLast = (selectedRun && selectedRun.groups_last) || {};
      const groupKeys = Object.keys(groupsLast);

      const vramList = validRuns.map((r) => r.vram_max).filter(Number.isFinite);
      const maxVram = vramList.length ? Math.max(...vramList) : null;
      const speedRun =
        (selectedRun && Number.isFinite(selectedRun.thr_med) && selectedRun) ||
        [...validRuns].reverse().find((r) => Number.isFinite(r.thr_med)) ||
        null;
      const speedText = runSpeedText(speedRun);

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("runs.title") }],
          title: t("runs.title"),
        }),

        liveEvalList.length > 0
          ? el("div", { className: cls("attention-banner", "is-warn") }, [
              el("span", {
                text: t("exp.liveEvalBanner", {
                  session: liveEvalList[0].session || "-",
                  gpu: liveEvalList[0].gpu || "L4",
                  lanes: formatNumber(liveEvalList[0].lanes ?? 0),
                  done: formatNumber(liveEvalList[0].complete ?? 0),
                }),
              }),
              el("a", { className: cls("btn", "primary"), href: "#/eval" }, [t("nav.item.eval")]),
            ])
          : null,

        renderStatStrip([
          {
            label: t("exp.statValidRuns"),
            value: formatNumber(validRuns.length),
            sub: t("exp.statValidRunsSub"),
          },
          {
            label: t("exp.statRound"),
            value: (round && (pickLang(round.title) || round.id)) || t("state.na"),
            sub:
              round && round.max_steps != null
                ? t("exp.statRoundSteps", { steps: formatNumber(round.max_steps) })
                : "",
          },
          {
            label: t("exp.statPerf"),
            value: speedText || t("state.na"),
            sub:
              maxVram != null
                ? t("runs.vramPeak", { n: formatNumber(maxVram, { maximumFractionDigits: 1 }) })
                : "",
          },
        ]),

        el("div", { className: "toolbar" }, [
          el("span", { className: "muted", text: t("runs.metricLabel") }),
          ...RUN_METRICS.map((m) =>
            el(
              "button",
              {
                type: "button",
                className: cls("tab", activeMetric === m && "active"),
                onClick: () => {
                  activeMetric = m;
                  load();
                },
              },
              [metricLabel(m)]
            )
          ),
          el("span", { className: "grow" }),
          activeMetric === "loss" || activeMetric === "gn"
            ? el(
                "button",
                {
                  type: "button",
                  className: cls("topbtn", useEma && "active"),
                  onClick: () => {
                    useEma = !useEma;
                    redrawCurve();
                  },
                },
                [`${useEma ? "✓ " : ""}${t("exp.emaToggle")}`]
              )
            : null,
        ]),

        chartSlot,

        el("section", { className: cls("card", "table-wrap") }, [
          el("h2", { text: t("runs.roundRunsTitle") }),
          el("table", { className: "table" }, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", { text: t("follow.colModel") }),
                el("th", { text: t("runs.colRole") }),
                el("th", { text: `${t("runs.colTrainSet")} · ${t("exp.colScale")}` }),
                el("th", { className: "num", text: t("exp.colStepProg") }),
                el("th", { className: "num", text: t("exp.colLossVal") }),
                el("th", { className: "num", text: t("exp.colSysPerf") }),
                el("th", { text: t("runs.colReleaseJob") }),
              ]),
            ]),
            el(
              "tbody",
              {},
              displayRoundRuns.map((rr) => {
                const matched = validRuns.find((x) => x.branch === rr.id);
                const mInfo = modelRuns[rr.id] || {};
                const epCount = (matched && matched.episodes) ?? mInfo.episodes ?? null;
                const frCount = matched && matched.frames ? matched.frames : null;
                const scaleTxt =
                  epCount != null
                    ? frCount
                      ? t("runs.scaleEpFr", {
                          ep: formatNumber(epCount),
                          fr: formatNumber(frCount),
                        })
                      : t("runs.scaleEp", { ep: formatNumber(epCount) })
                    : t("state.na");
                const effStep = matched ? matched.ckpt_step || matched.step : null;
                const hasRemoteCkpt =
                  matched && matched.ckpt_step && matched.step && matched.ckpt_step > matched.step + 10;
                // the local metrics.jsonl is a partial copy only when the VM's train did not end
                const partialFile =
                  matched && matched.fetched_final === false && matched.fetched_train !== "done";
                const isSel = selectedRun && selectedRun.branch === rr.id;

                return el(
                  "tr",
                  {
                    className: cls("is-clickable-row", isSel && "is-selected-row"),
                    onClick: () => {
                      selectedBranch = rr.id;
                      setSelection({ run_id: rr.id });
                      load();
                    },
                  },
                  [
                    el("td", { className: "mono" }, [el("b", { text: rr.id })]),
                    el("td", {}, [renderStateChip(rr.role || "info")]),
                    el(
                      "td",
                      {
                        className: "mono",
                        title: rr.train_set || mInfo.data || "-",
                      },
                      [
                        el("b", { text: compactPath(rr.train_set || mInfo.data || "-") }),
                        el("div", { className: "tiny", text: scaleTxt }),
                      ]
                    ),
                    el("td", { className: "num" }, [
                      matched
                        ? el("div", {}, [
                            el("b", {
                              className: "mono",
                              text: `${formatNumber(effStep)} / ${formatNumber(matched.max_steps)}`,
                            }),
                            hasRemoteCkpt
                              ? el("div", {
                                  className: "tiny",
                                  text: t("exp.ckptDoneRemote", {
                                    ckpt: formatNumber(matched.ckpt_step),
                                    local: formatNumber(matched.step),
                                  }),
                                })
                              : null,
                            partialFile
                              ? el("div", {
                                  className: "tiny",
                                  text: t("exp.fetchedPartial", {
                                    step: formatNumber(matched.fetched_step ?? matched.step),
                                  }),
                                })
                              : null,
                          ])
                        : t("state.na"),
                    ]),
                    el("td", { className: cls("num", "mono") }, [
                      matched
                        ? `${formatNumber(matched.loss_last, { maximumFractionDigits: 3 })} / ${
                            matched.val_last != null
                              ? formatNumber(matched.val_last, { maximumFractionDigits: 3 })
                              : "-"
                          }`
                        : t("state.na"),
                    ]),
                    el("td", { className: "num" }, [
                      runSpeedText(matched) || t("state.na"),
                      matched && matched.vram_max != null
                        ? el("div", {
                            className: "tiny",
                            text: t("runs.vramPeak", {
                              n: formatNumber(matched.vram_max, { maximumFractionDigits: 1 }),
                            }),
                          })
                        : null,
                    ]),
                    el("td", {}, [
                      matched
                        ? el("div", { className: "tag-row" }, [
                            el("span", { className: "mono", text: matched.job }),
                            matched.run_plan_id
                              ? el("span", {
                                  className: cls("short-hash", "mono"),
                                  text: matched.run_plan_id,
                                })
                              : null,
                          ])
                        : el("span", { className: "mono", text: rr.session || "-" }),
                    ]),
                  ]
                );
              })
            ),
          ]),
        ]),

        selectedRun && groupKeys.length > 0
          ? el("section", { className: "card" }, [
              el("h2", {
                text: t("exp.selectedRunGroupsTitle", { run: selectedRun.branch }),
              }),
              el("p", {
                className: "muted",
                style: "margin-top:3px",
                text: t("exp.selectedRunGroupsSub"),
              }),
              el(
                "div",
                { className: "joint-group-grid" },
                groupKeys.map((gk) => {
                  const g0 = Number(groupsFirst[gk] || 0);
                  const g1 = Number(groupsLast[gk] || 0);
                  const dropPct = g0 > 0 ? Math.max(0, Math.min(100, ((g0 - g1) / g0) * 100)) : 0;
                  return el("div", { className: "joint-group-card" }, [
                    el("div", { className: "task-head" }, [
                      el("b", { className: "mono", text: gk }),
                      el("span", {
                        className: cls("short-hash", "mono"),
                        text: `-${formatNumber(dropPct, { maximumFractionDigits: 1 })}%`,
                      }),
                    ]),
                    el("div", {
                      className: cls("tiny", "mono"),
                      text: `${t("exp.groupFirst")}: ${formatNumber(g0, { maximumFractionDigits: 3 })} → ${t("exp.groupLast")}: ${formatNumber(g1, { maximumFractionDigits: 4 })}`,
                    }),
                    el("div", { className: "stream-track" }, [
                      el("div", {
                        className: "stream-fill",
                        style: `width:${dropPct.toFixed(1)}%`,
                      }),
                    ]),
                  ]);
                })
              ),
            ])
          : null,

        vmPhases.length > 0
          ? el("section", { className: "card" }, [
              el("h2", {
                text: selectedRun
                  ? t("exp.vmPhasesForRun", { run: selectedRun.branch })
                  : t("runs.vmPhasesTitle"),
              }),
              el(
                "div",
                { className: "meta-strip" },
                vmPhases.map(([k, v]) =>
                  el("div", { className: "meta-box" }, [
                    el("span", { title: k, text: phaseLabel(k) }),
                    el("b", { text: formatDurationS(v) }),
                  ])
                )
              ),
              selPhasesObj.persist != null
                ? el("p", { className: cls("tiny", "muted"), text: t("exp.phasePersistNote") })
                : null,
            ])
          : null,

        logTail.length > 0
          ? el("details", { className: cls("card", "log-details") }, [
              el("summary", {
                text: selectedRun
                  ? t("exp.logTailForRun", { run: selectedRun.branch })
                  : t("runs.logTailTitle"),
              }),
              el("pre", { className: cls("log-box", "mono"), text: logTail.join("\n") }),
            ])
          : null
      );

      redrawCurve();
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/eval — Evaluation & Paired Comparisons
// ============================================================================
export function renderEvalPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("eval.title")));

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const task = getCurrentTask();
      const pair = story.pair || null;
      const jig = story.jig || null;
      const round = getCurrentRound();
      const jigEvals = jig && Array.isArray(jig.evals) ? jig.evals : [];
      const jigOutcomes = jig && Array.isArray(jig.outcomes) ? jig.outcomes : [];
      // One run is shown: the featured one (its results.json is ready), else the round's baseline.
      const jigRunId =
        (jig && jig.featured) ||
        (round && round.baseline) ||
        (jigEvals[0] && jigEvals[0].run) ||
        null;
      const jigEval = jigEvals.find((e) => e.run === jigRunId) || jigEvals[0] || null;
      // The descriptive blocks (scores.jsonl) restate the success count, so they only show beside
      // figures copied from results.json: none while it is missing ("Chưa có", story DA-53).
      const jigHasFigures =
        Boolean(jigEval) && (jigEval.status === "ready" || jigEval.status === "blocked");
      const jigDesc = jigHasFigures
        ? jigOutcomes.find((o) => o.run === jigEval.run) || null
        : null;
      const jigRollouts =
        jigDesc && jig && Array.isArray(jig.rollouts)
          ? jig.rollouts.filter((r) => r.run === jigDesc.run)
          : [];
      const jigLiveEvals = jig && Array.isArray(jig.live_evals) ? jig.live_evals : [];
      const jigSteps =
        (jig && Array.isArray(jig.steps) && jig.steps.length > 0
          ? jig.steps
          : jigDesc && jigDesc.step_pass
            ? Object.keys(jigDesc.step_pass)
            : []) || [];
      const ladderR1 = story.demo && story.demo.ladder ? story.demo.ladder : null;
      // The task-level baseline eval (policy C @40k, before round 1) is not shown on the jig
      // round, where it reads like a figure of the jig run (W9).
      const earlyEval = !jig && story.eval ? story.eval : null;
      const taskEvals = task && Array.isArray(task.evals) ? task.evals : [];

      const pairRuns = pair && Array.isArray(pair.runs) ? pair.runs : [];
      const pairComps = pair && Array.isArray(pair.comparisons) ? pair.comparisons : [];
      const stepKeys =
        pairRuns[0] && pairRuns[0].step_pass
          ? Object.keys(pairRuns[0].step_pass)
          : (pair && pair.steps) || [];

      // Rates, intervals and verdict codes are copied from results.json by the index (index/jig.py);
      // thresholds come from the readings (seed/tasks.yaml), never from this file.
      const isPair = (v) => Array.isArray(v) && v.length === 2 && v.every(Number.isFinite);
      const pct0 = (x) => (Number.isFinite(x) ? formatPercent(x, 0) : t("state.na"));
      const figFor = (ev, rd) =>
        rd.scope === "whole_task"
          ? ev.headline || {}
          : rd.scope === "level"
            ? (ev.levels || {})[rd.level] || {}
            : ev.place || {};
      const ruleTitle = (rd, fig) =>
        rd.scope === "whole_task"
          ? t("exp.ruleAllTitle", { rule: rd.rule })
          : rd.scope === "level"
            ? t("exp.ruleLevelTitle", {
                rule: rd.rule,
                lv: rd.level,
                cond: formatNumber(fig.conditions),
              })
            : t("exp.rulePlaceTitle", { rule: rd.rule });
      const verdictOf = (rd) => {
        if (rd.verdict === "met") {
          return {
            chip: "",
            text: t(rd.scope === "place" ? "exp.verdictPlaceMet" : "exp.verdictMet", {
              pct: pct0(rd.threshold),
            }),
          };
        }
        if (rd.verdict === "not_met") {
          return { chip: "warning", text: t("exp.verdictNotMet", { pct: pct0(rd.threshold) }) };
        }
        if (rd.why === "blocked") return { chip: "neutral", text: t("exp.verdictBlocked") };
        return { chip: "neutral", text: t("exp.verdictNoCi") };
      };

      const renderJigScorecard = (ev) => {
        const readings = Array.isArray(ev.readings) ? ev.readings : [];
        const grid = el(
          "div",
          { className: "scorecard-grid-4" },
          readings.map((rd) => {
            const fig = figFor(ev, rd);
            const v = verdictOf(rd);
            return el("div", { className: "scorecard-box" }, [
              el("div", { className: "task-head" }, [
                el("span", { className: "tiny", text: ruleTitle(rd, fig) }),
              ]),
              el("div", { className: "actions" }, [
                el("span", { className: "scorecard-val", text: formatPercent(fig.p) }),
                el("span", {
                  className: "muted",
                  text: `${formatNumber(fig.successes)} / ${formatNumber(fig.n)}`,
                }),
              ]),
              isPair(fig.ci)
                ? el("div", {
                    className: "tiny",
                    text: t("exp.ciBootstrap", {
                      lo: formatPercent(fig.ci[0]),
                      hi: formatPercent(fig.ci[1]),
                    }),
                  })
                : null,
              isPair(fig.wilson)
                ? el("div", {
                    className: cls("tiny", "muted"),
                    text: `${t("exp.wilsonDescr")} ${formatPercent(fig.wilson[0])}–${formatPercent(fig.wilson[1])}`,
                  })
                : null,
              el("div", {
                className: "tiny muted",
                text: t(rd.scope === "place" ? "exp.targetPlace" : "exp.targetAt", {
                  pct: pct0(rd.threshold),
                }),
              }),
              el("span", { className: cls("chip", v.chip), text: v.text }),
            ]);
          })
        );
        const method = ev.headline && ev.headline.wilson_method;
        return el("div", {}, [
          grid,
          el("p", { className: "tiny muted", text: t("exp.verdictNoteRules") }),
          method ? el("p", { className: cls("tiny", "muted"), text: t("exp.wilsonMethodNote") }) : null,
        ]);
      };

      // The figures of the whole task and of each level, with the failure labels of results.json.
      const renderJigLevelTable = (ev) => {
        const rows = [
          { name: t("exp.scopeWhole"), fig: ev.headline || {} },
          ...Object.entries(ev.levels || {}).map(([lv, fig]) => ({
            name: t("exp.scopeLevel", { lv }),
            fig: fig || {},
          })),
        ];
        return el("table", { className: "table", style: "margin-top:10px" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: t("exp.colScope") }),
              el("th", { className: "num", text: t("exp.colConditions") }),
              el("th", { className: "num", text: t("eval.colSuccN") }),
              el("th", { className: "num", text: t("eval.colRate") }),
              el("th", { className: "num", text: t("exp.colCiBootstrap") }),
              el("th", { text: t("eval.colTopFail") }),
            ]),
          ]),
          el(
            "tbody",
            {},
            rows.map(({ name, fig }) =>
              el("tr", {}, [
                el("td", { text: name }),
                el("td", { className: "num", text: formatNumber(fig.conditions) }),
                el("td", {
                  className: "num",
                  text: `${formatNumber(fig.successes)} / ${formatNumber(fig.n)}`,
                }),
                el("td", { className: "num", text: formatPercent(fig.p) }),
                el("td", {
                  className: "num",
                  text: isPair(fig.ci)
                    ? `${formatPercent(fig.ci[0])}–${formatPercent(fig.ci[1])}`
                    : t("state.na"),
                }),
                el("td", {
                  className: "fail-cell",
                  text:
                    Object.entries(fig.failures || {})
                      .map(([fk, fv]) => `${failureLabel(fk)}: ${fv}`)
                      .join(" · ") || "–",
                }),
              ])
            )
          ),
        ]);
      };

      const renderJigEvalSection = (ev) => {
        const status = ev.status || "missing";
        const rulesSrc = jig && jig.rules ? pickLang(jig.rules.source) : "";
        const head = el("div", { className: "task-head" }, [
          el("h2", { text: t("exp.jigEvalTitle", { run: ev.run }) }),
          renderStateChip(
            status === "ready" ? "done" : status === "blocked" ? "blocked" : status === "withheld" ? "waiting" : "missing"
          ),
        ]);
        const meta = el("div", {}, [
          el("p", {
            className: "muted",
            style: "margin:4px 0 6px",
            text: t("exp.jigEvalSceneNote", {
              scene: (jig && jig.scene) || "-",
              n: formatNumber(jig && jig.rollouts_expected),
              scorer: (jig && jig.scorer_version) ?? "-",
            }),
          }),
          rulesSrc
            ? el("div", { className: "rules-cite" }, [
                el("span", { className: cls("tiny", "muted"), text: t("exp.rulesLabel") }),
                renderSourceCitation(rulesSrc),
              ])
            : null,
          el("p", { className: cls("tiny", "muted"), text: t("exp.jigLimits") }),
        ]);
        let body;
        if (status === "withheld") {
          body = el("div", { className: "empty", text: t("exp.evalWithheld") });
        } else if (status === "missing") {
          body = el("div", {}, [
            el("div", { className: "empty", text: t("exp.evalMissing", { run: ev.run }) }),
            el("p", { className: "tiny", text: t("exp.evalMissingHow") }),
            ev.command ? el("pre", { className: cls("log-box", "mono"), text: ev.command }) : null,
          ]);
        } else {
          const problems = Array.isArray(ev.problems) ? ev.problems : [];
          body = el("div", {}, [
            status === "blocked"
              ? el("div", { className: cls("attention-banner", "is-warn") }, [
                  el("span", {
                    text: t("exp.evalBlocked", { problems: problems.join(" · ") || "-" }),
                  }),
                ])
              : null,
            renderJigScorecard(ev),
            renderJigLevelTable(ev),
          ]);
        }
        return el("section", { className: cls("card", "table-wrap") }, [
          head,
          meta,
          body,
          ev.results_source
            ? renderSourceCitation(ev.results_source)
            : null,
        ]);
      };

      const jigStepChart =
        jigDesc && jigSteps.length > 0
          ? renderChartBlock({
              title: t("exp.jigStepChartTitle", { n: formatNumber(jigSteps.length) }),
              height: 305,
              buildOption: ({ soft, line, colors }) => {
                const lvStep = jigDesc.levels_step_pass || {};
                const lv1Obj = (jigDesc.levels && jigDesc.levels["1"]) || {};
                const lv2Obj = (jigDesc.levels && jigDesc.levels["2"]) || {};
                const series = [
                  {
                    name: t("exp.jigStepAll", { run: jigDesc.run, n: formatNumber(jigDesc.n) }),
                    type: "line",
                    data: jigSteps.map((sk) =>
                      jigDesc.step_pass && jigDesc.step_pass[sk] != null
                        ? Number((jigDesc.step_pass[sk] * 100).toFixed(1))
                        : null
                    ),
                    lineStyle: { width: 3, color: colors[0] },
                    itemStyle: { color: colors[0] },
                  },
                ];
                if (lvStep["1"]) {
                  series.push({
                    name: t("exp.jigStepLv", {
                      run: jigDesc.run,
                      lv: "1",
                      n: formatNumber(lv1Obj.n),
                    }),
                    type: "line",
                    data: jigSteps.map((sk) =>
                      lvStep["1"][sk] != null ? Number((lvStep["1"][sk] * 100).toFixed(1)) : null
                    ),
                    lineStyle: { width: 2, type: "dashed", color: colors[1] },
                    itemStyle: { color: colors[1] },
                  });
                }
                if (lvStep["2"]) {
                  series.push({
                    name: t("exp.jigStepLv", {
                      run: jigDesc.run,
                      lv: "2",
                      n: formatNumber(lv2Obj.n),
                    }),
                    type: "line",
                    data: jigSteps.map((sk) =>
                      lvStep["2"][sk] != null ? Number((lvStep["2"][sk] * 100).toFixed(1)) : null
                    ),
                    lineStyle: { width: 2, type: "dotted", color: colors[3] },
                    itemStyle: { color: colors[3] },
                  });
                }
                return {
                  grid: { left: 48, right: 20, top: 54, bottom: 32 },
                  tooltip: { trigger: "axis" },
                  legend: { top: 0, textStyle: { color: soft } },
                  xAxis: {
                    type: "category",
                    data: jigSteps.map((sk) => stageLabel(sk)),
                    axisLabel: { color: soft, rotate: 18 },
                  },
                  yAxis: {
                    type: "value",
                    max: 100,
                    axisLabel: { color: soft, formatter: "{value}%" },
                    splitLine: { lineStyle: { color: line } },
                  },
                  series,
                };
              },
              tableNode: el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("eval.colStep") }),
                    el("th", { className: "num", text: jigDesc.run }),
                    el("th", { className: "num", text: "L1" }),
                    el("th", { className: "num", text: "L2" }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  jigSteps.map((sk) =>
                    el("tr", {}, [
                      el("td", { text: stageLabel(sk) }),
                      el("td", {
                        className: "num",
                        text: formatPercent(jigDesc.step_pass ? jigDesc.step_pass[sk] : null),
                      }),
                      el("td", {
                        className: "num",
                        text: formatPercent(
                          jigDesc.levels_step_pass && jigDesc.levels_step_pass["1"]
                            ? jigDesc.levels_step_pass["1"][sk]
                            : null
                        ),
                      }),
                      el("td", {
                        className: "num",
                        text: formatPercent(
                          jigDesc.levels_step_pass && jigDesc.levels_step_pass["2"]
                            ? jigDesc.levels_step_pass["2"][sk]
                            : null
                        ),
                      }),
                    ])
                  )
                ),
              ]),
            })
          : null;

      const jigScatterChart =
        jigRollouts.length > 0
          ? renderChartBlock({
              title: t("exp.jigScatterTitle", { n: formatNumber(jigRollouts.length) }),
              subtitle: t("exp.jigScatterSub"),
              height: 305,
              buildOption: ({ soft, line, colors }) => {
                const okPts = [];
                const posePts = [];
                const otherPts = [];
                for (const r of jigRollouts) {
                  if (r.dist_cm == null || r.yaw_deg == null) continue;
                  const pt = [
                    Math.min(35, r.dist_cm),
                    Math.min(35, r.yaw_deg),
                    r.ep,
                    r.dist_cm,
                    r.yaw_deg,
                    r.failure || "OK",
                  ];
                  if (r.success) okPts.push(pt);
                  else if (r.failure === "L-PLACE-POSE") posePts.push(pt);
                  else otherPts.push(pt);
                }
                return {
                  grid: { left: 48, right: 22, top: 54, bottom: 36 },
                  tooltip: {
                    formatter: (p) => {
                      const d = p.data || [];
                      return `${d[2]} (${d[5]})<br/>Δxy: ${d[3]} cm · Δyaw: ${d[4]}°`;
                    },
                  },
                  legend: { top: 0, textStyle: { color: soft } },
                  xAxis: {
                    type: "value",
                    name: "cm",
                    max: 35,
                    axisLabel: { color: soft },
                    splitLine: { lineStyle: { color: line } },
                  },
                  yAxis: {
                    type: "value",
                    name: t("unit.deg"),
                    max: 35,
                    axisLabel: { color: soft },
                    splitLine: { lineStyle: { color: line } },
                  },
                  series: [
                    {
                      name: t("exp.scatterOk"),
                      type: "scatter",
                      symbolSize: 7,
                      data: okPts,
                      itemStyle: { color: colors[0], opacity: 0.78 },
                      markLine: {
                        silent: true,
                        symbol: "none",
                        lineStyle: { type: "dashed", color: soft },
                        data: [{ xAxis: 5 }, { yAxis: 10 }],
                      },
                    },
                    {
                      name: t("exp.scatterPose"),
                      type: "scatter",
                      symbolSize: 8.5,
                      data: posePts,
                      itemStyle: { color: colors[3], opacity: 0.88 },
                    },
                    {
                      name: t("exp.scatterOther"),
                      type: "scatter",
                      symbolSize: 8,
                      data: otherPts,
                      itemStyle: { color: colors[2], opacity: 0.85 },
                    },
                  ],
                };
              },
            })
          : null;

      const jigRepeatAndRelaxed =
        jigDesc && (jigDesc.repeat_dist || jigDesc.relaxed)
          ? el("div", { className: "grid" }, [
              jigDesc.repeat_dist
                ? el("section", { className: "card" }, [
                    el("h2", { text: t("exp.repeatCardTitle") }),
                    el("p", { className: "muted", text: t("exp.repeatCardSub") }),
                    el(
                      "div",
                      { className: "repeat-bars" },
                      Object.entries(jigDesc.repeat_dist).map(([lvKey, arr]) => {
                        const [k3 = 0, k2 = 0, k1 = 0, k0 = 0] = Array.isArray(arr) ? arr : [];
                        const tot = Math.max(1, k3 + k2 + k1 + k0);
                        const segs = [
                          { clsName: "k3", count: k3, lbl: `3/3: ${k3}` },
                          { clsName: "k2", count: k2, lbl: `2/3: ${k2}` },
                          { clsName: "k1", count: k1, lbl: `1/3: ${k1}` },
                          { clsName: "k0", count: k0, lbl: `0/3: ${k0}` },
                        ].filter((s) => s.count > 0);
                        return el("div", {}, [
                          el("div", { className: "task-head", style: "margin-bottom:4px" }, [
                            el("b", {
                              text: t("exp.repeatLevelHead", {
                                lv: lvKey,
                                count: formatNumber(tot),
                              }),
                            }),
                            el("span", {
                              className: cls("tiny", "mono"),
                              text: `3/3=${k3} · 2/3=${k2} · 1/3=${k1} · 0/3=${k0}`,
                            }),
                          ]),
                          el(
                            "div",
                            { className: "repeat-stack-bar" },
                            segs.map((sg) =>
                              el("div", {
                                className: cls("repeat-seg", sg.clsName),
                                style: `width:${((sg.count / tot) * 100).toFixed(1)}%`,
                                title: sg.lbl,
                                text: sg.count / tot >= 0.12 ? sg.lbl : String(sg.count),
                              })
                            )
                          ),
                        ]);
                      })
                    ),
                  ])
                : null,
              jigDesc.relaxed
                ? el("section", { className: "card" }, [
                    el("h2", { text: t("exp.relaxedJigTitle") }),
                    el("p", { className: "muted", text: t("exp.relaxedJigSub") }),
                    comparisonPlot(
                      jigDesc.run,
                      [
                        ...Object.entries(jigDesc.relaxed).map(([cm, cnt]) => ({
                          name: `≤ ${formatNumber(Number(cm))} cm`,
                          value: (Number(cnt) / Math.max(1, jigDesc.n)) * 100,
                          label: `${formatPercent(Number(cnt) / Math.max(1, jigDesc.n))} (${cnt}/${jigDesc.n})`,
                        })),
                        {
                          name: t("exp.reachTableB"),
                          value: (Number(jigDesc.reach_b || 0) / Math.max(1, jigDesc.n)) * 100,
                          label: `${formatPercent(Number(jigDesc.reach_b || 0) / Math.max(1, jigDesc.n))} (${jigDesc.reach_b || 0}/${jigDesc.n})`,
                        },
                      ],
                      { bound: 100, unit: "%" }
                    ),
                  ])
                : null,
            ])
          : null;

      // Hiếu, 28/11/2026 (story DA-53, AC 11): repeat 0 of the jig round's run beside the earlier
      // runs at the same size. Descriptive only: no difference, interval or verdict is shown.
      const c60 = story.jig && story.jig.compare60 ? story.jig.compare60 : null;
      const compare60Card = c60
        ? (() => {
            const earlierScorer = c60.earlier_scorer
              ? scorerLabel(c60.earlier_scorer)
              : t("exp.c60ScorerV1");
            const rows = [
              ...(Array.isArray(c60.earlier) ? c60.earlier : []).map((e) => ({
                run: e.run,
                scene: t("exp.c60SceneEarlier"),
                scorer: earlierScorer,
                successes: e.successes,
                n: e.n,
              })),
              {
                run: t("exp.c60RunRepeat", { run: c60.run, repeat: c60.repeat }),
                scene: t("exp.c60SceneJig"),
                scorer: scorerLabel(c60.scorer_version),
                successes: c60.successes,
                n: c60.n,
              },
            ];
            const reps = Array.isArray(c60.repeats) ? c60.repeats : [];
            const repList = reps.map((r) => formatNumber(r.successes)).join(", ");
            const sources = [c60.source && c60.source.scores, c60.earlier_source, c60.earlier_doc]
              .filter(Boolean)
              .join(" · ");
            return el("section", { className: cls("card", "table-wrap") }, [
              el("div", { className: "task-head" }, [
                el("h2", { text: t("exp.c60Title", { run: c60.run, n: formatNumber(c60.n) }) }),
              ]),
              el("p", {
                className: "muted",
                text: t("exp.c60Caveat", {
                  scorer: scorerLabel(c60.scorer_version),
                  run: c60.run,
                  repeat: c60.repeat,
                }),
              }),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("exp.c60ColRun") }),
                    el("th", { text: t("exp.c60ColScene") }),
                    el("th", { text: t("exp.c60ColScorer") }),
                    el("th", { className: "num", text: t("eval.colSuccN") }),
                    el("th", { className: "num", text: t("eval.colRate") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  rows.map((r) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: r.run }),
                      el("td", { text: r.scene }),
                      el("td", { text: r.scorer }),
                      el("td", {
                        className: "num",
                        text: `${formatNumber(r.successes)} / ${formatNumber(r.n)}`,
                      }),
                      el("td", {
                        className: "num",
                        text: formatPercent(r.n ? r.successes / r.n : null),
                      }),
                    ])
                  )
                ),
              ]),
              reps.length > 0
                ? el("p", {
                    className: "tiny",
                    text: t(reps.length === 3 ? "exp.c60RepeatsThree" : "exp.c60Repeats", {
                      run: c60.run,
                      list: repList,
                      n: formatNumber(c60.n),
                    }),
                  })
                : null,
              sources ? renderSourceCitation(sources) : null,
            ]);
          })()
        : null;

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("eval.title") }],
          title: t("eval.title"),
        }),
        renderReportSubnav("eval"),

        jigLiveEvals.length > 0
          ? el("div", { className: cls("attention-banner", "is-warn") }, [
              el("span", {
                text: t("exp.liveEvalBanner", {
                  session: jigLiveEvals[0].session || "-",
                  gpu: jigLiveEvals[0].gpu || "L4",
                  lanes: formatNumber(jigLiveEvals[0].lanes ?? 0),
                  done: formatNumber(jigLiveEvals[0].complete ?? 0),
                }),
              }),
              el("a", { className: "link", href: "#/sim" }, [t("nav.item.sim")]),
            ])
          : null,

        jigEval ? renderJigEvalSection(jigEval) : null,

        compare60Card,

        jigDesc && (jigStepChart || jigScatterChart || jigRepeatAndRelaxed)
          ? el("div", { className: "sect" }, [
              el("h2", { text: t("exp.jigDescTitle", { run: jigDesc.run }) }),
            ])
          : null,

        jigStepChart || jigScatterChart
          ? el("div", { className: "grid" }, [jigStepChart, jigScatterChart])
          : null,

        jigRepeatAndRelaxed,

        pairRuns.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("div", { className: "task-head" }, [
                el("h2", { text: t("eval.pairRunsTitle") }),
                renderSourceCitation(pair.source),
              ]),
              successPlot(pairRuns),
              el("table", { className: "table", style: "margin-top:10px" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("follow.colModel") }),
                    el("th", { className: "num", text: t("eval.colSuccN") }),
                    el("th", { className: "num", text: t("eval.colRate") }),
                    el("th", { className: "num", text: t("eval.colWilson") }),
                    el("th", { text: t("eval.colTopFail") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  pairRuns.map((r) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: r.run }),
                      el("td", {
                        className: "num",
                        text: `${formatNumber(r.successes)} / ${formatNumber(r.n)}`,
                      }),
                      el("td", { className: "num", text: formatPercent(r.p) }),
                      el("td", {
                        className: "num",
                        text: Array.isArray(r.wilson)
                          ? `${formatPercent(r.wilson[0])} – ${formatPercent(r.wilson[1])}`
                          : t("state.na"),
                      }),
                      el("td", {
                        className: "fail-cell",
                        text: Object.entries(r.failures || {})
                          .map(([fk, fv]) => `${failureLabel(fk)}: ${fv}`)
                          .join(" · "),
                      }),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        pairRuns.length > 0 && stepKeys.length > 0
          ? renderChartBlock({
              title: t("eval.stepPassTitle"),
              height: 260,
              buildOption: ({ soft, line, colors }) => ({
                grid: { left: 48, right: 20, top: 34, bottom: 32 },
                tooltip: { trigger: "axis" },
                legend: { top: 0, textStyle: { color: soft } },
                xAxis: { type: "category", data: stepKeys.map((sk) => stageLabel(sk)), axisLabel: { color: soft, interval: 0, rotate: 30 } },
                yAxis: {
                  type: "value",
                  max: 100,
                  axisLabel: { color: soft, formatter: "{value}%" },
                  splitLine: { lineStyle: { color: line } },
                },
                series: pairRuns.map((r, idx) => ({
                  name: r.run,
                  type: "line",
                  data: stepKeys.map((sk) =>
                    r.step_pass && r.step_pass[sk] != null
                      ? Number((r.step_pass[sk] * 100).toFixed(1))
                      : null
                  ),
                  lineStyle: { width: 2, color: colors[idx % colors.length] },
                  itemStyle: { color: colors[idx % colors.length] },
                })),
              }),
              tableNode: el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("eval.colStep") }),
                    ...pairRuns.map((r) => el("th", { className: "num", text: r.run })),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  stepKeys.map((sk) =>
                    el("tr", {}, [
                      el("td", { text: stageLabel(sk) }),
                      ...pairRuns.map((r) =>
                        el("td", {
                          className: "num",
                          text: formatPercent(r.step_pass ? r.step_pass[sk] : null),
                        })
                      ),
                    ])
                  )
                ),
              ]),
            })
          : null,

        pairComps.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("h2", { text: t("eval.pairCompTitle") }),
              el("p", { className: "muted", text: t("eval.pairCompNote") }),
              renderPairCompTable(pairComps),
            ])
          : null,

        ladderR1 && ladderR1.runs && Object.keys(ladderR1.runs).length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("div", { className: "task-head" }, [
                el("h2", { text: t("exp.relaxedR1Title") }),
                renderSourceCitation(ladderR1.source),
              ]),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("follow.colModel") }),
                    el("th", { className: "num", text: t("exp.reachTableB") }),
                    ...(ladderR1.relaxed_cm || []).map((cm) =>
                      el("th", { className: "num", text: `≤ ${formatNumber(Number(cm))} cm` })
                    ),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  Object.entries(ladderR1.runs).map(([mId, mRow]) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: mId }),
                      el("td", {
                        className: "num",
                        text: `${formatNumber(mRow.on_table_b)} / ${formatNumber(ladderR1.n)}`,
                      }),
                      ...(ladderR1.relaxed_cm || []).map((cm) =>
                        el("td", {
                          className: "num",
                          text: formatNumber(mRow.relaxed ? mRow.relaxed[cm] : null),
                        })
                      ),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        taskEvals.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("h2", { text: t("eval.taskEvalsTitle") }),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("ds.attrName") }),
                    el("th", { className: "num", text: t("eval.colSuccN") }),
                    el("th", { className: "num", text: t("eval.colRate") }),
                    el("th", { text: t("eval.colModeLevel") }),
                    el("th", { text: t("common.source") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  taskEvals.map((ev) =>
                    el("tr", {}, [
                      el("td", { text: pickLang(ev.label) || ev.id }),
                      el("td", {
                        className: "num",
                        text:
                          ev.n != null
                            ? `${formatNumber(ev.successes)} / ${formatNumber(ev.n)}`
                            : t("state.na"),
                      }),
                      el("td", {
                        className: "num",
                        text:
                          ev.n && ev.successes != null
                            ? formatPercent(ev.successes / ev.n)
                            : t("state.na"),
                      }),
                      el("td", {
                        className: "mono",
                        text: `${ev.sim_mode || "-"} · L${ev.level ?? "-"}`,
                      }),
                      el("td", { className: "mono", text: scrubPath(ev.source || ev.doc || "–") }),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        earlyEval && Array.isArray(earlyEval.levels)
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("h2", { text: t("eval.earlyPolicyTitle") }),
              renderSourceCitation(earlyEval.source, earlyEval.policy),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("eval.colLevel") }),
                    el("th", { className: "num", text: t("eval.colSuccN") }),
                    el("th", { className: "num", text: t("eval.colWilson") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  earlyEval.levels.map((lv) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: lv.level }),
                      el("td", { className: "num", text: lv.succ || `${lv.successes}/${lv.n}` }),
                      el("td", { className: "num", text: lv.wilson ? localizeNumText(lv.wilson) : "–" }),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        !pair && !jig ? renderRoundEmpty({ keys: ["story.pair", "story.jig"] }) : null
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/diagnose — System Check & Failure Diagnosis
// ============================================================================
export function renderDiagnosePage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("diagnose.title")));

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const task = getCurrentTask();
      const round = getCurrentRound();

      const taskClusters =
        task && task.clusters && typeof task.clusters === "object" ? task.clusters : {};
      const taskClusterItems = Array.isArray(taskClusters.items) ? taskClusters.items : [];
      const diagDemo = story.demo && story.demo.diagnose ? story.demo.diagnose : null;
      const roundClusters =
        story.round && Array.isArray(story.round.clusters) ? story.round.clusters : [];
      const jigAgentQa =
        story.jig && Array.isArray(story.jig.agentqa) ? story.jig.agentqa : [];
      const latestAsm = jigAgentQa.length > 0 ? jigAgentQa[jigAgentQa.length - 1] : null;
      const asmClusters = latestAsm && Array.isArray(latestAsm.clusters) ? latestAsm.clusters : [];

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("diagnose.title") }],
          title: t("diagnose.title"),
          lead: t("diagnose.lead"),
          actions: round
            ? [el("a", { className: cls("btn", "primary"), href: "#/loop" }, [t("nav.item.loop")])]
            : [],
        }),
        renderReportSubnav("diagnose"),

        latestAsm && asmClusters.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("div", { className: "task-head" }, [
                el("h2", { text: t("exp.diagJigTitle", { caseId: latestAsm.case_id || "-" }) }),
                renderStateChip(latestAsm.status || "info"),
              ]),
              renderSourceCitation(latestAsm.source),
              comparisonPlot(
                t("diagnose.clustersTitle"),
                asmClusters
                  .filter((c) => Number(c.size) > 0)
                  .slice(0, 8)
                  .map((c) => ({
                    name: t("diag.clusterName", { label: failureLabel(c.label || "–"), lv: c.level ?? "–" }),
                    value: c.size,
                  }))
              ),
              el("table", { className: "table", style: "margin-top:10px" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("diagnose.colCluster") }),
                    el("th", { className: "num", text: "n" }),
                    el("th", { text: t("exp.diagColHyp") }),
                    el("th", { text: t("exp.diagColFacts") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  asmClusters.map((ac) =>
                    el("tr", {}, [
                      el("td", {}, [
                        el("b", { title: ac.label || "", text: failureLabel(ac.label || ac.cluster_id || "–") }),
                        el("div", {
                          className: "tiny",
                          text: t("diag.clusterWhere", {
                            run: ac.run || "–",
                            step: stageLabel(ac.step || "–"),
                            lv: ac.level ?? "–",
                          }),
                        }),
                      ]),
                      el("td", { className: "num", text: formatNumber(ac.size) }),
                      el("td", {}, [
                        ac.rule_id
                          ? el("span", {
                              className: "tax-badge",
                              style: "margin-bottom:3px",
                              title: ac.hypothesis_id || "",
                              text: hasI18nKey("diag.rule." + String(ac.rule_id).toLowerCase())
                                ? t("diag.rule." + String(ac.rule_id).toLowerCase())
                                : ac.rule_id,
                            })
                          : null,
                        el("div", {
                          text:
                            (ac.rule_id &&
                              {
                                place_rests_raised: t("exp.ruleDesc.place_rests_raised"),
                                near_miss_placement: t("exp.ruleDesc.near_miss_placement"),
                                scorer_latch_too_strict: t("exp.ruleDesc.scorer_latch_too_strict"),
                                label_signal_missing: t("exp.ruleDesc.label_signal_missing"),
                                model: t("exp.ruleDesc.model"),
                                none: t("exp.ruleDesc.none"),
                              }[String(ac.rule_id).toLowerCase()]) ||
                            ac.title ||
                            ac.diagnosis ||
                            t("state.na"),
                        }),
                      ]),
                      el("td", {
                        text: ac.support_count
                          ? t("diag.facts", { n: formatNumber(ac.support_count) })
                          : "–",
                      }),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        taskClusters.diagnosis === "unknown"
          ? el("section", { className: "card" }, [
              el("span", { className: cls("chip", "warning"), text: t("diagnose.verdictUnknown") }),
              renderSourceCitation(
                taskClusters.diagnosis_source,
                taskClusters.diagnosis_quote,
                taskClusters.origin
              ),
            ])
          : null,

        diagDemo && Array.isArray(diagDemo.checks)
          ? el("section", { className: "card" }, [
              el("h2", { text: t("diagnose.checksTitle") }),
              renderSourceCitation(diagDemo.source),
              el(
                "div",
                { className: "row-list" },
                // Use .check-row + .check-badge so long check IDs (e.g. delay_sync_camera) wrap cleanly (F3)
                diagDemo.checks.map((chk) =>
                  el("div", { className: "check-row" }, [
                    el("span", { className: "check-badge", text: diagCheckTitle(chk.id) }),
                    el("div", { className: "row-body" }, [
                      el("b", { text: diagCheckText(chk.value) }),
                      renderSourceCitation(chk.source, chk.quote),
                    ]),
                  ])
                )
              ),
            ])
          : null,

        roundClusters.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              comparisonPlot(t("diagnose.clustersTitle"), roundClusters.map((cluster) => ({
                name: cluster.id, value: cluster.n,
              }))),
              el("h2", { text: t("diagnose.colDiag") }),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("diagnose.colCluster") }),
                    el("th", { text: t("diagnose.colStage") }),
                    el("th", { className: "num", text: "n" }),
                    el("th", { text: t("diagnose.colDiag") }),
                    el("th", { text: t("diagnose.colInterv") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  roundClusters.map((c) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: c.id }),
                      el("td", { text: stageLabel(c.stage) }),
                      el("td", { className: "num", text: formatNumber(c.n) }),
                      el("td", { text: c.diagnosis }),
                      el("td", { text: c.intervention }),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        taskClusterItems.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("h2", { text: t("diagnose.clustersTitle") }),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("common.id") }),
                    el("th", { text: t("diagnose.colCheckpoint") }),
                    el("th", { text: t("diagnose.colStage") }),
                    el("th", { className: "num", text: t("diagnose.colMembers") }),
                    el("th", { text: t("common.source") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  taskClusterItems.map((it) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: it.id }),
                      el("td", { className: "mono", text: it.checkpoint }),
                      el("td", { text: `${it.step ?? "–"} · ${stageLabel(it.stage || "–")}` }),
                      el("td", { className: "num", text: formatNumber(it.members) }),
                      el("td", {}, [renderSourceCitation(it.source, it.quote)]),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        task && task.process && task.process["5"] && task.process["5"].missing
          ? renderProcessEmptyBlock(5)
          : null
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// The jig round (tray-jig-r1) shows its baseline only (after_round null; Hiếu, 28/11/2026): the
// run's eval status and data cut, and a plain "no after-round run yet" instead of a number.
function renderJigLoop(round, jig) {
  const evals = Array.isArray(jig.evals) ? jig.evals : [];
  const runId = round.baseline || (evals[0] && evals[0].run) || null;
  const ev = evals.find((e) => e.run === runId) || null;
  const train = (Array.isArray(jig.runs) ? jig.runs : []).find((r) => r.branch === runId) || null;
  const cut = (jig.cuts && runId && jig.cuts[runId]) || jig.m_cut || null;
  const head = ev && ev.headline ? ev.headline : null;
  const hasFigures = ev && (ev.status === "ready" || ev.status === "blocked") && head;
  const evalText = !ev
    ? t("state.na")
    : hasFigures
      ? t("loop.jigEvalVal", {
          succ: formatNumber(head.successes),
          n: formatNumber(head.n),
          pct: formatPercent(head.p),
        })
      : ev.status === "withheld"
        ? t("exp.evalWithheld")
        : t("exp.evalMissing", { run: ev.run });
  const evalSub = !ev
    ? ""
    : ev.status === "blocked"
      ? t("exp.verdictBlocked")
      : ev.status === "missing"
        ? t("loop.jigEvalMissingSub")
        : jigReadingLines(ev).join(" · ");
  const node = (num, label, value, sub, title = null, accent = false) =>
    el("div", { className: cls("loop-evo-node", accent && "is-accent") }, [
      el("span", { className: "tax-badge", text: num }),
      el("span", { className: "tiny", text: label }),
      el("b", { className: "mono", text: value, title: title || "" }),
      sub ? el("span", { className: "tiny", text: sub }) : null,
    ]);
  const sources = [ev && ev.results_source, cut && cut.source].filter(Boolean);
  return [
    ...renderCrumbHeading({
      crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("loop.title") }],
      title: pickLang(round.title) || t("loop.title"),
      actions: [
        el("a", { className: "btn", href: "#/runs" }, [t("nav.item.runs")]),
        el("a", { className: cls("btn", "primary"), href: "#/eval" }, [t("nav.item.eval")]),
      ],
    }),
    renderReportSubnav("loop"),
    el("div", { className: "sect" }, [el("h2", { text: t("loop.visualFlowTitle") })]),
    el("div", { className: "loop-evo-strip" }, [
      node(
        "01",
        t("loop.statBaseline"),
        runId || t("state.na"),
        train
          ? t("loop.jigTrainSub", {
              step: formatNumber(train.ckpt_step || train.step),
              max: formatNumber(train.max_steps),
            })
          : ""
      ),
      node("02", t("nav.item.eval"), evalText, evalSub),
      node(
        "03",
        t("loop.jigCutLabel", { run: runId || "-" }),
        cut ? cut.name || "-" : t("state.na"),
        cut
          ? t("loop.jigCutSub", { files: formatNumber(cut.files), size: formatBytes(cut.bytes) })
          : "",
        null
      ),
      node("04", t("loop.statAfter"), "—", "", null, true),
    ]),
    el("section", { className: "card" }, [
      el("p", { text: t("loop.jigNote", { run: runId || "-" }) }),
      ...sources.map((src) => renderSourceCitation(src)),
    ]),
  ];
}

// ============================================================================
// #/loop — Failure -> Data Loop
// ============================================================================
export function renderLoopPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("loop.title")));

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const round = getCurrentRound();

      if (round && !story.round && story.jig) {
        setChildren(wrap, ...renderJigLoop(round, story.jig));
        return;
      }

      if (!round || !story.round) {
        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("loop.title") }],
            title: t("loop.title"),
          }),
          renderReportSubnav("loop"),
          renderRoundEmpty({ keys: ["story.round", "story.jig"] })
        );
        return;
      }

      const sr = story.round;
      const chain = sr.chain || {};
      const presentChain = CHAIN_KEYS.filter((k) => chain[k] != null);
      const withheld = Array.isArray(round.withhold_eval) ? round.withhold_eval : [];

      const stepLabelMap = {
        targets: "loop.stepTargets",
        generated: "loop.stepGenerated",
        recorded: "loop.stepRecorded",
        qa_pass: "loop.stepQaPass",
        quality: "loop.stepQuality",
        selected: "loop.stepSelected",
      };
      const maxChainVal = Math.max(1, ...presentChain.map((k) => Number(chain[k]) || 0));

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("loop.title") }],
          title: pickLang(round.title) || t("loop.title"),
        }),
        renderReportSubnav("loop"),

        withheld.length > 0
          ? el("div", {
              className: "empty",
              text: t("loop.withheldNote"),
            })
          : null,

        el("div", { className: "sect" }, [el("h2", { text: t("loop.visualFlowTitle") })]),
        el("div", { className: "loop-evo-strip" }, [
          el("div", { className: "loop-evo-node" }, [
            el("span", { className: "tax-badge", text: "01" }),
            el("span", { className: "tiny", text: t("loop.statBaseline") }),
            el("b", { className: "mono", text: round.baseline || t("state.na") }),
          ]),
          el("div", { className: "loop-evo-node" }, [
            el("span", { className: "tax-badge", text: "02" }),
            el("span", { className: "tiny", text: t("nav.item.diagnose") }),
            el("b", {
              className: "mono",
              text: `${formatNumber(chain.targets)} ${t("loop.stepTargets").toLowerCase()}`,
            }),
          ]),
          el("div", { className: "loop-evo-node" }, [
            el("span", { className: "tax-badge", text: "03" }),
            el("span", { className: "tiny", text: t("loop.stepSelected") }),
            el("b", { className: "mono", text: t("loop.selectedEp", { n: formatNumber(chain.selected) }) }),
            round.cut
              ? el("span", {
                  className: cls("tiny", "mono"),
                  title: round.cut,
                  text: compactPath(round.cut),
                })
              : null,
          ]),
          el("div", { className: cls("loop-evo-node", "is-accent") }, [
            el("span", { className: "tax-badge", text: "04" }),
            el("span", { className: "tiny", text: t("loop.statAfter") }),
            el("b", { className: "mono", text: round.after_round || t("state.na") }),
          ]),
        ]),

        presentChain.length > 0
          ? el(
              "div",
              { className: "funnel-cards" },
              presentChain.map((k, idx) => {
                const val = Number(chain[k]) || 0;
                const prevVal = idx > 0 ? Number(chain[presentChain[idx - 1]]) || 0 : val;
                const conv =
                  idx === 0 || prevVal <= 0
                    ? "100%"
                    : val > prevVal
                      ? `×${formatNumber(val / prevVal, { maximumFractionDigits: 1 })}`
                      : formatPercent(val / prevVal);
                const barPct = Math.max(6, Math.min(100, (val / maxChainVal) * 100));
                return el("div", { className: "funnel-card" }, [
                  el("div", { className: "task-head" }, [
                    el("span", {
                      className: "tiny",
                      text: t(stepLabelMap[k] || "common.status"),
                    }),
                    el("span", { className: cls("short-hash", "mono"), text: conv }),
                  ]),
                  el("b", { className: "mono", text: formatNumber(val) }),
                  el("div", { className: "stream-track" }, [
                    el("div", { className: "stream-fill", style: `width:${barPct.toFixed(1)}%` }),
                  ]),
                ]);
              })
            )
          : null,

        presentChain.length > 0
          ? renderChartBlock({
              title: t("loop.funnelTitle"),
              height: 235,
              buildOption: ({ soft, line, colors }) => ({
                grid: { left: 48, right: 20, top: 24, bottom: 32 },
                tooltip: { trigger: "axis" },
                xAxis: {
                  type: "category",
                  data: presentChain.map((k) => t(stepLabelMap[k] || "common.status")),
                  axisLabel: { color: soft },
                },
                yAxis: {
                  type: "value",
                  axisLabel: { color: soft },
                  splitLine: { lineStyle: { color: line } },
                },
                series: [
                  {
                    type: "bar",
                    data: presentChain.map((k) => chain[k]),
                    itemStyle: { color: colors[0], borderRadius: [6, 6, 0, 0] },
                    label: { show: true, position: "top", color: soft },
                  },
                ],
              }),
              tableNode: el("table", { className: "table" }, [
                el(
                  "tbody",
                  {},
                  presentChain.map((k) =>
                    el("tr", {}, [
                      el("td", { text: t(stepLabelMap[k] || "common.status") }),
                      el("td", { className: "num", text: formatNumber(chain[k]) }),
                    ])
                  )
                ),
              ]),
            })
          : null,

      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/base — Baseline & Controls
// ============================================================================
export function renderBasePage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("base.title")));

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const round = getCurrentRound();

      if (!round) {
        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("base.title") }],
            title: t("base.title"),
          }),
          renderReportSubnav("base"),
          renderRoundEmpty({ keys: ["story.demo", "story.jig"] })
        );
        return;
      }

      const models = story.demo && story.demo.models ? story.demo.models : {};
      const modelRuns = models.runs || {};
      const cites = models.cites ? Object.entries(models.cites) : [];
      // On the jig round the train entries of story.jig give the episodes and the cut (A14).
      const jigRuns = hasIndexAccess("story.jig") && story.jig && Array.isArray(story.jig.runs)
        ? story.jig.runs
        : [];
      const jigCuts = (story.jig && story.jig.cuts) || {};

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("base.title") }],
          title: t("base.title"),
        }),
        renderReportSubnav("base"),

        renderStatStrip([
          { label: t("loop.statBaseline"), value: round.baseline || "—" },
          {
            label: t("base.statControls"),
            value: (round.controls || []).join(", ") || "—",
          },
          {
            label: t("base.statMaxSteps"),
            value: formatNumber(round.max_steps),
          },
        ]),

        el("section", { className: cls("card", "table-wrap") }, [
          el("h2", { text: t("base.modelsTitle") }),
          el("table", { className: "table" }, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", { text: t("follow.colModel") }),
                el("th", { text: t("runs.colRole") }),
                el("th", { text: t("base.colCut") }),
                el("th", { className: "num", text: t("data.colEpisodes") }),
                el("th", { className: "num", text: t("base.colHumanClips") }),
              ]),
            ]),
            el(
              "tbody",
              {},
              (round.runs || []).map((rr) => {
                const jr = jigRuns.find((r) => r && r.branch === rr.id) || null;
                const m = modelRuns[rr.id] || (jr ? { episodes: jr.episodes } : {});
                const cutName = jigCuts[rr.id] ? jigCuts[rr.id].name : null;
                return el("tr", {}, [
                  el("td", { className: "mono", text: rr.id }),
                  el("td", {}, [renderStateChip(rr.role)]),
                  el("td", { className: "mono", text: m.data || rr.train_set || cutName || "—" }),
                  el("td", {
                    className: "num",
                    text:
                      m.base_episodes != null
                        ? `${formatNumber(m.episodes)} (${formatNumber(m.base_episodes)}+${formatNumber(m.targeted_episodes)})`
                        : formatNumber(m.episodes),
                  }),
                  el("td", {
                    className: "num",
                    text: m.human_clips != null ? formatNumber(m.human_clips) : "—",
                  }),
                ]);
              })
            ),
          ]),
        ]),

        cites.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("base.citesTitle") }),
              el(
                "div",
                { className: "row-list" },
                cites.map(([ck, cv]) =>
                  el("div", { className: "row" }, [
                    el("div", { className: "row-body" }, [
                      el("b", { className: "mono", text: ck }),
                      renderSourceCitation(cv.source, cv.quote),
                    ]),
                  ])
                )
              ),
            ])
          : null
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/follow — Follow One Case
// ============================================================================
export function renderFollowPage(ctx) {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("follow.title")));
  const q = (ctx && ctx.query) || new URLSearchParams();
  let filterMode = q.get("seed") ? "all" : "fail";
  let selectedKey =
    q.get("seed") && q.get("level") ? `${q.get("level")}:${q.get("seed")}` : null;

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const fol = story.follow || null;
      const runEntries = fol && fol.runs ? Object.entries(fol.runs) : [];
      const jigConds =
        story.jig && Array.isArray(story.jig.conditions) ? story.jig.conditions : [];
      const failConds = jigConds.filter((c) => c.pass_k < c.n_rep);
      const visibleConds = filterMode === "fail" && failConds.length > 0 ? failConds : jigConds;

      if (!selectedKey || !visibleConds.some((c) => `${c.level}:${c.seed}` === selectedKey)) {
        const pick = visibleConds[0] || jigConds[0] || null;
        selectedKey = pick ? `${pick.level}:${pick.seed}` : null;
      }
      const activeCond =
        visibleConds.find((c) => `${c.level}:${c.seed}` === selectedKey) ||
        jigConds[0] ||
        null;

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("follow.title") }],
          title: t("follow.title"),
        }),
        renderReportSubnav("follow"),

        jigConds.length > 0 && activeCond
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("div", { className: "task-head", style: "margin-bottom:10px" }, [
                el("h2", { text: t("exp.followJigTitle") }),
                el("span", {
                  className: cls("chip", activeCond.pass_k === activeCond.n_rep ? "" : "warning"),
                  text: `${activeCond.pass_k}/${activeCond.n_rep} pass`,
                }),
              ]),
              el("div", { className: "toolbar" }, [
                el(
                  "select",
                  {
                    className: "field",
                    onChange: (ev) => {
                      filterMode = ev.target.value;
                      selectedKey = null;
                      load();
                    },
                  },
                  [
                    el("option", {
                      value: "fail",
                      selected: filterMode === "fail",
                      text: t("exp.followFilterFailOnly", { count: formatNumber(failConds.length) }),
                    }),
                    el("option", {
                      value: "all",
                      selected: filterMode === "all",
                      text: t("exp.followFilterAllConds", { count: formatNumber(jigConds.length) }),
                    }),
                  ]
                ),
                el(
                  "select",
                  {
                    className: cls("field", "mono"),
                    onChange: (ev) => {
                      selectedKey = ev.target.value;
                      load();
                    },
                  },
                  visibleConds.map((c) => {
                    const k = `${c.level}:${c.seed}`;
                    return el("option", {
                      value: k,
                      selected: k === selectedKey,
                      text: `L${c.level} · seed ${c.seed} (${c.pass_k}/${c.n_rep}${c.top_failure ? ` · ${failureLabel(c.top_failure)}` : ""})`,
                    });
                  })
                ),
              ]),
              el("div", { className: "comparison-grid" }, [
                comparisonPlot(
                  t("exp.axisDistCm"),
                  (activeCond.trials || []).map((tr) => ({
                    name: `#${tr.repeat}`,
                    value: tr.dist_cm,
                  })),
                  { threshold: 5, unit: " cm" }
                ),
                comparisonPlot(
                  t("follow.colYaw"),
                  (activeCond.trials || []).map((tr) => ({
                    name: `#${tr.repeat}`,
                    value: tr.yaw_deg,
                  })),
                  { threshold: 10, unit: "°" }
                ),
              ]),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("exp.colRepeatIdx") }),
                    el("th", { text: t("follow.colSuccess") }),
                    el("th", { className: "num", text: t("exp.axisDistCm") }),
                    el("th", { className: "num", text: t("follow.colYaw") }),
                    el("th", { className: "num", text: t("common.time") }),
                    el("th", { text: t("follow.colFailure") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  (activeCond.trials || []).map((tr) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: `#${tr.repeat}` }),
                      el("td", {}, [outcomeChip(tr.success)]),
                      el("td", {
                        className: "num",
                        text: tr.dist_cm != null ? `${formatNumber(tr.dist_cm, { maximumFractionDigits: 2 })} cm` : "-",
                      }),
                      el("td", {
                        className: "num",
                        text: tr.yaw_deg != null ? `${formatNumber(tr.yaw_deg, { maximumFractionDigits: 2 })}°` : "-",
                      }),
                      el("td", {
                        className: "num",
                        text: tr.sim_s != null ? `${formatNumber(tr.sim_s, { maximumFractionDigits: 1 })} s` : "-",
                      }),
                      el("td", { title: tr.failure || "", text: tr.failure ? failureLabel(tr.failure) : "–" }),
                    ])
                  )
                ),
              ]),
            ])
          : null,

        !fol || runEntries.length === 0
          ? activeCond
            ? null
            : renderRoundEmpty({ keys: ["story.follow", "story.jig"] })
          : el("section", { className: cls("card", "table-wrap") }, [
              el("div", { className: "task-head" }, [
                el("h2", {
                  text: t("follow.caseMeta", {
                    level: fol.level ?? "-",
                    seed: fol.seed ?? "-",
                    dist: fol.tol ? formatNumber(fol.tol.distance_m * 100, { maximumFractionDigits: 1 }) : "–",
                    yaw: fol.tol ? fol.tol.yaw_error_deg : "-",
                  }),
                }),
                renderSourceCitation(fol.source),
              ]),
              el("div", { className: "comparison-grid" }, [
                comparisonPlot(t("follow.colDist"), runEntries.map(([name, run]) =>
                  ({ name, value: Number.isFinite(run.distance_m) ? run.distance_m * 100 : null })), {
                  threshold: Number.isFinite(fol.tol?.distance_m) ? fol.tol.distance_m * 100 : null,
                  unit: " cm",
                }),
                comparisonPlot(t("follow.colYaw"), runEntries.map(([name, run]) =>
                  ({ name, value: run.yaw_error_deg })), { threshold: fol.tol?.yaw_error_deg, unit: "°" }),
              ]),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("follow.colModel") }),
                    el("th", { text: t("follow.colSuccess") }),
                    el("th", { text: t("follow.colReachB") }),
                    el("th", { className: "num", text: t("follow.colDist") }),
                    el("th", { className: "num", text: t("follow.colYaw") }),
                    el("th", { text: t("follow.colFailure") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  runEntries.map(([rId, rv]) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: rId }),
                      el("td", {}, [outcomeChip(rv.success)]),
                      el("td", { text: rv.reach_b ? t("common.yes") : t("common.no") }),
                      el("td", {
                        className: "num",
                        text: `${formatNumber(rv.distance_m * 100, { maximumFractionDigits: 2 })} cm`,
                      }),
                      el("td", {
                        className: "num",
                        text: `${formatNumber(rv.yaw_error_deg, { maximumFractionDigits: 2 })}°`,
                      }),
                      el("td", { title: rv.failure || "", text: rv.failure ? failureLabel(rv.failure) : "–" }),
                    ])
                  )
                ),
              ]),
            ])
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/design — Experiment Design
// ============================================================================
export function renderDesignPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("design.title")));

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const task = getCurrentTask();
      const design = story.demo && story.demo.design ? story.demo.design : null;

      const sections = ["input", "output", "environment", "devices", "resource"];

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("design.title") }],
          title: t("design.title"),
        }),
        renderReportSubnav("design"),

        task
          ? el("section", { className: "card" }, [
              el("h2", { text: pickLang(task.name) || task.id }),
              el("p", { className: "muted", text: pickLang(task.description) }),
              el("strong", { text: taskSuccessText(task) }),
              renderSourceCitation(task.success && task.success.source),
            ])
          : null,

        design
          ? el(
              "div",
              { className: "stack" },
              sections
                .filter((sec) => Array.isArray(design[sec]) && design[sec].length > 0)
                .map((sec) =>
                  el("section", { className: "card" }, [
                    el("h2", {
                      className: "eyebrow",
                      text: hasI18nKey("design.sec." + sec) ? t("design.sec." + sec) : sec,
                    }),
                    el(
                      "div",
                      { className: "row-list" },
                      design[sec].map((item) =>
                        el("div", { className: "row" }, [
                          el("div", { className: "row-body" }, [
                            el("b", { text: designItemTitle(item.id) }),
                            el("p", {
                              className: "muted",
                              text: designItemValue(item),
                            }),
                            renderSourceCitation(item.source, item.quote, item.kind),
                          ]),
                        ])
                      )
                    ),
                  ])
                )
            )
          : null,

        design && Array.isArray(design.unsourced) && design.unsourced.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("design.unsourcedTitle") }),
              el(
                "ul",
                { className: "missing-list" },
                design.unsourced.map((u) => el("li", { className: "missing-item", text: u }))
              ),
            ])
          : null
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/cost — Cost & Ledger
// ============================================================================
// Ledger rows (audit 02 P1-1): new shape {story, label, est_cu, mea_cu, est_usd, mea_usd};
// the old shape [story, est_usd, mea_usd] carries USD only, so it is never labelled CU.
function normalizeLedger(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const legacy = list.some((r) => Array.isArray(r));
  const out = list
    .map((r) => {
      if (Array.isArray(r)) {
        const [story, est, mea] = r;
        return { story, name: String(story ?? ""), est: numOrNull(est), mea: numOrNull(mea) };
      }
      if (!r || typeof r !== "object") return null;
      const label = pickLang(r.label);
      return {
        story: r.story,
        name: label || String(r.story ?? ""),
        est: numOrNull(r.est_cu),
        mea: numOrNull(r.mea_cu),
        estUsd: numOrNull(r.est_usd),
        meaUsd: numOrNull(r.mea_usd),
      };
    })
    .filter((r) => r && ((r.est || 0) !== 0 || (r.mea || 0) !== 0));
  return { legacy, rows: out };
}

function numOrNull(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function renderLedgerCard(rawLedger) {
  const { legacy, rows } = normalizeLedger(rawLedger);
  if (!rows.length) return null;
  // The old shape cannot fold hidden stories into the "other" row (tasks.json does not list
  // them), so it shows no per-story rows: rebuild the index for the table.
  if (legacy) {
    return el("section", { className: "card" }, [
      el("h2", { text: t("cost.ledgerTitle") }),
      el("p", { className: "muted", text: t("cost.ledgerLegacyNote") }),
    ]);
  }
  const unit = " CU";
  const fmt = (v) => (v == null ? "—" : formatNumber(v, { maximumFractionDigits: 2 }));
  const head = [t("cost.colTask"), t("cost.colEstCu"), t("cost.colMeaCu")];
  return el("section", { className: cls("card", "table-wrap") }, [
    el("h2", { text: t("cost.ledgerTitle") }),
    el("p", { className: "muted", text: t("cost.ledgerNote") }),
    el("table", { className: "table" }, [
      el("thead", {}, [el("tr", {}, head.map((h, i) => el("th", { className: i ? "num" : "", text: h })))]),
      el(
        "tbody",
        {},
        rows.map((r) =>
          el("tr", {}, [
            el("td", { text: r.name, title: r.story && r.story !== r.name ? String(r.story) : null }),
            el("td", { className: "num", text: fmt(r.est) }),
            el("td", { className: "num", text: fmt(r.mea) }),
          ])
        )
      ),
    ]),
    el("details", { className: "studio-details" }, [
      el("summary", { text: t("cost.ledgerChart") }),
      comparisonPlot(
        t("cost.colEstCu"),
        rows.map((r) => ({ name: r.name, value: r.est })),
        { unit }
      ),
      comparisonPlot(
        t("cost.colMeaCu"),
        rows.map((r) => ({ name: r.name, value: r.mea })),
        { unit }
      ),
    ]),
  ]);
}

function costLineLabel(id) {
  const key = "cost.line." + id;
  return hasI18nKey(key) ? t(key) : String(id ?? "");
}

// Measured cost of the jig round when the index carries it (story.jig.cost).
function renderJigCostCard(jigCost) {
  if (!jigCost || typeof jigCost !== "object") return null;
  const parts = Object.entries(jigCost).filter(([, v]) => v && typeof v === "object");
  if (!parts.length) return null;
  return el("section", { className: "card" }, [
    el("h2", { text: t("cost.jigTitle") }),
    el(
      "div",
      { className: "row-list" },
      parts.map(([part, v]) =>
        el("div", { className: "row" }, [
          el("div", { className: "row-body" }, [
            el("b", {
              text: `${costLineLabel("jig_" + part)}: ${
                v.cu != null ? formatNumber(v.cu, { maximumFractionDigits: 2 }) + " CU" : "—"
              }`,
            }),
            el("p", {
              className: "muted",
              text: [pickLang(v.label), v.kind === "measured" ? t("cost.kindMeasured") : t("cost.kindEstimated")]
                .filter(Boolean)
                .join(" · "),
            }),
            v.doc ? renderSourceCitation(v.doc.source, v.doc.quote) : null,
          ]),
        ])
      )
    ),
  ]);
}

export function renderCostPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("cost.title")));

  const load = async () => {
    try {
      const [rawStory, estimates] = await Promise.all([
        ensureStoryRaw(),
        getJSON("/api/estimates"),
      ]);
      const story = scopeStoryForTask(rawStory);
      const task = getCurrentTask();
      const roundCost = story.demo && story.demo.round_cost ? story.demo.round_cost : null;
      const jigCost = story.jig && story.jig.cost ? story.jig.cost : null;
      const colabMach =
        state.statusDoc && state.statusDoc.machines && state.statusDoc.machines.colab
          ? state.statusDoc.machines.colab
          : {};
      const colabHist = (Array.isArray(story.colab_balance) ? story.colab_balance : []).filter(
        (p) => Array.isArray(p) && Number.isFinite(p[1]) && Number.isFinite(Date.parse(p[0]))
      );

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("cost.title") }],
          title: t("cost.title"),
          lead: t("cost.lead"),
        }),
        renderReportSubnav("cost"),

        renderStatStrip([
          {
            label: t("jobs.machinesColab"),
            value:
              colabMach.balance != null
                ? `${formatNumber(colabMach.balance, { maximumFractionDigits: 2 })} CU`
                : t("state.na"),
            sub: colabMach.fresh === false ? t("jobs.colabStale") : formatDateTime(colabMach.time),
          },
          {
            label: t("cost.roundCostTitle"),
            value:
              roundCost && roundCost.total_cu != null
                ? `${formatNumber(roundCost.total_cu, { maximumFractionDigits: 2 })} CU`
                : "—",
            sub:
              roundCost && roundCost.total_usd != null
                ? `~${formatNumber(roundCost.total_usd, { maximumFractionDigits: 2 })} USD`
                : roundCost
                  ? ""
                  : t("cost.roundCostOther"),
          },
          {
            label: t("cost.estimatesTitle"),
            value: formatNumber((estimates || []).length),
          },
        ]),

        task && task.process && task.process["0"] && task.process["0"].missing
          ? renderProcessEmptyBlock(0)
          : null,

        roundCost
          ? el("section", { className: "card" }, [
              el("h2", { text: t("cost.roundCostTitle") }),
              el(
                "div",
                { className: "row-list" },
                (roundCost.lines || []).map((ln) =>
                  el("div", { className: "row" }, [
                    el("div", { className: "row-body" }, [
                      el("b", {
                        text: `${costLineLabel(ln.id)}: ${formatNumber(ln.value, { maximumFractionDigits: 2 })} CU`,
                      }),
                      renderSourceCitation(ln.source, ln.quote),
                    ]),
                  ])
                )
              ),
              renderSourceCitation(roundCost.source, t("cost.totalNote"), roundCost.kind),
            ])
          : null,

        renderJigCostCard(jigCost),

        renderLedgerCard(story.ledger),

        colabHist.length > 0
          ? renderChartBlock({
              title: t("cost.colabHistoryTitle"),
              height: 220,
              buildOption: ({ soft, line, colors }) => ({
                grid: { left: 48, right: 20, top: 18, bottom: 32 },
                tooltip: { trigger: "axis" },
                xAxis: {
                  type: "time",
                  axisLabel: { color: soft, hideOverlap: true },
                },
                yAxis: {
                  type: "value",
                  name: "CU",
                  nameTextStyle: { color: soft },
                  axisLabel: { color: soft },
                  splitLine: { lineStyle: { color: line } },
                },
                series: [
                  {
                    type: "line",
                    showSymbol: false,
                    data: colabHist.map((p) => [Date.parse(p[0]), p[1]]),
                    lineStyle: { width: 2, color: colors[0] },
                  },
                ],
              }),
              tableNode: el("table", { className: "table" }, [
                el(
                  "tbody",
                  {},
                  colabHist.slice(-40).map(([tm, bal]) =>
                    el("tr", {}, [
                      el("td", { text: formatDateTime(tm) }),
                      el("td", { className: "num", text: `${formatNumber(bal, { maximumFractionDigits: 2 })} CU` }),
                    ])
                  )
                ),
              ]),
            })
          : null,

        Array.isArray(estimates) && estimates.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("cost.estimatesTitle") }),
              el(
                "div",
                { className: "row-list" },
                estimates.map((es) =>
                  el("div", { className: "row" }, [
                    el("div", { className: "row-body" }, [
                      el("b", { text: pickLang(es.label) }),
                    ]),
                  ])
                )
              ),
            ])
          : null
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/report — Summary Round Report
// ============================================================================
export function renderReportPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("report.title")));

  const load = async () => {
    try {
      const rawStory = await ensureStoryRaw();
      const story = scopeStoryForTask(rawStory);
      const task = getCurrentTask();
      const demo = story.demo || {};
      const clip = demo.success_clip || null;
      const failShare = demo.fail_share || null;
      const pairRuns = story.pair && Array.isArray(story.pair.runs) ? story.pair.runs : [];
      const pairComps =
        story.pair && Array.isArray(story.pair.comparisons) ? story.pair.comparisons : [];
      const jig = hasIndexAccess("story.jig") && story.jig ? story.jig : null;
      const hasRound1 = pairRuns.length > 0 || pairComps.length > 0 || Boolean(clip);

      let clipUrl = null;
      if (clip && typeof clip.path === "string" && clip.path.startsWith("console/media/demo/")) {
        clipUrl = `/demomedia/${clip.path.slice("console/media/demo/".length)}`;
      }

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("report.title") }],
          title: t("report.title"),
          lead: t("report.lead"),
        }),
        renderReportSubnav("report"),

        task
          ? el("section", { className: "card" }, [
              el("h2", { text: pickLang(task.name) || task.id }),
              el("p", { className: "muted", text: taskSuccessText(task) }),
              renderSourceCitation(task.success && task.success.source),
            ])
          : null,

        jig ? renderJigReportBlock(jig) : null,

        pairRuns.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("report.round1Title") }),
              renderStatStrip(
                pairRuns.map((r) => ({
                  label: r.run,
                  value: `${formatNumber(r.successes)}/${formatNumber(r.n)}`,
                  sub: t("report.runSuccSub", { pct: formatPercent(r.p) }),
                }))
              ),
              wilsonOverlap(pairRuns)
                ? el("p", { className: "muted", text: t("report.round1Overlap") })
                : null,
              renderSourceCitation(story.pair.source),
            ])
          : null,

        clip
          ? el("section", { className: "card" }, [
              el("h2", { text: t("report.clipTitle") }),
              el("p", {
                className: "muted",
                text: t("report.clipMeta", {
                  model: clip.model || "–",
                  prov: clip.provenance || "–",
                  level: clip.level != null ? clip.level : "–",
                  seed: clip.seed != null ? clip.seed : "–",
                }),
              }),
              clipUrl
                ? el("video", {
                    className: "video-player",
                    controls: true,
                    preload: "metadata",
                    src: clipUrl,
                  })
                : null,
              clip.note ? el("p", { className: "sources-note", text: t("report.clipNote") }) : null,
              renderSourceCitation(clip.source, clip.deck_caption),
            ])
          : null,

        pairComps.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("h2", { text: t("eval.pairCompTitle") }),
              el("p", { className: "muted", text: t("eval.pairCompNote") }),
              renderPairCompTable(pairComps),
            ])
          : null,

        failShare && failShare.runs
          ? el("section", { className: "card" }, [
              el("h2", { text: t("report.failShareTitle") }),
              el(
                "div",
                { className: "meta-strip" },
                Object.entries(failShare.runs).map(([rk, rv]) =>
                  el("div", { className: "meta-box" }, [
                    el("span", { text: rk }),
                    el("b", { text: formatPercent(rv.share) }),
                    el("small", {
                      text: t("report.failShareSub", {
                        part: formatNumber(rv.place_pose + rv.tray_tilt),
                        failed: formatNumber(rv.failed),
                      }),
                    }),
                  ])
                )
              ),
              renderSourceCitation(failShare.source),
            ])
          : null,

        !jig && !hasRound1 ? renderRoundEmpty({ keys: ["story.jig", "story.pair", "story.demo"] }) : null
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// True when every Wilson interval of the runs shares a common point: the counts then do not
// separate the runs (W3: "các khoảng chồng nhau").
function wilsonOverlap(runs) {
  const iv = runs.map((r) => r && r.wilson).filter((w) => Array.isArray(w) && w.length === 2);
  if (iv.length < 2) return false;
  return Math.max(...iv.map((w) => w[0])) <= Math.min(...iv.map((w) => w[1]));
}

// Report of the jig round (story.jig, DA-53): headline of the featured run with the rule
// readings, the train run, and links to the pages with the detail. Numbers come from the
// index only; wording follows W1 (successes, never "đạt" for a count).
function renderJigReportBlock(jig) {
  const evals = Array.isArray(jig.evals) ? jig.evals : [];
  const ev =
    evals.find((e) => e && e.run === jig.featured && e.status === "ready") ||
    evals.find((e) => e && e.status === "ready") ||
    null;
  const head = ev && ev.headline ? ev.headline : null;
  const train = Array.isArray(jig.runs)
    ? jig.runs.find((r) => r && r.branch === (ev ? ev.run : jig.featured)) || jig.runs[0]
    : null;
  const readings = jigReadingLines(ev);
  const items = [];
  if (head) {
    items.push({
      label: t("report.jigHeadLabel", { run: ev.run }),
      value: `${formatNumber(head.successes)}/${formatNumber(head.n)}`,
      sub: t("report.jigHeadSub", { pct: formatPercent(head.p), conditions: formatNumber(head.conditions) }),
    });
    if (Array.isArray(head.ci)) {
      items.push({
        label: t("report.jigCiLabel"),
        value: `${formatPercent(head.ci[0])} – ${formatPercent(head.ci[1])}`,
        sub: t("report.jigCiSub"),
      });
    }
  }
  if (train) {
    items.push({
      label: t("report.jigTrainLabel", { run: train.branch }),
      value: formatNumber(train.ckpt_step ?? train.step),
      sub: t("report.jigTrainSub", {
        episodes: formatNumber(train.episodes),
        frames: formatNumber(train.frames),
      }),
    });
  }
  return el("section", { className: "card" }, [
    el("h2", { text: t("report.jigTitle", { scene: jig.scene || "" }) }),
    items.length > 0 ? renderStatStrip(items) : el("p", { className: "muted", text: t("state.empty") }),
    readings.length > 0
      ? el("ul", { className: "reading-list" }, readings.map((ln) => el("li", { text: ln })))
      : null,
    el("p", { className: "muted", text: t("report.jigNote") }),
    el("div", { className: "actions" }, [
      el("a", { className: cls("btn", "primary"), href: "#/eval" }, [t("report.jigToEval")]),
      el("a", { className: "btn", href: "#/follow" }, [t("nav.item.follow")]),
      el("a", { className: "btn", href: "#/diagnose" }, [t("nav.item.diagnose")]),
    ]),
    renderSourceCitation(ev ? ev.results_source : jig.source),
  ]);
}
