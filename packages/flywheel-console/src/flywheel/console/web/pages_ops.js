import {
  cleanInlineMarkdown,
  cleanLogLines,
  cls,
  compactPath,
  el,
  ensureCatalog,
  ensureKinds,
  ensureModels,
  ensureStoryRaw,
  formatBytes,
  formatDateTime,
  formatJobKindLabel,
  formatNumber,
  formatPercent,
  formatStateLabel,
  friendlyBatchTitle,
  getCurrentRound,
  getCurrentTask,
  getJSON,
  hasI18nKey,
  hasIndexAccess,
  isStageComplete,
  jigReadingLines,
  onRouteCleanup,
  pickLang,
  postJSON,
  renderChartBlock,
  renderCrumbHeading,
  renderErrorBlock,
  renderFlywheelOrbitalCanvas,
  renderLoadingView,
  renderSourceCitation,
  renderRoundLinks,
  renderStatStrip,
  renderTimeline,
  renderStateChip,
  scopeStoryForTask,
  scrubPath,
  setChildren,
  setSelection,
  shortHashId,
  state,
  t,
  tryGetJSON,
  uploadVideoFile,
} from "./core.js";
import { icon } from "./icons.js";

const STAGE_NUMS = ["1", "2", "3", "4", "5", "6"];
const JOB_TABS = ["all", "pipeline", "import", "export", "machines"];

function formatHowLine(howItems) {
  if (!Array.isArray(howItems) || howItems.length === 0) return "";
  return howItems
    .map((item) => {
      if (!item || typeof item !== "object") return "";
      if (item.text) return item.text;
      if (item.path) return item.section ? `${item.path} §${item.section}` : item.path;
      return "";
    })
    .filter(Boolean)
    .join(" · ");
}

// Reader's name of a job stage code ("eval" → "Đánh giá"); the code when no name exists.
function jobStageLabel(stage) {
  if (!stage) return t("state.na");
  return hasI18nKey("home.stageId." + stage) ? t("home.stageId." + stage) : String(stage);
}

// Job name cell: the reader's name, the kind code only in a tooltip (design audit P1-12).
function jobKindCell(rawKind, extraNode = null) {
  const { label, code } = formatJobKindLabel(rawKind);
  return el("div", { className: "job-kind-cell", title: code || null }, [
    el("div", { className: "actions" }, [el("b", { text: label }), extraNode]),
  ]);
}

// A closed "Nâng cao" disclosure for command lines and raw parameters (design audit P1-12).
function advancedBlock(children, label = t("ux.advanced")) {
  const list = (Array.isArray(children) ? children : [children]).filter(Boolean);
  if (list.length === 0) return null;
  return el("details", { className: cls("studio-details", "ops-advanced") }, [
    el("summary", { text: label }),
    el("div", { className: "stack-sm" }, list),
  ]);
}

function isLiveSession(sess) {
  return Boolean(
    sess &&
      String(sess.state || "").toLowerCase() === "running" &&
      sess.stale !== true &&
      sess.fresh !== false
  );
}

function runTrained(run) {
  const max = Number(run && run.max_steps);
  const reached = Number(
    run && (run.ckpt_step != null ? run.ckpt_step : run.step != null ? run.step + 1 : NaN)
  );
  return Number.isFinite(max) && max > 0 && Number.isFinite(reached) && reached >= max;
}

// Step 05 line(s) of the selected round, one per scene its index grants (content audit B5, W3):
// round 1 names the run with the most successes and adds "(các khoảng chồng nhau)" only when its
// Wilson interval overlaps another run's; the jig scene gives the featured run's count.
function roundEvalLines(curRound, story, jigDoc, jigEval) {
  const lines = [];
  const pairRuns =
    story.pair && Array.isArray(story.pair.runs)
      ? story.pair.runs.filter((r) => r && Number(r.n) > 0)
      : [];
  if (pairRuns.length > 0) {
    const top = pairRuns.reduce((a, b) => (Number(b.successes) > Number(a.successes) ? b : a));
    const others = pairRuns.filter((r) => r !== top);
    const overlap =
      Array.isArray(top.wilson) &&
      others.some((r) => Array.isArray(r.wilson) && Number(r.wilson[1]) >= Number(top.wilson[0]));
    const vars = {
      round: curRound.number != null ? formatNumber(curRound.number) : curRound.id,
      run: top.run,
      succ: formatNumber(top.successes),
      n: formatNumber(top.n),
    };
    const key =
      others.length === 0
        ? "ux.homeEvalRoundOne"
        : overlap
          ? "ux.homeEvalRoundTopOverlap"
          : "ux.homeEvalRoundTop";
    lines.push(t(key, vars));
  }
  const head = jigEval && jigEval.status === "ready" ? jigEval.headline : null;
  if (jigDoc && head) {
    lines.push(
      t("ux.homeEvalSceneLine", {
        scene: jigDoc.scene || curRound.scene || curRound.id,
        run: jigEval.run,
        succ: formatNumber(head.successes),
        n: formatNumber(head.n),
      })
    );
  }
  return lines;
}

// "{clusters} cụm · {fails} lượt hỏng" from the jig round's latest Agent QA assembly or the
// round's failure clusters; "—" when the round has none (content audit A10).
function diagnosisSummary(story, jigDoc) {
  const asmList = jigDoc && Array.isArray(jigDoc.agentqa) ? jigDoc.agentqa : [];
  const asm = asmList.length > 0 ? asmList[asmList.length - 1] : null;
  const asmClusters =
    asm && Array.isArray(asm.clusters) ? asm.clusters.filter((c) => Number(c && c.size) > 0) : [];
  if (asmClusters.length > 0) {
    return t("ux.homeDiagSummary", {
      clusters: formatNumber(asmClusters.length),
      fails: formatNumber(asmClusters.reduce((sum, c) => sum + Number(c.size), 0)),
    });
  }
  const roundClusters =
    story && story.round && Array.isArray(story.round.clusters)
      ? story.round.clusters.filter((c) => Number(c && c.failures) > 0)
      : [];
  if (roundClusters.length > 0) {
    return t("ux.homeDiagSummary", {
      clusters: formatNumber(roundClusters.length),
      fails: formatNumber(roundClusters.reduce((sum, c) => sum + Number(c.failures), 0)),
    });
  }
  return "—";
}

const HOME_STAGE_IDS = ["collect", "process", "release", "train", "eval", "loop"];

// The six home steps of the selected round (content audit A15). Each step comes from the
// round's scoped story (train, eval, loop, release of its runs) or task-level data (catalog,
// QA checks); a step neither gives falls back to the server's machine-wide stage, marked
// scope "machine" so the page labels it "toàn máy". No number is made up.
function deriveRoundStages({ serverStages, curTask, curRound, story, jigDoc, jigEval, jigRunId }) {
  const byId = new Map(serverStages.filter((s) => s && s.id).map((s) => [s.id, s]));
  const ids = serverStages.length > 0 ? serverStages.map((s) => s && s.id) : HOME_STAGE_IDS;
  const own = (id, scope, fields) => ({
    ...(byId.get(id) || { id }),
    task: curTask.id,
    issue: null,
    nowLines: null,
    scope,
    ...fields,
  });
  const machine = (id) =>
    byId.has(id)
      ? { ...byId.get(id), scope: "machine" }
      : { id, state: "idle", now: t("state.na"), task: curTask.id, scope: "machine" };

  const roundRunIds = new Set((curRound.runs || []).map((r) => r && r.id).filter(Boolean));
  const trainRuns = jigDoc
    ? Array.isArray(jigDoc.runs)
      ? jigDoc.runs.filter(Boolean)
      : []
    : Array.isArray(story.runs)
      ? story.runs.filter((r) => r && roundRunIds.has(r.branch))
      : [];
  const totals = (curTask.catalog_totals && curTask.catalog_totals.all) || {};
  const heat = Array.isArray(story.heat) ? story.heat : [];
  const chain = story.round && story.round.chain ? story.round.chain : null;
  const withheld = Array.isArray(curRound.withhold_eval) && curRound.withhold_eval.length > 0;

  return ids.map((id) => {
    if (id === "collect" && Number(totals.episodes) > 0) {
      return own(id, "task", {
        state: "done",
        now: t("ux.homeStageCollectNow", {
          episodes: formatNumber(totals.episodes),
          sets: formatNumber(totals.sets ?? 0),
        }),
      });
    }
    if (id === "process" && heat.length > 0) {
      return own(id, "task", {
        state: "done",
        now: t("ux.homeStageProcessNow", {
          checks: formatNumber(new Set(heat.map((row) => row[0])).size),
          sources: formatNumber(new Set(heat.map((row) => row[1])).size),
        }),
      });
    }
    if (id === "release" && trainRuns.length > 0) {
      const done = trainRuns.filter((r) => r.release).length;
      return own(id, "round", {
        state: done === trainRuns.length ? "done" : "partial",
        now: t("ux.homeStageReleaseNow", {
          done: formatNumber(done),
          total: formatNumber(trainRuns.length),
        }),
      });
    }
    if (id === "train" && trainRuns.length > 0) {
      const done = trainRuns.filter(runTrained).length;
      return own(id, "round", {
        state: done === trainRuns.length ? "done" : "partial",
        now: t("ux.homeStageTrainNow", {
          done: formatNumber(done),
          total: formatNumber(trainRuns.length),
        }),
      });
    }
    if (id === "eval") {
      const lines = roundEvalLines(curRound, story, jigDoc, jigEval);
      if (jigDoc) {
        const status = jigEval ? jigEval.status : "missing";
        if (status === "ready" && lines.length > 0) {
          return own(id, "round", { state: "done", now: lines.join(" · "), nowLines: lines });
        }
        return own(id, "round", {
          state: status === "missing" ? "waiting" : "partial",
          now:
            status === "blocked"
              ? t("ux.homeJigEvalBlocked", { run: jigEval.run })
              : status === "withheld"
                ? t("ux.homeEvalWithheldNote")
                : t("exp.evalMissing", { run: jigRunId || "-" }),
        });
      }
      if (lines.length > 0) {
        return own(id, "round", { state: "done", now: lines.join(" · "), nowLines: lines });
      }
    }
    if (id === "loop") {
      if (chain && chain.selected != null) {
        return own(id, "round", {
          state: "done",
          now: t("ux.homeStageLoopNow", { selected: formatNumber(chain.selected) }),
          issue: withheld ? t("ux.homeEvalWithheldNote") : null,
        });
      }
      if (jigDoc && !curRound.after_round) {
        return own(id, "round", { state: "idle", now: t("ux.homeStageLoopNone") });
      }
    }
    return machine(id);
  });
}

// ============================================================================
// #/home — Visual Closed-Loop Flywheel Command Center
// ============================================================================
export function renderHomePage() {
  const wrap = el("div", {});

  if (state.tasksLoading && !state.tasksLoaded) {
    return renderLoadingView(t("home.title"));
  }

  let disposed = false;
  let statusPollTimer = null;
  const connMarker = el("div", { className: "conn-lost", role: "status", hidden: true }, [
    icon("alert"),
    el("span", { text: t("ux.connLost") }),
  ]);
  onRouteCleanup(() => {
    disposed = true;
    if (statusPollTimer) window.clearInterval(statusPollTimer);
  });

  let selectedStageIdx = 0;
  let userSelectedStage = false;

  const getStageTitle = (st) => {
    if (!st) return "";
    return hasI18nKey("home.stageId." + st.id) ? t("home.stageId." + st.id) : st.label || st.id || "";
  };

  const renderContent = () => {
    if (disposed) return;
    const curTask = getCurrentTask();
    const curRound = getCurrentRound();
    const statusDoc = state.statusDoc || {};
    const serverStages = Array.isArray(statusDoc.stages) ? statusDoc.stages : [];

    const scopedStory = state.storyRawDoc ? scopeStoryForTask(state.storyRawDoc) : {};
    const pairDoc = scopedStory && scopedStory.pair ? scopedStory.pair : null;
    const pairRuns = pairDoc && Array.isArray(pairDoc.runs) ? pairDoc.runs : [];
    const pairBest =
      pairRuns.find((r) => pairDoc && r.run === pairDoc.best) || pairRuns[0] || null;
    const withheldList =
      curRound && Array.isArray(curRound.withhold_eval) ? curRound.withhold_eval : [];
    // The jig round (tray-jig-r1) has its own result: the featured eval when ready, else the
    // baseline's eval status; never a tray-r1 number (decision 4 of story DA-53).
    const jigDoc =
      hasIndexAccess("story.jig") && scopedStory && scopedStory.jig ? scopedStory.jig : null;
    const jigEvals = jigDoc && Array.isArray(jigDoc.evals) ? jigDoc.evals : [];
    const jigRunId =
      (jigDoc && jigDoc.featured) ||
      (curRound && curRound.baseline) ||
      (jigEvals[0] && jigEvals[0].run) ||
      null;
    const jigEval = jigEvals.find((e) => e.run === jigRunId) || null;
    const jigTrainRuns = jigDoc && Array.isArray(jigDoc.runs) ? jigDoc.runs : [];
    const jigTrain =
      jigTrainRuns.find((r) => r.branch === jigRunId) ||
      jigTrainRuns.find((r) => jigDoc && r.branch === jigDoc.log_run) ||
      null;

    // The six steps follow the selected round (content audit A15); without a round, or before
    // any data arrives, the ring shows the server's machine-wide stages as before.
    const stages =
      curTask && curRound && (serverStages.length > 0 || state.storyRawDoc)
        ? deriveRoundStages({
            serverStages,
            curTask,
            curRound,
            story: scopedStory || {},
            jigDoc,
            jigEval,
            jigRunId,
          })
        : serverStages;
    const recentJobs = Array.isArray(statusDoc.jobs) ? statusDoc.jobs : [];
    const catTotals = (curTask && curTask.catalog_totals) || {};
    const allTotals = catTotals.all || {};
    const hoursText =
      allTotals.hours == null
        ? t("state.na")
        : t("tasks.unitHours", { val: formatNumber(allTotals.hours, { maximumFractionDigits: 2 }) });

    const matchedStages = stages.filter((s) => curTask && s && s.task === curTask.id);
    const matchedDoneStages = matchedStages.filter((s) => isStageComplete(s && s.state)).length;
    const distinctOwners = Array.from(
      new Set(stages.map((s) => (s && s.task ? String(s.task).trim() : "")).filter(Boolean))
    );
    const hasUnscopedStages = stages.some((s) => !s || !String(s.task || "").trim());
    const isPureCurrentTask = Boolean(
      curTask &&
        stages.length > 0 &&
        !hasUnscopedStages &&
        distinctOwners.length === 1 &&
        distinctOwners[0] === curTask.id
    );
    const isSingleOtherTask = Boolean(
      curTask &&
        stages.length > 0 &&
        !hasUnscopedStages &&
        distinctOwners.length === 1 &&
        distinctOwners[0] !== curTask.id
    );
    const isMixedStageScope =
      stages.length > 0 &&
      (distinctOwners.length > 1 || (distinctOwners.length === 1 && hasUnscopedStages));
    const isAllUnscoped = stages.length > 0 && distinctOwners.length === 0;
    const singleOwner = distinctOwners.length === 1 ? distinctOwners[0] : "";
    const mixedOwnersLabel = (
      hasUnscopedStages ? [...distinctOwners, "?"] : distinctOwners
    ).join(", ");

    const doneStages = stages.filter((s) => isStageComplete(s && s.state)).length;
    const procMap = curTask && curTask.process ? curTask.process : {};
    const procKeys = STAGE_NUMS.filter((n) => procMap[n]);

    const resolveJobOwner = (job) => {
      if (!job) return "";
      if (typeof job.task === "string" && job.task.trim()) return job.task.trim();
      if (job.params && typeof job.params.task === "string" && job.params.task.trim()) {
        return job.params.task.trim();
      }
      if (job.id) {
        const ownerStages = stages.filter(
          (s) => s && s.task && Array.isArray(s.jobs) && s.jobs.includes(job.id)
        );
        const owners = Array.from(new Set(ownerStages.map((s) => String(s.task).trim())));
        if (owners.length === 1) return owners[0];
      }
      return "";
    };

    if (!userSelectedStage && stages.length > 0) {
      const blockedStates = ["blocked", "failed", "reject"];
      const activeStates = ["running", "queued", "waiting", "flag", "partial"];
      let pick = stages.findIndex(
        (s) =>
          curTask &&
          s &&
          s.task === curTask.id &&
          blockedStates.includes(String(s.state || "").toLowerCase())
      );
      if (pick < 0) {
        pick = stages.findIndex(
          (s) =>
            curTask &&
            s &&
            s.task === curTask.id &&
            activeStates.includes(String(s.state || "").toLowerCase())
        );
      }
      if (pick < 0 && isPureCurrentTask) {
        const evalIdx = stages.findIndex((s) => s && s.id === "eval");
        if (evalIdx >= 0) pick = evalIdx;
      }
      selectedStageIdx = pick >= 0 ? pick : 0;
    }

    const spotlightBox = el("div", { className: "stage-spotlight", "aria-live": "polite" });

    const updateSpotlight = (idx) => {
      selectedStageIdx = idx;
      const st = stages[idx];
      if (!st) {
        setChildren(
          spotlightBox,
          el("span", {
            className: "muted",
            text: state.statusLoaded ? t("state.empty") : t("state.loading"),
          })
        );
        return;
      }
      const sameTask = curTask && st.task === curTask.id;
      const scopeNote = !st.task
        ? t("home.stageUnknownTask")
        : !sameTask
          ? t("home.stageOtherTask", { task: st.task })
          : "";
      const stTitle = getStageTitle(st);
      const taskProc = curTask && procMap[String(idx + 1)] ? procMap[String(idx + 1)] : null;
      const taskProcMissing = taskProc ? pickLang(taskProc.missing) : "";
      const taskProcHow = taskProc ? formatHowLine(taskProc.how) : "";
      const numStr = String(idx + 1).padStart(2, "0");
      const nowLines =
        sameTask && Array.isArray(st.nowLines) && st.nowLines.length > 0
          ? st.nowLines
          : [sameTask ? st.now || t("state.na") : scopeNote];

      setChildren(
        spotlightBox,
        el("div", { className: "eyebrow", text: t("ux.stageFocusEyebrow") }),
        el("div", { className: "task-head" }, [
          el("div", { className: "actions" }, [
            el("b", { className: "spotlight-title", text: `${numStr} · ${stTitle}` }),
            isMixedStageScope || !sameTask
              ? el("span", {
                  className: cls("chip", sameTask ? "" : "neutral"),
                  text: st.task
                    ? t("ux.jobOwnerTag", { owner: st.task })
                    : t("ux.scopeBadgeUnscoped"),
                })
              : null,
            st.scope === "machine" || st.scope === "task"
              ? el("span", {
                  className: cls("chip", "neutral"),
                  text: t(st.scope === "machine" ? "ux.stageScopeMachine" : "ux.stageScopeTask"),
                })
              : null,
          ]),
          renderStateChip(st.state),
        ]),
        ...nowLines.map((line) =>
          el("div", {
            className: cls("spotlight-line", !sameTask && "muted"),
            text: line,
          })
        ),
        sameTask && st.issue
          ? el("div", { className: "sources-note", text: st.issue })
          : !sameTask && (taskProcMissing || taskProcHow)
            ? el("div", {
                className: cls("sources-note", taskProcHow && !taskProcMissing && "mono"),
                text: taskProcMissing || taskProcHow,
              })
            : null,
        st.link && st.link.startsWith("#/")
          ? el("div", { style: "margin-top:4px" }, [
              el("a", { className: "link", href: st.link }, [t("fly.stepOpenWorkspace")]),
            ])
          : null
      );
    };

    const maxStreamEps = Math.max(
      1,
      ...["egocentric", "teleop", "s1", "s2"].map(
        (g) => Number((catTotals[g] && catTotals[g].episodes) || 0)
      )
    );

    const streamGroups = ["egocentric", "teleop", "s1", "s2"].filter(
      (g) => catTotals[g] && catTotals[g].episodes != null
    );

    const taskLabel = curTask ? pickLang(curTask.name) || curTask.id : "";
    const scopeBadge = isMixedStageScope
      ? el("span", {
          className: cls("chip", "warning"),
          text: t("ux.scopeBadgeMixed", { owners: mixedOwnersLabel }),
        })
      : isSingleOtherTask
        ? el("span", {
            className: cls("chip", "neutral"),
            text: t("ux.scopeBadgeServer", { owner: singleOwner }),
          })
        : isAllUnscoped
          ? el("span", {
              className: cls("chip", "neutral"),
              text: t("ux.scopeBadgeUnscoped"),
            })
          : isPureCurrentTask
            ? el("span", {
                className: "chip",
                text: t("ux.scopeBadgeTask", { task: taskLabel }),
              })
            : null;

    const hubCenterTitle = isMixedStageScope
      ? t("ux.hubMixedTitle")
      : isSingleOtherTask
        ? singleOwner
        : isAllUnscoped
          ? t("ux.hubUnscopedTitle")
          : taskLabel || t("app.crumbRoot");
    const hubCenterSub =
      isMixedStageScope && curTask
        ? `${matchedDoneStages}/${matchedStages.length} · ${curTask.id}`
        : `${doneStages}/${stages.length}`;

    const streamColumn = el("div", { className: "stack" }, [
      el("section", { className: "card" }, [
        el("h2", { text: t("fly.streamsTitle") }),
        el("p", { className: cls("tiny", "muted"), text: t("ux.streamSubNote") }),
        streamGroups.length === 0
          ? el("p", { className: "muted", text: t("state.na") })
          : el(
              "div",
              { className: "stream-bars" },
              streamGroups.map((gk) => {
                const item = catTotals[gk] || {};
                const eps = Number(item.episodes || 0);
                const pct = eps <= 0 ? 0 : Math.max(2, Math.min(100, (eps / maxStreamEps) * 100));
                const gLabel = hasI18nKey("cat.group." + gk) ? t("cat.group." + gk) : gk;
                const streamHours =
                  item.hours != null
                    ? `${formatNumber(item.hours, { maximumFractionDigits: 2 })}h`
                    : t("state.na");
                const epLabel = t("tasks.unitEpisodes", { val: formatNumber(eps) });
                return el("div", { className: "stream-row" }, [
                  el("div", { className: "stream-row-head" }, [
                    el("b", { text: gLabel }),
                    el("span", {
                      className: cls("tiny", "mono"),
                      text: `${epLabel} · ${streamHours}`,
                    }),
                  ]),
                  el("div", { className: "stream-track" }, [
                    el("div", { className: "stream-fill", style: `width:${pct.toFixed(1)}%` }),
                  ]),
                ]);
              })
            ),
      ]),
      curRound
        ? el("section", { className: "card" }, [
            el("div", { className: "task-head" }, [
              el("h2", { text: t("fly.roundFlowTitle") }),
              el("a", { className: "link", href: "#/loop" }, [t("nav.item.loop")]),
            ]),
            el(
              "div",
              { className: "meta-strip", style: "margin-top:10px" },
              [
                { label: t("ux.mileBaseline"), value: curRound.baseline || "—", mono: true },
                // a diagnosis summary, never the round id or a file name (content audit A10)
                { label: t("ux.mileDiagnose"), value: diagnosisSummary(scopedStory, jigDoc) },
                {
                  label: t("ux.mileCut"),
                  value: curRound.cut ? compactPath(curRound.cut) : "—",
                  mono: true,
                },
                { label: t("ux.mileAfter"), value: curRound.after_round || "—", mono: true },
              ].map((m) =>
                el("div", { className: "meta-box" }, [
                  el("span", { text: m.label }),
                  el("b", { className: cls(m.mono && "mono"), text: m.value }),
                ])
              )
            ),
          ])
        : null,
      el("section", { className: "card" }, [
        el("div", { className: "grid" }, [
          el("a", { className: "sample-ep-card", href: "#/data" }, [
            el("b", { className: "quick-card-title" }, [icon("data"), t("home.quickData1")]),
            el("span", { className: "tiny", text: t("home.quickData1Sub") }),
          ]),
          el("a", { className: "sample-ep-card", href: "#/eval" }, [
            el("b", { className: "quick-card-title" }, [icon("eval"), t("home.quickExp1")]),
            el("span", { className: "tiny", text: t("home.quickExp1Sub") }),
          ]),
        ]),
      ]),
    ]);

    const orbitalSection =
      stages.length > 0
        ? el("section", { className: "card" }, [
            el("div", { className: "task-head", style: "margin-bottom:8px" }, [
              el("h2", { text: t("home.stageSection") }),
              scopeBadge,
            ]),
            renderStageRing(),
            spotlightBox,
          ])
        : null;

    // The ring is keyboard-operable (arrow keys, Enter) and the spotlight below announces the
    // chosen step, so the six duplicate step buttons under it are dropped (design audit P1-2).
    function renderStageRing() {
      const ringWrap = renderFlywheelOrbitalCanvas({
        stages,
        selectedIdx: selectedStageIdx,
        centerTitle: hubCenterTitle,
        centerSub: hubCenterSub,
        showTaskTag: isMixedStageScope,
        onSelect: (idx) => {
          userSelectedStage = true;
          updateSpotlight(idx);
        },
      });
      const pillBar = ringWrap.querySelector(".stage-pill-bar");
      if (pillBar) pillBar.remove();
      const canvas = ringWrap.querySelector("canvas");
      if (canvas) {
        canvas.setAttribute(
          "aria-label",
          t("ux.stageRingAria", {
            steps: stages
              .map((st, i) => `${i + 1} ${getStageTitle(st)}: ${formatStateLabel(st.state)}`)
              .join("; "),
          })
        );
      }
      return ringWrap;
    }

    const taskReadinessCard =
      isSingleOtherTask && procKeys.length > 0
        ? el("section", { className: "card" }, [
            el("div", { className: "task-head", style: "margin-bottom:10px" }, [
              el("h2", {
                text: t("ux.twoTableChecklistTitle", { count: formatNumber(procKeys.length) }),
              }),
              el("span", {
                className: "chip",
                text: t("ux.scopeBadgeTask", { task: taskLabel }),
              }),
            ]),
            el(
              "div",
              { className: "row-list" },
              procKeys.map((pk, idx) => {
                const pInfo = procMap[pk] || {};
                const pMissing = pickLang(pInfo.missing);
                const pHow = formatHowLine(pInfo.how);
                return el("div", { className: "row" }, [
                  el("div", { className: "row-body" }, [
                    el("div", { className: "task-head" }, [
                      el("b", {
                        text: `${String(idx + 1).padStart(2, "0")} · ${t("proc.stage." + pk)}`,
                      }),
                      renderStateChip(pMissing ? "waiting" : "done"),
                    ]),
                    el("p", {
                      className: cls("muted", !pMissing && pHow && "mono"),
                      text: pMissing || pHow || t("state.na"),
                    }),
                  ]),
                ]);
              })
            ),
          ])
        : null;

    const serverActivityDrawer =
      isSingleOtherTask && orbitalSection
        ? el("details", { className: cls("card", "server-activity-drawer") }, [
            el("summary", {
              text: t("ux.serverActivityToggle", {
                owner: singleOwner,
                done: formatNumber(doneStages),
                total: formatNumber(stages.length),
              }),
            }),
            el("p", {
              className: "muted",
              style: "margin:10px 0",
              text: t("ux.serverActivityHint", { owner: singleOwner, task: taskLabel }),
            }),
            orbitalSection,
          ])
        : null;

    const flywheelBoard =
      stages.length > 0
        ? isSingleOtherTask
          ? el("div", { className: "flywheel-board" }, [
              taskReadinessCard || el("div", {}),
              streamColumn,
            ])
          : el("div", { className: "flywheel-board" }, [orbitalSection, streamColumn])
        : state.statusError
          ? renderErrorBlock(state.statusError, () => {
              getJSON("/api/status").then((doc) => {
                state.statusDoc = doc;
                state.statusLoaded = true;
                state.statusError = null;
                renderContent();
              });
            })
          : state.statusLoaded
            ? el("div", { className: "empty", text: t("state.empty") })
            : el("div", { className: "empty", text: t("state.loading") });

    if (stages.length > 0) {
      updateSpotlight(selectedStageIdx);
    }

    const blockedTaskStage = matchedStages.find((s) =>
      ["blocked", "failed", "reject"].includes(String(s.state || "").toLowerCase())
    );
    const failedJobs = recentJobs.filter(
      (j) => j && String(j.state || "").toLowerCase() === "failed"
    );
    const taskFailedJob = curTask
      ? failedJobs.find((j) => resolveJobOwner(j) === curTask.id) || null
      : null;
    const serverFailedJob =
      failedJobs.find((j) => !curTask || resolveJobOwner(j) !== curTask.id) || null;
    const serverFailedOwner = serverFailedJob ? resolveJobOwner(serverFailedJob) : "";

    const hasTaskIncident = Boolean(blockedTaskStage || taskFailedJob);
    const hasAnyIncident = Boolean(hasTaskIncident || serverFailedJob);

    let taskAttentionBanner = null;
    if (blockedTaskStage) {
      const stState = String(blockedTaskStage.state || "").toLowerCase();
      const tone = stState === "failed" ? "is-danger" : "is-warn";
      const targetHref =
        blockedTaskStage.link && String(blockedTaskStage.link).startsWith("#/")
          ? blockedTaskStage.link
          : taskFailedJob
            ? `#/jobs?job=${encodeURIComponent(taskFailedJob.id)}`
            : "#/jobs";
      const ctaLabel =
        stState === "failed" && targetHref.startsWith("#/jobs")
          ? t("ux.attnInspectJob")
          : t("ux.openBlockedStageBtn");
      taskAttentionBanner = el(
        "div",
        { className: cls("attention-banner", tone), role: "status", "data-alert-scope": "task" },
        [
          el("div", { className: "attention-banner-body" }, [
            taskLabel
              ? el("span", {
                  className: "chip",
                  text: t("ux.scopeBadgeTask", { task: taskLabel }),
                })
              : null,
            el("span", {
              text: t("ux.attnBlocked", {
                stage: getStageTitle(blockedTaskStage),
                reason:
                  blockedTaskStage.issue ||
                  blockedTaskStage.now ||
                  formatStateLabel(blockedTaskStage.state),
              }),
            }),
          ]),
          el("a", { className: cls("btn", "primary"), href: targetHref }, [ctaLabel]),
        ]
      );
    } else if (taskFailedJob) {
      taskAttentionBanner = el(
        "div",
        {
          className: cls("attention-banner", "is-danger"),
          role: "status",
          "data-alert-scope": "task",
        },
        [
          el("div", { className: "attention-banner-body" }, [
            taskLabel
              ? el("span", {
                  className: "chip",
                  text: t("ux.scopeBadgeTask", { task: taskLabel }),
                })
              : null,
            el("span", {
              text: t("ux.attnJobFailed", { kind: taskFailedJob.kind || t("state.na") }),
            }),
          ]),
          el(
            "a",
            {
              className: cls("btn", "primary"),
              href: `#/jobs?job=${encodeURIComponent(taskFailedJob.id)}`,
            },
            [t("ux.attnInspectJob")]
          ),
        ]
      );
    } else if (isMixedStageScope) {
      taskAttentionBanner = el(
        "div",
        {
          className: cls("attention-banner", "is-warn"),
          role: "status",
          "data-alert-scope": "mixed",
        },
        [
          el("div", { className: "attention-banner-body" }, [
            el("span", {
              className: cls("chip", "warning"),
              text: t("ux.scopeBadgeMixed", { owners: mixedOwnersLabel }),
            }),
            el("span", {
              text: t("ux.attnMixedScope", {
                owners: mixedOwnersLabel,
                task: taskLabel || t("app.crumbRoot"),
                done: formatNumber(matchedDoneStages),
                total: formatNumber(matchedStages.length),
              }),
            }),
          ]),
        ]
      );
    } else if (isSingleOtherTask) {
      const epsTxt =
        allTotals.episodes != null
          ? t("tasks.unitEpisodes", { val: formatNumber(allTotals.episodes) })
          : t("state.na");
      taskAttentionBanner = el(
        "div",
        {
          className: "attention-banner",
          role: "status",
          "data-alert-scope": "task-data-only",
        },
        [
          el("div", { className: "attention-banner-body" }, [
            el("span", {
              className: "chip",
              text: t("ux.scopeBadgeTask", { task: taskLabel }),
            }),
            el("div", {}, [
              el("b", {
                text: t("ux.twoTableDataOnlyTitle", {
                  episodes: epsTxt,
                  sets: formatNumber(allTotals.sets ?? 0),
                  hours: hoursText,
                }),
              }),
              el("div", { className: "muted", text: t("ux.twoTableNoServerSub") }),
            ]),
          ]),
        ]
      );
    } else if (isAllUnscoped) {
      taskAttentionBanner = el(
        "div",
        {
          className: cls("attention-banner", "is-warn"),
          role: "status",
          "data-alert-scope": "unscoped",
        },
        [
          el("div", { className: "attention-banner-body" }, [
            el("span", {
              className: cls("chip", "neutral"),
              text: t("ux.scopeBadgeUnscoped"),
            }),
            el("span", { text: t("ux.attnUnscopedStages") }),
          ]),
        ]
      );
    } else if (isPureCurrentTask && stages.length > 0) {
      const runningStage = stages.find((s) =>
        ["running", "queued"].includes(String((s && s.state) || "").toLowerCase())
      );
      const evalStage = stages.find((s) => s && s.id === "eval");
      const trainStage = stages.find((s) => s && s.id === "train");
      const fallbackEvalLine = evalStage && evalStage.now ? evalStage.now : t("state.na");
      const jigHead = jigEval && jigEval.headline ? jigEval.headline : null;
      // W1: counts of successful rollouts read "lượt thành công", with the share and "sơ bộ"
      const succLine = (run, succ, n) =>
        t("ux.homeEvalSuccLine", {
          run,
          succ: formatNumber(succ),
          n: formatNumber(n),
          pct: Number(n) > 0 ? formatPercent(Number(succ) / Number(n)) : t("state.na"),
        });
      const bestEvalText = jigDoc
        ? jigEval && jigEval.status === "ready" && jigHead
          ? succLine(jigEval.run, jigHead.successes, jigHead.n)
          : jigEval && jigEval.status === "blocked"
            ? t("ux.homeJigEvalBlocked", { run: jigEval.run })
            : t("exp.evalMissing", { run: jigRunId || "-" })
        : pairBest
          ? succLine(pairBest.run, pairBest.successes, pairBest.n)
          : fallbackEvalLine;
      const bestEvalSub = jigDoc
        ? jigEval && jigEval.status === "ready"
          ? jigReadingLines(jigEval).join(" · ")
          : jigEval && jigEval.status === "missing"
            ? t("ux.homeJigEvalMissingSub")
            : ""
        : "";
      const withheldNote =
        withheldList.length > 0
          ? t("ux.homeEvalWithheldNote")
          : "";
      // "running" only for a live record: state running and not marked stale by the index
      // (an 11/11 batch record still said running on 28/11; managing session, 28/11 evening)
      const activeColabList = (
        jigDoc && Array.isArray(jigDoc.active_sessions) ? jigDoc.active_sessions : []
      ).filter(isLiveSession);
      const colabSuffix =
        activeColabList.length > 0
          ? t("ux.homeColabActive", {
              session: activeColabList[0].session || "",
              gpu: activeColabList[0].gpu || "GPU",
            })
          : "";

      taskAttentionBanner = el(
        "div",
        {
          className: cls(
            "attention-banner",
            runningStage ? "is-warn" : "is-ok",
            "outcome-decision-strip"
          ),
          role: "status",
          "data-alert-scope": "task",
        },
        [
          el("div", { className: "outcome-col" }, [
            el("div", { className: "actions" }, [
              el("span", {
                className: "chip",
                text: t("ux.scopeBadgeTask", { task: taskLabel }),
              }),
              el("span", { className: "eyebrow", text: t("ux.homeProcessDoneLabel") }),
            ]),
            el("b", {
              style: "font-size:15px",
              text: runningStage
                ? t("ux.homeProcessRunningVal", {
                    stage: getStageTitle(runningStage),
                    done: formatNumber(doneStages),
                    total: formatNumber(stages.length),
                  })
                : t("ux.homeProcessDoneVal", {
                    done: formatNumber(doneStages),
                    total: formatNumber(stages.length),
                  }),
            }),
            // the round's own train line; the server's machine-wide line is not repeated here,
            // and the jig round shows its run in the third column
            trainStage && trainStage.now && trainStage.scope === "round" && !jigDoc
              ? el("div", { className: "tiny", text: trainStage.now })
              : null,
          ]),
          el("div", { className: "outcome-col" }, [
            el("span", { className: "eyebrow", text: t("ux.homeEvalBestLabel") }),
            el("div", { className: "actions" }, [
              el("b", { style: "font-size:15px", text: bestEvalText }),
              el("a", { className: "link", href: "#/eval" }, [t("nav.item.eval")]),
            ]),
            bestEvalSub ? el("div", { className: "tiny", text: bestEvalSub }) : null,
            withheldNote ? el("div", { className: "tiny", text: withheldNote }) : null,
          ]),
          jigTrain
            ? el("div", { className: "outcome-col" }, [
                el("span", { className: "eyebrow", text: t("ux.homeJigLatestLabel") }),
                el("div", { className: "actions" }, [
                  el("b", {
                    style: "font-size:15px",
                    text: t("ux.homeJigTrainVal", {
                      run: jigTrain.branch,
                      step: formatNumber(jigTrain.ckpt_step || jigTrain.step),
                      max: formatNumber(jigTrain.max_steps),
                    }),
                  }),
                  el("a", { className: "link", href: "#/runs" }, [t("nav.item.runs")]),
                ]),
                el("div", {
                  className: "tiny",
                  text: [
                    jigTrain.loss_last != null
                      ? t("ux.homeJigLossSub", {
                          loss: formatNumber(jigTrain.loss_last, { maximumFractionDigits: 3 }),
                        })
                      : "",
                    colabSuffix.replace(/^ · /, ""),
                  ]
                    .filter(Boolean)
                    .join(" · "),
                }),
              ])
            : null,
        ]
      );
    }

    const serverIncidentBanner = serverFailedJob
      ? el(
          "div",
          {
            className: cls("attention-banner", "is-server"),
            role: "status",
            "data-alert-scope": "server",
          },
          [
            el("div", { className: "attention-banner-body" }, [
              el("span", {
                className: cls("chip", "warning"),
                text: serverFailedOwner
                  ? t("ux.serverEventScopeOther", { owner: serverFailedOwner })
                  : t("ux.serverEventScopeLocal"),
              }),
              el("span", {
                text: serverFailedOwner
                  ? t("ux.serverJobFailedOther", {
                      kind: serverFailedJob.kind || t("state.na"),
                      owner: serverFailedOwner,
                      task: taskLabel || t("app.crumbRoot"),
                    })
                  : t("ux.serverJobFailedLocal", {
                      kind: serverFailedJob.kind || t("state.na"),
                      task: taskLabel || t("app.crumbRoot"),
                    }),
              }),
            ]),
            el(
              "a",
              {
                className: cls("btn", !hasTaskIncident && "primary"),
                href: `#/jobs?job=${encodeURIComponent(serverFailedJob.id)}`,
              },
              [t("ux.attnInspectJob")]
            ),
          ]
        )
      : null;

    const pageTitle = curTask ? taskLabel : t("home.title");
    const pageLead =
      [
        curTask && curTask.robot,
        curTask && curTask.model,
        curRound && (pickLang(curRound.title) || curRound.id),
      ]
        .filter(Boolean)
        .join(" · ") || t("home.lead");

    // Third tile: the selected round's evaluation size, read from the scoped story; the local
    // job slots only when the round has no evaluation. No gateway or model name (Q3, P0-8).
    const roundEvalTile = (() => {
      const h = jigEval && jigEval.headline ? jigEval.headline : null;
      if (jigDoc && jigEval && jigEval.status === "ready" && h) {
        return {
          label: t("ux.homeRoundEvalLabel"),
          value: t("ux.homeRolloutsVal", { n: formatNumber(h.n) }),
          sub:
            h.conditions != null
              ? t("ux.homeRolloutsSubCond", {
                  runs: formatNumber(1),
                  conditions: formatNumber(h.conditions),
                })
              : t("ux.homeRolloutsSub", { runs: formatNumber(1) }),
        };
      }
      const counted = jigDoc ? [] : pairRuns.filter((r) => r && Number(r.n) > 0);
      if (counted.length > 0) {
        return {
          label: t("ux.homeRoundEvalLabel"),
          value: t("ux.homeRolloutsVal", {
            n: formatNumber(counted.reduce((sum, r) => sum + Number(r.n), 0)),
          }),
          sub: t("ux.homeRolloutsSub", { runs: formatNumber(counted.length) }),
        };
      }
      const laptop = statusDoc.machines && statusDoc.machines.laptop;
      return {
        label: t("ux.homeLocalSlots"),
        value: laptop
          ? t("ux.slotUsage", {
              used: formatNumber(laptop.running_jobs),
              total: formatNumber(laptop.slots),
            })
          : t("state.na"),
        sub: "",
      };
    })();

    const preferReportCta = Boolean(
      !hasAnyIncident &&
        (curRound || (isPureCurrentTask && stages.length > 0 && doneStages === stages.length))
    );
    const preferDataCta = Boolean(!hasAnyIncident && !preferReportCta);

    setChildren(
      wrap,
      ...renderCrumbHeading({
        crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("nav.item.home") }],
        title: pageTitle,
        lead: pageLead,
        actions: [
          el("a", { className: cls("btn", preferReportCta && "primary"), href: "#/report" }, [
            t("home.btnReport"),
          ]),
          el("a", { className: cls("btn", preferDataCta && "primary"), href: "#/data" }, [
            t("home.btnData"),
          ]),
        ],
      }),

      // the header badge already says the server is locked (design audit P1-14)
      connMarker,

      taskAttentionBanner,

      renderStatStrip([
        {
          label: t("ux.homeDataOfTask"),
          value:
            allTotals.episodes != null
              ? t("tasks.unitEpisodes", { val: formatNumber(allTotals.episodes) })
              : t("state.na"),
          sub: t("tasks.statDataSub", {
            sets: formatNumber(allTotals.sets),
            hours: hoursText,
          }),
        },
        {
          label: t("header.roundLabel"),
          value: curRound ? curRound.id : t("header.noRounds"),
          sub: curRound ? pickLang(curRound.title) : "",
        },
        roundEvalTile,
      ]),

      renderRoundLinks(curRound),

      serverIncidentBanner,

      flywheelBoard,

      serverActivityDrawer,

      renderTimeline(state.storyRawDoc),

      el("section", { className: cls("card", "table-wrap") }, [
        el("div", { className: "task-head", style: "margin-bottom:8px" }, [
          el("div", { className: "actions" }, [
            el("h2", { text: t("home.recentJobs") }),
            el("span", { className: cls("chip", "neutral"), text: t("ux.recentJobsScope") }),
          ]),
          el("a", { className: "link", href: "#/jobs" }, [t("home.viewAllJobs")]),
        ]),
        recentJobs.length === 0
          ? el("div", { className: "empty", text: t("state.empty") })
          : el("table", { className: "table" }, [
              el("thead", {}, [
                el("tr", {}, [
                  el("th", { text: t("jobs.colKind") }),
                  el("th", { text: t("jobs.colState") }),
                  el("th", { text: t("common.time") }),
                  el("th", { text: t("jobs.colStage") }),
                  el("th", { text: t("jobs.colId") }),
                  el("th", { text: "" }),
                ]),
              ]),
              el(
                "tbody",
                {},
                recentJobs.slice(0, 6).map((j) => {
                  const shortId = shortHashId(j.id);
                  const copyBtn = el(
                    "button",
                    {
                      type: "button",
                      className: cls("short-hash", "mono"),
                      title: t("ux.copyIdTitle"),
                      onClick: () => {
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                          navigator.clipboard.writeText(String(j.id || "")).catch(() => {});
                        }
                        copyBtn.textContent = t("chat.copiedBtn");
                        window.setTimeout(() => {
                          copyBtn.textContent = shortId;
                        }, 1200);
                      },
                    },
                    [shortId]
                  );
                  const jobOwner = resolveJobOwner(j);
                  const ownerBadge = jobOwner
                    ? el("span", {
                        className: cls(
                          "chip",
                          curTask && jobOwner === curTask.id ? "" : "neutral"
                        ),
                        text: t("ux.jobOwnerTag", { owner: jobOwner }),
                      })
                    : null;
                  return el("tr", {}, [
                    el("td", {}, [jobKindCell(j.kind, ownerBadge)]),
                    el("td", {}, [renderStateChip(j.state)]),
                    el("td", { text: formatDateTime(j.created) }),
                    el("td", { text: jobStageLabel(j.stage) }),
                    el("td", {}, [copyBtn]),
                    el("td", { style: "white-space:nowrap" }, [
                      el(
                        "a",
                        {
                          className: "link",
                          href: `#/jobs?job=${encodeURIComponent(j.id)}`,
                          "aria-label": t("ux.viewJobAria", {
                            kind: j.kind || "",
                            id: shortId,
                          }),
                        },
                        [t("common.view")]
                      ),
                    ]),
                  ]);
                })
              ),
            ]),
      ]),

      procKeys.length > 0
        ? el("details", { className: "studio-details", style: "margin-top:12px" }, [
            el("summary", {
              text: t("fly.techDetailsToggle", { count: formatNumber(procKeys.length) }),
            }),
            el(
              "div",
              { className: "grid", style: "margin-top:10px" },
              procKeys.map((n) => {
                const p = procMap[n] || {};
                const missing = pickLang(p.missing);
                const howLine = formatHowLine(p.how);
                return el("article", { className: "card" }, [
                  el("div", { className: "task-head" }, [
                    el("h3", { text: t("proc.stage." + n) }),
                    p.remote
                      ? el("span", { className: cls("chip", "neutral"), text: p.remote })
                      : null,
                  ]),
                  missing
                    ? el("div", { className: "missing-item", text: missing })
                    : el("p", { className: "muted", text: t("home.noMissingHint") }),
                  howLine ? el("p", { className: cls("sources-note", "mono"), text: howLine }) : null,
                ]);
              })
            ),
          ])
        : null
    );
  };

  if (!state.modelsDoc) {
    ensureModels(false).then(() => {
      if (!disposed && state.modelsDoc) renderContent();
    });
  }
  if (!state.storyRawDoc) {
    ensureStoryRaw()
      .then(() => {
        if (!disposed && state.storyRawDoc) renderContent();
      })
      .catch(() => {});
  }
  if (!state.kindsDoc) {
    ensureKinds(false)
      .then(() => {
        if (!disposed && state.kindsDoc) renderContent();
      })
      .catch(() => {});
  }

  // A failed poll shows a small "connection lost" marker instead of silently keeping the old
  // state; the next successful poll removes it (stability audit S-P2-15).
  statusPollTimer = window.setInterval(() => {
    if (disposed || document.hidden) return;
    tryGetJSON("/api/status")
      .then((res) => {
        if (disposed) return;
        if (res.ok && res.data) {
          connMarker.hidden = true;
          state.statusDoc = res.data;
          state.statusLoaded = true;
          renderContent();
        } else {
          connMarker.hidden = false;
        }
      })
      .catch(() => {
        if (!disposed) connMarker.hidden = false;
      });
  }, 15000);

  renderContent();
  return wrap;
}

// ============================================================================
// Dynamic Kind Runner Form Builder (from /api/kinds)
// ============================================================================
function buildKindRunnerCard(kindSpec, onCreated) {
  const samples = Array.isArray(kindSpec.samples) ? kindSpec.samples : [];
  const args = Array.isArray(kindSpec.args) ? kindSpec.args : [];
  const inputsByArg = new Map();

  const sampleSelect =
    samples.length > 0
      ? el(
          "select",
          {
            className: "field",
            onChange: (ev) => {
              const idx = Number(ev.target.value);
              if (Number.isNaN(idx) || idx < 0 || !samples[idx]) return;
              const smp = samples[idx].params || {};
              for (const [argName, ctrl] of inputsByArg.entries()) {
                if (Object.prototype.hasOwnProperty.call(smp, argName)) {
                  if (ctrl.type === "checkbox") {
                    ctrl.checked = Boolean(smp[argName]);
                  } else if (Array.isArray(smp[argName])) {
                    ctrl.value = smp[argName].join("\n");
                  } else {
                    ctrl.value = String(smp[argName] ?? "");
                  }
                }
              }
            },
          },
          [
            el("option", { value: "-1", text: t("jobs.sampleCustom") }),
            ...samples.map((smp, idx) =>
              el("option", {
                value: String(idx),
                disabled: !smp.available,
                text: `${pickLang(smp.label)}${!smp.available && smp.reason ? ` (${pickLang(smp.reason)})` : ""}`,
              })
            ),
          ]
        )
      : null;

  const argFields = args.map((arg) => {
    let ctrl;
    if (arg.type === "enum" && Array.isArray(arg.choices)) {
      ctrl = el(
        "select",
        { className: "field" },
        arg.choices.map((ch) =>
          el("option", {
            value: ch,
            selected: arg.default === ch,
            text: ch,
          })
        )
      );
    } else if (arg.type === "bool") {
      ctrl = el("input", {
        type: "checkbox",
        checked: Boolean(arg.default),
      });
    } else if (arg.type === "int") {
      ctrl = el("input", {
        type: "number",
        className: "field",
        value: arg.default != null ? String(arg.default) : "",
      });
    } else if (arg.type === "list[path]" || arg.type === "list[object]") {
      ctrl = el("textarea", {
        className: cls("field", "mono"),
        rows: "2",
      });
    } else {
      ctrl = el("input", {
        type: "text",
        className: cls("field", "mono"),
        value: arg.default != null ? String(arg.default) : "",
      });
    }
    inputsByArg.set(arg.name, ctrl);
    return el("div", { className: "form-field" }, [
      el("label", {}, [
        el("span", { className: "mono", text: arg.name }),
        arg.required ? " *" : "",
      ]),
      ctrl,
      el("small", { text: pickLang(arg.help) }),
    ]);
  });

  const firstAvail = samples.findIndex((s) => s.available);
  if (sampleSelect && firstAvail >= 0) {
    sampleSelect.value = String(firstAvail);
    sampleSelect.dispatchEvent(new Event("change"));
  }

  const msgNode = el("div", { className: "sources-note", hidden: true });
  const submitBtn =
    !state.locked && kindSpec.available
      ? el(
          "button",
          {
            type: "button",
            className: cls("btn", "primary"),
            onClick: async () => {
              const params = {};
              for (const arg of args) {
                const ctrl = inputsByArg.get(arg.name);
                if (!ctrl) continue;
                if (arg.type === "bool") {
                  params[arg.name] = Boolean(ctrl.checked);
                } else if (arg.type === "int") {
                  if (ctrl.value !== "") params[arg.name] = Number(ctrl.value);
                } else if (arg.type === "list[path]") {
                  const items = ctrl.value
                    .split(/[\n,]+/)
                    .map((s) => s.trim())
                    .filter(Boolean);
                  if (items.length) params[arg.name] = items;
                } else if (arg.type === "list[object]") {
                  if (ctrl.value.trim()) {
                    try {
                      params[arg.name] = JSON.parse(ctrl.value);
                    } catch {
                      params[arg.name] = [];
                    }
                  }
                } else if (ctrl.value.trim() !== "") {
                  params[arg.name] = ctrl.value.trim();
                }
              }
              submitBtn.disabled = true;
              msgNode.hidden = true;
              try {
                const created = await postJSON("/api/jobs", {
                  kind: kindSpec.kind,
                  params,
                });
                if (onCreated) onCreated(created);
              } catch (err) {
                msgNode.textContent = err.serverMessage || err.message;
                msgNode.hidden = false;
              } finally {
                submitBtn.disabled = false;
              }
            },
          },
          [t("jobs.runKindBtn")]
        )
      : null;

  // A locked server shows a neutral "Chỉ đọc" chip, not a red blocked chip with the CLI flag in
  // the reason (design audit P1-14); command, raw fields and outputs fold into "Nâng cao" (P1-12).
  const stateChip = state.locked
    ? el("span", { className: cls("chip", "neutral"), text: t("ux.readOnlyChip") })
    : kindSpec.available
      ? el("span", { className: "chip", text: t("ux.kindReadyChip") })
      : renderStateChip("blocked");
  const canRun = !state.locked && kindSpec.available;
  return el("article", { className: "card" }, [
    el("div", { className: "task-head" }, [
      el("h3", { title: kindSpec.kind || null, text: pickLang(kindSpec.title) || kindSpec.kind }),
      el("div", { className: "actions" }, [
        kindSpec.typical_seconds != null
          ? el("span", {
              className: cls("chip", "neutral"),
              text: t("ux.secondsApprox", { val: formatNumber(kindSpec.typical_seconds) }),
            })
          : null,
        stateChip,
      ]),
    ]),
    !state.locked && !kindSpec.available && kindSpec.reason
      ? el("p", { className: "muted", text: pickLang(kindSpec.reason) })
      : null,
    canRun
      ? el("div", {}, [
          sampleSelect
            ? el("div", { className: "form-field" }, [
                el("label", { text: t("jobs.sampleLabel") }),
                sampleSelect,
              ])
            : null,
          el("div", { className: "actions" }, [submitBtn]),
          msgNode,
        ])
      : null,
    advancedBlock([
      canRun && argFields.length > 0 ? el("div", { className: "form-grid" }, argFields) : null,
      kindSpec.command
        ? el("pre", { className: cls("log-box", "mono"), text: scrubPath(kindSpec.command) })
        : null,
      kindSpec.outputs
        ? el("p", { className: cls("muted", "mono"), text: scrubPath(pickLang(kindSpec.outputs)) })
        : null,
    ]),
  ]);
}

// ============================================================================
// #/jobs — Jobs, Machines, Pipeline, Import & Export
// ============================================================================
export function renderJobsPage(ctx) {
  const wrap = el("div", {});
  const q = ctx.query;
  const panel = q.get("panel");
  const view = q.get("view");
  const focusJobId = q.get("job");

  let activeTab = "all";
  if (panel === "import") activeTab = "import";
  else if (panel === "export") activeTab = "export";
  else if (view === "pipeline") activeTab = "pipeline";
  else if (view === "machines") activeTab = "machines";

  const tabHref = (tab) => {
    if (tab === "pipeline") return "#/jobs?view=pipeline";
    if (tab === "import") return "#/jobs?panel=import";
    if (tab === "export") return "#/jobs?panel=export";
    if (tab === "machines") return "#/jobs?view=machines";
    return "#/jobs";
  };

  wrap.appendChild(renderLoadingView(t("jobs.title")));

  let pollTimer = null;
  onRouteCleanup(() => {
    if (pollTimer) window.clearInterval(pollTimer);
  });

  const loadAndRender = async () => {
    const tabBar = el(
      "nav",
      { className: "tabs" },
      JOB_TABS.map((tb) =>
        el(
          "a",
          {
            href: tabHref(tb),
            className: cls("tab", activeTab === tb && "active"),
          },
          [t("jobs.tab." + tb)]
        )
      )
    );

    const headerNodes = [
      ...renderCrumbHeading({
        crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("jobs.title") }],
        title: activeTab === "all" ? t("jobs.title") : t("jobs.tab." + activeTab),
      }),
      tabBar,
    ];

    try {
      if (activeTab === "all") {
        const jobs = await getJSON("/api/jobs?limit=100");
        const selectedId = focusJobId;
        let detailCard = null;

        if (selectedId) {
          setSelection({ job_id: selectedId }, true);
          const jRes = await tryGetJSON(`/api/jobs/${encodeURIComponent(selectedId)}`);
          if (jRes.ok && jRes.data) {
            const job = jRes.data;
            const logPre = el("pre", { className: cls("log-box", "mono"), text: "" });
            const stateHolder = el("span", {}, [renderStateChip(job.state)]);
            let logOffset = 0;

            const pullLog = async () => {
              const lRes = await tryGetJSON(
                `/api/jobs/${encodeURIComponent(job.id)}/log?offset=${logOffset}`
              );
              if (!lRes.ok || !lRes.data) return;
              if (lRes.data.text) {
                logPre.textContent += cleanLogLines(lRes.data.text).join("\n");
              }
              logOffset = lRes.data.offset || logOffset;
              setChildren(stateHolder, renderStateChip(lRes.data.state));
              if (lRes.data.state !== "queued" && lRes.data.state !== "running" && pollTimer) {
                window.clearInterval(pollTimer);
                pollTimer = null;
              }
            };

            await pullLog();
            if (job.state === "queued" || job.state === "running") {
              pollTimer = window.setInterval(pullLog, 1000);
            }

            const cancelBtn =
              !state.locked && (job.state === "queued" || job.state === "running")
                ? el(
                    "button",
                    {
                      type: "button",
                      className: cls("btn", "danger"),
                      onClick: async () => {
                        await postJSON(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, {});
                        loadAndRender();
                      },
                    },
                    [t("jobs.cancelBtn")]
                  )
                : null;

            const outEntries = Object.entries(job.outputs || {});
            const { label: jobTitleLabel } = formatJobKindLabel(job.kind);
            detailCard = el("section", { className: "card" }, [
              el("div", { className: "task-head" }, [
                el("div", { title: job.kind || null }, [
                  el("h2", { text: `${jobTitleLabel} · ${shortHashId(job.id)}` }),
                  el("div", { className: "tiny", text: formatDateTime(job.created) }),
                ]),
                el("div", { className: "actions" }, [stateHolder, cancelBtn]),
              ]),
              // raw outputs and the command line stay one click away (design audit P1-12)
              advancedBlock([
                outEntries.length > 0
                  ? el(
                      "div",
                      { className: "meta-strip" },
                      outEntries.map(([k, v]) => {
                        const fullStr = typeof v === "object" ? JSON.stringify(v) : String(v);
                        return el("div", { className: "meta-box", title: scrubPath(fullStr) }, [
                          el("span", { text: k }),
                          el("b", {
                            className: cls("mono", "ops-raw-value"),
                            text: fullStr.includes("/") ? compactPath(fullStr) : fullStr,
                          }),
                        ]);
                      })
                    )
                  : null,
                job.argv && job.argv.length > 0
                  ? el("div", {}, [
                      el("b", { className: "tiny", text: t("fly.cliToggle") }),
                      el("pre", {
                        className: cls("log-box", "mono"),
                        text: scrubPath(job.argv.join(" ")),
                      }),
                    ])
                  : null,
              ]),
              el("div", { className: "sect" }, [el("h3", { text: t("jobs.logTitle") })]),
              logPre,
            ]);
          } else if (jRes.error) {
            detailCard = renderErrorBlock(jRes.error, loadAndRender);
          }
        }

        const status = q.get("status") || "";
        const statuses = Array.from(new Set(jobs.map((job) => job.state).filter(Boolean)));
        const filtered = status ? jobs.filter((job) => job.state === status) : jobs;
        const pages = Math.max(1, Math.ceil(filtered.length / 20));
        const page = Math.max(1, Math.min(pages, parseInt(q.get("page"), 10) || 1));
        const jobsHref = (nextPage, nextStatus, id) => {
          const params = new URLSearchParams();
          if (nextPage > 1) params.set("page", String(nextPage));
          if (nextStatus) params.set("status", nextStatus);
          if (id) params.set("job", id);
          return params.size ? `#/jobs?${params}` : "#/jobs";
        };
        const filterBar = el("div", { className: "toolbar" }, [
          el("select", { className: "field", "aria-label": t("jobs.colState"),
            onChange: (ev) => { window.location.hash = jobsHref(1, ev.target.value); } }, [
            el("option", { value: "", text: t("common.all") }),
            ...statuses.map((st) => el("option", { value: st, selected: st === status, text: formatStateLabel(st) })),
          ]),
          page > 1 ? el("a", { className: "btn", href: jobsHref(page - 1, status), text: t("analysis.prev") }) : null,
          el("span", { text: t("analysis.jobsPage", { page, pages, total: filtered.length }) }),
          page < pages ? el("a", { className: "btn", href: jobsHref(page + 1, status), text: t("analysis.next") }) : null,
        ]);
        const tableCard =
          filtered.length === 0
            ? el("div", { className: "empty", text: t("state.empty") })
            : el("div", { className: cls("card", "table-wrap") }, [
                el("table", { className: "table" }, [
                  el("thead", {}, [
                    el("tr", {}, [
                      el("th", { text: t("jobs.colKind") }),
                      el("th", { text: t("jobs.colState") }),
                      el("th", { text: t("common.time") }),
                      el("th", { text: t("jobs.colStage") }),
                      el("th", { className: "num", text: t("jobs.colDuration") }),
                      el("th", { text: t("jobs.colId") }),
                    ]),
                  ]),
                  el(
                    "tbody",
                    {},
                    filtered.slice((page - 1) * 20, page * 20).map((j) =>
                      el("tr", {}, [
                        el("td", {}, [jobKindCell(j.kind)]),
                        el("td", {}, [renderStateChip(j.state)]),
                        el("td", { text: formatDateTime(j.created) }),
                        el("td", { text: jobStageLabel(j.stage) }),
                        el("td", {
                          className: "num",
                          text:
                            j.seconds != null
                              ? t("ux.seconds", {
                                  val: formatNumber(j.seconds, { maximumFractionDigits: 1 }),
                                })
                              : t("state.na"),
                        }),
                        el("td", {}, [
                          el(
                            "a",
                            {
                              className: cls("link", "mono"),
                              href: jobsHref(page, status, j.id),
                            },
                            [shortHashId(j.id)]
                          ),
                        ]),
                      ])
                    )
                  ),
                ]),
              ]);

        setChildren(wrap, ...headerNodes, detailCard, filterBar, tableCard);
        return;
      }

      if (activeTab === "pipeline") {
        const kindsDoc = await ensureKinds(true);
        const kinds = Array.isArray(kindsDoc.kinds) ? kindsDoc.kinds : [];
        const remote = Array.isArray(kindsDoc.remote) ? kindsDoc.remote : [];

        const forms = new Map();
        const selectedForm = el("div", { className: "pipeline-selected" });
        const selectKind = (kind) => {
          if (!forms.has(kind)) {
            forms.set(kind, buildKindRunnerCard(kind, (job) => {
              window.location.hash = `#/jobs?job=${encodeURIComponent(job.id)}`;
            }));
          }
          setChildren(selectedForm, forms.get(kind));
        };
        if (kinds.length) selectKind(kinds[0]);
        setChildren(
          wrap,
          ...headerNodes,
          kinds.length ? el("label", { className: "analysis-picker" }, [
            t("jobs.colKind"),
            el("select", { className: "field", onChange: (event) => selectKind(kinds[event.target.selectedIndex]) },
              kinds.map((kind) => el("option", { text: pickLang(kind.title) || kind.kind }))),
          ]) : el("div", { className: "empty", text: t("state.empty") }),
          selectedForm,
          remote.length > 0
            ? el("div", {}, [
                el("div", { className: "sect" }, [el("h2", { text: t("jobs.remoteSection") })]),
                el(
                  "div",
                  { className: "grid" },
                  remote.map((rm) =>
                    el("article", { className: "card" }, [
                      el("div", { className: "task-head" }, [
                        el("h3", { text: pickLang(rm.title) || rm.id }),
                        el("span", { className: cls("chip", "neutral"), text: pickLang(rm.where) }),
                      ]),
                      el("p", { className: "muted", text: pickLang(rm.why) }),
                      advancedBlock([
                        rm.observe
                          ? el("p", {
                              className: "sources-note",
                              text: scrubPath(pickLang(rm.observe)),
                            })
                          : null,
                      ]),
                    ])
                  )
                ),
              ])
            : null
        );
        return;
      }

      if (activeTab === "import") {
        const kindsDoc = await ensureKinds();
        const ingestKinds = (kindsDoc.kinds || []).filter(
          (k) => k.kind === "data.ingest" || k.kind === "ego.ingest"
        );

        let uploadCard = null;
        let fsCard = null;

        if (!state.locked) {
          const now = new Date();
          const pad = (n) => String(n).padStart(2, "0");
          const defaultBatch = `upload-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
          const dirInput = el("input", {
            type: "text",
            className: cls("field", "mono"),
            value: defaultBatch,
          });
          const filePreview = el("ul", { className: "upload-preview", "aria-live": "polite" });
          const fileInput = el("input", {
            type: "file",
            className: "field",
            accept: ".mp4,.mov,.mkv,.avi,.webm,video/*",
            multiple: true,
            onChange: (event) => {
              setChildren(filePreview, ...Array.from(event.target.files || [], (file) =>
                el("li", {}, [
                  el("span", { text: file.name }),
                  el("small", { text: formatBytes(file.size) }),
                ])
              ));
            },
          });
          const uploadLog = el("div", { className: "stack" });

          uploadCard = el("section", { className: "card" }, [
            el("h2", { text: t("jobs.uploadTitle") }),
            el("div", { className: "form-field" }, [
              el("label", { text: t("nav.item.egoflow") }),
              fileInput,
              filePreview,
            ]),
            advancedBlock([
              el("div", { className: "form-field" }, [
                el("label", { text: t("jobs.uploadDirLabel") }),
                dirInput,
              ]),
            ]),
            el("div", { className: "actions" }, [
              el(
                "button",
                {
                  type: "button",
                  className: cls("btn", "primary"),
                  onClick: async () => {
                    const files = Array.from(fileInput.files || []);
                    for (const f of files) {
                      const res = await uploadVideoFile(
                        dirInput.value.trim(),
                        state.taskId || "tray",
                        f
                      );
                      uploadLog.appendChild(
                        el("div", {
                          className: cls("sources-note", "mono"),
                          text: t("jobs.uploadSuccess", {
                            name: res.name,
                            saved: res.saved,
                            size: formatBytes(res.size),
                          }),
                        })
                      );
                    }
                  },
                },
                [t("jobs.uploadBtn")]
              ),
            ]),
            uploadLog,
          ]);

          const fsBox = el("div", { className: "fs-browser" });
          const checkOut = el("p", { className: cls("sources-note", "mono") });
          const loadFs = async (targetPath = "") => {
            const url = targetPath
              ? `/api/fs?path=${encodeURIComponent(targetPath)}`
              : "/api/fs";
            const data = await getJSON(url);
            setChildren(
              fsBox,
              el("div", { className: "task-head" }, [
                el("b", { className: "mono", text: scrubPath(data.path) }),
                el("div", { className: "actions" }, [
                  data.parent
                    ? el(
                        "button",
                        {
                          type: "button",
                          className: "topbtn",
                          onClick: () => loadFs(data.parent),
                        },
                        [t("jobs.fsParentBtn")]
                      )
                    : null,
                  el(
                    "button",
                    {
                      type: "button",
                      className: "btn",
                      onClick: async () => {
                        const chk = await getJSON(
                          `/api/dir_check?path=${encodeURIComponent(data.path)}`
                        );
                        checkOut.textContent = t("ux.fsCheckResult", {
                          device: chk.has_device ? t("ux.yes") : t("ux.no"),
                          tasks: (chk.tasks || []).join(", ") || "—",
                        });
                      },
                    },
                    [t("jobs.fsCheckBtn")]
                  ),
                ]),
              ]),
              el(
                "div",
                { className: "fs-dirs" },
                (data.dirs || []).map((d) =>
                  el(
                    "button",
                    {
                      type: "button",
                      className: cls("topbtn", "fs-dir-btn"),
                      onClick: () => loadFs(d.path),
                    },
                    [icon("folder"), d.name]
                  )
                )
              ),
              checkOut
            );
          };

          fsCard = el("section", { className: "card" }, [
            el("div", { className: "task-head" }, [
              el("h3", { text: t("jobs.fsTitle") }),
              el(
                "button",
                {
                  type: "button",
                  className: "btn",
                  onClick: () => loadFs(""),
                },
                [t("common.open")]
              ),
            ]),
            fsBox,
          ]);
        }

        setChildren(
          wrap,
          ...headerNodes,
          uploadCard,
          el(
            "div",
            { className: "stack" },
            ingestKinds.map((k) =>
              buildKindRunnerCard(k, (created) => {
                window.location.hash = `#/jobs?job=${encodeURIComponent(created.id)}`;
              })
            )
          ),
          // the source-folder browser is a raw tool: folded under "Nâng cao" (P1-12)
          fsCard
            ? advancedBlock([fsCard], t("ux.advancedNamed", { name: t("jobs.fsTitle") }))
            : null
        );
        return;
      }

      if (activeTab === "export") {
        const [exportsList, kindsDoc] = await Promise.all([
          getJSON("/api/exports"),
          ensureKinds(),
        ]);
        const exportKinds = (kindsDoc.kinds || []).filter(
          (k) => k.kind === "export.zip" || k.kind === "ego.human1m"
        );

        setChildren(
          wrap,
          ...headerNodes,
          el("section", { className: cls("card", "table-wrap") }, [
            el("h2", { text: t("jobs.exportsTitle") }),
            !Array.isArray(exportsList) || exportsList.length === 0
              ? el("p", { className: "muted", text: t("state.empty") })
              : el("table", { className: "table" }, [
                  el("thead", {}, [
                    el("tr", {}, [
                      el("th", { text: t("common.id") }),
                      el("th", { text: t("jobs.colKind") }),
                      el("th", { className: "num", text: t("common.size") }),
                      el("th", { text: t("common.time") }),
                      el("th", { text: "" }),
                    ]),
                  ]),
                  el(
                    "tbody",
                    {},
                    exportsList.map((ex) =>
                      el("tr", {}, [
                        el("td", { className: "mono", text: ex.name }),
                        el("td", { text: ex.kind || "zip" }),
                        el("td", { className: "num", text: formatBytes(ex.size) }),
                        el("td", { text: formatDateTime(ex.time) }),
                        el("td", {}, [
                          !state.locked && ex.url && String(ex.url).startsWith("/api/exports/")
                            ? el("a", { className: "link", href: ex.url, download: ex.name }, [
                                t("jobs.downloadZip"),
                              ])
                            : null,
                        ]),
                      ])
                    )
                  ),
                ]),
          ]),
          !state.locked
            ? el(
                "div",
                { className: "stack" },
                exportKinds.map((k) =>
                  buildKindRunnerCard(k, (created) => {
                    window.location.hash = `#/jobs?job=${encodeURIComponent(created.id)}`;
                  })
                )
              )
            : null
        );
        return;
      }

      // activeTab === "machines"
      const [statusDoc, modelsDoc] = await Promise.all([
        getJSON("/api/status"),
        ensureModels(false),
      ]);
      state.statusDoc = statusDoc;
      const mach = statusDoc.machines || {};
      const colab = mach.colab || {};
      const mDoc = modelsDoc || {};
      const canAct = !state.locked || state.chatOn;

      setChildren(
        wrap,
        ...headerNodes,
        el("div", { className: "grid-3" }, [
          el("section", { className: "card" }, [
            el("h2", { text: t("jobs.machinesLaptop") }),
            Number.isFinite(mach.laptop?.running_jobs) && mach.laptop?.slots > 0
              ? el("meter", { className: "slot-meter", min: 0, max: mach.laptop.slots,
                  value: mach.laptop.running_jobs, "aria-label": t("jobs.machinesLaptop") })
              : null,
            el("p", {
              className: "muted",
              text: t("jobs.slotsSummary", {
                used: formatNumber(mach.laptop && mach.laptop.running_jobs),
                total: formatNumber(mach.laptop && mach.laptop.slots),
              }),
            }),
          ]),
          el("section", { className: "card" }, [
            el("div", { className: "task-head" }, [
              el("h2", { text: t("jobs.machines3060") }),
              renderStateChip(mDoc.tunnel),
            ]),
            // no gateway or model id outside the API configuration panel (Q3)
            el("p", {
              className: "muted",
              text: t(
                (mDoc.chat && mDoc.chat.ready) || mDoc.agent_ready
                  ? "ux.assistantReady"
                  : "ux.assistantNotReady"
              ),
            }),
            el("div", { className: "actions" }, [
              renderStateChip(mDoc.nemotron),
              canAct
                ? el(
                    "button",
                    {
                      type: "button",
                      className: "topbtn",
                      onClick: async () => {
                        await postJSON("/api/models/connect", {});
                        await ensureModels(true);
                        loadAndRender();
                      },
                    },
                    [t("jobs.connectTunnel")]
                  )
                : null,
              canAct
                ? el(
                    "button",
                    {
                      type: "button",
                      className: "topbtn",
                      onClick: async () => {
                        await postJSON("/api/models/prewarm", {});
                        await ensureModels(true);
                        loadAndRender();
                      },
                    },
                    [t("jobs.prewarmModel")]
                  )
                : null,
            ]),
          ]),
          el("section", { className: "card" }, [
            el("div", { className: "task-head" }, [
              el("h2", { text: t("jobs.machinesColab") }),
              colab.fresh === false
                ? el("span", { className: cls("chip", "warning"), text: t("jobs.colabStale") })
                : null,
            ]),
            el("p", {
              className: "muted",
              text:
                colab.balance != null
                  ? t("ux.colabBalanceLine", {
                      cu: formatNumber(colab.balance, { maximumFractionDigits: 2 }),
                      time: formatDateTime(colab.time),
                    })
                  : t("state.na"),
            }),
          ]),
        ])
      );
    } catch (err) {
      setChildren(wrap, ...headerNodes, renderErrorBlock(err, loadAndRender));
    }
  };

  loadAndRender();
  return wrap;
}

// Check × source matrix of rule QA flags (design audit P0-5). story.heat rows are
// [check, source, n]: each cell shows n and is shaded by n against the largest n; 0 is a faint
// dot and a pair never checked stays blank. Column heads use the source's catalog title when
// one exists, else its short id. It stays a plain table, so screen readers read every number.
function renderHeatMatrix(heat, works, catRows, ds) {
  const rows = (Array.isArray(heat) ? heat : []).filter((r) => Array.isArray(r) && r.length >= 2);
  const checks = Array.from(new Set(rows.map((r) => r[0]))).sort();
  const srcs = Array.from(new Set(rows.map((r) => r[1]))).sort();
  const cells = new Map(rows.map((r) => [`${r[0]}::${r[1]}`, Number(r[2]) || 0]));
  const max = Math.max(0, ...cells.values());
  const known = [
    ...(Array.isArray(catRows) ? catRows : []),
    ...(ds && Array.isArray(ds.rows) ? ds.rows : []),
  ];
  const srcTitle = (sid) => {
    const prefix = `src_${sid}`;
    const hit = known.find(
      (r) => r && typeof r.id === "string" && r.id.startsWith(prefix) && r.title
    );
    if (hit) return String(hit.title).replace(/^Pipeline\s*·\s*/i, "");
    const work = (Array.isArray(works) ? works : []).find(
      (w) => w && typeof w.name === "string" && w.name.startsWith(prefix)
    );
    return work ? shortHashId(work.name) : String(sid).slice(0, 8);
  };
  const named = srcs.map((sid) => ({ sid, name: srcTitle(sid) }));

  return el("section", { className: cls("card", "table-wrap") }, [
    el("h2", { text: t("qa.heatTitle") }),
    el("p", { className: cls("tiny", "muted"), text: t("qa.heatNote") }),
    el("table", { className: cls("table", "heat-table") }, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col", text: t("qa.matrixCheckCol") }),
          ...named.map(({ sid, name }) =>
            el("th", { scope: "col", className: "heat-col", title: sid, text: name })
          ),
        ]),
      ]),
      el(
        "tbody",
        {},
        checks.map((ck) =>
          el("tr", {}, [
            el("th", { scope: "row", className: "mono", text: ck }),
            ...named.map(({ sid, name }) => {
              const key = `${ck}::${sid}`;
              if (!cells.has(key)) {
                return el("td", { className: cls("heat-cell", "is-none"), text: "" });
              }
              const n = cells.get(key);
              const ratio = max > 0 ? n / max : 0;
              const title = t("qa.heatCellTitle", { check: ck, source: name, n: formatNumber(n) });
              return n === 0
                ? el("td", { className: cls("heat-cell", "is-zero"), title }, [
                    el("span", { className: "heat-zero", "aria-hidden": "true", text: "·" }),
                    el("span", { className: "sr-only", text: formatNumber(0) }),
                  ])
                : el("td", {
                    className: cls("heat-cell", ratio > 0.6 && "is-strong"),
                    style: `--heat:${(0.15 + 0.85 * ratio).toFixed(2)}`,
                    title,
                    text: formatNumber(n),
                  });
            }),
          ])
        )
      ),
    ]),
  ]);
}

// ============================================================================
// #/qa — Quality & Agent QA/QC
// ============================================================================
export function renderQaPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("qa.title")));

  const load = async () => {
    try {
      const [works, artifacts, agentStats, rawStory, cat] = await Promise.all([
        getJSON("/api/works"),
        getJSON("/api/artifacts"),
        getJSON("/api/agent_stats"),
        ensureStoryRaw(),
        ensureCatalog(),
      ]);
      const catRows = (cat && Array.isArray(cat.rows) && cat.rows) || [];
      const story = scopeStoryForTask(rawStory);
      const workEpsContainer = el("div", {});
      const agentResultContainer = el("div", {});

      const inspectWork = async (workName) => {
        const eps = await getJSON(`/api/work_episodes?work=${encodeURIComponent(workName)}`);
        setChildren(
          workEpsContainer,
          el("section", { className: cls("card", "table-wrap") }, [
            el("h3", { className: "mono", text: workName }),
            el("table", { className: "table" }, [
              el("thead", {}, [
                el("tr", {}, [
                  el("th", { text: t("ds.colEp") }),
                  el("th", { text: t("qa.colDeid") }),
                  el("th", { className: "num", text: t("qa.colFrames") }),
                  el("th", { text: t("qa.colQa") }),
                ]),
              ]),
              el(
                "tbody",
                {},
                (eps || []).slice(0, 60).map((e) =>
                  el("tr", {}, [
                    el("td", { className: "mono", text: e.episode_id }),
                    el("td", {}, [renderStateChip(e.deid ? "done" : "waiting")]),
                    el("td", { className: "num", text: formatNumber(e.frames) }),
                    el("td", {}, [renderStateChip(e.qa || "na")]),
                  ])
                )
              ),
            ]),
          ])
        );
      };

      const inspectAgentRun = async (jobId) => {
        const rootPrefix =
          state.statusDoc && state.statusDoc.fw_root ? state.statusDoc.fw_root : "fwdata";
        const outPath = `${rootPrefix}/console/agentqa/${jobId}`;
        const res = await getJSON(`/api/agent_result?out=${encodeURIComponent(outPath)}`);
        setChildren(
          agentResultContainer,
          el("section", { className: "card" }, [
            el("h3", { className: "mono", text: `${jobId} · ${scrubPath(res.reports_path || outPath)}` }),
            el("pre", {
              className: cls("log-box", "mono"),
              text: JSON.stringify(res.reports || [], null, 2),
            }),
          ])
        );
      };

      const bench = story.demo && story.demo.qa_bench ? story.demo.qa_bench : null;
      // Aborted train attempts (".attempt1" folders) are not QA artefacts worth showing.
      const shownArtifacts = (Array.isArray(artifacts) ? artifacts : []).filter(
        (a) => a && !/\.attempt\d*(?:\/|$)/.test(String(a.path || ""))
      );
      const reasons = Array.isArray(story.reasons) ? [...story.reasons].sort((a, b) => b[1] - a[1]) : [];

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("qa.title") }],
          title: t("qa.title"),
          actions: !state.locked
            ? [el("a", { className: cls("btn", "primary"), href: "#/jobs?view=pipeline" }, [t("jobs.tab.pipeline")])]
            : [],
        }),

        renderStatStrip([
          {
            label: t("ego.worksTitle"),
            value: formatNumber((works || []).length),
          },
          {
            label: t("qa.agentRunsTitle"),
            value: formatNumber(agentStats && agentStats.nemotron_runs),
            sub: t("qa.findingsSub", { count: formatNumber(agentStats && agentStats.findings) }),
          },
          {
            label: t("qa.artifactsTitle"),
            value: formatNumber(shownArtifacts.length),
          },
        ]),

        reasons.length > 0
          ? renderChartBlock({
              title: t("qa.reasonsTitle"),
              height: 220,
              buildOption: ({ ink, soft, line, colors }) => ({
                grid: { left: 150, right: 24, top: 14, bottom: 26 },
                tooltip: { trigger: "axis" },
                xAxis: { type: "value", axisLabel: { color: soft }, splitLine: { lineStyle: { color: line } } },
                yAxis: {
                  type: "category",
                  data: reasons.map((r) => r[0]).reverse(),
                  axisLabel: { color: ink },
                },
                series: [
                  {
                    type: "bar",
                    data: reasons.map((r) => r[1]).reverse(),
                    itemStyle: { color: colors[0], borderRadius: [0, 4, 4, 0] },
                  },
                ],
              }),
              tableNode: el("table", { className: "table" }, [
                el(
                  "tbody",
                  {},
                  reasons.map(([k, v]) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: k }),
                      el("td", { className: "num", text: formatNumber(v) }),
                    ])
                  )
                ),
              ]),
            })
          : null,

        bench
          ? el("section", { className: "card" }, [
              el("h2", { text: t("qa.benchTitle") }),
              renderSourceCitation(bench.source),
              el("div", { className: "grid-3" }, [
                bench.code_layer
                  ? el("div", { className: "meta-box" }, [
                      el("span", {
                        text: t("qa.codeLayerTitle", { date: bench.code_layer.date || "" }),
                      }),
                      el("b", {
                        text: `${formatNumber(bench.code_layer.caught)} / ${formatNumber(bench.code_layer.planted)}`,
                      }),
                      el("small", {
                        text: `${t("qa.falseAlarmsSub", { fa: formatNumber(bench.code_layer.false_alarms), clean: formatNumber(bench.code_layer.clean_units) })}${bench.code_layer.false_alarm_is_upper_bound ? ` (${t("qa.upperBound")})` : ""}`,
                      }),
                    ])
                  : null,
                bench.agent_layer_nemotron && bench.agent_layer_nemotron.value
                  ? el("div", { className: "meta-box" }, [
                      el("span", {
                        text: t("qa.agentLayerTitle", {
                          date: bench.agent_layer_nemotron.value.date || "—",
                        }),
                      }),
                      el("b", {
                        text: `${formatNumber(bench.agent_layer_nemotron.value.caught)} / ${formatNumber(bench.agent_layer_nemotron.value.planted)}`,
                      }),
                      el("small", { text: cleanInlineMarkdown(bench.agent_layer_nemotron.quote) }),
                    ])
                  : null,
                bench.psi_data_bench && bench.psi_data_bench.value
                  ? el("div", { className: "meta-box" }, [
                      el("span", { text: t("qa.psiBenchTitle") }),
                      el("b", {
                        text: bench.psi_data_bench.value.scored
                          ? String(bench.psi_data_bench.value.planted)
                          : t("qa.benchUnscored"),
                      }),
                      el("small", {
                        text: t("qa.plantedSub", {
                          count: formatNumber(bench.psi_data_bench.value.planted),
                          source: bench.psi_data_bench.source || "",
                        }),
                      }),
                    ])
                  : null,
              ]),
            ])
          : null,

        Array.isArray(story.heat) && story.heat.length > 0
          ? renderHeatMatrix(story.heat, works, catRows, story.ds)
          : null,

        story.qa_sample
          ? el("details", { className: "studio-details" }, [
              el("summary", { text: t("qa.sampleTitle") }),
              el("pre", {
                className: cls("log-box", "mono"),
                style: "margin-top:8px",
                text: String(story.qa_sample),
              }),
            ])
          : null,

        el("div", { className: "grid" }, [
          el("section", { className: "card" }, [
            el("h2", { text: t("ego.worksTitle") }),
            (works || []).length === 0
              ? el("p", { className: "muted", text: t("state.empty") })
              : el(
                  "div",
                  { className: "row-list" },
                  works.map((w) => {
                    const qaObj = (w.summary && w.summary.qa) || {};
                    const p = Number(qaObj.pass || 0);
                    const fl = Number(qaObj.flag || 0);
                    const rj = Number(qaObj.reject || 0);
                    const tot = Math.max(1, p + fl + rj);
                    return el("div", { className: "row" }, [
                      el("div", { className: "row-body" }, [
                        el("div", { className: "task-head" }, [
                          el(
                            "button",
                            {
                              type: "button",
                              className: "link",
                              onClick: () => inspectWork(w.name),
                            },
                            [friendlyBatchTitle(w.name, w.source_detail, catRows)]
                          ),
                          el("span", {
                            className: cls("short-hash", "mono"),
                            title: w.name,
                            text: shortHashId(w.name),
                          }),
                        ]),
                        el("div", { className: "qa-bar", style: "margin-top:6px" }, [
                          p > 0
                            ? el("span", {
                                className: "qa-seg-pass",
                                style: `width:${((p / tot) * 100).toFixed(1)}%`,
                              })
                            : null,
                          fl > 0
                            ? el("span", {
                                className: "qa-seg-flag",
                                style: `width:${((fl / tot) * 100).toFixed(1)}%`,
                              })
                            : null,
                          rj > 0
                            ? el("span", {
                                className: "qa-seg-reject",
                                style: `width:${((rj / tot) * 100).toFixed(1)}%`,
                              })
                            : null,
                        ]),
                        el("span", {
                          className: cls("tiny", "mono"),
                          text: t("qa.workCounts", {
                            eps: formatNumber(w.episodes),
                            pass: formatNumber(p),
                            flag: formatNumber(fl),
                            reject: formatNumber(rj),
                          }),
                        }),
                      ]),
                    ]);
                  })
                ),
          ]),

          el("section", { className: "card" }, [
            el("h2", { text: t("qa.agentRunsTitle") }),
            !(agentStats && Array.isArray(agentStats.runs) && agentStats.runs.length > 0)
              ? el("p", { className: "muted", text: t("state.empty") })
              : el(
                  "div",
                  { className: "row-list" },
                  agentStats.runs.map((r) =>
                    el("div", { className: "row" }, [
                      el("div", { className: "row-body" }, [
                        el(
                          "button",
                          {
                            type: "button",
                            className: cls("link", "mono"),
                            onClick: () => inspectAgentRun(r.id),
                          },
                          [r.id]
                        ),
                        el("p", {
                          className: "muted",
                          text: `${r.input} · ${t("qa.findingsSub", { count: formatNumber(r.findings) })} · ${formatDateTime(r.time)}`,
                        }),
                      ]),
                    ])
                  )
                ),
          ]),
        ]),

        workEpsContainer,
        agentResultContainer,

        shownArtifacts.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("qa.artifactsTitle") }),
              el(
                "div",
                { className: "row-list" },
                shownArtifacts.slice(0, 20).map((a) =>
                  el("div", { className: "row" }, [
                    el("div", { className: "row-body" }, [
                      el("b", { text: a.label }),
                      el("p", { className: cls("muted", "mono"), text: scrubPath(a.path) }),
                    ]),
                  ])
                )
              ),
            ])
          : null
      );
    } catch (err) {
      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("qa.title") }],
          title: t("qa.title"),
        }),
        renderErrorBlock(err, load)
      );
    }
  };

  load();
  return wrap;
}
