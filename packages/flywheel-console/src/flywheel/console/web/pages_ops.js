import {
  cleanInlineMarkdown,
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
  renderJobKindCell,
  renderLoadingView,
  renderSourceCitation,
  renderStatStrip,
  renderStateChip,
  scopeStoryForTask,
  setChildren,
  setSelection,
  shortHashId,
  state,
  t,
  tryGetJSON,
  uploadVideoFile,
} from "./core.js";

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
    const stages = Array.isArray(statusDoc.stages) ? statusDoc.stages : [];
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
      if (pick < 0 && isPureCurrentTask && doneStages === stages.length) {
        const evalIdx = stages.findIndex((s) => s && s.id === "eval");
        if (evalIdx >= 0) pick = evalIdx;
      }
      selectedStageIdx = pick >= 0 ? pick : 0;
    }

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

    const spotlightBox = el("div", { className: "stage-spotlight" });

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

      setChildren(
        spotlightBox,
        el("div", { className: "eyebrow", text: t("ux.stageFocusEyebrow") }),
        el("div", { className: "task-head" }, [
          el("div", { className: "actions" }, [
            el("b", { style: "font-size:14px", text: `${numStr} · ${stTitle}` }),
            isMixedStageScope || !sameTask
              ? el("span", {
                  className: cls("chip", sameTask ? "" : "neutral"),
                  text: st.task
                    ? t("ux.jobOwnerTag", { owner: st.task })
                    : t("ux.scopeBadgeUnscoped"),
                })
              : null,
          ]),
          renderStateChip(st.state),
        ]),
        el("div", {
          style: "font-size:13px;line-height:1.45",
          className: sameTask ? "" : "muted",
          text: sameTask ? st.now || t("state.na") : scopeNote,
        }),
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
                { label: t("ux.mileBaseline"), value: curRound.baseline || t("state.na") },
                {
                  label: t("ux.mileDiagnose"),
                  value:
                    (curRound.plan ? compactPath(curRound.plan) : "") ||
                    (curRound.rollouts ? compactPath(curRound.rollouts) : "") ||
                    curRound.id ||
                    t("state.na"),
                },
                {
                  label: t("ux.mileCut"),
                  value: curRound.cut ? compactPath(curRound.cut) : t("state.na"),
                },
                { label: t("ux.mileAfter"), value: curRound.after_round || t("state.na") },
              ].map((m) =>
                el("div", { className: "meta-box" }, [
                  el("span", { text: m.label }),
                  el("b", { className: "mono", text: m.value }),
                ])
              )
            ),
          ])
        : null,
      el("section", { className: "card" }, [
        el("div", { className: "grid" }, [
          el("a", { className: "sample-ep-card", href: "#/data" }, [
            el("b", { text: `▤ ${t("home.quickData1")}` }),
            el("span", { className: "tiny", text: t("home.quickData1Sub") }),
          ]),
          el("a", { className: "sample-ep-card", href: "#/eval" }, [
            el("b", { text: `◉ ${t("home.quickExp1")}` }),
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
            spotlightBox,
            renderFlywheelOrbitalCanvas({
              stages,
              selectedIdx: selectedStageIdx,
              centerTitle: hubCenterTitle,
              centerSub: hubCenterSub,
              showTaskTag: isMixedStageScope,
              onSelect: (idx) => {
                userSelectedStage = true;
                updateSpotlight(idx);
              },
            }),
          ])
        : null;

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
      const bestEvalText = jigDoc
        ? jigEval && jigEval.status === "ready" && jigHead
          ? t("ux.homeEvalBestVal", {
              run: jigEval.run,
              succ: formatNumber(jigHead.successes),
              n: formatNumber(jigHead.n),
            })
          : jigEval && jigEval.status === "blocked"
            ? t("ux.homeJigEvalBlocked", { run: jigEval.run })
            : t("exp.evalMissing", { run: jigRunId || "-" })
        : pairBest
          ? t("ux.homeEvalBestVal", {
              run: pairBest.run,
              succ: formatNumber(pairBest.successes),
              n: formatNumber(pairBest.n),
            })
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
          ? t("ux.homeEvalWithheldNote", { run: withheldList.join(", ") })
          : "";
      const activeColabList =
        jigDoc && Array.isArray(jigDoc.active_sessions) ? jigDoc.active_sessions : [];
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
            // the server's train line lists every scene's runs; the jig round shows its own below
            trainStage && trainStage.now && !jigDoc
              ? el("div", { className: cls("tiny", "mono"), text: trainStage.now })
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

    const apiSub =
      state.modelsDoc && state.modelsDoc.chat && state.modelsDoc.chat.provider && state.modelsDoc.chat.model
        ? `${state.modelsDoc.chat.provider} · ${state.modelsDoc.chat.model}`
        : "";

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

      state.locked ? el("div", { className: "empty", text: t("state.lockedReadOnly") }) : null,

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
        {
          label: t("ux.homeServerAndApi"),
          value:
            statusDoc.machines && statusDoc.machines.laptop
              ? t("ux.slotUsage", {
                  used: formatNumber(statusDoc.machines.laptop.running_jobs),
                  total: formatNumber(statusDoc.machines.laptop.slots),
                })
              : t("state.na"),
          sub: apiSub,
        },
      ]),

      serverIncidentBanner,

      flywheelBoard,

      serverActivityDrawer,

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
                    el("td", {}, [renderJobKindCell(j.kind, ownerBadge)]),
                    el("td", {}, [renderStateChip(j.state)]),
                    el("td", { text: formatDateTime(j.created) }),
                    el("td", { text: j.stage || t("state.na") }),
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

  statusPollTimer = window.setInterval(() => {
    if (disposed || document.hidden) return;
    tryGetJSON("/api/status").then((res) => {
      if (!disposed && res.ok && res.data) {
        state.statusDoc = res.data;
        state.statusLoaded = true;
        renderContent();
      }
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

  return el("article", { className: "card" }, [
    el("div", { className: "task-head" }, [
      el("div", {}, [
        el("h3", { text: pickLang(kindSpec.title) || kindSpec.kind }),
        el("div", { className: cls("tiny", "mono"), text: `${kindSpec.kind} · ${kindSpec.command}` }),
      ]),
      el("div", { className: "actions" }, [
        kindSpec.typical_seconds != null
          ? el("span", { className: cls("chip", "neutral"), text: `~${kindSpec.typical_seconds}s` })
          : null,
        renderStateChip(kindSpec.available ? "ok" : "blocked"),
      ]),
    ]),
    !kindSpec.available && kindSpec.reason
      ? el("p", { className: "muted", text: pickLang(kindSpec.reason) })
      : null,
    !state.locked && kindSpec.available
      ? el("div", {}, [
          sampleSelect
            ? el("div", { className: "form-field" }, [
                el("label", { text: t("jobs.sampleLabel") }),
                sampleSelect,
              ])
            : null,
          el("div", { className: "form-grid" }, argFields),
          el("div", { className: "actions" }, [submitBtn]),
          msgNode,
        ])
      : null,
    kindSpec.outputs
      ? el("p", { className: cls("muted", "mono"), text: pickLang(kindSpec.outputs) })
      : null,
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
      state.locked ? el("div", { className: "empty", text: t("state.lockedReadOnly") }) : null,
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
                logPre.textContent += lRes.data.text;
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
                el("div", {}, [
                  el("h2", { text: `${jobTitleLabel} · ${shortHashId(job.id)}` }),
                  el("div", {
                    className: cls("tiny", "mono"),
                    text: `${job.kind} · ${formatDateTime(job.created)}`,
                  }),
                ]),
                el("div", { className: "actions" }, [stateHolder, cancelBtn]),
              ]),
              outEntries.length > 0
                ? el("div", { style: "margin-top:10px" }, [
                    el(
                      "div",
                      { className: "meta-strip" },
                      outEntries.map(([k, v]) => {
                        const fullStr = typeof v === "object" ? JSON.stringify(v) : String(v);
                        return el("div", { className: "meta-box", title: fullStr }, [
                          el("span", { text: k }),
                          el("b", {
                            className: "mono",
                            style: "font-size:11.5px;overflow-wrap:anywhere",
                            text: fullStr.includes("/") ? compactPath(fullStr) : fullStr,
                          }),
                        ]);
                      })
                    ),
                  ])
                : null,
              el("details", { className: "studio-details", style: "margin-top:10px" }, [
                el("summary", { text: t("fly.cliToggle") }),
                el("pre", {
                  className: cls("log-box", "mono"),
                  style: "margin-top:6px",
                  text: (job.argv || []).join(" "),
                }),
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
                        el("td", {}, [renderJobKindCell(j.kind)]),
                        el("td", {}, [renderStateChip(j.state)]),
                        el("td", { text: formatDateTime(j.created) }),
                        el("td", { text: j.stage || t("state.na") }),
                        el("td", {
                          className: "num",
                          text:
                            j.seconds != null
                              ? `${formatNumber(j.seconds, { maximumFractionDigits: 1 })}s`
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
                      el("p", { className: "sources-note", text: pickLang(rm.observe) }),
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
            el("div", { className: "form-grid" }, [
              el("div", { className: "form-field" }, [
                el("label", { text: t("jobs.uploadDirLabel") }),
                dirInput,
              ]),
              el("div", { className: "form-field" }, [
                el("label", { text: t("nav.item.egoflow") }),
                fileInput,
                filePreview,
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
                el("b", { className: "mono", text: data.path }),
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
                        checkOut.textContent = `device.json: ${chk.has_device} · tasks: ${(chk.tasks || []).join(", ") || "-"}`;
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
                      className: "topbtn",
                      onClick: () => loadFs(d.path),
                    },
                    [`📁 ${d.name}`]
                  )
                )
              ),
              checkOut
            );
          };

          fsCard = el("section", { className: "card" }, [
            el("div", { className: "task-head" }, [
              el("h2", { text: t("jobs.fsTitle") }),
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
          fsCard,
          el(
            "div",
            { className: "stack" },
            ingestKinds.map((k) =>
              buildKindRunnerCard(k, (created) => {
                window.location.hash = `#/jobs?job=${encodeURIComponent(created.id)}`;
              })
            )
          )
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
            el("p", {
              className: cls("muted", "mono"),
              text: `${mDoc.chat ? `${mDoc.chat.provider}: ${mDoc.chat.model}` : mDoc.agent_model || ""}`,
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
                  ? `${formatNumber(colab.balance, { maximumFractionDigits: 2 })} CU · ${formatDateTime(colab.time)}`
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
                  el("th", { text: "QA" }),
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
            el("h3", { className: "mono", text: `${jobId} · ${res.reports_path || outPath}` }),
            el("pre", {
              className: cls("log-box", "mono"),
              text: JSON.stringify(res.reports || [], null, 2),
            }),
          ])
        );
      };

      const bench = story.demo && story.demo.qa_bench ? story.demo.qa_bench : null;
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
            sub: "/api/works",
          },
          {
            label: t("qa.agentRunsTitle"),
            value: formatNumber(agentStats && agentStats.nemotron_runs),
            sub: t("qa.findingsSub", { count: formatNumber(agentStats && agentStats.findings) }),
          },
          {
            label: t("qa.artifactsTitle"),
            value: formatNumber((artifacts || []).length),
            sub: "/api/artifacts",
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
                      el("span", { text: `Nemotron (${bench.agent_layer_nemotron.value.date || ""})` }),
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
          ? (() => {
              const checks = Array.from(new Set(story.heat.map(([c]) => c))).sort();
              const srcs = Array.from(new Set(story.heat.map(([, s]) => s))).sort();
              const pairSet = new Set(story.heat.map(([c, s]) => `${c}::${s}`));
              return el("section", { className: cls("card", "table-wrap") }, [
                el("h2", { style: "margin-bottom:8px", text: t("qa.heatTitle") }),
                el("table", { className: "table" }, [
                  el("thead", {}, [
                    el("tr", {}, [
                      el("th", { text: t("qa.matrixCheckCol") }),
                      ...srcs.map((s) =>
                        el("th", {
                          className: "mono",
                          style: "text-align:center",
                          text: `#${String(s).slice(0, 4)}`,
                        })
                      ),
                    ]),
                  ]),
                  el(
                    "tbody",
                    {},
                    checks.map((ck) =>
                      el("tr", {}, [
                        el("td", { className: "mono", text: ck }),
                        ...srcs.map((s) =>
                          el("td", { style: "text-align:center" }, [
                            pairSet.has(`${ck}::${s}`)
                              ? el("span", { className: "heat-dot", title: `${ck} × ${s}` })
                              : el("span", { className: "heat-empty", text: "·" }),
                          ])
                        ),
                      ])
                    )
                  ),
                ]),
              ]);
            })()
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
                          text: `${formatNumber(w.episodes)} ep · ${p}P · ${fl}F · ${rj}R`,
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

        Array.isArray(artifacts) && artifacts.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("qa.artifactsTitle") }),
              el(
                "div",
                { className: "row-list" },
                artifacts.slice(0, 20).map((a) =>
                  el("div", { className: "row" }, [
                    el("div", { className: "row-body" }, [
                      el("b", { text: a.label }),
                      el("p", { className: cls("muted", "mono"), text: `${a.kind} · ${a.path}` }),
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
