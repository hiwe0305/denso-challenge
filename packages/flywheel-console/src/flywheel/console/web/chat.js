import {
  clearSelection,
  cls,
  el,
  ensureModels,
  formatNumber,
  getJSON,
  postJSON,
  setChatOpen,
  setChildren,
  state,
  t,
  tryGetJSON,
} from "./core.js";

const STORAGE_KEY = "fw_agent_sessions_v1";

function makeId(prefix = "s") {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function loadSavedSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, 25) : [];
  } catch {
    return [];
  }
}

function createBlankSession() {
  return {
    id: makeId("sess"),
    title: "",
    mode: "ask",
    conversationId: null,
    messages: [],
    turns: [],
    artifacts: [],
    facts: [],
    reviews: [],
    pinned: [],
    updatedAt: Date.now(),
  };
}

const initialSessions = loadSavedSessions();
if (initialSessions.length === 0) {
  initialSessions.push(createBlankSession());
}

export const chatStore = {
  sessions: initialSessions,
  activeSessionId: initialSessions[0].id,
  activeArtifactId: null,
  running: false,
  abortCtrl: null,
  toolsList: [],
  wide: localStorage.getItem("fw_chat_wide") === "1",
  apiConfig: null,
  remoteModels: [],
  chartInstances: [],
};

const storeListeners = new Set();
const toolsCache = new Map();
const toolsInFlight = new Map();
let toolsTimer = null;
let els = null;
let stickBottom = true;
let slashIndex = 0;

export function subscribeChatStore(fn) {
  storeListeners.add(fn);
  return () => storeListeners.delete(fn);
}

function persistSessions() {
  try {
    const slim = chatStore.sessions.slice(0, 20).map((s) => ({
      id: s.id,
      title: s.title || "",
      mode: s.mode || "ask",
      conversationId: s.conversationId || null,
      messages: (s.messages || []).slice(-16),
      turns: (s.turns || []).slice(-12).map((tr) => ({
        id: tr.id,
        kind: tr.kind,
        question: tr.question,
        thinking: (tr.thinking || "").slice(0, 2000),
        answer: tr.answer || "",
        steps: (tr.steps || []).map((st) => ({
          callId: st.callId,
          name: st.name,
          args: st.args,
          ms: st.ms,
          ok: st.ok,
          artifactId: st.artifactId || null,
          ui: st.ui || null,
        })),
        navigate: tr.navigate || null,
        msTotal: tr.msTotal || 0,
        tokensIn: tr.tokensIn || 0,
        tokensOut: tr.tokensOut || 0,
        groundedCount: tr.groundedCount || 0,
        unverified: tr.unverified || [],
        error: tr.error || null,
        stopped: Boolean(tr.stopped),
      })),
      artifacts: (s.artifacts || []).slice(-14),
      facts: (s.facts || []).slice(-60),
      reviews: (s.reviews || []).slice(-30),
      pinned: (s.pinned || []).slice(0, 8),
      updatedAt: s.updatedAt || Date.now(),
    }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(slim));
  } catch {
    // Ignore storage quota errors.
  }
}

export function emitChatStore(reason = "update") {
  persistSessions();
  for (const fn of storeListeners) {
    try {
      fn(reason);
    } catch {
      // Keep other listeners running.
    }
  }
}

export function getActiveSession() {
  let found = chatStore.sessions.find((s) => s.id === chatStore.activeSessionId);
  if (!found) {
    found = createBlankSession();
    chatStore.sessions.unshift(found);
    chatStore.activeSessionId = found.id;
  }
  return found;
}

export function createNewSession() {
  if (chatStore.abortCtrl) chatStore.abortCtrl.abort();
  const s = createBlankSession();
  chatStore.sessions.unshift(s);
  chatStore.activeSessionId = s.id;
  chatStore.activeArtifactId = null;
  emitChatStore("session");
  renderSidePanelTurns();
  return s;
}

export function selectSession(sessionId) {
  const target = chatStore.sessions.find((s) => s.id === sessionId);
  if (!target) return;
  if (chatStore.abortCtrl) chatStore.abortCtrl.abort();
  chatStore.activeSessionId = target.id;
  const arts = target.artifacts || [];
  chatStore.activeArtifactId = arts.length > 0 ? arts[arts.length - 1].id : null;
  emitChatStore("session");
  renderSidePanelTurns();
}

export function deleteSession(sessionId) {
  chatStore.sessions = chatStore.sessions.filter((s) => s.id !== sessionId);
  if (chatStore.sessions.length === 0) {
    chatStore.sessions.push(createBlankSession());
  }
  if (!chatStore.sessions.some((s) => s.id === chatStore.activeSessionId)) {
    chatStore.activeSessionId = chatStore.sessions[0].id;
  }
  const active = getActiveSession();
  const arts = active.artifacts || [];
  chatStore.activeArtifactId = arts.length > 0 ? arts[arts.length - 1].id : null;
  emitChatStore("session");
  renderSidePanelTurns();
}

export function setSessionMode(mode) {
  const sess = getActiveSession();
  sess.mode = mode;
  emitChatStore("mode");
}

export function addSessionPin(pinObj) {
  const sess = getActiveSession();
  if (!Array.isArray(sess.pinned)) sess.pinned = [];
  if (!sess.pinned.some((p) => p.id === pinObj.id)) {
    sess.pinned.push(pinObj);
    emitChatStore("pin");
  }
}

export function removeSessionPin(pinId) {
  const sess = getActiveSession();
  sess.pinned = (sess.pinned || []).filter((p) => p.id !== pinId);
  emitChatStore("pin");
}

export function recordSessionReview(turnId, decision, note = "") {
  const sess = getActiveSession();
  if (!Array.isArray(sess.reviews)) sess.reviews = [];
  sess.reviews.push({
    id: makeId("rev"),
    turnId,
    decision,
    note: String(note || "").trim(),
    ts: new Date().toISOString(),
  });
  emitChatStore("review");
}

function cleanToolModelSummary(raw) {
  if (!raw) return "";
  return String(raw)
    .split("\n")
    .filter(
      (ln) =>
        !/^(DIRECT ANSWER|HOW TO ANSWER|CÂU TRẢ LỜI THẲNG|CÁCH TRẢ LỜI)/i.test(ln.trim())
    )
    .slice(0, 6)
    .join("\n")
    .trim();
}

function extractFactsFromTool(sess, toolName, args, ui, modelText) {
  if (!Array.isArray(sess.facts)) sess.facts = [];
  const nextSeq = () => `F${String(sess.facts.length + 1).padStart(3, "0")}`;

  if (ui && ui.type === "group" && Array.isArray(ui.items)) {
    for (const sub of ui.items) {
      extractFactsFromTool(sess, toolName, args, sub, "");
    }
    return;
  }
  if (ui && ui.type === "stat" && Array.isArray(ui.items)) {
    for (const it of ui.items.slice(0, 8)) {
      sess.facts.push({
        id: nextSeq(),
        source: "code",
        tool: toolName,
        label: String(it.label || toolName),
        value: String(it.value ?? "-"),
      });
    }
    return;
  }
  if (ui && ui.type === "table" && Array.isArray(ui.rows)) {
    sess.facts.push({
      id: nextSeq(),
      source: "code",
      tool: toolName,
      label: `${toolName}(${formatArgsChip(args) || "all"})`,
      value: `${ui.total ?? ui.rows.length} rows`,
    });
    return;
  }
  if (ui && (ui.type === "line" || ui.type === "bar") && Array.isArray(ui.series)) {
    sess.facts.push({
      id: nextSeq(),
      source: "code",
      tool: toolName,
      label: ui.title || toolName,
      value: `${ui.series.length} series`,
    });
    return;
  }
  const cleaned = cleanToolModelSummary(modelText);
  if (cleaned) {
    const firstLine = cleaned.split("\n").find((l) => l.trim()) || "";
    if (firstLine) {
      sess.facts.push({
        id: nextSeq(),
        source: "code",
        tool: toolName,
        label: toolName,
        value: firstLine.slice(0, 96),
      });
    }
  }
}

export async function fetchApiConfig(force = false) {
  if (chatStore.apiConfig && !force) return chatStore.apiConfig;
  const res = await tryGetJSON("/api/chat/config");
  if (res.ok && res.data) {
    chatStore.apiConfig = res.data;
    emitChatStore("api-config");
    if (res.data.ready && (chatStore.remoteModels.length === 0 || force)) {
      const rm = await tryGetJSON("/api/chat/remote_models");
      if (rm.ok && rm.data && Array.isArray(rm.data.models)) {
        chatStore.remoteModels = rm.data.models;
        emitChatStore("api-config");
      }
    }
  }
  return chatStore.apiConfig;
}

export async function switchActiveApiModel(newModelId) {
  if (!newModelId || state.locked) return;
  const cfg = chatStore.apiConfig || {};
  const saved = await postJSON("/api/chat/config", {
    preset: cfg.preset || "custom",
    base_url: cfg.base_url || "",
    model: newModelId,
    reasoning: cfg.reasoning || "off",
  });
  chatStore.apiConfig = saved;
  await ensureModels(true);
  emitChatStore("api-config");
  syncChatMeta();
}

function currentRouteHash() {
  return window.location.hash || "#/tasks";
}

function pageKeyFromHash(hash) {
  const clean = String(hash || "").replace(/^#\/?/, "");
  return clean.split("?")[0].split("/")[0] || "tasks";
}

function suggestionsForPage(pageKey) {
  if (pageKey === "data" || pageKey === "egoflow") {
    return [t("chat.sug.data1"), t("chat.sug.data2")];
  }
  if (pageKey === "runs") return [t("chat.sug.runs1"), t("chat.sug.default1")];
  if (pageKey === "eval" || pageKey === "loop" || pageKey === "diagnose") {
    return [t("chat.sug.eval1"), t("chat.sug.default2")];
  }
  if (pageKey === "jobs" || pageKey === "qa") return [t("chat.sug.jobs1"), t("chat.sug.default1")];
  return [t("chat.sug.default1"), t("chat.sug.default2")];
}

export function shortModelLabel(rawModel) {
  if (!rawModel) return "api";
  const tail = String(rawModel).split("/").pop() || String(rawModel);
  return tail.split(":")[0];
}

export function copyText(text, btn) {
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(text).then(() => {
    if (!btn) return;
    const orig = btn.textContent;
    btn.textContent = t("chat.copiedBtn");
    window.setTimeout(() => {
      btn.textContent = orig || t("chat.copyBtn");
    }, 1400);
  });
}

// ============================================================================
// Safe DOM Markdown & Route-Entity Renderer (zero innerHTML)
// ============================================================================
const INLINE_TOKEN_RE = /(`[^`]+`|\*\*[^*]+\*\*|#\/[A-Za-z0-9_./?=&%-]+)/g;

function renderInlineTokens(lineText) {
  const parts = String(lineText || "").split(INLINE_TOKEN_RE);
  const nodes = [];
  for (const part of parts) {
    if (!part) continue;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      nodes.push(el("code", { className: cls("md-inline-code", "mono"), text: part.slice(1, -1) }));
    } else if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      nodes.push(el("strong", { text: part.slice(2, -2) }));
    } else if (part.startsWith("#/")) {
      nodes.push(el("a", { className: cls("md-route-pill", "mono"), href: part }, [`${part} ↗`]));
    } else {
      nodes.push(part);
    }
  }
  return nodes;
}

export function splitThinkAndAnswer(rawText) {
  const text = String(rawText || "");
  const openIdx = text.indexOf("<think>");
  if (openIdx === -1) {
    return { thinking: "", answer: text, thinkingOpen: false };
  }
  const closeIdx = text.indexOf("</think>", openIdx + 7);
  if (closeIdx === -1) {
    return {
      thinking: text.slice(openIdx + 7).trim(),
      answer: text.slice(0, openIdx).trim(),
      thinkingOpen: true,
    };
  }
  return {
    thinking: text.slice(openIdx + 7, closeIdx).trim(),
    answer: (text.slice(0, openIdx) + text.slice(closeIdx + 8)).trim(),
    thinkingOpen: false,
  };
}

export function renderMarkdownInto(container, rawText, isStreaming = false) {
  const lines = String(rawText || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const ln = lines[i];

    if (ln.trim().startsWith("```")) {
      const lang = ln.trim().slice(3).trim() || "text";
      const codeLines = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      i += 1;
      const codeStr = codeLines.join("\n");
      const copyBtn = el("button", { type: "button", className: "mono", text: t("chat.copyBtn") });
      copyBtn.addEventListener("click", () => copyText(codeStr, copyBtn));
      blocks.push(
        el("div", { className: "md-code-block" }, [
          el("div", { className: cls("md-code-head", "mono") }, [el("span", { text: lang }), copyBtn]),
          el("pre", { className: "mono", text: codeStr }),
        ])
      );
      continue;
    }

    if (!ln.trim()) {
      i += 1;
      continue;
    }

    if (/^#{1,3}\s+/.test(ln)) {
      blocks.push(el("h4", {}, renderInlineTokens(ln.replace(/^#{1,3}\s+/, ""))));
      i += 1;
      continue;
    }

    if (/^\s*[-*•]\s+/.test(ln)) {
      const items = [];
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) {
        items.push(el("li", {}, renderInlineTokens(lines[i].replace(/^\s*[-*•]\s+/, ""))));
        i += 1;
      }
      blocks.push(el("ul", {}, items));
      continue;
    }

    if (/^\s*\d+[.)]\s+/.test(ln)) {
      const items = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(el("li", {}, renderInlineTokens(lines[i].replace(/^\s*\d+[.)]\s+/, ""))));
        i += 1;
      }
      blocks.push(el("ol", {}, items));
      continue;
    }

    const paraLines = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("```") &&
      !/^#{1,3}\s+/.test(lines[i]) &&
      !/^\s*[-*•]\s+/.test(lines[i]) &&
      !/^\s*\d+[.)]\s+/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i += 1;
    }
    blocks.push(el("p", {}, renderInlineTokens(paraLines.join(" "))));
  }

  if (isStreaming) {
    const cursor = el("span", { className: "stream-cursor" });
    if (blocks.length > 0) {
      blocks[blocks.length - 1].appendChild(cursor);
    } else {
      blocks.push(el("p", {}, [cursor]));
    }
  }

  setChildren(container, ...blocks);
}

// ============================================================================
// Rich Interactive Tool Artifact Renderer (Charts, Thumbs, Linked Tables, Logs)
// ============================================================================
function resolveRowHref(template, rowObj) {
  if (!template || !rowObj) return null;
  let out = String(template);
  out = out.replace(/\{([A-Za-z0-9_]+)\}/g, (_, k) =>
    rowObj[k] != null ? encodeURIComponent(String(rowObj[k])) : ""
  );
  return out.startsWith("#") ? out : `#/${out.replace(/^\/+/, "")}`;
}

function mountInlineChart(ui, large = false) {
  const host = el("div", {
    className: "chat-chart-host",
    style: large ? "height:320px" : "",
  });
  requestAnimationFrame(() => {
    if (!window.echarts || !document.body.contains(host)) return;
    const cs = getComputedStyle(document.documentElement);
    const soft = cs.getPropertyValue("--soft").trim();
    const line = cs.getPropertyValue("--line").trim();
    const palette = [1, 2, 3, 4, 5].map((i) => cs.getPropertyValue(`--s${i}`).trim());
    const inst = window.echarts.init(host);
    chatStore.chartInstances.push(inst);

    if (ui.type === "bar") {
      const cats = Array.isArray(ui.categories) ? ui.categories : [];
      const ser = Array.isArray(ui.series) ? ui.series : [];
      inst.setOption({
        animation: false,
        grid: { left: 44, right: 16, top: 26, bottom: 28 },
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: cats, axisLabel: { color: soft, fontSize: 10.5 } },
        yAxis: {
          type: "value",
          axisLabel: { color: soft, fontSize: 10.5 },
          splitLine: { lineStyle: { color: line } },
        },
        series: ser.map((s, idx) => ({
          name: s.name || "",
          type: "bar",
          data: s.values || [],
          itemStyle: { color: palette[idx % palette.length], borderRadius: [4, 4, 0, 0] },
        })),
      });
    } else {
      const ser = Array.isArray(ui.series) ? ui.series : [];
      inst.setOption({
        animation: false,
        grid: { left: 48, right: 16, top: 28, bottom: 28 },
        tooltip: { trigger: "axis" },
        legend: { top: 0, textStyle: { color: soft, fontSize: 10.5 } },
        xAxis: { type: "value", axisLabel: { color: soft, fontSize: 10.5 }, splitLine: { show: false } },
        yAxis: {
          type: ui.log_y ? "log" : "value",
          axisLabel: { color: soft, fontSize: 10.5 },
          splitLine: { lineStyle: { color: line } },
        },
        series: ser.map((s, idx) => ({
          name: s.name || "",
          type: "line",
          showSymbol: false,
          data: s.points || [],
          lineStyle: { width: large ? 2 : 1.6, color: palette[idx % palette.length] },
        })),
      });
    }
  });
  return el("div", {}, [
    ui.title ? el("div", { className: cls("tiny", "mono"), text: ui.title }) : null,
    host,
  ]);
}

export function isRichWorkbenchUi(ui) {
  if (!ui || typeof ui !== "object") return false;
  return ["bar", "line", "table", "thumbs", "confirm", "group", "stat", "log"].includes(ui.type);
}

export function renderToolUi(ui, opts = {}) {
  const large = Boolean(opts.large);
  if (!ui || typeof ui !== "object") return null;

  if (ui.type === "group" && Array.isArray(ui.items)) {
    return el(
      "div",
      { className: "stack-sm" },
      ui.items.map((sub) => renderToolUi(sub, opts)).filter(Boolean)
    );
  }

  if (ui.type === "text") {
    return el("div", { className: "muted", text: String(ui.text || "") });
  }

  if (ui.type === "stat" && Array.isArray(ui.items)) {
    return el(
      "div",
      { className: "meta-strip" },
      ui.items.map((it) =>
        el("div", { className: "meta-box" }, [
          el("span", { text: String(it.label || "") }),
          el("b", {
            className: "mono",
            style: "font-size:12px",
            text:
              typeof it.value === "number"
                ? formatNumber(it.value, { maximumFractionDigits: 3 })
                : String(it.value ?? "-"),
          }),
        ])
      )
    );
  }

  if (ui.type === "table" && Array.isArray(ui.rows)) {
    const cols = Array.isArray(ui.columns) ? ui.columns : [];
    const shown = ui.rows.slice(0, large ? 50 : 10);
    return el("div", { className: "stack-sm" }, [
      el("div", { className: "mini-table-wrap" }, [
        el("table", { className: "table" }, [
          el("thead", {}, [
            el(
              "tr",
              {},
              cols.map((c) => el("th", { text: c.label || c.key }))
            ),
          ]),
          el(
            "tbody",
            {},
            shown.map((r) => {
              const rowHref = resolveRowHref(ui.row_link, r);
              return el(
                "tr",
                {},
                cols.map((c, cIdx) => {
                  const valTxt =
                    typeof r[c.key] === "number"
                      ? formatNumber(r[c.key], { maximumFractionDigits: 3 })
                      : String(r[c.key] ?? "-");
                  if (cIdx === 0 && rowHref) {
                    return el("td", { className: "mono" }, [
                      el("a", { className: "link", href: rowHref }, [valTxt]),
                    ]);
                  }
                  return el("td", { text: valTxt });
                })
              );
            })
          ),
        ]),
      ]),
      ui.total != null || ui.link
        ? el("div", { className: "task-head" }, [
            ui.total != null
              ? el("span", {
                  className: "tiny",
                  text: t("chat.rowsShown", {
                    shown: formatNumber(shown.length),
                    total: formatNumber(ui.total),
                  }),
                })
              : el("span", {}),
            ui.link
              ? el(
                  "a",
                  {
                    className: "link",
                    style: "font-size:11px",
                    href: ui.link.startsWith("#") ? ui.link : `#/${String(ui.link).replace(/^\/+/, "")}`,
                  },
                  [t("chat.openTableLink")]
                )
              : null,
          ])
        : null,
    ]);
  }

  if (ui.type === "log") {
    const logStr = String(ui.text || "");
    const copyBtn = el("button", { type: "button", className: "mono", text: t("chat.copyBtn") });
    copyBtn.addEventListener("click", () => copyText(logStr, copyBtn));
    return el("div", { className: "md-code-block" }, [
      el("div", { className: cls("md-code-head", "mono") }, [
        el("span", { text: ui.title || "log" }),
        copyBtn,
      ]),
      el("pre", { className: "mono", text: logStr }),
    ]);
  }

  if (ui.type === "thumbs" && Array.isArray(ui.items)) {
    return el(
      "div",
      { className: "chat-thumb-grid" },
      ui.items.slice(0, large ? 16 : 8).map((it) => {
        const href = it.link
          ? it.link.startsWith("#")
            ? it.link
            : `#/${String(it.link).replace(/^\/+/, "")}`
          : null;
        const inner = [
          it.src
            ? el("img", {
                src: it.src,
                alt: it.label || "",
                loading: "lazy",
                onError: (ev) => {
                  ev.target.hidden = true;
                },
              })
            : null,
          el("span", { className: "mono", text: it.label || it.id || "" }),
        ];
        return href
          ? el("a", { className: "chat-thumb-item", href }, inner)
          : el("div", { className: "chat-thumb-item" }, inner);
      })
    );
  }

  if (ui.type === "confirm") {
    return el("div", { className: "meta-box" }, [
      el("b", { className: "mono", text: `${ui.kind} (${ui.host || "laptop"})` }),
      el("small", { className: "mono", text: ui.argv_preview || "" }),
      !state.locked
        ? el(
            "button",
            {
              type: "button",
              className: cls("btn", "primary"),
              style: "margin-top:6px",
              onClick: async () => {
                const job = await postJSON("/api/jobs", {
                  kind: ui.kind,
                  params: ui.params || {},
                });
                window.location.hash = `#/jobs?job=${encodeURIComponent(job.id)}`;
              },
            },
            [t("jobs.runKindBtn")]
          )
        : null,
    ]);
  }

  if (ui.type === "bar" || ui.type === "line") {
    return mountInlineChart(ui, large);
  }

  return null;
}

export function resizeChatCharts() {
  for (let i = chatStore.chartInstances.length - 1; i >= 0; i--) {
    const inst = chatStore.chartInstances[i];
    if (!inst || inst.isDisposed()) {
      chatStore.chartInstances.splice(i, 1);
    } else if (!document.body.contains(inst.getDom())) {
      inst.dispose();
      chatStore.chartInstances.splice(i, 1);
    } else {
      inst.resize();
    }
  }
}

// Debounced, cached per-route /api/tools loader; skipped while chat panel is closed (F5).
function scheduleToolsRefresh() {
  if (!state.chatOpen) return;
  const route = currentRouteHash();
  if (toolsCache.has(route)) {
    chatStore.toolsList = toolsCache.get(route);
    return;
  }
  if (toolsTimer) window.clearTimeout(toolsTimer);
  toolsTimer = window.setTimeout(async () => {
    toolsTimer = null;
    if (!state.chatOpen) return;
    const activeRoute = currentRouteHash();
    if (toolsCache.has(activeRoute)) {
      chatStore.toolsList = toolsCache.get(activeRoute);
      return;
    }
    if (toolsInFlight.has(activeRoute)) {
      await toolsInFlight.get(activeRoute);
      return;
    }
    const req = tryGetJSON(`/api/tools?route=${encodeURIComponent(activeRoute)}`).then((res) => {
      toolsInFlight.delete(activeRoute);
      if (res.ok && Array.isArray(res.data)) {
        toolsCache.set(activeRoute, res.data);
        if (currentRouteHash() === activeRoute) {
          chatStore.toolsList = res.data;
        }
      }
    });
    toolsInFlight.set(activeRoute, req);
    await req;
  }, 80);
}

export async function ensureRouteToolsLoaded(routeOverride = null) {
  const key = routeOverride === "all" ? "__all__" : routeOverride || currentRouteHash();
  if (toolsCache.has(key)) {
    chatStore.toolsList = toolsCache.get(key);
    return chatStore.toolsList;
  }
  const url =
    routeOverride === "all"
      ? "/api/tools"
      : `/api/tools?route=${encodeURIComponent(key)}`;
  const res = await tryGetJSON(url);
  if (res.ok && Array.isArray(res.data)) {
    toolsCache.set(key, res.data);
    chatStore.toolsList = res.data;
  }
  return chatStore.toolsList;
}

// ============================================================================
// Slash Command Argument Parser & Shared Turn Execution Engine
// ============================================================================
export function parseSlashArgs(toolSpec, rawRest) {
  const rest = String(rawRest || "").trim();
  if (!rest) return {};
  if (rest.startsWith("{")) {
    try {
      return JSON.parse(rest);
    } catch {
      return {};
    }
  }
  const props = (toolSpec.parameters && toolSpec.parameters.properties) || {};
  const reqKeys = (toolSpec.parameters && toolSpec.parameters.required) || [];
  const propNames = Object.keys(props);

  const out = {};
  const freeTokens = [];
  for (const tok of rest.split(/\s+/)) {
    const eq = tok.indexOf("=");
    if (eq > 0) {
      const k = tok.slice(0, eq);
      const v = tok.slice(eq + 1);
      out[k] = /^\d+$/.test(v) ? Number(v) : v;
    } else {
      freeTokens.push(tok);
    }
  }
  if (freeTokens.length > 0) {
    const primaryKey = reqKeys[0] || propNames[0];
    if (primaryKey && out[primaryKey] === undefined) {
      const pType = props[primaryKey] && props[primaryKey].type;
      if (pType === "array") {
        out[primaryKey] = freeTokens.join(",").split(",").filter(Boolean);
      } else if (pType === "integer") {
        out[primaryKey] = Number(freeTokens[0]) || freeTokens[0];
      } else {
        out[primaryKey] = freeTokens.length === 1 ? freeTokens[0] : freeTokens.join(" ");
      }
      if (freeTokens.length > 1 && reqKeys.length >= 2 && out[reqKeys[1]] === undefined) {
        out[reqKeys[0]] = freeTokens[0];
        out[reqKeys[1]] = freeTokens[1];
      }
    }
  }
  return out;
}

export function formatArgsChip(args) {
  if (!args || typeof args !== "object") return "";
  const entries = Object.entries(args).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (entries.length === 0) return "";
  return entries
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : v}`)
    .join(" · ");
}

function registerArtifact(sess, name, args, ui) {
  if (!isRichWorkbenchUi(ui)) return null;
  const art = {
    id: makeId("art"),
    name,
    args,
    ui,
    ts: Date.now(),
  };
  if (!Array.isArray(sess.artifacts)) sess.artifacts = [];
  sess.artifacts.push(art);
  chatStore.activeArtifactId = art.id;
  return art.id;
}

export async function runSharedTurn(rawQuestion, opts = {}) {
  const question = String(rawQuestion || "").trim();
  if (!question) return;
  if (chatStore.running && chatStore.abortCtrl) {
    chatStore.abortCtrl.abort();
    return;
  }

  const sess = getActiveSession();
  const route = opts.routeOverride || currentRouteHash();
  if (!sess.title) {
    sess.title = question.replace(/^\//, "").slice(0, 42);
  }
  sess.updatedAt = Date.now();
  stickBottom = true;

  // 1. Direct /slash tool execution (instant, zero API tokens needed)
  if (!state.locked && question.startsWith("/")) {
    await ensureRouteToolsLoaded("all");
    const cmd = question.split(/\s+/)[0];
    const rest = question.slice(cmd.length).trim();
    const matched = (chatStore.toolsList || []).find(
      (tl) => tl.slash === cmd || `/${tl.name}` === cmd
    );
    if (matched) {
      const argsObj = parseSlashArgs(matched, rest);
      const t0 = performance.now();
      let res;
      try {
        res = await getJSON(
          `/api/tool?name=${encodeURIComponent(matched.name)}&args=${encodeURIComponent(JSON.stringify(argsObj))}&route=${encodeURIComponent(route)}`
        );
      } catch (err) {
        res = { ok: false, ui: null, model: (err && err.message) || t("error.network") };
      }
      const elapsed = Math.round(performance.now() - t0);
      const artId = registerArtifact(sess, matched.name, argsObj, res.ui);
      extractFactsFromTool(sess, matched.name, argsObj, res.ui, res.model);
      const slashTurn = {
        id: makeId("turn"),
        kind: "slash",
        question,
        thinking: "",
        answer: res.answer || cleanToolModelSummary(res.model),
        steps: [
          {
            callId: makeId("call"),
            name: matched.name,
            args: argsObj,
            ms: elapsed,
            ok: Boolean(res.ok),
            ui: res.ui || null,
            artifactId: artId,
          },
        ],
        navigate: res.navigate || null,
        msTotal: elapsed,
        tokensIn: 0,
        tokensOut: 0,
        groundedCount: 0,
        unverified: [],
        phase: "done",
      };
      sess.turns.push(slashTurn);
      emitChatStore("turn");
      renderSidePanelTurns();
      if (artId && typeof opts.onArtifact === "function") opts.onArtifact(artId);
      return;
    }
  }

  // 2. Streamed API Agent Turn (/api/chat SSE)
  const pinnedNote =
    Array.isArray(sess.pinned) && sess.pinned.length > 0
      ? `[Pinned context: ${sess.pinned.map((p) => `${p.kind}=${p.id}`).join(", ")}] `
      : "";
  sess.messages.push({ role: "user", content: pinnedNote + question });

  const turnObj = {
    id: makeId("turn"),
    kind: "agent",
    question,
    mode: sess.mode || "ask",
    thinking: "",
    rawStream: "",
    answer: "",
    steps: [],
    navigate: null,
    msTotal: 0,
    tokensIn: 0,
    tokensOut: 0,
    groundedCount: 0,
    unverified: [],
    error: null,
    stopped: false,
    phase: "scope",
  };
  sess.turns.push(turnObj);

  chatStore.running = true;
  chatStore.abortCtrl = new AbortController();
  emitChatStore("stream-start");
  renderSidePanelTurns();
  syncChatMeta();

  const selectionCtx = { ...(state.selection || {}) };
  for (const p of sess.pinned || []) {
    if (p.kind === "dataset" && !selectionCtx.dataset_id) selectionCtx.dataset_id = p.id;
    if (p.kind === "run" && !selectionCtx.run_id) selectionCtx.run_id = p.id;
  }

  const payload = {
    mode: sess.mode || "ask",
    messages: sess.messages.slice(-10),
    context: {
      route: route === "#/chat" ? "#/home" : route,
      task: state.taskId,
      round: state.roundId,
      selection: Object.keys(selectionCtx).length > 0 ? selectionCtx : state.selection,
    },
  };
  if (sess.conversationId) {
    payload.conversation_id = sess.conversationId;
  }

  const handleEvent = (evName, dataObj) => {
    if (evName === "trace_start") {
      if (dataObj.conversation_id) sess.conversationId = dataObj.conversation_id;
      turnObj.phase = "scope";
      emitChatStore("stream");
      renderSidePanelTurns();
      return;
    }

    if (evName === "thinking" || evName === "reasoning") {
      if (dataObj.text) {
        turnObj.thinking += dataObj.text;
        turnObj.phase = "synth";
        emitChatStore("stream");
        renderSidePanelTurns();
      }
      return;
    }

    if (evName === "tool_start") {
      turnObj.phase = "tools";
      turnObj.steps.push({
        callId: dataObj.call_id,
        name: dataObj.name,
        args: dataObj.args || {},
        ms: null,
        ok: true,
        ui: null,
        artifactId: null,
      });
      emitChatStore("stream");
      renderSidePanelTurns();
      return;
    }

    if (evName === "tool_result") {
      const st = turnObj.steps.find((s) => s.callId === dataObj.call_id);
      const artId = registerArtifact(sess, dataObj.name, st ? st.args : {}, dataObj.ui);
      extractFactsFromTool(sess, dataObj.name, st ? st.args : {}, dataObj.ui, "");
      if (st) {
        st.ms = dataObj.ms ?? 0;
        st.ok = Boolean(dataObj.ok);
        st.ui = dataObj.ui || null;
        st.artifactId = artId;
      }
      if (dataObj.navigate) {
        turnObj.navigate = dataObj.navigate;
      }
      emitChatStore("stream");
      renderSidePanelTurns();
      if (artId && typeof opts.onArtifact === "function") opts.onArtifact(artId);
      return;
    }

    if (evName === "token") {
      turnObj.phase = "synth";
      if (dataObj.text) {
        turnObj.rawStream += dataObj.text;
        const parsed = splitThinkAndAnswer(turnObj.rawStream);
        if (parsed.thinking) {
          turnObj.thinking = parsed.thinking;
        }
        turnObj.answer = parsed.answer;
        emitChatStore("stream");
        renderSidePanelTurns();
      }
      return;
    }

    if (evName === "done") {
      const parsed = splitThinkAndAnswer(turnObj.rawStream);
      turnObj.answer = (parsed.answer || turnObj.answer || "").trim();
      turnObj.msTotal = dataObj.ms_total || 0;
      turnObj.tokensIn = dataObj.tokens_in || 0;
      turnObj.tokensOut = dataObj.tokens_out || 0;
      turnObj.unverified = Array.isArray(dataObj.unverified) ? dataObj.unverified : [];
      const grounded = Array.isArray(dataObj.numbers)
        ? dataObj.numbers.filter((n) => n && n.grounded)
        : [];
      turnObj.groundedCount = grounded.length;
      turnObj.phase = "done";
      if (turnObj.answer) {
        sess.messages.push({ role: "assistant", content: turnObj.answer });
      }
      emitChatStore("done");
      renderSidePanelTurns();
      return;
    }

    if (evName === "error") {
      turnObj.error = dataObj.message || t("error.network");
      turnObj.fallback = dataObj.fallback || null;
      turnObj.phase = "done";
      emitChatStore("error");
      renderSidePanelTurns();
      ensureModels(true);
    }
  };

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: chatStore.abortCtrl.signal,
    });

    if (!res.ok || !res.body) {
      const txt = await res.text();
      let msg = txt;
      try {
        msg = JSON.parse(txt).error || txt;
      } catch {
        // Keep raw text.
      }
      handleEvent("error", { message: msg });
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sepIdx = buffer.indexOf("\n\n");
      while (sepIdx !== -1) {
        const block = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        let evName = "message";
        const dataLines = [];
        for (const ln of block.split("\n")) {
          if (ln.startsWith("event:")) evName = ln.slice(6).trim();
          else if (ln.startsWith("data:")) dataLines.push(ln.slice(5).trim());
        }
        if (dataLines.length > 0) {
          try {
            handleEvent(evName, JSON.parse(dataLines.join("\n")));
          } catch {
            // Skip malformed SSE JSON chunk.
          }
        }
        sepIdx = buffer.indexOf("\n\n");
      }
    }
  } catch (err) {
    if (err && err.name === "AbortError") {
      turnObj.stopped = true;
      turnObj.phase = "done";
    } else {
      handleEvent("error", { message: (err && err.message) || t("error.network") });
    }
  } finally {
    chatStore.running = false;
    chatStore.abortCtrl = null;
    emitChatStore("settled");
    renderSidePanelTurns();
    syncChatMeta();
  }
}

// ============================================================================
// API Provider Configuration Modal (OpenAI, DeepSeek, Claude, Gemini, Custom)
// ============================================================================
export async function openApiConfigModal() {
  if (state.locked) return;
  const existing = document.getElementById("api-config-modal");
  if (existing) existing.remove();

  const cfg = (await fetchApiConfig(true)) || {};
  const presets = cfg.presets || {};
  const presetKeys = Object.keys(presets);

  let selectedPreset = cfg.preset || "openai";
  const baseInput = el("input", {
    type: "text",
    className: cls("field", "mono"),
    style: "width:100%",
    value: cfg.base_url || (presets[selectedPreset] && presets[selectedPreset].base_url) || "",
  });
  const modelInput = el("input", {
    type: "text",
    className: cls("field", "mono"),
    style: "width:100%",
    value: cfg.model || (presets[selectedPreset] && presets[selectedPreset].default_model) || "",
  });
  const modelChipsBox = el("div", { className: "tag-row", style: "margin-top:6px" });

  const keyInput = el("input", {
    type: "password",
    className: cls("field", "mono"),
    style: "width:100%",
    placeholder: cfg.has_key
      ? t("studio.fieldApiKeyKeep", { source: cfg.key_source || "session" })
      : "sk-...",
  });

  const reasoningSelect = el(
    "select",
    { className: "field", style: "width:100%" },
    ["off", "low", "medium", "high", "default"].map((r) =>
      el("option", { value: r, selected: (cfg.reasoning || "off") === r, text: r })
    )
  );

  const renderModelChips = () => {
    const spec = presets[selectedPreset] || {};
    const baseModels = Array.isArray(spec.models) ? spec.models : [];
    const extraAnthropic =
      selectedPreset === "anthropic" ? ["claude-opus-5-5", "claude-haiku-5-5"] : [];
    const models = [...extraAnthropic, ...baseModels];
    setChildren(
      modelChipsBox,
      ...models.map((mId) =>
        el(
          "button",
          {
            type: "button",
            className: cls("turn-action-btn", "mono"),
            onClick: () => {
              modelInput.value = mId;
            },
          },
          [mId]
        )
      )
    );
  };

  const presetSelect = el(
    "select",
    {
      className: "field",
      style: "width:100%",
      onChange: (ev) => {
        selectedPreset = ev.target.value;
        const spec = presets[selectedPreset];
        if (spec) {
          baseInput.value = spec.base_url || "";
          modelInput.value = spec.default_model || "";
        }
        renderModelChips();
      },
    },
    presetKeys.map((pk) =>
      el("option", {
        value: pk,
        selected: pk === selectedPreset,
        text: (presets[pk] && presets[pk].label) || pk,
      })
    )
  );

  renderModelChips();

  const statusNote = el("div", { className: "tiny muted" });

  const backdrop = el(
    "div",
    {
      className: "api-modal-backdrop",
      id: "api-config-modal",
      onClick: (ev) => {
        if (ev.target === backdrop) backdrop.remove();
      },
    },
    [
      el("div", { className: cls("card", "api-modal-card"), role: "dialog", "aria-modal": "true" }, [
        el("div", { className: "task-head" }, [
          el("h2", { text: t("studio.modalTitle") }),
          el(
            "button",
            { type: "button", className: "topbtn", onClick: () => backdrop.remove() },
            ["×"]
          ),
        ]),
        el("p", { className: "muted", text: t("studio.modalSub") }),
        el("div", { className: "stack-sm", style: "margin-top:10px" }, [
          el("label", { className: "tiny", text: t("studio.fieldPreset") }),
          presetSelect,
          el("label", { className: "tiny", text: t("studio.fieldBaseUrl") }),
          baseInput,
          el("label", { className: "tiny", text: t("studio.fieldModel") }),
          modelInput,
          modelChipsBox,
          el("label", { className: "tiny", text: t("studio.fieldApiKey") }),
          keyInput,
          el("label", { className: "tiny", text: t("studio.fieldReasoning") }),
          reasoningSelect,
        ]),
        statusNote,
        el("div", { className: "card-foot" }, [
          el(
            "button",
            { type: "button", className: "btn", onClick: () => backdrop.remove() },
            [t("studio.cancelBtn")]
          ),
          el(
            "button",
            {
              type: "button",
              className: cls("btn", "primary"),
              onClick: async () => {
                const payload = {
                  preset: selectedPreset,
                  base_url: baseInput.value.trim(),
                  model: modelInput.value.trim(),
                  reasoning: reasoningSelect.value,
                };
                if (keyInput.value.trim()) {
                  payload.api_key = keyInput.value.trim();
                }
                const saved = await postJSON("/api/chat/config", payload);
                chatStore.apiConfig = saved;
                await ensureModels(true);
                emitChatStore("api-config");
                syncChatMeta();
                statusNote.textContent = t("studio.savedOk");
                window.setTimeout(() => backdrop.remove(), 350);
              },
            },
            [t("studio.saveApiBtn")]
          ),
        ]),
      ]),
    ]
  );

  document.body.appendChild(backdrop);
}

// ============================================================================
// Diagnostics & Traces Loader (shared by Side Copilot & Studio Workbench)
// ============================================================================
export async function loadChatDiagnostics(diagContent) {
  const benchRes = await tryGetJSON("/api/chat/bench");
  let tracesNode = null;
  const detailBox = el("div", {});

  if (!state.locked) {
    const trRes = await tryGetJSON("/api/chat/traces?limit=12");
    const traces = trRes.ok && Array.isArray(trRes.data) ? trRes.data : [];
    tracesNode =
      traces.length === 0
        ? el("p", { className: "tiny", text: t("chat.tracesEmpty") })
        : el(
            "div",
            { className: "stack-sm", style: "margin-top:8px" },
            traces.map((tr) =>
              el("div", { className: "task-head" }, [
                el(
                  "button",
                  {
                    type: "button",
                    className: cls("link", "mono"),
                    style: "font-size:11px",
                    onClick: async () => {
                      const full = await tryGetJSON(
                        `/api/chat/traces/${encodeURIComponent(tr.turn_id)}`
                      );
                      if (!full.ok || !full.data) return;
                      setChildren(
                        detailBox,
                        el("div", { className: "md-code-block", style: "margin-top:6px" }, [
                          el("div", { className: cls("md-code-head", "mono") }, [
                            el("span", { text: tr.turn_id }),
                            el(
                              "button",
                              {
                                type: "button",
                                onClick: () => setChildren(detailBox),
                              },
                              [t("chat.traceInspectClose")]
                            ),
                          ]),
                          el("pre", {
                            className: "mono",
                            text: JSON.stringify(
                              {
                                question: full.data.question,
                                provider: full.data.provider,
                                model: full.data.model,
                                hosted: full.data.hosted,
                                tools_offered: full.data.tools_offered,
                                nodes: (full.data.nodes || []).map((n) => ({
                                  type: n.type,
                                  name: n.name,
                                  ms: n.ms,
                                  ok: n.ok,
                                  tool_calls: n.tool_calls,
                                })),
                                unverified: full.data.unverified,
                              },
                              null,
                              2
                            ),
                          }),
                        ])
                      );
                    },
                  },
                  [tr.question ? `${tr.question.slice(0, 32)}…` : tr.turn_id]
                ),
                el("span", {
                  className: cls("tiny", "mono"),
                  text: `${tr.ms_total ?? 0}ms · ${(tr.tools || []).join(",") || "-"}`,
                }),
              ])
            )
          );
  }

  const b = benchRes.ok && benchRes.data ? benchRes.data : null;
  const benchNode = b
    ? el("div", { className: "meta-strip" }, [
        el("div", { className: "meta-box" }, [
          el("span", { text: t("chat.benchGrounded") }),
          el("b", { className: "mono", text: `${Math.round((b.grounded_rate || 0) * 100)}%` }),
        ]),
        el("div", { className: "meta-box" }, [
          el("span", { text: t("chat.benchToolAcc") }),
          el("b", { className: "mono", text: `${Math.round((b.tool_acc || 0) * 100)}%` }),
        ]),
        el("div", { className: "meta-box" }, [
          el("span", { text: t("chat.benchGuard") }),
          el("b", {
            className: "mono",
            text: b.guardrail ? `${b.guardrail.pass}/${b.guardrail.n}` : "-",
          }),
        ]),
      ])
    : el("div", { className: "tiny", text: t("chat.benchNone") });

  setChildren(diagContent, benchNode, tracesNode, detailBox);
}

// ============================================================================
// Side Copilot Drawer (#chat-panel) — synced with Shared Store
// ============================================================================
function updateSlashMenu() {
  if (!els || state.locked) {
    if (els && els.slashMenu) els.slashMenu.hidden = true;
    return;
  }
  const val = els.textarea.value;
  if (!val.startsWith("/") || val.includes("\n") || val.includes(" ")) {
    els.slashMenu.hidden = true;
    return;
  }
  const token = val.split(/\s+/)[0].toLowerCase();
  const matches = (chatStore.toolsList || []).filter((tl) => {
    const sl = String(tl.slash || `/${tl.name}`).toLowerCase();
    return sl.startsWith(token) || `/${tl.name}`.toLowerCase().startsWith(token);
  });
  if (matches.length === 0) {
    els.slashMenu.hidden = true;
    return;
  }
  slashIndex = Math.max(0, Math.min(matches.length - 1, slashIndex));

  setChildren(
    els.slashMenu,
    el("div", { className: "slash-menu-head", text: t("chat.slashTitle") }),
    ...matches.map((tl, idx) => {
      const reqs = ((tl.parameters && tl.parameters.required) || []).map((k) => `<${k}>`).join(" ");
      const cmdLabel = `${tl.slash || `/${tl.name}`}${reqs ? ` ${reqs}` : ""}`;
      return el(
        "button",
        {
          type: "button",
          className: cls("slash-item", idx === slashIndex && "is-selected"),
          onClick: () => {
            const baseCmd = tl.slash || `/${tl.name}`;
            els.textarea.value = reqs ? `${baseCmd} ` : baseCmd;
            els.slashMenu.hidden = true;
            els.textarea.focus();
            if (!reqs) {
              const q = els.textarea.value;
              els.textarea.value = "";
              runSharedTurn(q);
            }
          },
        },
        [
          el("span", { className: cls("slash-cmd", "mono"), text: cmdLabel }),
          el("span", { className: "slash-desc", text: tl.description || "" }),
        ]
      );
    })
  );
  els.slashMenu.hidden = false;
  els.slashMenu._matches = matches;
}

function renderSideTurnNode(tr) {
  const frag = el("div", { className: "stack-sm" });
  frag.appendChild(el("div", { className: "user-turn", text: tr.question }));

  const isRunning = tr.phase && tr.phase !== "done";
  const mdZone = el("div", { className: "md-body" });
  if (tr.answer || isRunning) {
    renderMarkdownInto(mdZone, tr.answer || "", isRunning && !tr.steps.some((s) => s.ms === null));
  }

  const card = el("div", { className: cls("agent-turn", "bubble") }, [
    el("div", { className: "turn-header" }, [
      el("span", {
        className: "turn-header-brand",
        text: tr.kind === "slash" ? `⚡ ${tr.question.split(/\s+/)[0]}` : `✦ ${t("chat.title")}`,
      }),
      isRunning
        ? el("span", { className: "turn-badge-live" }, [
            el("span", { className: "pulse-dot" }),
            el("span", { text: t("chat.statusStreaming") }),
          ])
        : el("span", {
            className: "mono",
            text: tr.msTotal ? `${(tr.msTotal / 1000).toFixed(2)} s` : "",
          }),
    ]),
    tr.thinking
      ? el("details", { className: "reasoning-box", open: isRunning && !tr.answer }, [
          el("summary", { text: `💭 ${t("chat.reasoningTitle")}` }),
          el("div", { className: cls("reasoning-body", "mono"), text: tr.thinking }),
        ])
      : null,
    (tr.steps || []).length > 0
      ? el(
          "div",
          { className: "agent-steps" },
          tr.steps.map((st) =>
            el(
              "details",
              {
                className: "agent-step",
                open: Boolean(st.ui && ["bar", "line", "thumbs", "confirm"].includes(st.ui.type)),
              },
              [
                el("summary", {}, [
                  el("span", {
                    className: cls(
                      "step-status-icon",
                      st.ms === null && "running",
                      st.ms !== null && !st.ok && "err"
                    ),
                    text: st.ms === null ? "⚙" : st.ok ? "✓" : "!",
                  }),
                  el("b", { className: "mono", text: st.name }),
                  el("span", {
                    className: cls("step-args-preview", "mono"),
                    text: formatArgsChip(st.args),
                  }),
                  el("span", {
                    className: cls("step-ms", "mono"),
                    text: st.ms === null ? "…" : `${st.ms} ms`,
                  }),
                ]),
                st.ui ? el("div", { className: "agent-step-body" }, [renderToolUi(st.ui)]) : null,
              ]
            )
          )
        )
      : null,
    tr.answer || isRunning ? mdZone : null,
    tr.error ? el("div", { className: "missing-item", text: tr.error }) : null,
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
    !isRunning && (tr.groundedCount > 0 || tr.answer)
      ? el("div", { className: "turn-footer" }, [
          tr.groundedCount > 0
            ? el("span", {
                className: "grounded-pill",
                text: t("chat.groundedOk", { count: formatNumber(tr.groundedCount) }),
              })
            : el("span", {}),
          el("div", { className: "turn-actions" }, [
            tr.artifactId || (tr.steps || []).some((s) => s.artifactId)
              ? el("a", { className: "turn-action-btn", href: "#/chat" }, [
                  t("studio.openInWorkbench"),
                ])
              : null,
          ]),
        ])
      : null,
  ]);

  frag.appendChild(card);
  return frag;
}

function renderSidePanelTurns() {
  if (!els || pageKeyFromHash(currentRouteHash()) === "chat") return;
  const sess = getActiveSession();
  const turns = sess.turns || [];
  if (turns.length === 0) {
    setChildren(els.messagesBox, els.welcomeBubble, els.suggestWrap);
  } else {
    setChildren(els.messagesBox, ...turns.map((tr) => renderSideTurnNode(tr)));
  }
  if (stickBottom) {
    els.messagesBox.scrollTop = els.messagesBox.scrollHeight;
    els.jumpBtn.hidden = true;
  }
}

function syncChatMeta() {
  if (!els) return;
  const cfg = chatStore.apiConfig;
  const m = state.modelsDoc;
  const isApiActive =
    (cfg && cfg.active_kind && cfg.active_kind !== "ollama") ||
    (m && m.chat && m.chat.kind && m.chat.kind !== "ollama");

  if (isApiActive) {
    const provName = (cfg && cfg.provider) || (m && m.chat && m.chat.provider) || "API";
    const modName = (cfg && cfg.active_model) || (m && m.chat && m.chat.model) || "";
    const ready = cfg ? Boolean(cfg.ready) : Boolean(m && m.chat && m.chat.ready);
    els.subEl.textContent = `${shortModelLabel(modName)} · ${provName}`;
    els.statusDot.className = cls("status-dot", ready ? "warm" : "cold");
    els.modelStatusLabel.textContent = ready
      ? `${provName} · ${shortModelLabel(modName)}`
      : `${provName} · ${t("studio.apiNeedsKey")}`;
  } else {
    els.subEl.textContent = t("chat.sub");
    els.statusDot.className = cls("status-dot", "cold");
    els.modelStatusLabel.textContent = t("studio.apiNeedsKey");
  }
  els.apiBtn.hidden = state.locked;
  els.apiBtn.textContent = t("studio.apiConfigureBtn");

  // Context pills
  const route = currentRouteHash();
  const pills = [
    el("span", { className: cls("ctx-pill", "mono"), text: route }),
    state.taskId ? el("span", { className: cls("ctx-pill", "mono"), text: state.taskId }) : null,
  ];
  if (state.selection && typeof state.selection === "object") {
    const selLabel = Object.entries(state.selection)
      .map(([k, v]) => `${k.replace(/_id$/, "")}:${v}`)
      .join(" · ");
    if (selLabel) {
      pills.push(
        el("span", { className: cls("ctx-pill", "mono") }, [
          selLabel,
          el(
            "button",
            {
              type: "button",
              title: t("chat.ctxClearSel"),
              onClick: () => clearSelection(),
            },
            ["×"]
          ),
        ])
      );
    }
  }
  setChildren(els.ctxPillsBox, ...pills.filter(Boolean));

  const pageKey = pageKeyFromHash(route);
  els.suggestHeader.textContent = t("chat.suggestHeader");
  setChildren(
    els.suggestBox,
    ...suggestionsForPage(pageKey).map((s) =>
      el(
        "button",
        {
          type: "button",
          onClick: () => {
            els.textarea.value = s.replace(/\s*↗$/, "");
            els.textarea.focus();
          },
        },
        [s]
      )
    )
  );

  const chatDisabled = state.statusLoaded && !state.chatOn;
  els.disabledNote.hidden = !chatDisabled;
  els.disabledNote.textContent = t("chat.disabledLocked");
  els.textarea.disabled = chatDisabled || !state.statusLoaded;
  els.textarea.placeholder = t("chat.placeholder");
  els.hintKeys.textContent = t("chat.hintKeys");
  els.slashTriggerBtn.hidden = state.locked || chatDisabled;
  els.slashTriggerBtn.textContent = t("chat.slashBtn");
  els.sendBtn.disabled = chatDisabled || !state.statusLoaded;
  els.sendBtn.textContent = chatStore.running ? t("chat.stop") : t("chat.send");
  els.studioLinkBtn.title = t("studio.openFullBtn");
  els.studioLinkBtn.setAttribute("aria-label", t("studio.openFullBtn"));
  els.wideBtn.title = chatStore.wide ? t("chat.collapseWide") : t("chat.expandWide");
  els.wideBtn.setAttribute("aria-label", els.wideBtn.title);
  els.wideBtn.textContent = chatStore.wide ? "⇥" : "⇔";
  els.newBtn.title = t("chat.newTurn");
  els.newBtn.setAttribute("aria-label", t("chat.newTurn"));
  els.jumpBtn.textContent = t("chat.jumpLatest");
  els.welcomeBubbleText.textContent = t("chat.welcome");
  els.diagSummary.textContent = t("chat.diagToggle");
}

export function initChatShell() {
  const panel = document.getElementById("chat-panel");
  const head = document.querySelector("#chat-panel .chat-head");
  const body = document.getElementById("chat-body");
  const closeBtn = document.getElementById("chat-close");

  if (closeBtn) {
    closeBtn.addEventListener("click", () => setChatOpen(false, true));
  }
  if (!body || !panel) return;

  const resizer = el("div", { className: "chat-resizer" });
  panel.appendChild(resizer);
  let dragging = false;
  resizer.addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    dragging = true;
    resizer.classList.add("is-dragging");
  });
  window.addEventListener("mousemove", (ev) => {
    if (!dragging) return;
    const w = Math.max(300, Math.min(760, window.innerWidth - ev.clientX));
    document.documentElement.style.setProperty("--chat-w", `${w}px`);
    resizeChatCharts();
  });
  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove("is-dragging");
  });

  const studioLinkBtn = el("a", { className: "topbtn", href: "#/chat" }, ["⤢"]);

  const wideBtn = el(
    "button",
    {
      type: "button",
      className: "topbtn",
      onClick: () => {
        chatStore.wide = !chatStore.wide;
        localStorage.setItem("fw_chat_wide", chatStore.wide ? "1" : "0");
        document.documentElement.style.removeProperty("--chat-w");
        syncChatShell();
        window.setTimeout(resizeChatCharts, 50);
      },
    },
    ["⇔"]
  );

  const newBtn = el(
    "button",
    {
      type: "button",
      className: "topbtn",
      onClick: () => createNewSession(),
    },
    ["＋"]
  );

  if (head && closeBtn) {
    head.insertBefore(studioLinkBtn, closeBtn);
    head.insertBefore(wideBtn, closeBtn);
    head.insertBefore(newBtn, closeBtn);
  }

  const statusDot = el("span", { className: "status-dot" });
  const modelStatusLabel = el("span", { className: "mono" });
  const apiBtn = el(
    "button",
    {
      type: "button",
      className: "turn-action-btn",
      onClick: () => openApiConfigModal(),
    },
    []
  );
  const modelBar = el("div", { className: "chat-model-bar" }, [
    el("div", { className: "model-status-pill" }, [statusDot, modelStatusLabel]),
    el("div", { className: "turn-actions" }, [apiBtn]),
  ]);

  const ctxPillsBox = el("div", { className: "chat-ctx-pills" });

  const welcomeBubbleText = el("div", { className: "bubble-text" });
  const welcomeBubble = el("div", { className: cls("agent-turn", "bubble") }, [welcomeBubbleText]);
  const suggestHeader = el("div", { className: "tiny" });
  const suggestBox = el("div", { className: "suggestions" });
  const suggestWrap = el("div", {}, [suggestHeader, suggestBox]);

  const messagesBox = el(
    "div",
    {
      className: "messages",
      onScroll: () => {
        const nearBottom =
          messagesBox.scrollHeight - messagesBox.scrollTop - messagesBox.clientHeight < 36;
        stickBottom = nearBottom;
        if (nearBottom) jumpBtn.hidden = true;
      },
    },
    [welcomeBubble, suggestWrap]
  );

  const jumpBtn = el(
    "button",
    {
      type: "button",
      className: cls("topbtn", "scroll-jump"),
      hidden: true,
      onClick: () => {
        stickBottom = true;
        messagesBox.scrollTop = messagesBox.scrollHeight;
        jumpBtn.hidden = true;
      },
    },
    []
  );

  const disabledNote = el("div", { className: "missing-item", hidden: true });
  const slashMenu = el("div", { className: "slash-menu", hidden: true });

  const submitSideInput = () => {
    if (chatStore.running && chatStore.abortCtrl) {
      chatStore.abortCtrl.abort();
      return;
    }
    const q = els.textarea.value.trim();
    if (!q) return;
    els.textarea.value = "";
    els.slashMenu.hidden = true;
    runSharedTurn(q);
  };

  const textarea = el("textarea", {
    rows: "2",
    onInput: () => {
      slashIndex = 0;
      updateSlashMenu();
    },
    onKeydown: (ev) => {
      if (!slashMenu.hidden && Array.isArray(slashMenu._matches) && slashMenu._matches.length > 0) {
        const list = slashMenu._matches;
        if (ev.key === "ArrowDown") {
          ev.preventDefault();
          slashIndex = (slashIndex + 1) % list.length;
          updateSlashMenu();
          return;
        }
        if (ev.key === "ArrowUp") {
          ev.preventDefault();
          slashIndex = (slashIndex - 1 + list.length) % list.length;
          updateSlashMenu();
          return;
        }
        if (ev.key === "Tab") {
          ev.preventDefault();
          const chosen = list[slashIndex];
          if (chosen) {
            textarea.value = `${chosen.slash || `/${chosen.name}`} `;
            slashMenu.hidden = true;
          }
          return;
        }
        if (ev.key === "Escape") {
          slashMenu.hidden = true;
          return;
        }
      }
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        submitSideInput();
      }
    },
  });

  const slashTriggerBtn = el(
    "button",
    {
      type: "button",
      className: cls("turn-action-btn", "mono"),
      onClick: async () => {
        await ensureRouteToolsLoaded();
        textarea.value = "/";
        textarea.focus();
        slashIndex = 0;
        updateSlashMenu();
      },
    },
    []
  );
  const hintKeys = el("span", { className: "tiny" });
  const sendBtn = el(
    "button",
    {
      type: "button",
      className: cls("btn", "primary"),
      onClick: () => submitSideInput(),
    },
    []
  );
  const composerWrap = el("div", { className: "composer-wrap" }, [
    slashMenu,
    el("div", { className: "composer" }, [
      textarea,
      el("div", { className: "composer-foot" }, [
        el("div", { className: "turn-actions" }, [slashTriggerBtn, hintKeys]),
        sendBtn,
      ]),
    ]),
  ]);

  const diagSummary = el("summary", {});
  const diagContent = el("div", { className: "tool-ui-body" });
  const diagDetails = el(
    "details",
    {
      className: "studio-details",
      onToggle: (ev) => {
        if (ev.target.open) loadChatDiagnostics(diagContent);
      },
    },
    [diagSummary, diagContent]
  );

  setChildren(
    body,
    modelBar,
    ctxPillsBox,
    disabledNote,
    messagesBox,
    jumpBtn,
    composerWrap,
    diagDetails
  );

  els = {
    subEl: document.getElementById("chat-pane-sub"),
    studioLinkBtn,
    wideBtn,
    newBtn,
    statusDot,
    modelStatusLabel,
    apiBtn,
    ctxPillsBox,
    welcomeBubble,
    welcomeBubbleText,
    suggestWrap,
    suggestHeader,
    suggestBox,
    messagesBox,
    jumpBtn,
    disabledNote,
    slashMenu,
    slashTriggerBtn,
    textarea,
    hintKeys,
    sendBtn,
    diagSummary,
  };

  syncChatShell();
  renderSidePanelTurns();
  ensureModels(false);
  fetchApiConfig(false);
}

export function syncChatShell() {
  const shell = document.getElementById("workspace-shell");
  const panel = document.getElementById("chat-panel");
  const titleEl = document.getElementById("chat-pane-title");
  const closeBtn = document.getElementById("chat-close");
  const toggleBtn = document.getElementById("chat-toggle");
  const toggleLabel = document.getElementById("chat-toggle-label");
  const onStudioPage = pageKeyFromHash(currentRouteHash()) === "chat";

  if (shell) {
    shell.classList.toggle("is-studio-route", onStudioPage);
    shell.classList.toggle("chat-collapsed", onStudioPage || !state.chatOpen);
    shell.classList.toggle("chat-wide", Boolean(!onStudioPage && state.chatOpen && chatStore.wide));
  }
  if (panel) {
    panel.hidden = onStudioPage;
    panel.setAttribute("aria-label", t("chat.ariaLabel"));
  }
  if (titleEl) {
    titleEl.textContent = t("chat.title");
  }
  if (closeBtn) {
    closeBtn.setAttribute("aria-label", t("chat.close"));
    closeBtn.title = t("chat.close");
  }
  if (toggleBtn) {
    toggleBtn.setAttribute("aria-expanded", String(onStudioPage || state.chatOpen));
    toggleBtn.setAttribute("aria-label", t("header.chatToggleAria"));
  }
  if (toggleLabel) {
    toggleLabel.textContent = t("header.chatToggle");
  }
  syncChatMeta();
  if (!onStudioPage) {
    renderSidePanelTurns();
  }
  if (state.chatOpen && !onStudioPage) {
    scheduleToolsRefresh();
  }
}

export function notifyChatRouteChanged() {
  syncChatShell();
  scheduleToolsRefresh();
}
