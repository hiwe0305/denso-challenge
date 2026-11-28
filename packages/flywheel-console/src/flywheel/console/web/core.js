import vi from "./i18n/vi.js";
import en from "./i18n/en.js";

const DICTIONARIES = { vi, en };
const CHAT_ALLOWED_WHEN_LOCKED = new Set([
  "/api/chat",
  "/api/models/prewarm",
  "/api/models/connect",
]);

export function readPref(key, allowed, fallback) {
  try {
    const val = window.localStorage.getItem(key);
    return allowed.includes(val) ? val : fallback;
  } catch {
    return fallback;
  }
}

export function writePref(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage quota or privacy-mode errors.
  }
}

function readExplicitChatPref() {
  try {
    const val = window.localStorage.getItem("fw_chat");
    if (val === "open") return true;
    if (val === "closed") return false;
  } catch {
    // Ignore storage errors.
  }
  return null;
}

const explicitChatPref = typeof window !== "undefined" ? readExplicitChatPref() : null;

export const state = {
  lang: typeof window !== "undefined" ? readPref("fw_lang", ["vi", "en"], "vi") : "vi",
  theme: typeof window !== "undefined" ? readPref("fw_theme", ["light", "dark"], "light") : "light",
  chatExplicit: explicitChatPref !== null,
  // Closed until the reader opens it (decision Q3 / design P0-8, 28/11/2026).
  chatOpen: explicitChatPref !== null ? explicitChatPref : false,
  dataViewMode:
    typeof window !== "undefined" ? readPref("fw_data_view", ["list", "gallery"], "gallery") : "gallery",
  // Default to locked until /api/status confirms otherwise (ui-spec §2).
  locked: true,
  chatOn: false,
  statusLoaded: false,
  statusDoc: null,
  statusError: null,
  tasksLoaded: false,
  tasksLoading: true,
  tasksDoc: null,
  tasksError: null,
  // Cached index & model docs
  catalogDoc: null,
  storyRawDoc: null,
  simRawDoc: null,
  kindsDoc: null,
  modelsDoc: null,
  // Task & round selection: kept for this browser tab only (sessionStorage), never in
  // localStorage, so a reload mid-recording stays on the same round.
  taskId: null,
  roundId: null,
  selection: null,
  taskCache: {},
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notifyStateChange(reason = "update") {
  for (const fn of listeners) {
    fn(reason);
  }
}

export function hasI18nKey(key) {
  const dict = DICTIONARIES[state.lang] || DICTIONARIES.vi;
  return Object.prototype.hasOwnProperty.call(dict, key);
}

export function t(key, params = null) {
  const dict = DICTIONARIES[state.lang] || DICTIONARIES.vi;
  let str = Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replaceAll(`{${k}}`, String(v ?? ""));
    }
  }
  return str;
}

export function pickLang(val) {
  if (val == null) return "";
  if (typeof val === "string") return val;
  if (typeof val === "object") {
    return val[state.lang] ?? val.vi ?? val.en ?? "";
  }
  return String(val);
}

// Success condition in reader's words (W7) when the dictionary has one for the task;
// otherwise the seed text.
export function taskSuccessText(task) {
  if (!task) return t("state.na");
  const key = "task.success." + task.id;
  return hasI18nKey(key) ? t(key) : pickLang(task.success) || t("state.na");
}

// Reader's name of a task step id ("approach_a" → "tới bàn A") from task.stages in tasks.json;
// the id itself when the task has no entry (design audit P1-4).
export function stageLabel(id, task = getCurrentTask()) {
  const stages = task && Array.isArray(task.stages) ? task.stages : [];
  const found = stages.find((st) => st && st.id === id);
  return found ? pickLang(found) || id : id;
}

// Reader's name of a failure label ("L-PLACE-POSE" → "đặt lệch", W10); the code when the
// dictionary has no entry. Pages keep the code in a tooltip.
export function failureLabel(code) {
  const key = "fail." + code;
  return code && hasI18nKey(key) ? t(key) : String(code ?? "");
}

// Pure inline markdown cleaner for document quotes (F1): strips **, backticks,
// outer table pipes, and converts inner pipes to middle dots. Always used with textContent.
export function cleanInlineMarkdown(raw) {
  if (raw === null || raw === undefined) return "";
  return String(raw)
    .split("\n")
    .map((line) =>
      line
        .replace(/\*\*/g, "")
        .replace(/`/g, "")
        .replace(/^\s*\|\s*/, "")
        .replace(/\s*\|\s*$/, "")
        .replace(/\s*\|\s*/g, " · ")
        .replace(/\s{2,}/g, " ")
        .trim()
    )
    .filter(Boolean)
    .join("\n");
}

export function formatNumber(val, options = {}) {
  if (val === null || val === undefined || Number.isNaN(val)) {
    return t("state.na");
  }
  const locale = state.lang === "vi" ? "vi-VN" : "en-US";
  return new Intl.NumberFormat(locale, options).format(val);
}

export function formatPercent(ratio, digits = 1) {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) {
    return t("state.na");
  }
  return `${formatNumber(ratio * 100, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

// Decimal units (1 GB = 10^9 bytes), as the catalog and the docs write sizes (N3, A19).
export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) {
    return t("state.na");
  }
  if (bytes < 1e3) return `${bytes} B`;
  if (bytes < 1e6) return `${formatNumber(bytes / 1e3, { maximumFractionDigits: 1 })} KB`;
  if (bytes < 1e9) return `${formatNumber(bytes / 1e6, { maximumFractionDigits: 1 })} MB`;
  return `${formatNumber(bytes / 1e9, { maximumFractionDigits: 2 })} GB`;
}

export function formatDateTime(isoStr) {
  if (!isoStr) return t("state.na");
  const date = new Date(isoStr);
  if (Number.isNaN(date.getTime())) return String(isoStr);
  const locale = state.lang === "vi" ? "vi-VN" : "en-US";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function announce(message) {
  if (typeof document === "undefined") return;
  const region = document.getElementById("live-region");
  if (region) {
    region.textContent = message;
  }
}

export function setLang(nextLang) {
  if (nextLang !== "vi" && nextLang !== "en") return;
  if (state.lang === nextLang) return;
  state.lang = nextLang;
  writePref("fw_lang", nextLang);
  document.documentElement.lang = nextLang;
  // Clear stale live-region announcement from previous language (F4.2).
  announce("");
  notifyStateChange("lang");
}

export function setTheme(nextTheme) {
  if (nextTheme !== "light" && nextTheme !== "dark") return;
  state.theme = nextTheme;
  writePref("fw_theme", nextTheme);
  document.documentElement.setAttribute("data-theme", nextTheme);
  refreshMountedCharts();
  notifyStateChange("theme");
}

export function setChatOpen(open, persist = true) {
  state.chatOpen = Boolean(open);
  if (persist) {
    state.chatExplicit = true;
    writePref("fw_chat", state.chatOpen ? "open" : "closed");
  }
  notifyStateChange("chat");
  if (typeof window !== "undefined") {
    window.setTimeout(() => resizeMountedCharts(), 60);
  }
}

export function setDataViewMode(mode) {
  if (mode !== "list" && mode !== "gallery") return;
  state.dataViewMode = mode;
  writePref("fw_data_view", mode);
  notifyStateChange("data-view");
}

export function setSelection(sel, silent = false) {
  state.selection = sel;
  if (!silent) {
    notifyStateChange("selection");
  }
}

export function clearSelection() {
  if (state.selection !== null) {
    state.selection = null;
    notifyStateChange("selection");
  }
}

// Page cleanup & ECharts lifecycle registry
const activeCharts = new Set();
const routeCleanups = new Set();

export function onRouteCleanup(fn) {
  routeCleanups.add(fn);
}

export function cleanupCurrentPage() {
  for (const fn of routeCleanups) {
    try {
      fn();
    } catch {
      // Ignore cleanup errors.
    }
  }
  routeCleanups.clear();

  for (const entry of activeCharts) {
    try {
      if (entry.ro) entry.ro.disconnect();
      entry.chart.dispose();
    } catch {
      // Ignore chart disposal errors.
    }
  }
  activeCharts.clear();
}

export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function chartPalette() {
  return [1, 2, 3, 4, 5, 6, 7, 8].map((i) => cssVar(`--s${i}`) || cssVar("--green"));
}

// Value and log axes without their own formatter print numbers in the reader's locale
// (vi: "10.000", "0,1"; audit 02 A19).
function localizeAxes(opt) {
  if (!opt || typeof opt !== "object") return opt;
  for (const key of ["xAxis", "yAxis"]) {
    const axes = Array.isArray(opt[key]) ? opt[key] : opt[key] ? [opt[key]] : [];
    for (const ax of axes) {
      if (!ax || (ax.type !== "value" && ax.type !== "log")) continue;
      ax.axisLabel = ax.axisLabel || {};
      if (ax.axisLabel.formatter == null) {
        ax.axisLabel.formatter = (v) => formatNumber(v, { maximumFractionDigits: 4 });
      }
    }
  }
  return opt;
}

export function mountChart(boxEl, buildOption) {
  if (!boxEl || typeof window.echarts === "undefined") return null;
  const chart = window.echarts.init(boxEl);
  const apply = () => {
    const opt = buildOption({
      ink: cssVar("--ink"),
      soft: cssVar("--soft"),
      line: cssVar("--line"),
      surface: cssVar("--surface"),
      colors: chartPalette(),
    });
    chart.setOption(localizeAxes(opt), true);
  };
  apply();
  let ro = null;
  if (typeof ResizeObserver !== "undefined") {
    ro = new ResizeObserver(() => {
      chart.resize();
    });
    ro.observe(boxEl);
  }
  const entry = { chart, apply, ro };
  activeCharts.add(entry);
  return chart;
}

export function refreshMountedCharts() {
  for (const entry of activeCharts) {
    try {
      entry.apply();
      entry.chart.resize();
    } catch {
      // Ignore chart refresh errors.
    }
  }
}

export function resizeMountedCharts() {
  for (const entry of activeCharts) {
    try {
      entry.chart.resize();
    } catch {
      // Ignore resize errors.
    }
  }
}

// API Client & Error Notification
export class ApiError extends Error {
  constructor({ status = 0, url = "", serverMessage = "" }) {
    super(serverMessage || t("error.network"));
    this.name = "ApiError";
    this.status = status;
    this.url = url;
    this.serverMessage = serverMessage;
  }
}

let activeBannerRetry = null;
let activeBannerNetwork = false;

export function showErrorBanner(err, onRetry = null) {
  const banner = document.getElementById("error-banner");
  const titleEl = document.getElementById("error-banner-title");
  const codeEl = document.getElementById("error-banner-code");
  const msgEl = document.getElementById("error-banner-msg");
  const retryBtn = document.getElementById("error-banner-retry");
  const closeBtn = document.getElementById("error-banner-close");
  if (!banner || !titleEl || !codeEl || !msgEl || !retryBtn || !closeBtn) return;

  titleEl.textContent = t("error.bannerTitle");
  closeBtn.setAttribute("aria-label", t("error.dismiss"));

  const status = err && typeof err.status === "number" ? err.status : 0;
  if (status > 0) {
    codeEl.textContent = t("error.httpCode", { code: status });
    codeEl.hidden = false;
  } else {
    codeEl.hidden = true;
  }

  msgEl.textContent =
    (err && err.serverMessage) ||
    (err && err.message) ||
    t("error.network");

  activeBannerRetry = typeof onRetry === "function" ? onRetry : null;
  activeBannerNetwork = status === 0;
  if (activeBannerRetry) {
    retryBtn.textContent = t("error.retry");
    retryBtn.hidden = false;
  } else {
    retryBtn.hidden = true;
  }
  banner.hidden = false;
}

export function hideErrorBanner() {
  const banner = document.getElementById("error-banner");
  if (banner) {
    banner.hidden = true;
  }
  activeBannerRetry = null;
  activeBannerNetwork = false;
}

// A later successful call proves the server is back: drop a stale "cannot reach" banner
// (stability audit S-P2-14). HTTP errors stay until dismissed or the route changes.
function clearNetworkBanner() {
  if (activeBannerNetwork) hideErrorBanner();
}

export function bindErrorBannerControls() {
  const retryBtn = document.getElementById("error-banner-retry");
  const closeBtn = document.getElementById("error-banner-close");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      const fn = activeBannerRetry;
      hideErrorBanner();
      if (fn) fn();
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", () => hideErrorBanner());
  }
}

async function parseJsonResponse(res, url, notify) {
  const text = await res.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!res.ok) {
    const serverMessage =
      payload && typeof payload.error === "string"
        ? payload.error
        : text || `HTTP ${res.status}`;
    if (res.status === 403 && serverMessage === "locked") {
      state.locked = true;
      notifyStateChange("lock");
    }
    const apiErr = new ApiError({
      status: res.status,
      url,
      serverMessage,
    });
    if (notify) {
      showErrorBanner(apiErr);
    }
    throw apiErr;
  }
  return payload;
}

export async function getJSON(url, options = {}) {
  const { signal, notify = true, onRetry = null } = options;
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-cache",
      signal,
    });
    const payload = await parseJsonResponse(res, url, notify);
    clearNetworkBanner();
    return payload;
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    if (err instanceof ApiError) {
      if (notify && onRetry) showErrorBanner(err, onRetry);
      throw err;
    }
    const netErr = new ApiError({ status: 0, url, serverMessage: t("error.network") });
    if (notify) showErrorBanner(netErr, onRetry);
    throw netErr;
  }
}

export async function tryGetJSON(url, options = {}) {
  try {
    const data = await getJSON(url, { ...options, notify: false });
    return { ok: true, status: 200, data, error: null };
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    const status = err && typeof err.status === "number" ? err.status : 0;
    if (status !== 404 && options.notifyOnError) {
      showErrorBanner(err);
    }
    return { ok: false, status, data: null, error: err };
  }
}

export async function postJSON(url, body = {}, options = {}) {
  const { signal, notify = true, onRetry = null } = options;
  const pathOnly = url.split("?")[0];
  const allowedWhenLocked = state.chatOn && CHAT_ALLOWED_WHEN_LOCKED.has(pathOnly);
  if (state.locked && !allowedWhenLocked) {
    const lockErr = new ApiError({
      status: 403,
      url,
      serverMessage: t("error.lockedClient"),
    });
    if (notify) showErrorBanner(lockErr);
    throw lockErr;
  }

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body ?? {}),
      signal,
    });
    return await parseJsonResponse(res, url, notify);
  } catch (err) {
    if (err && err.name === "AbortError") throw err;
    if (err instanceof ApiError) {
      if (notify && onRetry) showErrorBanner(err, onRetry);
      throw err;
    }
    const netErr = new ApiError({ status: 0, url, serverMessage: t("error.network") });
    if (notify) showErrorBanner(netErr, onRetry);
    throw netErr;
  }
}

export async function uploadVideoFile(batchDir, taskId, file) {
  if (state.locked) {
    const lockErr = new ApiError({
      status: 403,
      url: "/api/upload",
      serverMessage: t("error.lockedClient"),
    });
    showErrorBanner(lockErr);
    throw lockErr;
  }
  const qs = new URLSearchParams({ dir: batchDir, task: taskId }).toString();
  const url = `/api/upload?${qs}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "X-Filename": encodeURIComponent(file.name),
      Accept: "application/json",
    },
    body: file,
  });
  return parseJsonResponse(res, url, true);
}

// Cached index & singleton model loaders (F5)
let modelsInFlight = null;

export async function ensureModels(force = false) {
  if (state.modelsDoc && !force) return state.modelsDoc;
  if (modelsInFlight && !force) return modelsInFlight;
  modelsInFlight = tryGetJSON("/api/models").then((res) => {
    modelsInFlight = null;
    if (res.ok && res.data) {
      state.modelsDoc = res.data;
      notifyStateChange("models");
    }
    return state.modelsDoc;
  });
  return modelsInFlight;
}

export async function ensureCatalog(force = false) {
  if (state.catalogDoc && !force) return state.catalogDoc;
  state.catalogDoc = await getJSON("data/catalog.json");
  return state.catalogDoc;
}

export async function ensureStoryRaw(force = false) {
  if (state.storyRawDoc && !force) return state.storyRawDoc;
  state.storyRawDoc = await getJSON("data/story.json");
  return state.storyRawDoc;
}

export async function ensureSimRaw(force = false) {
  if (state.simRawDoc && !force) return state.simRawDoc;
  state.simRawDoc = await getJSON("data/sim.json");
  return state.simRawDoc;
}

export async function ensureKinds(force = false) {
  if (state.kindsDoc && !force) return state.kindsDoc;
  state.kindsDoc = await getJSON("/api/kinds");
  return state.kindsDoc;
}

// Task, round & withhold_eval scoping helpers (api-contract §1.2, ui-spec §2)
export function getTasks() {
  return state.tasksDoc && Array.isArray(state.tasksDoc.tasks) ? state.tasksDoc.tasks : [];
}

export function getCurrentTask() {
  const tasks = getTasks();
  return tasks.find((item) => item.id === state.taskId) || null;
}

export function getRoundsForTask(taskId) {
  if (!state.tasksDoc || !Array.isArray(state.tasksDoc.rounds)) return [];
  const task = getTasks().find((item) => item.id === taskId);
  const roundOrder = task && Array.isArray(task.rounds) ? task.rounds : [];
  const byTask = state.tasksDoc.rounds.filter((r) => r.task === taskId);
  if (!roundOrder.length) return byTask;
  const map = new Map(byTask.map((r) => [r.id, r]));
  const ordered = roundOrder.map((id) => map.get(id)).filter(Boolean);
  for (const r of byTask) {
    if (!roundOrder.includes(r.id)) ordered.push(r);
  }
  return ordered;
}

export function getCurrentRound() {
  const rounds = getRoundsForTask(state.taskId);
  return rounds.find((r) => r.id === state.roundId) || null;
}

export function getAllowedIndexSet() {
  const task = getCurrentTask();
  const round = getCurrentRound();
  return new Set([
    ...((task && task.index) || []),
    ...((round && round.index) || []),
  ]);
}

export function hasIndexAccess(key) {
  return getAllowedIndexSet().has(key);
}

function readSession(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSession(key, value) {
  try {
    if (value) window.sessionStorage.setItem(key, value);
    else window.sessionStorage.removeItem(key);
  } catch {
    // Ignore storage errors (private mode, blocked site data).
  }
}

// Only a round the viewer picked (menu, link card, `round=` link) is remembered, under its own
// key, so a tab that stored the first round under the old rule opens on the new default.
const ROUND_PICK_KEY = "fw_round_pick";

function rememberSelection({ roundPicked = false } = {}) {
  writeSession("fw_task", state.taskId);
  if (roundPicked) writeSession(ROUND_PICK_KEY, state.roundId);
}

// The round a task opens on: tasks[].default_round when it names one of the task's rounds
// (tray-jig-r1, the latest presented result; Hiếu 28/11/2026 evening), else its first round.
export function defaultRoundId(taskId) {
  const rounds = getRoundsForTask(taskId);
  const task = getTasks().find((item) => item.id === taskId);
  const want = task && typeof task.default_round === "string" ? task.default_round : null;
  if (want && rounds.some((r) => r.id === want)) return want;
  return rounds.length > 0 ? rounds[0].id : null;
}

// Picks the task and round after tasks.json loads: the ones remembered for this tab when
// they still exist, else the first task and its default round.
export function restoreSelection() {
  const tasks = getTasks();
  if (tasks.length === 0) return;
  const savedTask = readSession("fw_task");
  if (!tasks.some((item) => item.id === state.taskId)) {
    state.taskId = tasks.some((item) => item.id === savedTask) ? savedTask : tasks[0].id;
  }
  const rounds = getRoundsForTask(state.taskId);
  if (!rounds.some((r) => r.id === state.roundId)) {
    const savedRound = readSession(ROUND_PICK_KEY);
    state.roundId = rounds.some((r) => r.id === savedRound)
      ? savedRound
      : defaultRoundId(state.taskId);
  }
  rememberSelection();
}

// A `round=<id>` in the hash query (for links in a script) selects that round of the
// current task without a second render. Returns true when the round changed.
export function applyRoundParam(roundId) {
  if (!roundId || roundId === state.roundId) return false;
  const rounds = getRoundsForTask(state.taskId);
  if (!rounds.some((r) => r.id === roundId)) return false;
  state.roundId = roundId;
  state.selection = null;
  rememberSelection({ roundPicked: true });
  return true;
}

export function selectTask(nextTaskId) {
  const tasks = getTasks();
  const found = tasks.find((item) => item.id === nextTaskId);
  if (!found) return;
  const changed = state.taskId !== found.id;
  if (changed) {
    state.selection = null;
    state.taskCache = {};
    state.taskId = found.id;
    state.roundId = defaultRoundId(found.id);
    writeSession(ROUND_PICK_KEY, null);
    rememberSelection();
  }
  notifyStateChange("task");
}

export function selectRound(nextRoundId) {
  const rounds = getRoundsForTask(state.taskId);
  const found = rounds.find((r) => r.id === nextRoundId);
  state.roundId = found ? found.id : null;
  state.selection = null;
  rememberSelection({ roundPicked: true });
  notifyStateChange("round");
}

// Rounds of the current task (other than the selected one) whose index grants one of `keys`.
export function roundsWithIndex(keys) {
  const want = Array.isArray(keys) ? keys : [keys];
  return getRoundsForTask(state.taskId).filter(
    (r) => r.id !== state.roundId && (r.index || []).some((k) => want.includes(k))
  );
}

// Empty state for a page whose data belongs to another round: names the round and offers a
// button that switches to it, instead of a bare "no data" line (design audit P0-1).
export function renderRoundEmpty({ keys = [], text = null } = {}) {
  const others = roundsWithIndex(keys);
  const cur = getCurrentRound();
  const curName = cur ? pickLang(cur.title) || cur.id : t("state.na");
  return el("section", { className: cls("card", "round-empty") }, [
    el("p", {
      className: "round-empty-text",
      text:
        text ||
        (others.length > 0
          ? t("round.emptyElsewhere", { round: curName })
          : t("round.emptyNone", { round: curName })),
    }),
    others.length > 0
      ? el(
          "div",
          { className: "actions" },
          others.map((r) =>
            el(
              "button",
              {
                type: "button",
                className: cls("btn", "primary"),
                onClick: () => selectRound(r.id),
              },
              [t("round.switchTo", { round: pickLang(r.title) || r.id })]
            )
          )
        )
      : null,
  ]);
}

// "k/n" of a links count: {successes, n} or {k, n}; a preformatted string passes through.
function linkCount(v) {
  if (v == null) return null;
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    const k = v.successes ?? v.k;
    if (k != null && v.n != null) return `${formatNumber(k)}/${formatNumber(v.n)}`;
  }
  return null;
}

// Short name of a round for the link cards ("vòng đồ gá"), else its title.
function roundShortName(r, id) {
  const key = "round.shortName." + id;
  return hasI18nKey(key) ? t(key) : (r && pickLang(r.title)) || id;
}

// Cards that join the task's rounds both ways (tasks.json rounds[].links; Hiếu 28/11/2026
// evening): what the previous round found and what the next round reached. They place the
// numbers side by side only; never "better" or "+X points" (tray-jig.md §2, rule 4).
export function renderRoundLinks(round = getCurrentRound()) {
  const links = round && round.links && typeof round.links === "object" ? round.links : null;
  if (!links) return null;
  const rounds = getRoundsForTask(state.taskId);
  const withheld = getAllWithheldRuns();
  const card = (dir, L) => {
    if (!L || typeof L !== "object" || !L.round) return null;
    const target = rounds.find((r) => r.id === L.round);
    if (!target) return null;
    const result = withheld.has(L.run) ? null : linkCount(L);
    const name = roundShortName(target, L.round);
    let text;
    if (dir === "prev") {
      const carried = linkCount(L.carried);
      const placed = linkCount(L.placed);
      text =
        carried && placed
          ? t("round.linkPrevFound", { round: name, carried, placed })
          : t("round.linkPrev", { round: name });
    } else {
      text = result
        ? t("round.linkNext", { round: name, run: L.run || "—", result })
        : t("round.linkNextNoResult", { round: name });
    }
    const differs = L.scene_differs || L.scorer_differs;
    return el(
      "button",
      {
        type: "button",
        className: cls("round-link", "is-" + dir),
        title: t("round.switchTo", { round: pickLang(target.title) || target.id }),
        onClick: () => selectRound(L.round),
      },
      [
        el("span", { className: "round-link-dir", "aria-hidden": "true", text: dir === "prev" ? "←" : "→" }),
        el("b", { className: "round-link-text", text }),
        differs ? el("span", { className: "tiny muted", text: t("round.linkDiffers") }) : null,
      ]
    );
  };
  const cards = [card("prev", links.prev), card("next", links.next)].filter(Boolean);
  if (cards.length === 0) return null;
  return el("section", { className: "round-links", "aria-label": t("round.linksAria") }, cards);
}

// "Diễn tiến": story.timeline newest first, at most `max` rows (index contract 28/11 evening).
// The row of story.latest's round is marked; a row's round opens that round.
export function renderTimeline(raw = state.storyRawDoc, { max = 6 } = {}) {
  const rows = raw && Array.isArray(raw.timeline) ? raw.timeline.slice() : [];
  if (rows.length === 0) return null;
  const latest = raw.latest && typeof raw.latest === "object" ? raw.latest : null;
  const rounds = getRoundsForTask(state.taskId);
  rows.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  const shown = rows.slice(0, max);
  // one marked row: the latest round's row on latest.date, else that round's newest row
  const latestRow = latest
    ? shown.find((r) => r.round === latest.round && latest.date && r.date === latest.date) ||
      shown.find((r) => r.round === latest.round) ||
      null
    : null;
  return el("section", { className: "card" }, [
    el("div", { className: "task-head" }, [
      el("h2", { text: t("home.timelineTitle") }),
      latest && latest.round
        ? el("span", {
            className: "chip",
            text: t("home.timelineLatest", {
              round: roundShortName(rounds.find((r) => r.id === latest.round), latest.round),
              run: latest.run || "—",
            }),
          })
        : null,
    ]),
    el(
      "ol",
      { className: "timeline-list" },
      shown.map((row) => {
        const isLatest = row === latestRow;
        const target = row.round ? rounds.find((r) => r.id === row.round) : null;
        const result = pickLang(row.result);
        return el("li", { className: cls("timeline-row", isLatest && "is-latest") }, [
          el("span", { className: "timeline-date mono", text: row.date || "—" }),
          el("div", { className: "timeline-body" }, [
            el("div", {}, [
              row.story ? el("span", { className: "tax-badge", text: row.story }) : null,
              el("b", { text: pickLang(row.title) || row.story || "—" }),
              isLatest
                ? el("span", { className: "chip", text: t("home.timelineLatestTag") })
                : null,
            ]),
            result ? el("div", { className: "tiny", text: result }) : null,
            el("div", { className: "timeline-meta tiny muted" }, [
              row.doc ? el("span", { className: "mono", text: scrubPath(row.doc) }) : null,
              target && target.id !== state.roundId
                ? el(
                    "button",
                    {
                      type: "button",
                      className: "link timeline-round",
                      onClick: () => selectRound(target.id),
                    },
                    [t("round.switchTo", { round: roundShortName(target, target.id) })]
                  )
                : null,
            ]),
          ]),
        ]);
      })
    ),
  ]);
}

export function getAllWithheldRuns() {
  const rounds =
    state.tasksDoc && Array.isArray(state.tasksDoc.rounds) ? state.tasksDoc.rounds : [];
  const set = new Set();
  for (const r of rounds) {
    for (const runId of r.withhold_eval || []) {
      set.add(runId);
    }
  }
  return set;
}

export function filterWithheldStory(doc, withheldSet = getAllWithheldRuns()) {
  if (!doc || typeof doc !== "object" || withheldSet.size === 0) return doc;
  const omitKeys = (obj) => {
    if (!obj || typeof obj !== "object") return {};
    const copy = {};
    for (const [k, v] of Object.entries(obj)) {
      if (!withheldSet.has(k)) copy[k] = v;
    }
    return copy;
  };
  const out = { ...doc };
  if (out.pair && typeof out.pair === "object") {
    out.pair = {
      ...out.pair,
      runs: (out.pair.runs || []).filter((r) => !withheldSet.has(r.run)),
      comparisons: (out.pair.comparisons || []).filter(
        (c) => !withheldSet.has(c.variant) && !withheldSet.has(c.baseline)
      ),
    };
  }
  if (out.jig && typeof out.jig === "object") {
    // Results of a withheld run in the jig block (defence in depth: the index writes only
    // {run, role, status: "withheld"} for it). Its train entry in jig.runs stays, as for pair.
    const keep = (list) =>
      Array.isArray(list) ? list.filter((r) => !(r && withheldSet.has(r.run))) : list;
    const nextJig = {
      ...out.jig,
      evals: Array.isArray(out.jig.evals)
        ? out.jig.evals.map((e) =>
            e && withheldSet.has(e.run) ? { run: e.run, role: e.role, status: "withheld" } : e
          )
        : out.jig.evals,
      outcomes: keep(out.jig.outcomes),
      rollouts: keep(out.jig.rollouts),
      conditions: keep(out.jig.conditions),
    };
    if (withheldSet.has(nextJig.featured)) nextJig.featured = null;
    if (nextJig.compare60 && typeof nextJig.compare60 === "object") {
      nextJig.compare60 = withheldSet.has(nextJig.compare60.run)
        ? null
        : { ...nextJig.compare60, earlier: keep(nextJig.compare60.earlier) };
    }
    out.jig = nextJig;
  }
  if (out.follow && typeof out.follow === "object") {
    const nextFollow = { ...out.follow, runs: omitKeys(out.follow.runs) };
    delete nextFollow.r3;
    out.follow = nextFollow;
  }
  if (out.demo && typeof out.demo === "object") {
    const nextDemo = { ...out.demo };
    delete nextDemo.round1_reading;
    if (nextDemo.ladder && typeof nextDemo.ladder === "object") {
      const nextLadder = { ...nextDemo.ladder, runs: omitKeys(nextDemo.ladder.runs) };
      if (nextLadder.on_table_b && typeof nextLadder.on_table_b === "object") {
        nextLadder.on_table_b = {
          ...nextLadder.on_table_b,
          value: omitKeys(nextLadder.on_table_b.value),
          check_from_rollouts: omitKeys(nextLadder.on_table_b.check_from_rollouts),
          quote: null,
        };
      }
      nextDemo.ladder = nextLadder;
    }
    out.demo = nextDemo;
  }
  return out;
}

export function scopeStoryForTask(rawStory) {
  const allowed = getAllowedIndexSet();
  const scoped = {};
  for (const [k, v] of Object.entries(rawStory || {})) {
    if (allowed.has(`story.${k}`)) {
      scoped[k] = v;
    }
  }
  return filterWithheldStory(scoped);
}

// Short reading lines of one jig eval (story.jig.evals[], index/jig.py): one per rule whose
// verdict is given, threshold from the reading itself. Empty unless the eval is "ready".
export function jigReadingLines(ev) {
  if (!ev || ev.status !== "ready" || !Array.isArray(ev.readings)) return [];
  const out = [];
  for (const rd of ev.readings) {
    if (rd.verdict !== "met" && rd.verdict !== "not_met") continue;
    const pct = Number.isFinite(rd.threshold) ? formatPercent(rd.threshold, 0) : t("state.na");
    const scope =
      rd.scope === "whole_task"
        ? t("exp.scopeWhole")
        : rd.scope === "level"
          ? t("exp.scopeLevel", { lv: rd.level })
          : t("exp.scopePlace");
    const verdict =
      rd.verdict === "met"
        ? t("exp.verdictMet", { pct })
        : t("exp.verdictNotMet", { pct });
    out.push(`${scope}: ${verdict}`);
  }
  return out;
}

export function scopeSimForTask(rawSim) {
  const sim = rawSim || {};
  const tid = state.taskId;
  const teleop = (sim.teleop || []).filter((e) => !tid || e.task === tid);
  if (hasIndexAccess("sim")) {
    // Both rounds list "sim"; sim.rounds[round] holds the round's own cut (index contract 28/11).
    const own = sim.rounds && state.roundId ? sim.rounds[state.roundId] : null;
    return { ...sim, ...(own && typeof own === "object" ? own : {}), teleop };
  }
  return {
    source: null,
    sha8: null,
    parts: [],
    cuts: {},
    batch: {},
    episodes: [],
    round: null,
    format: null,
    teleop,
    simLockedByScope: true,
  };
}

// DOM & Studio UI Builders
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "className") {
      node.className = v;
    } else if (k === "text") {
      node.textContent = String(v);
    } else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v === true) {
      node.setAttribute(k, "");
    } else {
      node.setAttribute(k, String(v));
    }
  }
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child === null || child === undefined || child === false) continue;
    if (typeof child === "string" || typeof child === "number") {
      node.appendChild(document.createTextNode(String(child)));
    } else {
      node.appendChild(child);
    }
  }
  return node;
}

export function safeThumbUrl(url) {
  if (!url || typeof url !== "string") return null;
  if (url.startsWith("/data/") || url.startsWith("data/") || url.startsWith("/media/")) {
    return url;
  }
  if (url.startsWith("posters/")) {
    return `/ego/${url}`;
  }
  return null;
}

export function cls(...parts) {
  return parts.filter(Boolean).join(" ");
}

export function setChildren(parent, ...items) {
  if (!parent) return;
  parent.replaceChildren(...items.flat(2).filter(Boolean));
}

export function renderCrumbHeading({ crumbs = [], title = "", lead = "", actions = [] }) {
  const crumbChildren = [];
  crumbs.forEach((c, idx) => {
    if (idx > 0) crumbChildren.push(" / ");
    if (c.href) {
      crumbChildren.push(el("a", { href: c.href, text: c.label }));
    } else {
      crumbChildren.push(el("span", { text: c.label }));
    }
  });
  return [
    el("div", { className: "crumb" }, crumbChildren),
    el("div", { className: "heading" }, [
      el("div", {}, [
        el("h1", { text: title }),
        lead ? el("p", { text: lead }) : null,
      ]),
      actions && actions.length > 0 ? el("div", { className: "actions" }, actions) : null,
    ]),
  ];
}

export function renderHero({ eyebrow, title, body, tags = [] }) {
  return el("section", { className: "hero" }, [
    eyebrow ? el("div", { className: "eyebrow", text: eyebrow }) : null,
    el("h2", { text: title }),
    body ? el("p", { text: body }) : null,
    tags.length > 0
      ? el(
          "div",
          { className: "hero-tags" },
          tags.filter(Boolean).map((tag) => el("span", { text: tag }))
        )
      : null,
  ]);
}

export function renderStatStrip(items) {
  return el(
    "div",
    { className: "summary" },
    items.map((it) =>
      el("div", { className: "stat" }, [
        el("div", { className: "label", text: it.label }),
        el("b", { text: it.value }),
        it.sub ? el("small", { text: it.sub }) : null,
      ])
    )
  );
}

export function isStageComplete(rawState) {
  return ["done", "ok", "pass"].includes(String(rawState || "").toLowerCase());
}

export function formatStateLabel(rawState) {
  if (rawState === null || rawState === undefined || rawState === "") return t("state.na");
  const st = String(rawState).toLowerCase();
  const key = "status.state." + st;
  return hasI18nKey(key) ? t("status.state." + st) : String(rawState);
}

export function formatJobKindLabel(rawKind) {
  const code = String(rawKind || "").trim();
  if (!code) return { label: t("state.na"), code: "" };
  const i18nKey = "job.kind." + code;
  if (hasI18nKey(i18nKey)) {
    return { label: t("job.kind." + code), code };
  }
  const kindsList = state.kindsDoc && Array.isArray(state.kindsDoc.kinds) ? state.kindsDoc.kinds : [];
  const found = kindsList.find((k) => k && (k.kind === code || k.id === code));
  if (found) {
    const title = pickLang(found.title) || found.label || "";
    if (title && title !== code) return { label: title, code };
  }
  return { label: code, code: "" };
}

export function renderJobKindCell(rawKind, extraNode = null) {
  const { label, code } = formatJobKindLabel(rawKind);
  return el("div", { className: "job-kind-cell" }, [
    el("div", { className: "actions" }, [
      el("b", { text: label }),
      extraNode,
    ]),
    code ? el("div", { className: cls("tiny", "mono"), text: code }) : null,
  ]);
}

export function renderStateChip(rawState) {
  const st = String(rawState || "idle").toLowerCase();
  const label = formatStateLabel(rawState || "idle");
  let tone = "neutral";
  if (
    st === "done" ||
    st === "ok" ||
    st === "pass" ||
    st === "current" ||
    st === "up" ||
    st === "warm" ||
    st === "baseline"
  ) {
    tone = "";
  } else if (
    st === "running" ||
    st === "queued" ||
    st === "waiting" ||
    st === "flag" ||
    st === "partial" ||
    st === "estimated" ||
    st === "cold" ||
    st === "busy" ||
    st === "continue" ||
    st === "after_round"
  ) {
    tone = "warning";
  } else if (
    st === "failed" ||
    st === "blocked" ||
    st === "reject" ||
    st === "cancelled" ||
    st === "down" ||
    st === "f"
  ) {
    tone = "danger";
  }
  return el("span", { className: cls("chip", tone), text: label });
}

// Source of a number: one small "Nguồn" disclosure instead of a monospace path line, so
// pages read as a report while every number keeps its source one click away (audit G3).
export function renderSourceCitation(source, quote = null, kind = null) {
  const cleanedQuote = cleanInlineMarkdown(quote);
  if (!source && !cleanedQuote && !kind) return null;
  return el("div", { className: "citation-block" }, [
    kind
      ? el("span", {
          className: cls("chip", kind === "estimated" ? "warning" : "neutral"),
          text: hasI18nKey("cite.kind." + kind) ? t("cite.kind." + kind) : kind,
        })
      : null,
    source || cleanedQuote
      ? el("details", { className: "citation-excerpt" }, [
          el("summary", { text: t("common.source") }),
          source ? el("span", { className: "sources-note mono", text: scrubPath(source) }) : null,
          cleanedQuote ? el("blockquote", { className: "cite-quote", text: cleanedQuote }) : null,
        ])
      : null,
  ]);
}

export function renderProcessEmptyBlock(stageNum, customTitle = null) {
  const task = getCurrentTask();
  const proc = (task && task.process && task.process[String(stageNum)]) || {};
  const missing = pickLang(proc.missing);
  const remote = proc.remote || null;
  const howItems = Array.isArray(proc.how) ? proc.how : [];

  return el("section", { className: "card" }, [
    el("div", { className: "ds" }, [
      el("div", { className: "tile", text: `0${stageNum}` }),
      el("div", { className: "row-body" }, [
        el("h2", { text: customTitle || t("proc.stage." + String(stageNum)) }),
        el("p", {
          className: "muted",
          text: missing || t("state.scopeRestricted"),
        }),
      ]),
    ]),
    remote
      ? el("p", {
          className: "sources-note",
          text: t("tasks.remoteLabel", { where: remote }),
        })
      : null,
    howItems.length > 0
      ? el(
          "ul",
          { className: "how-list" },
          howItems.map((h) =>
            el("li", { className: "how-item mono" }, [
              h.text || (h.section ? `${h.path} §${h.section}` : h.path) || "",
              h.note ? ` (${h.note})` : "",
            ])
          )
        )
      : null,
  ]);
}

export function renderReportSubnav(activePath) {
  const links = [
    { key: "report", hash: "#/report" },
    { key: "base", hash: "#/base" },
    { key: "eval", hash: "#/eval" },
    { key: "diagnose", hash: "#/diagnose" },
    { key: "loop", hash: "#/loop" },
    { key: "follow", hash: "#/follow" },
    { key: "design", hash: "#/design" },
    { key: "cost", hash: "#/cost" },
  ];
  return el("nav", { className: "tabs subnav-bar", "aria-label": t("report.subnavAria") }, [
    el("span", { className: "eyebrow subnav-label", text: t("report.subnavTitle") }),
    ...links.map((item) =>
      el(
        "a",
        {
          href: item.hash,
          className: cls("tab", activePath === item.key && "active"),
          "aria-current": activePath === item.key ? "page" : null,
        },
        [t("nav.item." + item.key)]
      )
    ),
  ]);
}

export function renderChartBlock({
  title,
  subtitle = null,
  height = 260,
  buildOption,
  tableNode,
  onChartClick = null,
}) {
  const chartBox = el("div", { className: "chart-box", style: `height:${height}px` });
  const fallbackWrap = el("div", { className: "chart-fallback", hidden: true }, [
    tableNode || el("p", { className: "muted", text: t("state.empty") }),
  ]);
  const toggleBtn = el(
    "button",
    {
      type: "button",
      className: "topbtn",
      onClick: () => {
        const showingTable = !fallbackWrap.hidden;
        fallbackWrap.hidden = showingTable;
        chartBox.hidden = !showingTable;
        toggleBtn.textContent = showingTable ? t("chart.showTable") : t("chart.showChart");
        if (showingTable) resizeMountedCharts();
      },
    },
    [t("chart.showTable")]
  );

  const card = el("section", { className: "card" }, [
    el("div", { className: "sect chart-head" }, [
      el("div", {}, [
        el("h2", { text: title }),
        subtitle ? el("p", { className: "muted", text: subtitle }) : null,
      ]),
      tableNode ? toggleBtn : null,
    ]),
    chartBox,
    fallbackWrap,
  ]);

  window.requestAnimationFrame(() => {
    if (typeof window.echarts === "undefined") {
      chartBox.hidden = true;
      fallbackWrap.hidden = false;
      toggleBtn.hidden = true;
      return;
    }
    mountChart(chartBox, buildOption);
    if (typeof onChartClick === "function") {
      const inst = window.echarts.getInstanceByDom(chartBox);
      if (inst) inst.on("click", onChartClick);
    }
  });

  return card;
}

export function renderLoadingView(titleKeyOrText = null) {
  const headingText = titleKeyOrText || t("state.loading");
  return el("div", { "aria-busy": "true" }, [
    el("div", { className: "heading" }, [
      el("div", {}, [
        el("h1", { text: headingText }),
        el("p", { text: t("state.loading") }),
      ]),
    ]),
    el("div", { className: "skeleton-box" }),
    el("div", { className: "grid" }, [
      el("div", { className: "card" }, [
        el("div", { className: "skeleton-line lg" }),
        el("div", { className: "skeleton-box" }),
      ]),
      el("div", { className: "card" }, [
        el("div", { className: "skeleton-line lg" }),
        el("div", { className: "skeleton-box" }),
      ]),
    ]),
  ]);
}

export function renderErrorBlock(err, onRetry = null) {
  const status = err && typeof err.status === "number" ? err.status : 0;
  const rawMessage =
    (err && err.serverMessage) ||
    (err && err.message) ||
    t("error.network");

  return el("section", { className: cls("card", "state-error"), role: "alert" }, [
    el("h2", { text: t("error.blockTitle") }),
    status > 0
      ? el("span", {
          className: cls("chip", "danger", "mono"),
          text: t("error.httpCode", { code: status }),
        })
      : null,
    el("p", { className: "mono", text: rawMessage }),
    typeof onRetry === "function"
      ? el(
          "button",
          {
            type: "button",
            className: "btn",
            onClick: onRetry,
          },
          [t("error.retry")]
        )
      : null,
  ]);
}

export function shortHashId(rawId) {
  if (!rawId) return "-";
  const s = String(rawId).trim();
  const hexMatch = s.match(/(?:^|[_-])([0-9a-f]{8,40})$/i);
  if (hexMatch) return `#${hexMatch[1].slice(0, 4)}`;
  if (s.startsWith("src_") && s.length >= 8) return `#${s.slice(4, 8)}`;
  if (s.length <= 14) return s;
  return `${s.slice(0, 10)}…${s.slice(-4)}`;
}

export function compactPath(raw) {
  if (!raw) return "-";
  const s = String(raw).trim();
  if (!s) return "-";
  if (s.includes("+")) {
    const parts = s.split("+").map((p) => {
      const hm = p.trim().match(/(?:^|[_-])([0-9a-f]{8,40})$/i);
      return hm ? `#${hm[1].slice(0, 4)}` : compactPath(p);
    });
    return parts.join(" + ");
  }
  const clean = s.replace(/\/+$/, "");
  const segs = clean.split("/").filter(Boolean);
  const last = segs.length > 0 ? segs[segs.length - 1] : clean;
  const hexTail = last.match(/^([a-z0-9_-]{2,16}?)[_-]([0-9a-f]{8,40})$/i);
  if (hexTail) return `${hexTail[1]}#${hexTail[2].slice(0, 4)}`;
  if (last.length > 26) {
    return `${last.slice(0, 16)}…${last.slice(-6)}`;
  }
  return last;
}

// Machine paths never reach the screen (design 15/11 §5.3.3, design audit P0-3): a path
// under fwdata/ or the repo keeps only its relative part; any other absolute path
// (a user home, /content on Colab, /mnt, /tmp) keeps only its file name.
const ABS_PATH = /(?:\/(?:home|Users|root|content|mnt|tmp|workspace|opt|srv)\/)[^\s"'`<>()\],;]*/g;

export function scrubPath(raw) {
  if (raw === null || raw === undefined) return "";
  return String(raw).replace(ABS_PATH, (m) => {
    const fw = m.indexOf("/fwdata/");
    if (fw >= 0) return m.slice(fw + 1);
    if (m.endsWith("/fwdata")) return "fwdata";
    const repo = m.search(/\/denso-[a-z0-9-]+\//i);
    if (repo >= 0) return m.slice(m.indexOf("/", repo + 1) + 1);
    const segs = m.split("/").filter(Boolean);
    return segs.length > 2 ? `…/${segs[segs.length - 1]}` : m;
  });
}

// Log tail shown on a page: drops W&B lines and any line with a URL (account names ride in
// them), then hides machine paths in what is left.
export function cleanLogLines(lines) {
  const list = Array.isArray(lines) ? lines : String(lines || "").split("\n");
  return list
    .filter((ln) => !/wandb|https?:\/\//i.test(String(ln)))
    .map((ln) => scrubPath(ln));
}

export function canonicalDatasetTaxonomy(row) {
  const r = row || {};
  const id = String(r.id || "");
  const taskRaw = String(r.task || "");
  let taskTag = "gen";
  if (taskRaw.includes("tray") || id.includes("tray") || id.startsWith("s70") || id.startsWith("h1m")) {
    taskTag = "tray";
  } else if (taskRaw.includes("cube") || id.includes("cube")) {
    taskTag = "cube";
  }

  const grp = String(r.group || "").toLowerCase();
  let modTag = grp || "data";
  if (grp === "egocentric") modTag = "ego";
  else if (grp === "s1" || grp === "s2") modTag = `sim-${grp}`;

  let stageTag = "set";
  if (id.startsWith("src_")) stageTag = "work";
  else if (r.status === "current") stageTag = "cut";
  else if (r.status === "reference") stageTag = "ref";
  else if (grp === "eval") stageTag = "eval";

  let cleanTitle = String(r.title || r.name || id).trim();
  if (cleanTitle === id && id.startsWith("src_")) {
    cleanTitle = `${modTag} ${shortHashId(id)}`;
  }
  cleanTitle = cleanTitle.replace(/\s*\(src_[0-9a-f]+\)\s*/gi, " ").trim();

  return {
    code: `${taskTag} · ${modTag} · ${stageTag}`,
    cleanTitle: cleanTitle || id,
    shortId: shortHashId(id),
  };
}

export function friendlyBatchTitle(name, sourceDetail = "", catRows = []) {
  const nm = String(name || "");
  if (Array.isArray(catRows) && catRows.length > 0) {
    const hit = catRows.find((r) => r && r.id === nm);
    if (hit && hit.title && hit.title !== nm) {
      return String(hit.title).replace(/\s*\(src_[0-9a-f]+\)\s*/gi, "").trim();
    }
  }
  if (sourceDetail) {
    const base = compactPath(sourceDetail)
      .replace(/\.(mp4|mov|mkv|zip|tar|json|parquet)$/i, "")
      .replace(/[_-]+/g, " ")
      .trim();
    if (base && base !== "-") return base;
  }
  return `${t("cat.group.egocentric")} ${shortHashId(nm)}`;
}

export function renderFlywheelOrbitalCanvas({
  stages = [],
  selectedIdx = 0,
  centerTitle = "",
  centerSub = "",
  showTaskTag = false,
  onSelect = null,
}) {
  const logicalW = 450;
  const logicalH = 344;
  let activeIdx = Math.max(0, Math.min(Math.max(0, stages.length - 1), Number(selectedIdx) || 0));
  let hoverIdx = -1;

  const canvas = el("canvas", {
    tabindex: "0",
    role: "region",
    "aria-label": t("fly.hubLabel"),
    style: "width:100%;max-width:450px;height:auto;aspect-ratio:450/344;cursor:pointer;display:block",
  });
  const nodeHitBoxes = [];

  const cssColor = (varName) =>
    getComputedStyle(document.documentElement).getPropertyValue(varName).trim();

  const draw = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(logicalW * dpr)) {
      canvas.width = Math.round(logicalW * dpr);
      canvas.height = Math.round(logicalH * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, logicalW, logicalH);

    const cGreen = cssColor("--green");
    const cPale = cssColor("--pale");
    const cSurface = cssColor("--surface");
    const cSurface2 = cssColor("--surface2");
    const cLine = cssColor("--line");
    const cInk = cssColor("--ink");
    const cSoft = cssColor("--soft");
    const cSuccess = cssColor("--success");
    const cWarn = cssColor("--warning");
    const cDanger = cssColor("--danger");

    const cx = logicalW / 2;
    const cy = logicalH / 2;
    const rx = 156;
    const ry = 122;
    const n = Math.max(1, stages.length);

    // Outer subtle orbit guide
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx + 24, ry + 20, 0, 0, Math.PI * 2);
    ctx.setLineDash([4, 6]);
    ctx.strokeStyle = cLine;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();

    // Main flywheel ring
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.strokeStyle = cLine;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();

    // Directional clockwise arcs + arrowheads between stages
    for (let i = 0; i < n; i += 1) {
      const a1 = -Math.PI / 2 + (i * Math.PI * 2) / n + 0.24;
      const a2 = -Math.PI / 2 + ((i + 1) * Math.PI * 2) / n - 0.24;
      if (a2 <= a1) continue;
      const st = stages[i] || {};
      const stDone = isStageComplete(st.state);
      ctx.save();
      ctx.beginPath();
      for (let step = 0; step <= 18; step += 1) {
        const ang = a1 + ((a2 - a1) * step) / 18;
        const px = cx + rx * Math.cos(ang);
        const py = cy + ry * Math.sin(ang);
        if (step === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = stDone ? cGreen : cLine;
      ctx.lineWidth = stDone ? 2.6 : 1.6;
      ctx.stroke();

      // Arrowhead at midpoint of arc
      const mid = (a1 + a2) / 2;
      const mx = cx + rx * Math.cos(mid);
      const my = cy + ry * Math.sin(mid);
      const tx = -rx * Math.sin(mid);
      const ty = ry * Math.cos(mid);
      const tang = Math.atan2(ty, tx);
      ctx.translate(mx, my);
      ctx.rotate(tang);
      ctx.beginPath();
      ctx.moveTo(5, 0);
      ctx.lineTo(-4, -3.8);
      ctx.lineTo(-4, 3.8);
      ctx.closePath();
      ctx.fillStyle = stDone ? cGreen : cSoft;
      ctx.fill();
      ctx.restore();
    }

    // Center hub
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, 56, 0, Math.PI * 2);
    ctx.fillStyle = cPale;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = cGreen;
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = cGreen;
    ctx.font = "700 9.5px ui-sans-serif, system-ui, sans-serif";
    ctx.fillText(t("fly.hubLabel").slice(0, 22), cx, cy - 22);

    ctx.fillStyle = cInk;
    ctx.font = "700 13px ui-sans-serif, system-ui, sans-serif";
    const hubTitle = String(centerTitle || "").slice(0, 16);
    ctx.fillText(hubTitle, cx, cy - 3);

    ctx.fillStyle = cGreen;
    ctx.font = "700 13px ui-monospace, monospace";
    ctx.fillText(String(centerSub || ""), cx, cy + 18);
    ctx.restore();

    // Stage orbital pills
    nodeHitBoxes.length = 0;
    const boxW = 108;
    const boxH = 46;

    for (let i = 0; i < n; i += 1) {
      const ang = -Math.PI / 2 + (i * Math.PI * 2) / n;
      const nx = cx + rx * Math.cos(ang);
      const ny = cy + ry * Math.sin(ang);
      const st = stages[i] || {};
      const isSel = i === activeIdx;
      const isHov = i === hoverIdx;
      const stKey = String(st.state || "idle").toLowerCase();

      let dotColor = cSoft;
      if (isStageComplete(st.state)) dotColor = cSuccess;
      else if (stKey === "blocked" || stKey === "failed" || stKey === "reject") dotColor = cDanger;
      else if (
        stKey === "waiting" ||
        stKey === "running" ||
        stKey === "queued" ||
        stKey === "flag" ||
        stKey === "partial"
      ) {
        dotColor = cWarn;
      }

      const x0 = nx - boxW / 2;
      const y0 = ny - boxH / 2;
      nodeHitBoxes.push({ idx: i, x0, y0, x1: x0 + boxW, y1: y0 + boxH });

      ctx.save();
      if (isSel) {
        ctx.beginPath();
        ctx.roundRect(x0 - 3, y0 - 3, boxW + 6, boxH + 6, 13);
        ctx.fillStyle = cPale;
        ctx.fill();
      }
      ctx.beginPath();
      ctx.roundRect(x0, y0, boxW, boxH, 10);
      ctx.fillStyle = isSel ? cSurface : isHov ? cPale : cSurface2;
      ctx.fill();
      ctx.lineWidth = isSel ? 2.2 : 1.2;
      ctx.strokeStyle = isSel || isHov ? cGreen : cLine;
      ctx.stroke();

      // Status dot + number
      ctx.beginPath();
      ctx.arc(x0 + 13, y0 + 14, 4.2, 0, Math.PI * 2);
      ctx.fillStyle = dotColor;
      ctx.fill();

      ctx.fillStyle = cSoft;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.font = "700 10.5px ui-monospace, monospace";
      ctx.fillText(`0${i + 1}`, x0 + 22, y0 + 14);

      const rawLabel = hasI18nKey("home.stageId." + st.id)
        ? t("home.stageId." + st.id)
        : st.label || st.id || "";
      const shortLbl = rawLabel.length > 13 ? `${rawLabel.slice(0, 12)}…` : rawLabel;
      ctx.fillStyle = cInk;
      ctx.font = "650 11.5px ui-sans-serif, system-ui, sans-serif";
      ctx.fillText(shortLbl, x0 + 10, y0 + 32);
      ctx.restore();
    }
  };

  let pillButtons = [];

  const selectStage = (nextIdx, notify = true) => {
    if (stages.length === 0) return;
    activeIdx = Math.max(0, Math.min(stages.length - 1, nextIdx));
    pillButtons.forEach((btn, idx) => {
      const isAct = idx === activeIdx;
      btn.classList.toggle("is-active", isAct);
      btn.setAttribute("aria-pressed", String(isAct));
    });
    draw();
    if (notify && typeof onSelect === "function") onSelect(activeIdx);
  };

  pillButtons = stages.map((item, i) => {
    const st = item || {};
    const stLow = String(st.state || "").toLowerCase();
    const sym = isStageComplete(st.state)
      ? "✓"
      : ["blocked", "failed", "reject"].includes(stLow)
        ? "!"
        : "•";
    const fullTitle = hasI18nKey("home.stageId." + st.id)
      ? t("home.stageId." + st.id)
      : st.label || st.id || "";
    const num = String(i + 1).padStart(2, "0");
    const ownerSuffix = showTaskTag ? ` [${st.task || "?"}]` : "";
    const toneCls = ["blocked", "failed", "reject"].includes(stLow)
      ? "is-danger"
      : ["waiting", "running", "queued", "flag", "partial"].includes(stLow)
        ? "is-warn"
        : "";
    return el(
      "button",
      {
        type: "button",
        className: cls("stage-pill", toneCls, i === activeIdx && "is-active"),
        "aria-pressed": String(i === activeIdx),
        onClick: () => selectStage(i, true),
      },
      [`${num} · ${fullTitle}${ownerSuffix} ${sym}`]
    );
  });

  const hitIndexFromEvent = (ev) => {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return -1;
    const lx = ((ev.clientX - rect.left) / rect.width) * logicalW;
    const ly = ((ev.clientY - rect.top) / rect.height) * logicalH;
    for (const b of nodeHitBoxes) {
      if (lx >= b.x0 && lx <= b.x1 && ly >= b.y0 && ly <= b.y1) return b.idx;
    }
    return -1;
  };

  canvas.addEventListener("mousemove", (ev) => {
    const idx = hitIndexFromEvent(ev);
    if (idx !== hoverIdx) {
      hoverIdx = idx;
      canvas.style.cursor = idx >= 0 ? "pointer" : "default";
      draw();
    }
  });

  canvas.addEventListener("mouseleave", () => {
    if (hoverIdx !== -1) {
      hoverIdx = -1;
      draw();
    }
  });

  canvas.addEventListener("click", (ev) => {
    const idx = hitIndexFromEvent(ev);
    if (idx >= 0) {
      selectStage(idx, true);
    }
  });

  canvas.addEventListener("keydown", (ev) => {
    const n = stages.length;
    if (n <= 0) return;
    if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
      ev.preventDefault();
      selectStage((activeIdx + 1) % n, true);
    } else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
      ev.preventDefault();
      selectStage((activeIdx - 1 + n) % n, true);
    } else if (ev.key === "Enter") {
      const cur = stages[activeIdx];
      if (cur && typeof cur.link === "string" && cur.link.startsWith("#/")) {
        ev.preventDefault();
        window.location.hash = cur.link;
      }
    }
  });

  window.requestAnimationFrame(draw);

  return el("div", { className: "flywheel-canvas-wrap" }, [
    canvas,
    el("div", { className: "stage-pill-bar" }, pillButtons),
    el("div", {
      className: cls("tiny", "muted"),
      style: "text-align:center",
      text: t("ux.kbdStageHint"),
    }),
  ]);
}
