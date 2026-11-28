import {
  addSessionPin,
  chatStore,
  copyText,
  createNewSession,
  deleteSession,
  emitChatStore,
  ensureRouteToolsLoaded,
  fetchApiConfig,
  formatArgsChip,
  getActiveSession,
  loadChatDiagnostics,
  openApiConfigModal,
  recordSessionReview,
  removeSessionPin,
  renderMarkdownInto,
  renderToolUi,
  resizeChatCharts,
  runSharedTurn,
  selectSession,
  setSessionMode,
  shortModelLabel,
  subscribeChatStore,
  switchActiveApiModel,
} from "./chat.js";
import {
  canonicalDatasetTaxonomy,
  cls,
  el,
  ensureCatalog,
  ensureStoryRaw,
  formatNumber,
  getCurrentRound,
  getCurrentTask,
  onRouteCleanup,
  pickLang,
  scopeStoryForTask,
  setChildren,
  shortHashId,
  state,
  t,
} from "./core.js";

const MODES = [
  { id: "ask", labelKey: "studio.modeAsk", subKey: "studio.modeAskSub" },
  { id: "investigate", labelKey: "studio.modeInvestigate", subKey: "studio.modeInvestigateSub" },
  { id: "operate", labelKey: "studio.modeOperate", subKey: "studio.modeOperateSub" },
];

export function renderChatStudioPage() {
  const root = el("div", { className: "studio-page" });

  const drawer = el("dialog", { className: "analysis-drawer" });
  const drawerTitle = el("h2");
  const drawerBody = el("div", { className: "analysis-drawer-body" });
  const closeDrawer = () => drawer.close();
  drawer.append(el("header", { className: "task-head" }, [
    drawerTitle, el("button", { type: "button", className: "topbtn",
      onClick: closeDrawer, text: t("analysis.close") }),
  ]), drawerBody);
  const showDrawer = (title, node) => {
    drawerTitle.textContent = title;
    drawer.setAttribute("aria-label", title);
    setChildren(drawerBody, node);
    if (!drawer.open) drawer.showModal();
    requestAnimationFrame(resizeChatCharts);
  };
  let wbTab = "artifact";
  let slashMenuIdx = 0;
  let mentionEntities = [];

  // Pre-build persistent containers so typing in textarea never loses focus during streaming!
  const railSessionsBox = el("div", { className: "studio-session-list" });
  const railChecklistBox = el("div", { className: "studio-pinned-card" });
  const railApiBox = el("div", { className: "studio-api-card" });
  const railPinnedBox = el("div", { className: "studio-pinned-card" });

  const centerHeadTitle = el("b", { className: "studio-session-heading" });
  const modeBar = el("div", { className: "mode-seg" });
  const wbToggleBtn = el("button", { type: "button", className: "topbtn" });

  const streamBox = el("div", { className: "studio-stream" });
  const popupMenu = el("div", { className: "slash-menu", hidden: true });

  const wbTabsBar = el("div", { className: "tabs" });
  const wbBody = el("div", { className: "studio-wb-body" });
  const wbPane = el("aside", { className: "studio-workbench" }, [wbTabsBar, wbBody]);

  let catalogCache = null;
  let storyCache = null;

  const loadContextEntities = async () => {
    const [cat, rawStory] = await Promise.all([
      ensureCatalog().catch(() => null),
      ensureStoryRaw().catch(() => null),
    ]);
    catalogCache = cat;
    storyCache = rawStory ? scopeStoryForTask(rawStory) : null;
    const items = [];
    const rows = (cat && Array.isArray(cat.rows) ? cat.rows : []).filter(
      (r) => r && (r.status === "current" || r.status === "reference")
    );
    for (const r of rows.slice(0, 14)) {
      const tax = canonicalDatasetTaxonomy(r);
      items.push({
        id: r.id,
        kind: "dataset",
        label: `${tax.cleanTitle} (${r.episodes ?? 0} ep)`,
      });
    }
    const runs = storyCache && Array.isArray(storyCache.runs) ? storyCache.runs : [];
    for (const rn of runs.slice(0, 8)) {
      if (rn && rn.branch) {
        items.push({
          id: rn.branch,
          kind: "run",
          label: `run · ${rn.branch}`,
        });
      }
    }
    mentionEntities = items;
    renderRailPinned();
    if (wbTab === "scope") renderWorkbench();
  };

  // ------------------------------------------------------------------ Left Rail
  const renderRailSessions = () => {
    const active = getActiveSession();
    setChildren(
      railSessionsBox,
      ...chatStore.sessions.map((s) => {
        const isCur = s.id === active.id;
        const turnCount = (s.turns || []).length;
        const artCount = (s.artifacts || []).length;
        return el(
          "div",
          {
            className: cls("studio-session-item", isCur && "is-active"),
          },
          [
            el("button", { type: "button", className: "studio-session-meta session-select",
              onClick: () => { selectSession(s.id); closeDrawer(); } }, [
              el("span", {
                className: "studio-session-name",
                text: s.title || t("studio.untitledSession"),
              }),
              el("span", {
                className: cls("tiny", "mono"),
                text: `${turnCount} turns${artCount > 0 ? ` · ${artCount} art` : ""}`,
              }),
            ]),
            chatStore.sessions.length > 1
              ? el(
                  "button",
                  {
                    type: "button",
                    className: "session-del-btn",
                    title: t("studio.deleteSession"),
                    onClick: (ev) => {
                      ev.stopPropagation();
                      deleteSession(s.id);
                    },
                  },
                  ["×"]
                )
              : null,
          ]
        );
      })
    );
  };

  const renderRailChecklist = () => {
    const sess = getActiveSession();
    const usedTools = new Set();
    for (const tr of sess.turns || []) {
      for (const st of tr.steps || []) {
        if (st && st.name) usedTools.add(st.name);
      }
    }
    const specSteps = [
      {
        label: t("studio.chkClusters"),
        done: ["loop_proposals", "eval_failures", "round_report"].some((x) => usedTools.has(x)),
        slash: "/loop",
      },
      {
        label: t("studio.chkSystem"),
        done: ["findings", "job_list", "job_get", "log_tail"].some((x) => usedTools.has(x)),
        slash: "/findings",
      },
      {
        label: t("studio.chkCoverage"),
        done: ["dataset_stats", "qa_summary", "lineage", "ego_summary", "catalog_search"].some((x) =>
          usedTools.has(x)
        ),
        slash: "/catalog",
      },
      {
        label: t("studio.chkCompare"),
        done: ["eval_summary", "run_list", "run_metrics", "run_compare", "round_report"].some((x) =>
          usedTools.has(x)
        ),
        slash: "/runs",
      },
      {
        label: t("studio.chkBudget"),
        done: ["ledger_query", "propose_job"].some((x) => usedTools.has(x)),
        slash: "/ledger",
      },
    ];

    setChildren(
      railChecklistBox,
      el("span", { className: "eyebrow", text: t("studio.specChecklistTitle") }),
      el(
        "div",
        { className: "stack-sm", style: "margin-top:4px" },
        specSteps.map((st) =>
          el("div", { className: "task-head", style: "font-size:11.5px" }, [
            el("span", {
              style: st.done ? "color:var(--green);font-weight:650" : "color:var(--soft)",
              text: `${st.done ? "✓" : "○"} ${st.label}`,
            }),
            !state.locked
              ? el(
                  "button",
                  {
                    type: "button",
                    className: cls("turn-action-btn", "mono"),
                    style: "padding:1px 6px;font-size:10px",
                    onClick: () =>
                      runSharedTurn(st.slash, {
                        routeOverride: "#/home",
            
                      }),
                  },
                  [st.slash]
                )
              : null,
          ])
        )
      )
    );
  };

  const renderRailApi = () => {
    const cfg = chatStore.apiConfig;
    const isConfigured = cfg && cfg.active_kind && cfg.active_kind !== "ollama";
    const ready = Boolean(isConfigured && cfg.ready);
    const provLabel = isConfigured ? cfg.provider : "API";
    const fullModel = isConfigured ? cfg.active_model : "";
    const modLabel = isConfigured ? shortModelLabel(fullModel) : "-";
    const remModels = Array.isArray(chatStore.remoteModels) ? chatStore.remoteModels : [];
    const modelOptions = Array.from(new Set([fullModel, ...remModels].filter(Boolean)));

    const liveModelSelect =
      ready && !state.locked && modelOptions.length > 0
        ? el(
            "select",
            {
              className: cls("field", "mono"),
              style: "width:100%;font-size:11px;margin-top:4px",
              onChange: (ev) => switchActiveApiModel(ev.target.value),
            },
            modelOptions.map((mId) =>
              el("option", { value: mId, selected: mId === fullModel, text: mId })
            )
          )
        : null;

    setChildren(
      railApiBox,
      el("div", { className: "task-head" }, [
        el("span", { className: "eyebrow", text: t("studio.apiCardTitle") }),
        el("span", {
          className: cls("status-dot", ready ? "warm" : "cold"),
        }),
      ]),
      el("b", {
        className: "mono",
        style: "font-size:12px",
        text: ready ? `${provLabel} · ${modLabel}` : t("studio.apiNeedsKey"),
      }),
      liveModelSelect,
      el("span", {
        className: "tiny muted",
        text: t("studio.publicShield"),
      }),
      !state.locked
        ? el(
            "button",
            {
              type: "button",
              className: cls("btn", ready ? "" : "primary"),
              style: "margin-top:4px;width:100%;justify-content:center",
              onClick: () => { closeDrawer(); openApiConfigModal(); },
            },
            [t("studio.apiConfigureBtn")]
          )
        : null
    );
  };

  const renderRailPinned = () => {
    const sess = getActiveSession();
    const curTask = getCurrentTask();
    const curRound = getCurrentRound();
    const pins = sess.pinned || [];

    const addSelect = el(
      "select",
      {
        className: "field",
        style: "width:100%;font-size:11.5px;margin-top:6px",
        onChange: (ev) => {
          const val = ev.target.value;
          if (!val) return;
          const hit = mentionEntities.find((m) => m.id === val);
          if (hit) addSessionPin(hit);
          ev.target.value = "";
        },
      },
      [
        el("option", { value: "", text: t("studio.pinAddPlaceholder") }),
        ...mentionEntities.map((m) =>
          el("option", { value: m.id, text: `@${m.id} — ${m.label}` })
        ),
      ]
    );

    setChildren(
      railPinnedBox,
      el("span", { className: "eyebrow", text: t("studio.pinnedTitle") }),
      el("div", { className: "tag-row", style: "margin-top:6px" }, [
        curTask
          ? el("span", {
              className: "tax-badge",
              text: `task:${curTask.id}`,
            })
          : null,
        curRound
          ? el("span", {
              className: "tax-badge",
              text: `round:${curRound.id}`,
            })
          : null,
        ...pins.map((p) =>
          el("span", { className: cls("ctx-pill", "mono") }, [
            `@${p.id}`,
            el(
              "button",
              {
                type: "button",
                onClick: () => removeSessionPin(p.id),
              },
              ["×"]
            ),
          ])
        ),
      ]),
      mentionEntities.length > 0 ? addSelect : null
    );
  };

  // ------------------------------------------------------------------ Center Header & Stream
  const renderCenterHeader = () => {
    const sess = getActiveSession();
    centerHeadTitle.textContent = sess.title || t("studio.untitledSession");
    const activeMode = sess.mode || "ask";


    setChildren(
      modeBar,
      ...MODES.map((m) =>
        el(
          "button",
          {
            type: "button",
            title: t(m.subKey),
            "aria-pressed": String(activeMode === m.id),
            className: cls("mode-btn", activeMode === m.id && "is-active"),
            onClick: () => setSessionMode(m.id),
          },
          [t(m.labelKey)]
        )
      )
    );

    wbToggleBtn.textContent = t("analysis.evidence");
  };

  const showWorkbench = () => {
    renderWorkbench();
    showDrawer(t("analysis.evidence"), wbPane);
  };
  wbToggleBtn.addEventListener("click", showWorkbench);

  const openArtifactInWorkbench = (artId) => {
    chatStore.activeArtifactId = artId;
    wbTab = "artifact";
    showWorkbench();
  };

  const renderResults = (turn) => {
    const artifacts = getActiveSession().artifacts || [];
    const results = (turn.steps || []).map((step) => ({
      step, ui: step.ui || artifacts.find((item) => item.id === step.artifactId)?.ui,
    })).filter(({ step, ui }) => step.ok && ui && !["log", "text"].includes(ui.type));
    if (!results.length) return [];
    const panel = el("section", { className: "analysis-result" });
    const output = el("div");
    const draw = (index) => {
      const { step, ui } = results[index];
      const resultBody = el("div", {}, [renderToolUi(ui, { large: true })]);
      const controls = el("div", { className: "analysis-prompts" });
      if (["bar", "line"].includes(ui.type) && Array.isArray(ui.series)) {
        let tableVisible = false;
        const toggle = el("button", { type: "button", className: "link", text: t("chart.showTable"),
          onClick: () => {
            tableVisible = !tableVisible;
            toggle.textContent = t(tableVisible ? "chart.showChart" : "chart.showTable");
            if (tableVisible) {
              const rows = ui.series.flatMap((series) => {
                const points = ui.type === "line" ? series.points || [] :
                  (series.values || []).map((value, i) => [ui.categories?.[i] ?? i, value]);
                return points.map(([x, y]) => el("tr", {}, [series.name, x, y].map((value) =>
                  el("td", { text: value ?? t("state.na") }))));
              });
              setChildren(resultBody, el("div", { className: "mini-table-wrap" }, [
                el("table", { className: "table" }, [
                  el("thead", {}, [el("tr", {}, [t("analysis.series"), "X", "Y"].map((label) =>
                    el("th", { text: label })))]),
                  el("tbody", {}, rows),
                ]),
              ]));
            } else setChildren(resultBody, renderToolUi(ui, { large: true }));
            requestAnimationFrame(resizeChatCharts);
          } });
        controls.appendChild(toggle);
      }
      if (step.artifactId && artifacts.some((item) => item.id === step.artifactId)) {
        controls.appendChild(el("button", { type: "button", className: "link", text: t("analysis.source"),
          onClick: () => openArtifactInWorkbench(step.artifactId) }));
      }
      setChildren(output, resultBody, controls);
    };
    if (results.length > 1) {
      panel.appendChild(el("select", { className: "field", "aria-label": t("analysis.result"),
        onChange: (event) => draw(Number(event.target.value)) },
        results.map(({ step, ui }, index) => el("option", { value: String(index),
          text: ui.title || step.name, selected: index === results.length - 1 }))));
    }
    panel.appendChild(output);
    draw(results.length - 1);
    return [panel];
  };

  const renderStudioTurn = (tr) => {
    const wrap = el("div", { className: "studio-turn-pair" });
    wrap.appendChild(el("div", { className: "user-turn", text: tr.question }));

    const isRunning = Boolean(chatStore.running && tr.phase && tr.phase !== "done");
    const mdZone = el("div", { className: "md-body" });
    if (tr.answer || isRunning) {
      renderMarkdownInto(mdZone, tr.answer || "", isRunning && !tr.steps.some((s) => s.ms === null));
    }

    const tokMeta =
      tr.tokensIn || tr.tokensOut
        ? `${formatNumber(tr.tokensIn || 0)} in · ${formatNumber(tr.tokensOut || 0)} out`
        : tr.msTotal
          ? `${(tr.msTotal / 1000).toFixed(2)} s`
          : "";

    const copyBtn = el("button", {
      type: "button",
      className: "turn-action-btn",
      text: t("chat.copyBtn"),
    });
    copyBtn.addEventListener("click", () => copyText(tr.answer || "", copyBtn));

    const retryBtn = el("button", {
      type: "button",
      className: "turn-action-btn",
      text: t("chat.retryBtn"),
      onClick: () => {
        if (!chatStore.running) {
          runSharedTurn(tr.question, {
            routeOverride: "#/home",
          });
        }
      },
    });

    const card = el("article", { className: cls("agent-turn", "studio-agent-card") }, [
      el("div", { className: "turn-header" }, [
        el("span", {
          className: "turn-header-brand",
          text: tr.kind === "slash" ? `⚡ ${tr.question.split(/\s+/)[0]}` : `✦ ${t("chat.title")}`,
        }),
        isRunning
          ? el("span", { className: "turn-badge-live" }, [
              el("span", { className: "pulse-dot" }),
              el("span", { text: t(tr.phase === "tools" ? "analysis.reading" : tr.phase === "scope" ? "analysis.scoping" : "chat.statusStreaming") }),
            ])
          : null,
      ]),

      tr.answer || isRunning ? mdZone : null,
      tr.steps?.some((step) => step.ok === false)
        ? el("p", { className: "missing-item", text: t("analysis.partial") }) : null,
      Array.isArray(tr.unverified) && tr.unverified.length > 0
        ? el("div", {
            className: "missing-item",
            text: t("chat.unverifiedWarn", { nums: tr.unverified.join(", ") }),
          })
        : null,

      tr.error ? el("div", { className: "missing-item", text: tr.error }) : null,

      ...renderResults(tr),
      (tr.steps || []).length > 0
        ? el("details", { className: "analysis-activity" }, [
            el("summary", { text: t("analysis.activity", { count: tr.steps.length }) }),
            tokMeta ? el("small", { className: "muted", text: tokMeta }) : null,
            el("div", { className: "agent-steps" },
            tr.steps.map((st) =>
              el("div", { className: "studio-tool-pill" }, [
                el("span", {
                  className: cls(
                    "step-status-icon",
                    st.ms === null && "running",
                    st.ms !== null && !st.ok && "err"
                  ),
                  text: st.ms === null ? "⚙" : st.ok ? "✓" : "!",
                }),
                el("b", { text: st.ui?.title || st.name }),
                st.ui?.type === "text" && st.ui.text ? el("small", { text: st.ui.text }) : null,
                el("span", {
                  className: cls("step-ms", "mono"),
                  text: st.ms === null ? "…" : `${st.ms} ms`,
                }),
                getActiveSession().artifacts?.some((item) => item.id === st.artifactId)
                  ? el(
                      "button",
                      {
                        type: "button",
                        className: "turn-action-btn",
                        onClick: () => openArtifactInWorkbench(st.artifactId),
                      },
                      [t("studio.openInWorkbench")]
                    )
                  : null,
              ])
            )
          )])
        : null,

      tr.navigate
        ? el(
            "a",
            {
              className: cls("btn", "primary"),
              href: tr.navigate.startsWith("#")
                ? tr.navigate
                : `#/${String(tr.navigate).replace(/^\/+/, "")}`,
            },
            [t("chat.openSuggested", { route: tr.navigate })]
          )
        : null,

      !isRunning && (tr.answer || tr.groundedCount > 0 || (tr.steps || []).length > 0)
        ? (() => {
            const overrideWrap = el("div", { hidden: true, style: "margin-top:6px;width:100%" });
            const ovInput = el("input", {
              type: "text",
              className: "field",
              style: "width:100%;font-size:11.5px",
              placeholder: t("studio.overridePlaceholder"),
            });
            setChildren(
              overrideWrap,
              el("div", { className: "tag-row" }, [
                ovInput,
                el(
                  "button",
                  {
                    type: "button",
                    className: cls("btn", "primary"),
                    onClick: () => {
                      if (!ovInput.value.trim()) return;
                      recordSessionReview(tr.id, "override", ovInput.value.trim());
                      overrideWrap.hidden = true;
                      wbTab = "review";
                      showWorkbench();
                    },
                  },
                  [t("studio.overrideSave")]
                ),
              ])
            );

            const agreeBtn = el(
              "button",
              {
                type: "button",
                className: "turn-action-btn",
                onClick: () => {
                  recordSessionReview(tr.id, "agree", tr.question);
                  wbTab = "review";
                  showWorkbench();
                },
              },
              [t("studio.btnAgree")]
            );
            const ovBtn = el(
              "button",
              {
                type: "button",
                className: "turn-action-btn",
                onClick: () => {
                  overrideWrap.hidden = !overrideWrap.hidden;
                  if (!overrideWrap.hidden) ovInput.focus();
                },
              },
              [t("studio.btnOverride")]
            );

            return el("div", { className: "stack-sm" }, [
              el("div", { className: "turn-footer" }, [
                tr.groundedCount > 0 && (!tr.unverified || tr.unverified.length === 0)
                  ? el("span", {
                      className: "grounded-pill",
                      text: t("chat.groundedOk", { count: formatNumber(tr.groundedCount) }),
                    })
                  : null,
                el("div", { className: "turn-actions" }, [
                  agreeBtn,
                  ovBtn,
                  tr.answer ? copyBtn : null,
                  retryBtn,
                ]),
              ]),
              overrideWrap,
            ]);
          })()
        : null,
    ]);

    wrap.appendChild(card);
    return wrap;
  };

  const rendered = new Map();
  const jumpLatest = el("button", { type: "button", className: "analysis-latest topbtn", hidden: true,
    text: t("analysis.latest"), onClick: () => { streamBox.scrollTop = streamBox.scrollHeight; jumpLatest.hidden = true; } });

  const renderStream = () => {
    const sess = getActiveSession();
    const turns = sess.turns || [];
    if (turns.length === 0) {
      setChildren(streamBox, el("div", { className: "analysis-start" }, [
        el("h1", { text: t("analysis.title") }),
        el("div", { className: "analysis-prompts" }, [
          [t("analysis.summary"), t("analysis.summaryPrompt")],
          [t("analysis.compare"), t("analysis.comparePrompt")],
          [t("analysis.failures"), t("analysis.failuresPrompt")],
        ].map(([label, prompt]) =>
          el("button", { type: "button", className: "btn", text: label,
            onClick: () => { textarea.value = prompt; textarea.focus(); } })
        )),
      ]));
      rendered.clear();
      streamBox.dataset.session = sess.id;
      return;
    }
    const switched = streamBox.dataset.session !== sess.id;
    const atEnd = streamBox.scrollHeight - streamBox.clientHeight - streamBox.scrollTop < 48;
    const position = streamBox.scrollTop;
    if (switched || !rendered.size) {
      streamBox.replaceChildren();
      rendered.clear();
    }
    streamBox.dataset.session = sess.id;
    for (const turn of turns) {
      const previous = rendered.get(turn.id);
      const signature = JSON.stringify([turn.phase, turn.phase && turn.phase !== "done" && chatStore.running, turn.steps?.map((s) => [s.ms, s.ok, s.artifactId]),
        turn.groundedCount, turn.unverified, turn.error, turn.stopped, turn.navigate, turn.msTotal]);
      if (previous && previous.signature === signature) {
        if (previous.answer !== turn.answer) {
          const target = previous.node.querySelector(".md-body");
          if (target) renderMarkdownInto(target, turn.answer || "", Boolean(turn.phase && turn.phase !== "done"));
          previous.answer = turn.answer;
        }
        continue;
      }
      const node = renderStudioTurn(turn);
      if (previous) {
        const activity = node.querySelector(".analysis-activity");
        if (activity && previous.node.querySelector(".analysis-activity")?.open) activity.open = true;
        previous.node.replaceWith(node);
        requestAnimationFrame(resizeChatCharts);
      } else streamBox.appendChild(node);
      rendered.set(turn.id, { node, signature, answer: turn.answer });
    }
    streamBox.scrollTop = switched || atEnd ? streamBox.scrollHeight : position;
    jumpLatest.hidden = switched || atEnd;
  };

  // ------------------------------------------------------------------ Right Workbench
  const renderWorkbench = () => {
    const sess = getActiveSession();
    const arts = sess.artifacts || [];
    const facts = sess.facts || [];
    const reviews = sess.reviews || [];
    setChildren(
      wbTabsBar,
      ...[
        { id: "artifact", label: `${t("studio.wbTabArtifact")}${arts.length ? ` (${arts.length})` : ""}` },
        { id: "facts", label: `${t("studio.wbTabFacts")}${facts.length ? ` (${facts.length})` : ""}` },
        { id: "review", label: `${t("studio.wbTabReview")}${reviews.length ? ` (${reviews.length})` : ""}` },
        { id: "trace", label: t("studio.wbTabTrace") },
      ].map((tb) =>
        el(
          "button",
          {
            type: "button",
            className: cls("tab", wbTab === tb.id && "active"),
            onClick: () => {
              wbTab = tb.id;
              renderWorkbench();
              window.setTimeout(resizeChatCharts, 60);
            },
          },
          [tb.label]
        )
      )
    );

    if (wbTab === "facts") {
      if (facts.length === 0) {
        setChildren(wbBody, el("div", { className: "empty", text: t("studio.factsEmpty") }));
        return;
      }
      setChildren(
        wbBody,
        el("div", { className: cls("card", "table-wrap") }, [
          el("table", { className: "table" }, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", { text: "ID" }),
                el("th", { text: t("common.source") }),
                el("th", { text: t("ds.attrName") }),
                el("th", { text: "Value" }),
              ]),
            ]),
            el(
              "tbody",
              {},
              facts.map((f) =>
                el("tr", {}, [
                  el("td", {}, [el("span", { className: "tax-badge", text: `{${f.id}}` })]),
                  el("td", { className: "mono", text: `${f.source} · ${f.tool}` }),
                  el("td", { text: f.label }),
                  el("td", { className: "mono", text: f.value }),
                ])
              )
            ),
          ]),
        ])
      );
      return;
    }

    if (wbTab === "review") {
      setChildren(
        wbBody,
        el("div", { className: "stack-sm" }, [
          el("div", { className: "sources-note", text: t("studio.capsNote") }),
          reviews.length === 0
            ? el("div", { className: "empty", text: t("studio.reviewEmpty") })
            : el(
                "div",
                { className: "stack-sm" },
                reviews.map((rv) =>
                  el("div", { className: "card" }, [
                    el("div", { className: "task-head" }, [
                      el("span", {
                        className: "tax-badge",
                        text: rv.decision,
                      }),
                      el("span", { className: cls("tiny", "mono"), text: rv.ts.slice(0, 19) }),
                    ]),
                    el("p", { style: "margin-top:6px", text: rv.note || "-" }),
                  ])
                )
              ),
        ])
      );
      return;
    }

    if (wbTab === "trace") {
      const box = el("div", { className: "stack-sm" });
      setChildren(wbBody, box);
      loadChatDiagnostics(box);
      return;
    }

    if (wbTab === "scope") {
      const curTask = getCurrentTask();
      const curRound = getCurrentRound();
      const sr = storyCache && storyCache.round ? storyCache.round : null;
      const chain = (sr && sr.chain) || {};
      const pins = sess.pinned || [];
      const catRows = (catalogCache && catalogCache.rows) || [];

      setChildren(
        wbBody,
        el("div", { className: "stack-sm" }, [
          curTask
            ? el("div", { className: "card" }, [
                el("span", { className: "eyebrow", text: t("header.taskLabel") }),
                el("h3", { text: pickLang(curTask.name) || curTask.id }),
                el("p", { className: "tiny muted", text: pickLang(curTask.description) || "" }),
              ])
            : null,
          curRound
            ? el("div", { className: "card" }, [
                el("span", { className: "eyebrow", text: t("header.roundLabel") }),
                el("h3", { text: pickLang(curRound.title) || curRound.id }),
                Object.keys(chain).length > 0
                  ? el(
                      "div",
                      { className: "meta-strip", style: "margin-top:8px" },
                      Object.entries(chain)
                        .slice(0, 6)
                        .map(([k, v]) =>
                          el("div", { className: "meta-box" }, [
                            el("span", { className: "mono", text: k }),
                            el("b", { className: "mono", text: formatNumber(v) }),
                          ])
                        )
                    )
                  : null,
              ])
            : null,
          ...pins.map((p) => {
            const ds = catRows.find((r) => r.id === p.id);
            return el("div", { className: "card" }, [
              el("div", { className: "task-head" }, [
                el("b", { className: "mono", text: `@${p.id}` }),
                ds
                  ? el("a", { className: "link", href: `#/data/${encodeURIComponent(ds.id)}` }, [
                      t("common.open"),
                    ])
                  : null,
              ]),
              ds
                ? el("p", {
                    className: "tiny mono",
                    text: `${ds.format || "-"} · ${formatNumber(ds.episodes || 0)} ep · ${shortHashId(ds.id)}`,
                  })
                : el("p", { className: "tiny muted", text: p.label || p.kind }),
            ]);
          }),
        ])
      );
      return;
    }

    // wbTab === "artifact"
    if (arts.length === 0) {
      setChildren(
        wbBody,
        el("div", { className: "empty" }, [
          el("b", { text: t("studio.wbEmptyTitle") }),
          el("p", { style: "margin-top:6px", text: t("studio.wbEmptySub") }),
        ])
      );
      return;
    }

    const activeArt =
      arts.find((a) => a.id === chatStore.activeArtifactId) || arts[arts.length - 1];
    chatStore.activeArtifactId = activeArt.id;

    const jsonCopyBtn = el("button", {
      type: "button",
      className: cls("turn-action-btn", "mono"),
      text: t("studio.copyJson"),
    });
    jsonCopyBtn.addEventListener("click", () =>
      copyText(JSON.stringify(activeArt.ui, null, 2), jsonCopyBtn)
    );

    setChildren(
      wbBody,
      arts.length > 1
        ? el(
            "div",
            { className: "tag-row", style: "margin-bottom:10px" },
            arts.map((a, idx) =>
              el(
                "button",
                {
                  type: "button",
                  className: cls(
                    "turn-action-btn",
                    "mono",
                    a.id === activeArt.id && "is-selected"
                  ),
                  onClick: () => {
                    chatStore.activeArtifactId = a.id;
                    renderWorkbench();
                    window.setTimeout(resizeChatCharts, 60);
                  },
                },
                [`#${idx + 1} ${a.name}`]
              )
            )
          )
        : null,
      el("div", { className: "card" }, [
        el("div", { className: "task-head", style: "margin-bottom:10px" }, [
          el("div", {}, [
            el("b", { className: "mono", text: activeArt.name }),
            el("div", {
              className: cls("tiny", "mono"),
              text: formatArgsChip(Object.fromEntries(Object.entries(activeArt.args || {}).filter(
                ([key]) => !/token|passw|secret|credential|api.?key|authorization/i.test(key)
              ))),
            }),
          ]),
          jsonCopyBtn,
        ]),
        renderToolUi(activeArt.ui, { large: true }),
      ])
    );
  };

  // ------------------------------------------------------------------ Composer (/ & @ menus)
  const updateComposerMenu = () => {
    const val = textarea.value;
    if (val.startsWith("/") && !val.includes("\n") && !val.includes(" ") && !state.locked) {
      const tok = val.toLowerCase();
      const matches = (chatStore.toolsList || []).filter((tl) => {
        const sl = String(tl.slash || `/${tl.name}`).toLowerCase();
        return sl.startsWith(tok) || `/${tl.name}`.toLowerCase().startsWith(tok);
      });
      if (matches.length === 0) {
        popupMenu.hidden = true;
        return;
      }
      slashMenuIdx = Math.max(0, Math.min(matches.length - 1, slashMenuIdx));
      setChildren(
        popupMenu,
        el("div", { className: "slash-menu-head", text: t("chat.slashTitle") }),
        ...matches.map((tl, idx) => {
          const reqs = ((tl.parameters && tl.parameters.required) || [])
            .map((k) => `<${k}>`)
            .join(" ");
          const cmd = tl.slash || `/${tl.name}`;
          return el(
            "button",
            {
              type: "button",
              className: cls("slash-item", idx === slashMenuIdx && "is-selected"),
              onClick: () => {
                textarea.value = reqs ? `${cmd} ` : cmd;
                popupMenu.hidden = true;
                textarea.focus();
                if (!reqs) submitTurn();
              },
            },
            [
              el("span", { className: cls("slash-cmd", "mono"), text: `${cmd}${reqs ? ` ${reqs}` : ""}` }),
              el("span", { className: "slash-desc", text: tl.description || "" }),
            ]
          );
        })
      );
      popupMenu.hidden = false;
      popupMenu._mode = "slash";
      popupMenu._items = matches;
      return;
    }

    const atMatch = val.match(/(?:^|\s)@([A-Za-z0-9_-]*)$/);
    if (atMatch && mentionEntities.length > 0) {
      const needle = atMatch[1].toLowerCase();
      const matches = mentionEntities.filter(
        (m) => m.id.toLowerCase().includes(needle) || m.label.toLowerCase().includes(needle)
      );
      if (matches.length === 0) {
        popupMenu.hidden = true;
        return;
      }
      slashMenuIdx = Math.max(0, Math.min(matches.length - 1, slashMenuIdx));
      setChildren(
        popupMenu,
        el("div", { className: "slash-menu-head", text: t("studio.mentionTitle") }),
        ...matches.slice(0, 8).map((m, idx) =>
          el(
            "button",
            {
              type: "button",
              className: cls("slash-item", idx === slashMenuIdx && "is-selected"),
              onClick: () => {
                textarea.value = val.replace(/@[A-Za-z0-9_-]*$/, `@${m.id} `);
                addSessionPin(m);
                popupMenu.hidden = true;
                textarea.focus();
              },
            },
            [
              el("span", { className: cls("slash-cmd", "mono"), text: `@${m.id}` }),
              el("span", { className: "slash-desc", text: m.label }),
            ]
          )
        )
      );
      popupMenu.hidden = false;
      popupMenu._mode = "mention";
      popupMenu._items = matches.slice(0, 8);
      return;
    }

    popupMenu.hidden = true;
  };

  const submitTurn = () => {
    if (chatStore.running && chatStore.abortCtrl) {
      chatStore.abortCtrl.abort();
      return;
    }
    const q = textarea.value.trim();
    if (!q) return;
    textarea.value = "";
    popupMenu.hidden = true;
    runSharedTurn(q, {
      routeOverride: "#/home",
    });
  };

  const textarea = el("textarea", {
    rows: "1",
    "aria-label": t("chat.placeholder"),
    placeholder: t("chat.placeholder"),
    onInput: () => {
      slashMenuIdx = 0;
      updateComposerMenu();
    },
    onKeydown: (ev) => {
      if (!popupMenu.hidden && Array.isArray(popupMenu._items) && popupMenu._items.length > 0) {
        const list = popupMenu._items;
        if (ev.key === "ArrowDown") {
          ev.preventDefault();
          slashMenuIdx = (slashMenuIdx + 1) % list.length;
          updateComposerMenu();
          return;
        }
        if (ev.key === "ArrowUp") {
          ev.preventDefault();
          slashMenuIdx = (slashMenuIdx - 1 + list.length) % list.length;
          updateComposerMenu();
          return;
        }
        if (ev.key === "Tab") {
          ev.preventDefault();
          const chosen = list[slashMenuIdx];
          if (chosen) {
            if (popupMenu._mode === "slash") {
              textarea.value = `${chosen.slash || `/${chosen.name}`} `;
            } else {
              textarea.value = textarea.value.replace(/@[A-Za-z0-9_-]*$/, `@${chosen.id} `);
              addSessionPin(chosen);
            }
            popupMenu.hidden = true;
          }
          return;
        }
        if (ev.key === "Escape") {
          popupMenu.hidden = true;
          return;
        }
      }
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        submitTurn();
      }
    },
  });

  const sendBtn = el(
    "button",
    {
      type: "button",
      className: cls("btn", "primary"),
      onClick: () => submitTurn(),
    },
    [t("chat.send")]
  );

  const composerZone = el("div", { className: "studio-composer-zone" }, [
    popupMenu,
    el("div", { className: "composer" }, [
      textarea,
      el("div", { className: "composer-foot" }, [
        el("div", { className: "turn-actions" }, [
          !state.locked
            ? el(
                "button",
                {
                  type: "button",
                  className: cls("turn-action-btn", "mono"),
                  onClick: async () => {
                    await ensureRouteToolsLoaded("all");
                    textarea.value = "/";
                    textarea.focus();
                    updateComposerMenu();
                  },
                },
                [t("chat.slashBtn")]
              )
            : null,
          el(
            "button",
            {
              type: "button",
              className: cls("turn-action-btn", "mono"),
              onClick: () => {
                textarea.value = `${textarea.value}${textarea.value.endsWith(" ") || !textarea.value ? "" : " "}@`;
                textarea.focus();
                updateComposerMenu();
              },
            },
            [t("studio.mentionBtn")]
          ),
        ]),
        sendBtn,
      ]),
    ]),
  ]);

  const historyPanel = el("aside", { className: "studio-rail" }, [
      el(
        "button",
        {
          type: "button",
          className: cls("btn", "primary"),
          style: "width:100%;justify-content:center",
          onClick: () => { createNewSession(); closeDrawer(); },
        },
        [t("studio.newSession")]
      ),
      el("div", { className: "eyebrow", style: "margin-top:6px", text: t("studio.sessionsTitle") }),
      railSessionsBox,
      railPinnedBox,
      el("details", { className: "studio-details" }, [
        el("summary", { text: t("visual.tools") }),
        railChecklistBox,
        railApiBox,
      ]),
  ]);
  const layoutGrid = el("div", { className: "analysis-layout" }, [
    el("section", { className: "studio-center" }, [
      el("header", { className: "studio-center-head" }, [
        el("button", { type: "button", className: "topbtn", text: t("studio.sessionsTitle"),
          onClick: () => showDrawer(t("studio.sessionsTitle"), historyPanel) }),
        centerHeadTitle, modeBar, wbToggleBtn,
      ]),
      streamBox, jumpLatest, composerZone,
    ]),
    drawer,
  ]);

  const syncStudioLayout = () => {
    sendBtn.textContent = chatStore.running ? t("chat.stop") : t("chat.send");
    const chatDisabled = state.statusLoaded && !state.chatOn;
    textarea.disabled = chatDisabled;
    sendBtn.disabled = chatDisabled;
  };

  const refreshAll = () => {
    renderRailSessions();
    renderRailChecklist();
    renderRailApi();
    renderRailPinned();
    renderCenterHeader();
    renderStream();
    syncStudioLayout();
  };

  root.appendChild(layoutGrid);
  refreshAll();

  ensureRouteToolsLoaded("all");
  fetchApiConfig(false);
  loadContextEntities();

  const unsub = subscribeChatStore((reason) => {
    if (reason !== "stream") {
      renderRailSessions();
      renderRailChecklist();
      renderCenterHeader();
    }
    if (reason === "api-config") renderRailApi();
    if (reason === "pin" || reason === "session") renderRailPinned();
    renderStream();
    if (drawer.open && drawerBody.contains(wbPane) && reason !== "stream") {
      renderWorkbench();
    }
    syncStudioLayout();
  });

  onRouteCleanup(() => {
    if (drawer.open) drawer.close();
    unsub();
    emitChatStore("leave-studio");
  });

  return root;
}
