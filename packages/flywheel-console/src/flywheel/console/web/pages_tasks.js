import {
  announce,
  el,
  ensureCatalog,
  ensureSimRaw,
  safeThumbUrl,
  formatNumber,
  getCurrentTask,
  getTasks,
  hasI18nKey,
  pickLang,
  renderErrorBlock,
  selectTask,
  state,
  t,
  taskSuccessText,
} from "./core.js";

const STAGE_ORDER = ["1", "2", "3", "4", "5", "6", "0"];
const GROUP_ORDER = ["egocentric", "teleop", "s1", "s2", "eval", "other", "all"];

function renderCrumbAndHeading(actionsNode = null) {
  return [
    el("div", { className: "crumb" }, [
      `${t("app.crumbRoot")} / `,
      el("span", { text: t("tasks.title") }),
    ]),
    el("div", { className: "heading" }, [
      el("div", {}, [
        el("h1", { text: t("tasks.title") }),

      ]),
      actionsNode ? el("div", { className: "actions" }, [actionsNode]) : null,
    ]),
  ];
}

function renderSkeleton() {
  return el("div", { "aria-busy": "true" }, [
    ...renderCrumbAndHeading(),
    el("div", { className: "skeleton-box" }),
    el("div", { className: "grid" }, [0, 1].map(() =>
      el("div", { className: "card" }, [
        el("div", { className: "skeleton-line lg" }),
        el("div", { className: "skeleton-line" }),
        el("div", { className: "skeleton-box" }),
        el("div", { className: "skeleton-box" }),
      ])
    )),
  ]);
}

function formatHowList(howItems) {
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

function renderCatalogTotals(task) {
  const totals = task.catalog_totals;
  const invKey = task.inventory ? "tasks.inv." + task.inventory : "";
  const invNote = invKey && hasI18nKey(invKey) ? t("tasks.inv." + task.inventory) : "";

  if (!totals || typeof totals !== "object" || Object.keys(totals).length === 0) {
    return el("p", { className: "muted", text: invNote || t("tasks.catalogEmpty") });
  }

  const keys = Object.keys(totals)
    .filter((k) => k !== "all")
    .sort((a, b) => {
      const ia = GROUP_ORDER.indexOf(a);
      const ib = GROUP_ORDER.indexOf(b);
      const oa = ia === -1 ? 99 : ia;
      const ob = ib === -1 ? 99 : ib;
      return oa - ob || a.localeCompare(b);
    });

  if (keys.length === 0) {
    return el("p", { className: "muted", text: invNote || t("tasks.catalogEmpty") });
  }

  const maxEps = Math.max(1, ...keys.map((k) => Number((totals[k] || {}).episodes || 0)));

  return el("div", {}, [
    invNote ? el("p", { className: "muted", text: invNote }) : null,
    el("p", { className: "tiny muted", text: t("ux.streamSubNote") }),
    el(
      "div",
      { className: "stream-bars" },
      keys.map((groupKey) => {
        const entry = totals[groupKey] || {};
        const eps = Number(entry.episodes || 0);
        const pct = eps <= 0 ? 0 : Math.max(2, Math.min(100, (eps / maxEps) * 100));
        const i18nKey = "cat.group." + groupKey;
        const label = hasI18nKey(i18nKey) ? t("cat.group." + groupKey) : groupKey;
        const hoursText =
          entry.hours == null
            ? t("state.na")
            : t("tasks.unitHours", { val: formatNumber(entry.hours, { maximumFractionDigits: 2 }) });
        const metricText = `${t("tasks.unitEpisodes", { val: formatNumber(eps) })} · ${t(
          "data.setsHoursSub",
          {
            sets: formatNumber(entry.sets ?? 0),
            hours: hoursText,
          }
        )}`;
        return el("div", { className: "stream-row" }, [
          el("div", { className: "stream-row-head" }, [
            el("span", { text: label }),
            el("span", {
              className: "tiny mono",
              text: metricText,
            }),
          ]),
          el("div", { className: "stream-track" }, [
            el("div", { className: "stream-fill", style: `width:${pct.toFixed(1)}%` }),
          ]),
        ]);
      })
    ),
  ]);
}

function renderProcessBlock(task) {
  const procMap = task.process && typeof task.process === "object" ? task.process : {};
  const presentKeys = STAGE_ORDER.filter((k) => Object.prototype.hasOwnProperty.call(procMap, k));
  if (presentKeys.length === 0) {
    return el("p", { className: "muted", text: t("state.empty") });
  }

  const missingEntries = presentKeys
    .map((k) => ({ key: k, missing: pickLang((procMap[k] || {}).missing) }))
    .filter((item) => Boolean(item.missing));

  return el("div", {}, [
    el("p", {
      className: "muted",
      text:
        missingEntries.length > 0
          ? t("tasks.processMissingCount", { count: formatNumber(missingEntries.length) })
          : t("tasks.processAllReady", { count: formatNumber(presentKeys.length) }),
    }),
    missingEntries.length > 0
      ? el(
          "ul",
          { className: "missing-list" },
          missingEntries.map((item) =>
            el("li", { className: "missing-item" }, [
              el("strong", { text: `${t("proc.stage." + item.key)}:` }),
              el("span", { text: item.missing }),
            ])
          )
        )
      : null,
    el("details", { className: "studio-details" }, [
      el("summary", {
        text: t("tasks.processToggleHow", { count: formatNumber(presentKeys.length) }),
      }),
      el(
        "ul",
        { className: "how-list" },
        presentKeys.map((stageKey) => {
          const info = procMap[stageKey] || {};
          const howText = formatHowList(info.how);
          const remoteText = info.remote ? t("tasks.remoteLabel", { where: info.remote }) : "";
          const line = [remoteText, howText].filter(Boolean).join(" · ") || t("state.na");
          return el("li", { className: "how-item" }, [
            el("b", { text: t("proc.stage." + stageKey) }),
            el("span", { className: "mono", text: line }),
          ]);
        })
      ),
    ]),
  ]);
}

function renderTaskCard(task, roundsById, media) {
  const isSelected = state.taskId === task.id;
  const stages = Array.isArray(task.stages) ? task.stages : [];
  const roundIds = Array.isArray(task.rounds) ? task.rounds : [];
  const successText = taskSuccessText(task);
  const successSource = task.success && task.success.source ? task.success.source : null;
  const descText = pickLang(task.description) || t("state.na");
  const taskTitle = pickLang(task.name) || task.id;
  const allTotals = (task.catalog_totals && task.catalog_totals.all) || {};
  const allSets = allTotals.sets ?? 0;
  const epsText =
    allTotals.episodes != null
      ? t("tasks.unitEpisodes", { val: formatNumber(allTotals.episodes) })
      : t("state.na");
  const compareLineText =
    roundIds.length > 0
      ? t("ux.taskCardCompareHasRounds", {
          sets: formatNumber(allSets),
          episodes: epsText,
          rounds: formatNumber(roundIds.length),
        })
      : t("ux.taskCardCompareNoRound", {
          sets: formatNumber(allSets),
          episodes: epsText,
        });

  const chooseAndOpenHome = () => {
    selectTask(task.id);
    window.location.hash = "#/home";
  };

  const copyIdBtn = el(
    "button",
    {
      type: "button",
      className: "short-hash mono",
      title: t("ux.copyIdTitle"),
      onClick: (ev) => {
        ev.stopPropagation();
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(task.id).catch(() => {});
        }
        copyIdBtn.textContent = t("chat.copiedBtn");
        announce(t("chat.copiedBtn"));
        window.setTimeout(() => {
          copyIdBtn.textContent = task.id;
        }, 1200);
      },
    },
    [task.id]
  );

  const preview = el("div", { className: "task-preview", hidden: true });
  media.then(([doc, sim]) => {
    const row = doc?.rows?.find((item) =>
      item.task === (task.catalog_task || task.id) && safeThumbUrl(item.thumbs?.[0])
    );
    const clip = sim?.teleop?.find((ep) => ep.task === task.id && ep.poster);
    const src = safeThumbUrl(row?.thumbs?.[0]) || (clip && `/simmedia/${clip.poster}`);
    if (!src) return;
    preview.appendChild(el("img", {
      src, alt: row?.title || taskTitle, decoding: "async",
      onLoad: () => { preview.hidden = false; },
    }));
  });

  return el(
    "article",
    {
      className: `card task-card${isSelected ? " is-selected" : ""}`,
      "data-task-id": task.id,
    },
    [
      preview,
      el("div", { className: "task-head" }, [
        el("div", { className: "ds" }, [
          el("div", {}, [
            el("h3", { className: "task-title" }, [
              el(
                "a",
                {
                  href: "#/home",
                  onClick: (ev) => {
                    ev.preventDefault();
                    chooseAndOpenHome();
                  },
                },
                [taskTitle]
              ),
            ]),
            el("p", {
              className: "task-compare-line",
              text: compareLineText,
            }),
          ]),
        ]),
        el("div", { className: "actions" }, [
          isSelected
            ? el("span", { className: "chip", text: `✓ ${t("tasks.selectedBadge")}` })
            : null,
          el(
            "button",
            {
              type: "button",
              className: isSelected ? "btn primary" : "btn",
              onClick: chooseAndOpenHome,
            },
            [isSelected ? t("ux.continueShort") : t("ux.openTaskShort")]
          ),
        ]),
      ]),

      el("div", { className: "meta-strip" }, [
        el("div", { className: "meta-box" }, [
          el("span", { text: t("tasks.robot") }),
          el("b", { text: task.robot || t("state.na") }),
        ]),
        el("div", { className: "meta-box" }, [
          el("span", { text: t("tasks.model") }),
          el("b", { text: task.model || t("state.na") }),
        ]),
        el("div", { className: "meta-box" }, [
          el("span", { text: t("common.id") }),
          copyIdBtn,
        ]),
      ]),

      el("details", { className: "studio-details" }, [
        el("summary", { text: t("tasks.success") }),
        el("p", { className: "muted", text: descText }),
        el("div", { className: "row" }, [
          el("div", { className: "row-body" }, [
            el("b", { text: t("tasks.success") }),
            el("p", { className: "muted", text: successText }),
            successSource
              ? el("div", {
                  className: "sources-note mono",
                  text: `${t("common.source")}: ${successSource}`,
                })
              : null,
          ]),
        ]),

        el("div", { className: "row" }, [
          el("div", { className: "row-body" }, [
            el("b", { text: t("tasks.roundsTitle") }),
            roundIds.length === 0
              ? el("div", { className: "step-tags" }, [
                  el("span", { className: "chip neutral", text: t("tasks.roundsNone") }),
                ])
              : el(
                  "div",
                  { className: "step-tags" },
                  roundIds.map((rid) => {
                    const rObj = roundsById.get(rid);
                    const rTitle = rObj ? pickLang(rObj.title) : "";
                    return el("span", {
                      className: "step-tag",
                      text: rTitle ? `${rid} · ${rTitle}` : rid,
                    });
                  })
                ),
          ]),
        ]),
      ]),

      el("details", { className: "studio-details", style: "margin-top:auto" }, [
        el("summary", {
          text: t("ux.detailsDataProcess", { sets: formatNumber(allSets) }),
        }),
        el("div", { className: "row-list", style: "margin-top:8px" }, [
          el("div", { className: "row" }, [
            el("div", { className: "row-body" }, [
              el("b", { text: t("tasks.catalogTitle") }),
              renderCatalogTotals(task),
            ]),
          ]),

          stages.length > 0
            ? el("div", { className: "row" }, [
                el("div", { className: "row-body" }, [
                  el("b", {
                    text: t("tasks.stages", { count: formatNumber(stages.length) }),
                  }),
                  el(
                    "div",
                    { className: "step-tags" },
                    stages.map((st, idx) =>
                      el("span", {
                        className: "step-tag",
                        text: `${String(idx + 1).padStart(2, "0")} · ${pickLang(st) || st.id}`,
                      })
                    )
                  ),
                ]),
              ])
            : null,

          el("div", { className: "row" }, [
            el("div", { className: "row-body" }, [
              el("b", { text: t("tasks.processTitle") }),
              renderProcessBlock(task),
            ]),
          ]),

          task.scorer_config
            ? el("div", { className: "row" }, [
                el("div", { className: "row-body" }, [
                  el("span", { className: "tiny mono", text: task.scorer_config }),
                ]),
              ])
            : null,
        ]),
      ]),
    ]
  );
}

export function renderTasksPage({ onRetry }) {
  if (state.tasksLoading && !state.tasksLoaded) {
    return renderSkeleton();
  }

  if (state.tasksError && !state.tasksDoc) {
    return el("div", {}, [
      ...renderCrumbAndHeading(),
      renderErrorBlock(state.tasksError, onRetry),
    ]);
  }

  const tasks = getTasks();
  const activeTask = getCurrentTask() || tasks[0] || null;
  const activeName = activeTask ? pickLang(activeTask.name) || activeTask.id : t("state.na");
  const rounds = (state.tasksDoc && Array.isArray(state.tasksDoc.rounds))
    ? state.tasksDoc.rounds
    : [];
  const media = tasks.length ? Promise.all([
    ensureCatalog().catch(() => null),
    ensureSimRaw().catch(() => null),
  ]) : null;
  const roundsById = new Map(rounds.map((r) => [r.id, r]));
  const docSource = state.tasksDoc && state.tasksDoc.source ? state.tasksDoc.source : null;

  return el("div", {}, [
    ...renderCrumbAndHeading(
      activeTask
        ? el(
            "a",
            {
              className: "btn primary",
              href: "#/home",
              onClick: () => selectTask(activeTask.id),
            },
            [t("ux.continueTaskBtn", { task: activeName })]
          )
        : null
    ),

    el("div", { className: "sect" }, [
      el("div", { className: "actions" }, [
        el("h2", { text: t("tasks.sectionTitle") }),
        el("span", {
          className: "chip neutral",
          text: t("ux.taskCountBadge", { count: formatNumber(tasks.length) }),
        }),
      ]),
      docSource
        ? el("span", {
            className: "muted mono",
            text: t("tasks.indexSource", { source: docSource }),
          })
        : null,
    ]),
    tasks.length === 0
      ? el("div", { className: "empty", text: t("state.empty") })
      : el(
          "div",
          { className: "grid" },
          tasks.map((task) => renderTaskCard(task, roundsById, media))
        ),
  ]);
}
