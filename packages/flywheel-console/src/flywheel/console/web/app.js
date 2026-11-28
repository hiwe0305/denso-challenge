import { initChatShell, notifyChatRouteChanged, syncChatShell } from "./chat.js";
import {
  announce,
  bindErrorBannerControls,
  cleanupCurrentPage,
  el,
  getJSON,
  getRoundsForTask,
  getTasks,
  hideErrorBanner,
  notifyStateChange,
  pickLang,
  selectRound,
  selectTask,
  setChatOpen,
  setLang,
  setTheme,
  state,
  subscribe,
  t,
} from "./core.js";
import { renderChatStudioPage } from "./pages_chat.js";
import {
  renderDataCatalogPage,
  renderDatasetDetailPage,
  renderEgoflowPage,
  renderEpisodeDetailPage,
  renderSimDetailPage,
  renderSimLibraryPage,
} from "./pages_data.js";
import { renderHomePage, renderJobsPage, renderQaPage } from "./pages_ops.js";
import {
  renderBasePage,
  renderCostPage,
  renderDesignPage,
  renderDiagnosePage,
  renderEvalPage,
  renderFollowPage,
  renderLoopPage,
  renderReportPage,
  renderRunsPage,
} from "./pages_story.js";
import { renderTasksPage } from "./pages_tasks.js";

// Mandatory legacy route redirects (ui-spec §1)
export const REDIRECT = {
  "overview": "home",
  "process": "jobs?view=pipeline",
  "training": "runs",
  "agent": "qa",
  "data/nhap": "jobs?panel=import",
  "data/xuat": "jobs?panel=export",
};

const ROUTE_REASONS = new Set([
  "bootstrap",
  "lang",
  "task",
  "round",
  "data-view",
  "lock",
  "tasks",
  "tasks-error",
  "status-error",
]);

const NAV_GROUPS = [
  {
    group: "start",
    items: [
      { key: "home", icon: "◫", hash: "#/home" },
      { key: "chat", icon: "✦", hash: "#/chat" },
      { key: "tasks", icon: "▦", hash: "#/tasks" },
    ],
  },
  {
    group: "data",
    items: [
      { key: "data", icon: "▤", hash: "#/data" },
      { key: "import", icon: "⇣", hash: "#/jobs?panel=import" },
      { key: "pipeline", icon: "↻", hash: "#/jobs?view=pipeline" },
      { key: "qa", icon: "✓", hash: "#/qa" },
      { key: "egoflow", icon: "◷", hash: "#/egoflow" },
      { key: "export", icon: "⇡", hash: "#/jobs?panel=export" },
    ],
  },
  {
    group: "ops",
    items: [{ key: "jobs", icon: "≡", hash: "#/jobs" }],
  },
  {
    group: "exp",
    items: [
      { key: "runs", icon: "⌁", hash: "#/runs" },
      { key: "eval", icon: "◉", hash: "#/eval" },
      { key: "sim", icon: "▷", hash: "#/sim" },
    ],
  },
  {
    group: "f2d",
    items: [
      { key: "diagnose", icon: "⌕", hash: "#/diagnose" },
      { key: "loop", icon: "⟳", hash: "#/loop" },
      { key: "base", icon: "◨", hash: "#/base" },
      { key: "follow", icon: "⊕", hash: "#/follow" },
    ],
  },
  {
    group: "plan",
    items: [
      { key: "design", icon: "◇", hash: "#/design" },
      { key: "cost", icon: "$", hash: "#/cost" },
      { key: "report", icon: "▧", hash: "#/report" },
    ],
  },
];

let mobileMenuOpen = false;

function parseHash(rawHash) {
  const clean = (rawHash || "").replace(/^#/, "");
  const [rawPath = "", rawQuery = ""] = clean.split("?");
  const path = rawPath.replace(/^\/+|\/+$/g, "");
  return { path, rawQuery, query: new URLSearchParams(rawQuery) };
}

export function resolveRedirectHash(rawHash) {
  const { path, rawQuery, query } = parseHash(rawHash);
  if (!path) {
    return rawQuery ? `#/tasks?${rawQuery}` : "#/tasks";
  }
  if (path === "home" && (query.has("s") || query.has("tour"))) {
    return rawQuery ? `#/report?${rawQuery}` : "#/report";
  }
  if (path === "loop" && query.get("tab") === "cost") {
    return "#/cost";
  }
  if (Object.prototype.hasOwnProperty.call(REDIRECT, path)) {
    const target = REDIRECT[path];
    const [targetPath, targetQuery = ""] = target.split("?");
    const merged = new URLSearchParams(targetQuery);
    for (const [k, v] of query.entries()) {
      merged.set(k, v);
    }
    const qs = merged.toString();
    return qs ? `#/${targetPath}?${qs}` : `#/${targetPath}`;
  }
  return null;
}

function matchRoute(path, query, fullHash) {
  const parts = path.split("/").filter(Boolean);
  const ctx = { path, query, fullHash, params: {}, onRetry: () => bootstrapData() };

  if (parts.length === 1) {
    switch (parts[0]) {
      case "tasks":
        return () => renderTasksPage(ctx);
      case "home":
        return () => renderHomePage(ctx);
      case "chat":
        return () => renderChatStudioPage(ctx);
      case "data":
        return () => renderDataCatalogPage(ctx);
      case "egoflow":
        return () => renderEgoflowPage(ctx);
      case "qa":
        return () => renderQaPage(ctx);
      case "jobs":
        return () => renderJobsPage(ctx);
      case "runs":
        return () => renderRunsPage(ctx);
      case "eval":
        return () => renderEvalPage(ctx);
      case "sim":
        return () => renderSimLibraryPage(ctx);
      case "base":
        return () => renderBasePage(ctx);
      case "diagnose":
        return () => renderDiagnosePage(ctx);
      case "loop":
        return () => renderLoopPage(ctx);
      case "follow":
        return () => renderFollowPage(ctx);
      case "design":
        return () => renderDesignPage(ctx);
      case "cost":
        return () => renderCostPage(ctx);
      case "report":
        return () => renderReportPage(ctx);
      default:
        return null;
    }
  }

  if (parts.length === 2 && parts[0] === "data") {
    ctx.params.id = decodeURIComponent(parts[1]);
    return () => renderDatasetDetailPage(ctx);
  }
  if (parts.length === 4 && parts[0] === "data" && parts[2] === "ep") {
    ctx.params.id = decodeURIComponent(parts[1]);
    ctx.params.n = decodeURIComponent(parts[3]);
    return () => renderEpisodeDetailPage(ctx);
  }
  if (parts.length === 2 && parts[0] === "sim") {
    ctx.params.i = decodeURIComponent(parts[1]);
    return () => renderSimDetailPage(ctx);
  }

  return null;
}

function isNavItemActive(itemKey, path, query) {
  if (path.startsWith("data/") || path === "data") {
    return itemKey === "data";
  }
  if (path.startsWith("sim/") || path === "sim") {
    return itemKey === "sim";
  }
  if (path === "jobs") {
    const panel = query.get("panel");
    const view = query.get("view");
    if (panel === "import") return itemKey === "import";
    if (panel === "export") return itemKey === "export";
    if (view === "pipeline") return itemKey === "pipeline";
    return itemKey === "jobs";
  }
  return itemKey === path;
}

function setMobileMenu(open) {
  mobileMenuOpen = Boolean(open);
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("menu-toggle");
  const backdrop = document.getElementById("drawer-backdrop");
  if (sidebar) sidebar.classList.toggle("is-open", mobileMenuOpen);
  if (toggleBtn) toggleBtn.setAttribute("aria-expanded", String(mobileMenuOpen));
  if (backdrop) backdrop.hidden = !mobileMenuOpen;
}

function renderSidebar(path, query) {
  const nav = document.getElementById("sidebar-nav");
  if (!nav) return;
  nav.setAttribute("aria-label", t("nav.ariaLabel"));
  nav.replaceChildren(
    ...NAV_GROUPS.flatMap((grp) => [
      el("div", { className: "group", text: t("nav.group." + grp.group) }),
      el(
        "ul",
        { className: "nav-list" },
        grp.items.map((item) => {
          const active = isNavItemActive(item.key, path, query);
          return el("li", {}, [
            el(
              "a",
              {
                href: item.hash,
                className: `nav${active ? " active" : ""}`,
                "aria-current": active ? "page" : null,
                onClick: () => setMobileMenu(false),
              },
              [
                el("span", { className: "icon", "aria-hidden": "true", text: item.icon }),
                el("span", { text: t("nav.item." + item.key) }),
              ]
            ),
          ]);
        })
      ),
    ])
  );

  const sideTitle = document.getElementById("side-bottom-title");
  const sideDesc = document.getElementById("side-bottom-desc");
  if (sideTitle) sideTitle.textContent = t("nav.sideTitle");
  if (sideDesc) sideDesc.textContent = t("nav.sideDesc");
}

function renderHeader() {
  const skipLink = document.getElementById("skip-link");
  if (skipLink) skipLink.textContent = t("app.skipToMain");

  const menuToggle = document.getElementById("menu-toggle");
  if (menuToggle) menuToggle.setAttribute("aria-label", t("header.menuToggle"));

  const brandTitle = document.getElementById("brand-title");
  const brandSub = document.getElementById("brand-sub");
  if (brandTitle) brandTitle.textContent = t("app.brand");
  if (brandSub) brandSub.textContent = t("app.subtitle");

  // Task selector
  const taskLabel = document.getElementById("task-select-label");
  const taskSelect = document.getElementById("task-select");
  if (taskLabel) taskLabel.textContent = t("header.taskLabel");
  if (taskSelect) {
    const tasks = getTasks();
    if (!state.tasksLoaded && state.tasksLoading) {
      taskSelect.disabled = true;
      taskSelect.replaceChildren(el("option", { value: "", text: t("header.taskLoading") }));
    } else if (tasks.length === 0) {
      taskSelect.disabled = true;
      taskSelect.replaceChildren(el("option", { value: "", text: t("header.noTasks") }));
    } else {
      taskSelect.disabled = false;
      taskSelect.replaceChildren(
        ...tasks.map((task) =>
          el("option", {
            value: task.id,
            selected: task.id === state.taskId,
            text: pickLang(task.name) || task.id,
          })
        )
      );
      if (state.taskId) taskSelect.value = state.taskId;
    }
  }

  // Round selector
  const roundLabel = document.getElementById("round-select-label");
  const roundSelect = document.getElementById("round-select");
  if (roundLabel) roundLabel.textContent = t("header.roundLabel");
  if (roundSelect) {
    const rounds = state.taskId ? getRoundsForTask(state.taskId) : [];
    if (rounds.length === 0) {
      roundSelect.disabled = true;
      roundSelect.replaceChildren(el("option", { value: "", text: t("header.noRounds") }));
    } else {
      roundSelect.disabled = false;
      roundSelect.replaceChildren(
        ...rounds.map((r) => {
          const rTitle = pickLang(r.title);
          return el("option", {
            value: r.id,
            selected: r.id === state.roundId,
            text: rTitle ? `${r.id} · ${rTitle}` : r.id,
          });
        })
      );
      if (state.roundId) roundSelect.value = state.roundId;
    }
  }

  // Lock badge from /api/status
  const lockBadge = document.getElementById("lock-badge");
  if (lockBadge) {
    lockBadge.hidden = false;
    lockBadge.className = "topbtn";
    if (state.statusError && !state.statusLoaded) {
      lockBadge.classList.add("is-error");
      lockBadge.textContent = `⚠ ${t("header.statusError")}`;
      lockBadge.title = state.statusError.serverMessage || "";
    } else if (!state.statusLoaded) {
      lockBadge.textContent = `◌ ${t("header.statusLoading")}`;
      lockBadge.title = "";
    } else if (state.locked) {
      lockBadge.classList.add("is-locked");
      lockBadge.textContent = `🔒 ${t("header.locked")}`;
      lockBadge.title = t("header.lockedHint");
    } else {
      lockBadge.textContent = `◉ ${t("header.unlocked")}`;
      lockBadge.title = t("header.unlockedHint");
    }
  }

  // Language switch
  const langGroup = document.getElementById("lang-group");
  const btnVi = document.getElementById("lang-vi");
  const btnEn = document.getElementById("lang-en");
  if (langGroup) langGroup.setAttribute("aria-label", t("header.langSwitch"));
  if (btnVi) btnVi.setAttribute("aria-pressed", String(state.lang === "vi"));
  if (btnEn) btnEn.setAttribute("aria-pressed", String(state.lang === "en"));

  // Theme switch
  const themeBtn = document.getElementById("theme-toggle");
  const themeLabel = document.getElementById("theme-label");
  if (themeBtn) {
    const nextHint = state.theme === "light" ? t("header.themeToDark") : t("header.themeToLight");
    themeBtn.setAttribute("aria-label", nextHint);
    themeBtn.title = nextHint;
  }
  if (themeLabel) {
    themeLabel.textContent =
      state.theme === "light" ? t("header.themeLightShort") : t("header.themeDarkShort");
  }
}

function renderNotFound(routeText) {
  return el("div", {}, [
    el("div", { className: "crumb" }, [
      `${t("app.crumbRoot")} / `,
      el("span", { text: t("route.notFoundTitle") }),
    ]),
    el("div", { className: "heading" }, [
      el("div", {}, [
        el("h1", { text: t("route.notFoundTitle") }),
        el("p", { text: t("route.notFoundBody", { route: routeText }) }),
      ]),
    ]),
    el("a", { className: "btn primary", href: "#/tasks" }, [t("common.backToTasks")]),
  ]);
}

let lastRenderedPath = null;

function renderRoute() {
  const redirected = resolveRedirectHash(window.location.hash);
  if (redirected && redirected !== window.location.hash) {
    window.history.replaceState(null, "", redirected);
  }

  const fullHash = window.location.hash || "#/tasks";
  const { path, query } = parseHash(fullHash);
  renderSidebar(path, query);

  const main = document.getElementById("main-content");
  if (!main) return;

  cleanupCurrentPage();
  const renderer = matchRoute(path, query, fullHash);
  const viewNode = renderer ? renderer() : renderNotFound(fullHash);
  main.replaceChildren(viewNode);
  if (path !== lastRenderedPath) {
    lastRenderedPath = path;
    main.scrollTop = 0;
    window.scrollTo(0, 0);
  }
  notifyChatRouteChanged();
}

async function loadStatus(emit = true) {
  try {
    const statusDoc = await getJSON("/api/status", {
      notify: true,
      onRetry: () => loadStatus(true),
    });
    state.statusDoc = statusDoc;
    state.locked = Boolean(statusDoc && statusDoc.locked);
    state.chatOn = Boolean(statusDoc && statusDoc.chat_on);
    state.statusLoaded = true;
    state.statusError = null;
    document.documentElement.classList.toggle("locked", state.locked);
    if (emit) notifyStateChange("lock");
  } catch (err) {
    state.statusError = err;
    if (emit) notifyStateChange("status-error");
  }
}

async function loadTasks(emit = true) {
  state.tasksLoading = true;
  state.tasksError = null;
  announce(t("state.loading"));

  try {
    const doc = await getJSON("data/tasks.json", {
      notify: true,
      onRetry: () => bootstrapData(),
    });
    state.tasksDoc = doc;
    state.tasksLoaded = true;
    state.tasksLoading = false;
    state.tasksError = null;

    const tasks = getTasks();
    if (tasks.length > 0 && !tasks.some((item) => item.id === state.taskId)) {
      state.taskId = tasks[0].id;
      const rounds = getRoundsForTask(state.taskId);
      state.roundId = rounds.length > 0 ? rounds[0].id : null;
    }
    hideErrorBanner();
    if (emit) notifyStateChange("tasks");
  } catch (err) {
    state.tasksLoading = false;
    state.tasksError = err;
    if (emit) notifyStateChange("tasks-error");
  } finally {
    announce("");
  }
}

async function bootstrapData() {
  await Promise.allSettled([loadStatus(false), loadTasks(false)]);
  notifyStateChange("bootstrap");
}

function bindHeaderEvents() {
  const menuToggle = document.getElementById("menu-toggle");
  const backdrop = document.getElementById("drawer-backdrop");
  if (menuToggle) {
    menuToggle.addEventListener("click", () => setMobileMenu(!mobileMenuOpen));
  }
  if (backdrop) {
    backdrop.addEventListener("click", () => setMobileMenu(false));
  }

  const taskSelect = document.getElementById("task-select");
  if (taskSelect) {
    taskSelect.addEventListener("change", (ev) => {
      selectTask(ev.target.value);
    });
  }

  const roundSelect = document.getElementById("round-select");
  if (roundSelect) {
    roundSelect.addEventListener("change", (ev) => {
      selectRound(ev.target.value);
    });
  }

  const lockBadge = document.getElementById("lock-badge");
  if (lockBadge) {
    lockBadge.addEventListener("click", () => {
      if (state.statusError) {
        loadStatus(true);
      }
    });
  }

  const btnVi = document.getElementById("lang-vi");
  const btnEn = document.getElementById("lang-en");
  if (btnVi) btnVi.addEventListener("click", () => setLang("vi"));
  if (btnEn) btnEn.addEventListener("click", () => setLang("en"));

  const themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      setTheme(state.theme === "light" ? "dark" : "light");
    });
  }

  const chatToggle = document.getElementById("chat-toggle");
  if (chatToggle) {
    chatToggle.addEventListener("click", () => {
      const { path } = parseHash(window.location.hash || "#/tasks");
      if (path === "chat") {
        window.location.hash = "#/home";
        return;
      }
      setChatOpen(!state.chatOpen, true);
    });
  }

  window.addEventListener("resize", () => {
    if (!state.chatExplicit) {
      const shouldOpen = window.innerWidth >= 1220;
      if (state.chatOpen !== shouldOpen) {
        setChatOpen(shouldOpen, false);
      }
    }
  });
}

function initApp() {
  document.documentElement.lang = state.lang;
  document.documentElement.setAttribute("data-theme", state.theme);

  bindErrorBannerControls();
  bindHeaderEvents();
  initChatShell();

  subscribe((reason) => {
    renderHeader();
    syncChatShell();
    if (ROUTE_REASONS.has(reason)) {
      renderRoute();
    }
  });

  window.addEventListener("hashchange", () => {
    renderRoute();
  });

  renderHeader();
  renderRoute();
  bootstrapData();
}

if (typeof document !== "undefined") {
  initApp();
}
