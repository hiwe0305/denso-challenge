import {
  canonicalDatasetTaxonomy,
  cls,
  compactPath,
  el,
  ensureCatalog,
  ensureSimRaw,
  ensureStoryRaw,
  failureLabel,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatStateLabel,
  friendlyBatchTitle,
  getCurrentTask,
  getJSON,
  hasI18nKey,
  hasIndexAccess,
  pickLang,
  renderChartBlock,
  renderCrumbHeading,
  renderErrorBlock,
  renderLoadingView,
  renderRoundEmpty,
  renderStatStrip,
  renderStateChip,
  scopeSimForTask,
  scopeStoryForTask,
  roundsWithIndex,
  safeThumbUrl,
  scrubPath,
  setChildren,
  setDataViewMode,
  setSelection,
  shortHashId,
  stageLabel,
  state,
  t,
  tryGetJSON,
  onRouteCleanup,
} from "./core.js";
import { icon } from "./icons.js";

const DS_TABS = ["overview", "content", "quality", "lineage", "jobs"];

// Step ids of the selected task in order (task.stages in tasks.json); sim episodes and jig
// rollouts store one boolean per step in this order.
function taskStageIds() {
  const task = getCurrentTask();
  return task && Array.isArray(task.stages) ? task.stages.map((st) => st && st.id).filter(Boolean) : [];
}

// One line "1 reach table A · 2 grasp tray · …" so the numbered step cells read without ids.
function renderStepLegend(stepIds) {
  if (!Array.isArray(stepIds) || stepIds.length === 0) return null;
  return el(
    "p",
    { className: cls("tiny", "step-legend") },
    stepIds.map((id, idx) =>
      el("span", { className: "step-legend-item", title: id }, [
        el("b", { className: "mono", text: String(idx + 1) }),
        ` ${stageLabel(id)}`,
      ])
    )
  );
}

const HAND_BONES = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
];

let egoViewerIndexPromise = null;
const egoEpisodeTrackCache = new Map();

async function ensureEgoViewerIndex() {
  if (!egoViewerIndexPromise) {
    egoViewerIndexPromise = tryGetJSON("/ego/data/index.json").then((res) => {
      const episodes = res.ok && res.data && Array.isArray(res.data.episodes) ? res.data.episodes : [];
      const map = new Map();
      for (const ep of episodes) {
        if (ep && ep.id) map.set(String(ep.id), ep);
      }
      return { episodes, map };
    });
  }
  return egoViewerIndexPromise;
}

async function fetchEgoEpisodeTrack(epId) {
  const key = String(epId);
  if (egoEpisodeTrackCache.has(key)) return egoEpisodeTrackCache.get(key);
  const p = fetch(`/ego/data/ep/${encodeURIComponent(key)}.js`, { cache: "no-cache" })
    .then(async (res) => {
      if (!res.ok) return null;
      const txt = (await res.text()).trim();
      const eq = txt.indexOf("= {");
      if (eq < 0) return null;
      const jsonPart = txt.slice(eq + 2).replace(/;\s*$/, "").trim();
      return JSON.parse(jsonPart);
    })
    .catch(() => null);
  egoEpisodeTrackCache.set(key, p);
  return p;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function resolveQaDatasetId(dsId, row) {
  if (row && row.view === "src") return dsId;
  if (dsId === "h1m-team") return "src_805804635f9af7f7";
  if (dsId === "h1m-egodex") return "src_158ec3c813ffe9a6";
  return dsId;
}

function isInspectableOnLaptop(row) {
  if (!row) return false;
  if (Array.isArray(row.thumbs) && row.thumbs.length > 0) return true;
  if (row.view === "ego" || row.view === "src" || row.view === "robot") return true;
  if (row.lerobot || row.ego_viewer) return true;
  return false;
}

function datasetSortRank(row) {
  const inspectable = isInspectableOnLaptop(row) ? 0 : 10;
  const st = String(row.status || "");
  const stRank =
    st === "current" ? 0 : st === "reference" ? 1 : st === "benchmark" ? 2 : st === "superseded" ? 4 : 6;
  return inspectable + stRank;
}

// Statuses left out of the default filter "Tập chính" (design audit P0-7).
const HIDDEN_BY_DEFAULT = new Set(["superseded", "duplicate", "archived"]);
const GALLERY_PAGE = 12;
const TABLE_PAGE = 20;
const COMPACT_PAGE = 10;

// Dataset id → a poster of sim.json for the sim cut or release part that dataset is: the cut
// whose sha256 starts with sim.sha8 (posters live under that folder) and each release part of
// the cut (first episode with a poster in its range).
function simPosterByDataset(rawSim) {
  const out = new Map();
  const sim = rawSim || {};
  const eps = Array.isArray(sim.episodes) ? sim.episodes : [];
  const firstPoster = (lo, hi) => {
    const hit = eps.find((e) => e && e.poster && e.i >= lo && e.i < hi);
    return hit ? `/simmedia/${hit.poster}` : null;
  };
  const sha8 = String(sim.sha8 || "");
  const cuts = sim.cuts && typeof sim.cuts === "object" ? sim.cuts : {};
  for (const [cutId, cut] of Object.entries(cuts)) {
    if (sha8 && cut && String(cut.sha256 || "").startsWith(sha8)) {
      const poster = firstPoster(0, Number.MAX_SAFE_INTEGER);
      if (poster) out.set(cutId, poster);
    }
  }
  for (const part of Array.isArray(sim.parts) ? sim.parts : []) {
    if (!part || !part.release) continue;
    const lo = Number(part.first) || 0;
    const poster = firstPoster(lo, lo + (Number(part.n) || 0));
    if (poster) out.set(String(part.release), poster);
  }
  return out;
}

function locationLabel(row, forceOnLaptop = false) {
  if (forceOnLaptop) return t("data.locLaptop");
  const locs = Array.isArray(row.locations) ? row.locations : [];
  if (locs.some((l) => l.where === "laptop" && l.exists)) return t("data.locLaptop");
  if (row.view === "remote" || (locs.length > 0 && locs.every((l) => l.where === "remote"))) {
    return t("data.locRemote");
  }
  const hosts = Array.from(new Set(locs.map((l) => l.where).filter((w) => w && w !== "?")));
  if (hosts.length > 0 && locs.every((l) => l.exists === false)) {
    return `${t("data.locMissing")} (${hosts.join(", ")})`;
  }
  if (locs.length > 0 && locs.every((l) => l.exists === false)) return t("data.locMissing");
  return t("data.locUnknown");
}

function renderQaMiniSummary(row) {
  const qc = row && row.qa_counts && typeof row.qa_counts === "object" ? row.qa_counts : null;
  const pass = qc ? Number(qc.pass || 0) : 0;
  const flag = qc ? Number(qc.flag || 0) : 0;
  const reject = qc ? Number(qc.reject || 0) : 0;
  const tot = pass + flag + reject;
  const rawQa = row && row.qa && row.qa !== "-" ? String(row.qa) : null;

  if (!tot && !rawQa) {
    return el("span", { className: "muted", text: t("state.na") });
  }

  return el("div", { className: "qa-bar-wrap" }, [
    tot > 0
      ? el("div", { className: "qa-bar" }, [
          pass > 0
            ? el("span", {
                className: "qa-seg-pass",
                style: `width:${((pass / tot) * 100).toFixed(1)}%`,
              })
            : null,
          flag > 0
            ? el("span", {
                className: "qa-seg-flag",
                style: `width:${((flag / tot) * 100).toFixed(1)}%`,
              })
            : null,
          reject > 0
            ? el("span", {
                className: "qa-seg-reject",
                style: `width:${((reject / tot) * 100).toFixed(1)}%`,
              })
            : null,
        ])
      : null,
    el("span", {
      className: cls("tiny", "mono"),
      text:
        tot > 0
          ? `${pass}P · ${flag}F · ${reject}R`
          : rawQa.length > 28
            ? `${rawQa.slice(0, 26)}…`
            : rawQa,
    }),
  ]);
}

function renderQuickFormatStrip() {
  const pill = (title, tags, links) =>
    el("div", { className: "quick-format-pill" }, [
      el("div", { className: "quick-format-head" }, [
        el("b", { text: title }),
        el(
          "div",
          { className: "actions" },
          links.map(([label, href]) =>
            el("a", { className: "link", style: "font-size:12px", href }, [label])
          )
        ),
      ]),
      el(
        "div",
        { className: "tag-row" },
        tags.map((tg) => el("span", { className: cls("mini-tag", "mono"), text: tg }))
      ),
    ]);

  return el("div", { className: "quick-format-strip" }, [
    pill(
      t("data.quickRobot"),
      ["parquet", "mp4 50fps", "action[36]", "state[45]", "tray_pose"],
      [
        ["S70 →", "#/data/S70"],
        ["Ep 0 →", "#/data/S70/ep/0"],
      ]
    ),
    pill(
      t("data.quickH1m"),
      ["deid mp4 30fps", "hands 21×2", "3D pose", "subtasks"],
      [
        ["h1m-team →", "#/data/h1m-team"],
        ["h1m-egodex →", "#/data/h1m-egodex"],
      ]
    ),
    pill(
      t("data.quickSrc"),
      [".deid.mp4", "pose.npz", "jitter °/s", "7 QA checks"],
      [["src_8058 →", "#/data/src_805804635f9af7f7"]]
    ),
  ]);
}

// ============================================================================
// Native 2D + 3D Hand Pose Player (replaces external /ego/ iframe & link)
// ============================================================================
function displayPoint3D(ep, arr, offset) {
  const x = arr[offset] / 1000;
  const y = arr[offset + 1] / 1000;
  const z = arr[offset + 2] / 1000;
  return ep.space === "world" ? [x, y, z] : [x, -y, -z];
}

function mount3DHandCanvas(box, ep) {
  const canvas = el("canvas", {});
  box.appendChild(canvas);
  box.appendChild(el("div", { className: "ego-3d-hint", text: t("ep.pose3dHint") }));
  const ctx2d = canvas.getContext("2d");

  const pts = [];
  for (const side of ["left", "right"]) {
    const sideArr = (ep.hands3d && ep.hands3d[side]) || [];
    for (const k of sideArr) {
      if (k) pts.push(displayPoint3D(ep, k, 0));
    }
  }
  if (ep.head && Array.isArray(ep.head.position)) {
    for (const p of ep.head.position) {
      if (p) pts.push(displayPoint3D(ep, p, 0));
    }
  }
  if (ep.space !== "world") pts.push([0, 0, 0]);
  if (pts.length === 0) pts.push([0, 0, 0]);

  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const p of pts) {
    for (let i = 0; i < 3; i++) {
      lo[i] = Math.min(lo[i], p[i]);
      hi[i] = Math.max(hi[i], p[i]);
    }
  }
  const center = [0, 1, 2].map((i) => (lo[i] + hi[i]) / 2);
  const span = Math.max(0.3, Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]));

  let yaw = 0.7;
  let pitch = 0.45;
  let dist = span * 1.65;
  let curFrame = 0;
  let drag = null;

  const fit = () => {
    const dpr = window.devicePixelRatio || 1;
    const w = box.clientWidth || 380;
    const h = box.clientHeight || 340;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
  };

  const project = (p) => {
    const x = p[0] - center[0];
    const y = p[1] - center[1];
    const z = p[2] - center[2];
    const cy = Math.cos(yaw);
    const sy = Math.sin(yaw);
    const cp = Math.cos(pitch);
    const sp = Math.sin(pitch);
    const x1 = cy * x + sy * z;
    const z1 = -sy * x + cy * z;
    const y2 = cp * y - sp * z1;
    const z2 = sp * y + cp * z1;
    const d = dist - z2;
    const f = Math.min(canvas.width, canvas.height) * 0.9;
    return d <= 0.01 ? null : [canvas.width / 2 + (f * x1) / d, canvas.height / 2 - (f * y2) / d];
  };

  const drawSeg = (a, b, color, width, alpha = 1) => {
    const pa = project(a);
    const pb = project(b);
    if (!pa || !pb) return;
    ctx2d.globalAlpha = alpha;
    ctx2d.strokeStyle = color;
    ctx2d.lineWidth = width;
    ctx2d.beginPath();
    ctx2d.moveTo(pa[0], pa[1]);
    ctx2d.lineTo(pb[0], pb[1]);
    ctx2d.stroke();
    ctx2d.globalAlpha = 1;
  };

  const draw = () => {
    if (!canvas.width) fit();
    const dpr = window.devicePixelRatio || 1;
    ctx2d.clearRect(0, 0, canvas.width, canvas.height);

    const gridColor = cssVar("--line");
    const leftColor = cssVar("--hand-left");
    const rightColor = cssVar("--hand-right");
    const headColor = cssVar("--hand-head");

    const g = Math.ceil(span * 5) / 5;
    const floor = lo[1] - 0.02;
    const step = g / 5;
    for (let i = -5; i <= 5; i++) {
      drawSeg(
        [center[0] + i * step, floor, center[2] - g],
        [center[0] + i * step, floor, center[2] + g],
        gridColor,
        dpr
      );
      drawSeg(
        [center[0] - g, floor, center[2] + i * step],
        [center[0] + g, floor, center[2] + i * step],
        gridColor,
        dpr
      );
    }

    for (const side of ["left", "right"]) {
      const col = side === "left" ? leftColor : rightColor;
      const tracks = (ep.hands3d && ep.hands3d[side]) || [];
      let prev = null;
      for (const k of tracks) {
        const p = k ? displayPoint3D(ep, k, 0) : null;
        if (p && prev) drawSeg(prev, p, col, 1.4 * dpr, 0.45);
        prev = p;
      }
      const kf = tracks[curFrame];
      if (kf) {
        for (const [b0, b1] of HAND_BONES) {
          drawSeg(
            displayPoint3D(ep, kf, 3 * b0),
            displayPoint3D(ep, kf, 3 * b1),
            col,
            2.5 * dpr,
            1
          );
        }
      }
    }

    if (ep.head && Array.isArray(ep.head.position) && ep.head.position[curFrame]) {
      let prev = null;
      for (const hp of ep.head.position) {
        const q = hp ? displayPoint3D(ep, hp, 0) : null;
        if (q && prev) drawSeg(prev, q, headColor, 1.4 * dpr, 0.65);
        prev = q;
      }
      const hNow = displayPoint3D(ep, ep.head.position[curFrame], 0);
      const fw = (ep.head.forward && ep.head.forward[curFrame]) || [0, 0, -1];
      drawSeg(
        hNow,
        [hNow[0] + 0.15 * fw[0], hNow[1] + 0.15 * fw[1], hNow[2] + 0.15 * fw[2]],
        headColor,
        2.8 * dpr
      );
    } else {
      drawSeg([0, 0, 0], [0, 0, -0.15], headColor, 2.8 * dpr);
    }
  };

  canvas.addEventListener("mousedown", (ev) => {
    drag = [ev.clientX, ev.clientY, yaw, pitch];
  });
  const onMove = (ev) => {
    if (!drag) return;
    yaw = drag[2] + (ev.clientX - drag[0]) * 0.01;
    pitch = Math.max(-1.5, Math.min(1.5, drag[3] + (ev.clientY - drag[1]) * 0.01));
    draw();
  };
  const onUp = () => {
    drag = null;
  };
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
  canvas.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      dist = Math.max(span * 0.3, dist * (ev.deltaY > 0 ? 1.1 : 0.9));
      draw();
    },
    { passive: false }
  );
  const detach = () => {
    window.removeEventListener("resize", onResize);
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  };
  const onResize = () => {
    if (!document.body.contains(box)) {
      detach();
      return;
    }
    fit();
    draw();
  };
  window.addEventListener("resize", onResize);
  // Leaving the page removes the window listeners even when no resize happens (server audit S-P2-7).
  onRouteCleanup(detach);
  requestAnimationFrame(() => {
    fit();
    draw();
  });

  return {
    update(f) {
      curFrame = f;
      draw();
    },
  };
}

function renderNativeEgoStudioPlayer(epTrack) {
  const fps = epTrack.fps || 30;
  const totalFrames = epTrack.frames || 1;
  const [vw, vh] = Array.isArray(epTrack.size) ? epTrack.size : [640, 480];
  const videoSrc = `/ego/${String(epTrack.video || "").replace(/^\/+/, "")}`;

  const video = el("video", {
    src: videoSrc,
    playsinline: true,
    muted: true,
    preload: "auto",
  });
  video.muted = true;

  const canvas2d = el("canvas", { width: String(vw), height: String(vh) });
  const ctx2d = canvas2d.getContext("2d");

  let showHands = true;
  const timeLabel = el("span", { className: cls("ego-time", "mono") });
  const playBtn = el("button", { type: "button", className: "topbtn", text: t("ep.play") });
  const toggleBtn = el("button", { type: "button", className: "topbtn", text: t("ep.handsHide") });
  const rateSelect = el(
    "select",
    {
      className: "topbtn",
      onChange: (ev) => {
        video.playbackRate = Number(ev.target.value) || 1;
      },
    },
    ["0.25", "0.5", "1"].map((r) =>
      el("option", { value: r, selected: r === "1", text: `${r}×` })
    )
  );

  // Seconds with two decimals in the reader's locale (vi: comma, A19).
  const secs = (v) => formatNumber(v, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const frameNow = () =>
    Math.max(0, Math.min(totalFrames - 1, Math.floor(video.currentTime * fps + 1e-3)));

  const timeline = el("div", { className: "ego-timeline" });
  const playhead = el("div", { className: "ego-playhead" });
  const subList = el("ul", { className: "ego-sub-list" });
  const segNodes = [];
  const liNodes = [];

  const box3d = el("div", { className: "ego-3d-box" });
  const view3d = mount3DHandCanvas(box3d, epTrack);

  const drawHands2D = (f) => {
    ctx2d.clearRect(0, 0, canvas2d.width, canvas2d.height);
    if (!showHands || !epTrack.hands2d) return;
    const lw = Math.max(2, canvas2d.width / 300);
    for (const side of ["left", "right"]) {
      const k = epTrack.hands2d[side] && epTrack.hands2d[side][f];
      if (!k) continue;
      const col = cssVar(side === "left" ? "--hand-left" : "--hand-right");
      ctx2d.strokeStyle = col;
      ctx2d.fillStyle = col;
      ctx2d.lineWidth = lw;
      const off = (j) => k[2 * j] <= -9999 || k[2 * j + 1] <= -9999;
      for (const [b0, b1] of HAND_BONES) {
        if (off(b0) || off(b1)) continue;
        ctx2d.beginPath();
        ctx2d.moveTo(k[2 * b0], k[2 * b0 + 1]);
        ctx2d.lineTo(k[2 * b1], k[2 * b1 + 1]);
        ctx2d.stroke();
      }
      for (let j = 0; j < 21; j++) {
        if (off(j)) continue;
        ctx2d.beginPath();
        ctx2d.arc(k[2 * j], k[2 * j + 1], lw * 1.35, 0, Math.PI * 2);
        ctx2d.fill();
      }
    }
  };

  let lastFrame = -1;
  const syncFrame = (force = false) => {
    const f = frameNow();
    if (f === lastFrame && !force) return;
    lastFrame = f;
    drawHands2D(f);
    playhead.style.left = `${((f + 0.5) / totalFrames) * 100}%`;
    timeLabel.textContent = `f ${f}/${totalFrames - 1} · ${secs(f / fps)} s`;
    (epTrack.subtasks || []).forEach((s, idx) => {
      const active = f >= s.start && f < s.end;
      if (segNodes[idx]) segNodes[idx].classList.toggle("is-active", active);
      if (liNodes[idx]) liNodes[idx].classList.toggle("is-active", active);
    });
    view3d.update(f);
  };

  const seekFrame = (f) => {
    const clamped = Math.max(0, Math.min(totalFrames - 1, f));
    video.currentTime = (clamped + 0.5) / fps;
    syncFrame(true);
  };

  playBtn.addEventListener("click", () => {
    if (video.paused) video.play();
    else video.pause();
  });
  video.addEventListener("play", () => {
    playBtn.textContent = t("ep.pause");
  });
  video.addEventListener("pause", () => {
    playBtn.textContent = t("ep.play");
  });
  toggleBtn.addEventListener("click", () => {
    showHands = !showHands;
    toggleBtn.textContent = showHands ? t("ep.handsHide") : t("ep.handsShow");
    syncFrame(true);
  });

  const stepBtn = (delta, label) =>
    el(
      "button",
      {
        type: "button",
        className: "topbtn",
        onClick: () => {
          video.pause();
          seekFrame(frameNow() + delta);
        },
      },
      [label]
    );

  (epTrack.subtasks || []).forEach((s) => {
    const pctW = Math.max(2, ((s.end - s.start) / totalFrames) * 100);
    const seg = el("div", {
      className: "ego-timeline-seg",
      style: `width:${pctW.toFixed(2)}%`,
      title: s.text,
      text: s.text,
      onClick: (ev) => {
        ev.stopPropagation();
        seekFrame(s.start);
      },
    });
    segNodes.push(seg);
    timeline.appendChild(seg);

    const li = el(
      "li",
      {
        onClick: () => {
          seekFrame(s.start);
          video.play();
        },
      },
      [
        el("span", {
          className: cls("ego-sub-when", "mono"),
          text: `${secs(s.start / fps)}–${secs(s.end / fps)} s`,
        }),
        el("span", { text: s.text }),
      ]
    );
    liNodes.push(li);
    subList.appendChild(li);
  });

  timeline.appendChild(playhead);
  timeline.addEventListener("click", (ev) => {
    const rect = timeline.getBoundingClientRect();
    seekFrame(Math.floor(((ev.clientX - rect.left) / rect.width) * totalFrames));
  });

  const loop = () => {
    if (!document.body.contains(video)) {
      video.pause();
      return;
    }
    syncFrame(false);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(() => {
    syncFrame(true);
    requestAnimationFrame(loop);
  });

  const m = epTrack.meta || {};
  const metaChips = [
    [t("ep.meta.video"), `${vw}×${vh} · ${fps} fps`],
    [t("ep.meta.frames"), `${formatNumber(totalFrames)} (${secs(totalFrames / fps)} s)`],
    [t("ep.meta.pose"), `${m.pose_source || "-"} (${epTrack.space || "camera"})`],
    [t("ep.meta.hands"), m.hands_visible != null ? formatPercent(m.hands_visible) : null],
    [
      t("ep.meta.handsLR"),
      m.left_visible != null
        ? `${formatPercent(m.left_visible)} / ${formatPercent(m.right_visible)}`
        : null,
    ],
    [
      t("ep.meta.accel"),
      m.left_accel_m_s2 != null
        ? `${formatNumber(m.left_accel_m_s2, { maximumFractionDigits: 1 })} / ${formatNumber(m.right_accel_m_s2, { maximumFractionDigits: 1 })}`
        : null,
    ],
    [
      t("ep.meta.intrinsics"),
      Array.isArray(m.intrinsic) ? m.intrinsic.map((v) => Math.round(v)).join(", ") : null,
    ],
    [t("ep.meta.scene"), m.scene || m.environment || null],
  ].filter(([, v]) => v != null && v !== "");

  return el("div", { className: "ego-studio-grid" }, [
    el("section", { className: "card" }, [
      el("div", { className: "ego-stage" }, [video, canvas2d]),
      el("div", { className: "ego-controls" }, [
        playBtn,
        stepBtn(-1, t("ep.stepPrev")),
        stepBtn(1, t("ep.stepNext")),
        rateSelect,
        toggleBtn,
        timeLabel,
      ]),
      el("div", { className: "tiny", style: "margin-top:10px", text: t("ep.subtasksTimeline") }),
      timeline,
      el("div", { className: "ego-legend" }, [
        el("span", {}, [
          el("i", { className: "ego-legend-dot", style: "background:var(--hand-left)" }),
          t("ep.leftHand"),
        ]),
        el("span", {}, [
          el("i", { className: "ego-legend-dot", style: "background:var(--hand-right)" }),
          t("ep.rightHand"),
        ]),
      ]),
      subList,
    ]),
    el("div", { className: "stack" }, [
      el("section", { className: "card" }, [
        el("h2", { style: "margin-bottom:8px", text: t("ep.pose3dTitle") }),
        box3d,
        el("div", { className: "ego-legend" }, [
          el("span", {}, [
            el("i", { className: "ego-legend-dot", style: "background:var(--hand-left)" }),
            t("ep.leftHand"),
          ]),
          el("span", {}, [
            el("i", { className: "ego-legend-dot", style: "background:var(--hand-right)" }),
            t("ep.rightHand"),
          ]),
          el("span", {}, [
            el("i", { className: "ego-legend-dot", style: "background:var(--hand-head)" }),
            t("ep.headPath"),
          ]),
        ]),
      ]),
      el("section", { className: "card" }, [
        el("h2", { style: "margin-bottom:8px", text: t("ep.metaCompactTitle") }),
        el(
          "div",
          { className: "meta-strip" },
          metaChips.map(([k, v]) =>
            el("div", { className: "meta-box" }, [
              el("span", { text: k }),
              el("b", { className: "mono", style: "font-size:12px", text: String(v) }),
            ])
          )
        ),
      ]),
    ]),
  ]);
}

function renderLineageSankeyCard(edges, rowMap, focusId = null) {
  const rawPairs = [];
  const seenEdge = new Set();
  for (const ed of edges || []) {
    const [p, c] = Array.isArray(ed) ? ed : [ed.from, ed.to];
    if (!p || !c || p === c) continue;
    const key = `${p}::${c}`;
    if (seenEdge.has(key)) continue;
    seenEdge.add(key);
    rawPairs.push([String(p), String(c)]);
  }
  if (rawPairs.length === 0) return null;

  // Cycle-safe DAG filter so ECharts Sankey never receives a cycle
  const adj = new Map();
  const canReach = (start, goal) => {
    const stack = [start];
    const vis = new Set();
    while (stack.length > 0) {
      const cur = stack.pop();
      if (cur === goal) return true;
      if (vis.has(cur)) continue;
      vis.add(cur);
      for (const nxt of adj.get(cur) || []) stack.push(nxt);
    }
    return false;
  };

  // Prioritize active/inspectable datasets on overview Sankey so labels stay airy & readable
  const prioritizedPairs =
    focusId !== null
      ? rawPairs
      : [
          ...rawPairs.filter(([a, b]) => {
            const ra = rowMap.get(a);
            const rb = rowMap.get(b);
            const okA = ra && (ra.status === "current" || ra.status === "reference");
            const okB = rb && (rb.status === "current" || rb.status === "reference");
            return okA || okB;
          }),
          ...rawPairs,
        ];

  const dagLinks = [];
  const nodeIds = new Set();
  const usedKeys = new Set();
  for (const [src, dst] of prioritizedPairs) {
    if (dagLinks.length >= (focusId ? 30 : 22)) break;
    const ek = `${src}::${dst}`;
    if (usedKeys.has(ek)) continue;
    if (canReach(dst, src)) continue;
    usedKeys.add(ek);
    if (!adj.has(src)) adj.set(src, []);
    adj.get(src).push(dst);
    const dstRow = rowMap.get(dst);
    const srcRow = rowMap.get(src);
    const weight = Math.max(
      1,
      Number((dstRow && dstRow.episodes) || (srcRow && srcRow.episodes) || 10)
    );
    dagLinks.push({ source: src, target: dst, value: Math.min(500, Math.round(Math.sqrt(weight) * 10)) });
    nodeIds.add(src);
    nodeIds.add(dst);
  }
  if (dagLinks.length === 0) return null;

  const nodeLabel = (id) => {
    const r = rowMap.get(id);
    if (!r) return shortHashId(id);
    const tax = canonicalDatasetTaxonomy(r);
    const base = tax.cleanTitle.length > 18 ? `${tax.cleanTitle.slice(0, 17)}…` : tax.cleanTitle;
    return `${base} (${tax.shortId})`;
  };

  // One edge: a Sankey draws one block over the whole card and cuts the right label, so
  // draw two boxes and an arrow instead (design audit P1-15).
  if (dagLinks.length === 1) {
    const { source, target } = dagLinks[0];
    const box = (id) => {
      const r = rowMap.get(id);
      const tax = r ? canonicalDatasetTaxonomy(r) : null;
      const body = [
        el("b", { className: "lineage-box-title", text: tax ? tax.cleanTitle : shortHashId(id) }),
        el("span", { className: cls("tiny", "mono"), title: id, text: tax ? tax.shortId : id }),
        r && r.episodes != null
          ? el("span", { className: "tiny", text: t("tasks.unitEpisodes", { val: formatNumber(r.episodes) }) })
          : null,
      ];
      const boxCls = cls("lineage-box", id === focusId && "is-focus");
      return r && id !== focusId
        ? el("a", { className: boxCls, href: `#/data/${encodeURIComponent(id)}` }, body)
        : el("div", { className: boxCls }, body);
    };
    return el("section", { className: "card" }, [
      el("h2", { text: t("data.sankeyTitle") }),
      el("div", { className: "lineage-pair" }, [
        box(source),
        el("span", { className: "lineage-arrow", "aria-hidden": "true", text: "→" }),
        box(target),
      ]),
    ]);
  }

  const chartHeight = Math.max(280, Math.min(520, nodeIds.size * 26));

  return renderChartBlock({
    title: t("data.sankeyTitle"),
    subtitle: t("data.sankeyHint"),
    height: chartHeight,
    onChartClick: (params) => {
      if (params && params.dataType === "node" && params.data && params.data.name) {
        const nid = params.data.name;
        if (rowMap.has(nid)) {
          window.location.hash = `#/data/${encodeURIComponent(nid)}`;
        }
      }
    },
    buildOption: ({ ink, soft, colors }) => ({
      tooltip: {
        trigger: "item",
        formatter: (p) => {
          if (p.dataType === "edge") {
            return `${p.data.source} → ${p.data.target}`;
          }
          const r = rowMap.get(p.name);
          if (!r) return p.name;
          return `${r.title || r.id}<br/>${r.id} · ${formatNumber(r.episodes || 0)} ep`;
        },
      },
      series: [
        {
          type: "sankey",
          emphasis: { focus: "adjacency" },
          nodeAlign: "left",
          nodeWidth: 14,
          nodeGap: 10,
          left: 14,
          right: 230,
          top: 12,
          bottom: 12,
          data: Array.from(nodeIds).map((id, idx) => ({
            name: id,
            itemStyle: {
              color: id === focusId ? colors[0] : colors[idx % colors.length],
              borderWidth: id === focusId ? 2 : 0,
            },
          })),
          links: dagLinks,
          lineStyle: { color: "source", curveness: 0.45, opacity: 0.34 },
          label: {
            color: ink || soft,
            fontSize: 12,
            formatter: (p) => nodeLabel(p.name),
          },
          labelLayout: { hideOverlap: true },
        },
      ],
    }),
    tableNode: el("table", { className: "table" }, [
      el(
        "tbody",
        {},
        dagLinks.map((lk) =>
          el("tr", {}, [
            el("td", { className: "mono", text: lk.source }),
            el("td", { className: "mono", text: `→ ${lk.target}` }),
          ])
        )
      ),
    ]),
  });
}

// ============================================================================
// #/data — Data Library (concise & visual)
// ============================================================================
export function renderDataCatalogPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("data.title")));

  let searchQuery = "";
  let groupFilter = "all";
  let availFilter = "curated";
  let scopeOnlyTask = false;

  const load = async () => {
    try {
      const [cat, rawSim] = await Promise.all([
        ensureCatalog(),
        ensureSimRaw().catch(() => null),
      ]);
      const rawRows = Array.isArray(cat.rows) ? cat.rows : [];
      const rows = [...rawRows].sort((a, b) => {
        const diff = datasetSortRank(a) - datasetSortRank(b);
        if (diff !== 0) return diff;
        return (Number(b.episodes) || 0) - (Number(a.episodes) || 0);
      });
      const edges = Array.isArray(cat.edges) ? cat.edges : [];
      const rowMap = new Map(rows.map((r) => [r.id, r]));
      const listHolder = el("div", {});

      const isCuratedRow = (r) =>
        !HIDDEN_BY_DEFAULT.has(String(r.status || "")) &&
        (isInspectableOnLaptop(r) || r.status === "current" || r.status === "reference");

      // Picture of a dataset: its own poster, else a poster of the sim cut it holds.
      const borrowed = simPosterByDataset(rawSim);
      const rowImage = (r) =>
        (Array.isArray(r.thumbs) ? safeThumbUrl(r.thumbs[0]) : null) || borrowed.get(String(r.id)) || null;

      const groups = Array.from(new Set(rows.map((r) => r.group).filter(Boolean))).sort();
      const curatedCount = rows.filter(isCuratedRow).length;
      const inspectableCount = rows.filter((r) => isInspectableOnLaptop(r)).length;
      const activeCount = rows.filter(
        (r) => r.status === "current" || r.status === "reference"
      ).length;

      // How many rows each block shows before "show more" (mobile page height, P1-13).
      let galleryLimit = GALLERY_PAGE;
      let tableLimit = TABLE_PAGE;
      let compactLimit = COMPACT_PAGE;

      const renderMoreButton = (hidden, onMore) =>
        hidden > 0
          ? el("div", { className: "data-more" }, [
              el(
                "button",
                { type: "button", className: "btn", onClick: onMore },
                [t("data.showMore", { count: formatNumber(hidden) })]
              ),
            ])
          : null;

      const renderGalleryCard = (r) => {
        const img = rowImage(r);
        const tax = canonicalDatasetTaxonomy(r);
        return el(
          "a",
          {
            className: "ep-visual-card",
            href: `#/data/${encodeURIComponent(r.id)}`,
          },
          [
            el("img", { src: img, alt: tax.cleanTitle, loading: "lazy" }),
            el("div", { className: "ep-visual-body" }, [
              el("div", { className: "tag-row" }, [
                el("span", { className: "tax-badge", text: tax.code }),
                el("span", { className: cls("short-hash", "mono"), title: r.id, text: tax.shortId }),
              ]),
              el("div", { className: "ep-visual-title", title: tax.cleanTitle, text: tax.cleanTitle }),
              el("div", { className: "tag-row" }, [
                el("span", {
                  className: cls("mini-tag", "mono"),
                  text:
                    r.episodes != null
                      ? t("tasks.unitEpisodes", { val: formatNumber(r.episodes) })
                      : t("state.na"),
                }),
                r.fps
                  ? el("span", { className: cls("mini-tag", "mono"), text: `${r.fps} fps` })
                  : null,
                renderStateChip(r.status),
              ]),
            ]),
          ]
        );
      };

      // Full table (list view) or compact table (rows without a picture under the gallery).
      const renderRowsTable = (list, compact) =>
        el("div", { className: cls("card", "table-wrap", compact && "data-compact") }, [
          el("table", { className: "table" }, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", { text: t("data.colDataset") }),
                compact ? null : el("th", { text: t("data.colFormatSchema") }),
                el("th", { className: "num", text: t("data.colVolume") }),
                compact ? null : el("th", { text: t("data.colQaSummary") }),
                el("th", { text: t("common.status") }),
              ]),
            ]),
            el(
              "tbody",
              {},
              list.map((r) => {
                const img = rowImage(r);
                const canInspect = isInspectableOnLaptop(r);
                const tax = canonicalDatasetTaxonomy(r);
                return el("tr", {}, [
                  el("td", {}, [
                    el("div", { className: "ds" }, [
                      compact
                        ? null
                        : img
                          ? el("img", {
                              className: "ds-thumb-mini",
                              src: img,
                              alt: "",
                              loading: "lazy",
                            })
                          : el("div", { className: "tile", "aria-hidden": "true" }, [icon("data")]),
                      el("div", { className: "row-body" }, [
                        el(
                          "a",
                          {
                            className: "link",
                            href: `#/data/${encodeURIComponent(r.id)}`,
                          },
                          [tax.cleanTitle]
                        ),
                        el("div", { className: "tag-row", style: "margin-top:3px" }, [
                          el("span", { className: "tax-badge", text: tax.code }),
                          el("span", {
                            className: cls("short-hash", "mono"),
                            title: r.id,
                            text: tax.shortId,
                          }),
                        ]),
                      ]),
                    ]),
                  ]),
                  compact
                    ? null
                    : el("td", {}, [
                        el("div", {
                          className: cls("mono", "data-format"),
                          text: r.format || r.data_type || t("state.na"),
                        }),
                        r.fps
                          ? el("span", { className: cls("tiny", "mono"), text: `${r.fps} fps` })
                          : null,
                      ]),
                  el("td", { className: "num", style: "white-space:nowrap" }, [
                    el("b", {
                      className: "mono",
                      text:
                        r.episodes != null
                          ? t("tasks.unitEpisodes", { val: formatNumber(r.episodes) })
                          : t("state.na"),
                    }),
                    r.hours != null
                      ? el("div", {
                          className: cls("tiny", "mono"),
                          text: t("tasks.unitHours", {
                            val: formatNumber(r.hours, { maximumFractionDigits: 2 }),
                          }),
                        })
                      : null,
                  ]),
                  compact ? null : el("td", {}, [renderQaMiniSummary(r)]),
                  el("td", { style: "white-space:nowrap" }, [
                    renderStateChip(r.status),
                    el("div", {
                      className: "tiny",
                      style: "margin-top:3px",
                      text: locationLabel(r, canInspect && Boolean(r.lerobot)),
                    }),
                  ]),
                ]);
              })
            ),
          ]),
        ]);

      const redrawRows = (resetLimits = false) => {
        if (resetLimits) {
          galleryLimit = GALLERY_PAGE;
          tableLimit = TABLE_PAGE;
          compactLimit = COMPACT_PAGE;
        }
        const curTask = getCurrentTask();
        const catTaskKey = curTask ? curTask.catalog_task || curTask.id : null;
        const q = searchQuery.trim().toLowerCase();

        const filtered = rows.filter((r) => {
          if (scopeOnlyTask && catTaskKey && r.task !== catTaskKey) return false;
          if (groupFilter !== "all" && r.group !== groupFilter) return false;
          if (availFilter === "curated" && !isCuratedRow(r)) return false;
          if (availFilter === "inspectable" && !isInspectableOnLaptop(r)) return false;
          if (availFilter === "active" && r.status !== "current" && r.status !== "reference") {
            return false;
          }
          if (q) {
            const hay = `${r.id || ""} ${r.title || ""} ${r.name || ""} ${r.kind || ""} ${r.format || ""}`.toLowerCase();
            if (!hay.includes(q)) return false;
          }
          return true;
        });

        if (filtered.length === 0) {
          setChildren(listHolder, el("div", { className: "empty", text: t("state.empty") }));
          return;
        }

        if (state.dataViewMode === "gallery") {
          // Gallery only for sets with a picture; the rest go to a compact table (P0-7).
          const withImg = filtered.filter((r) => rowImage(r));
          const noImg = filtered.filter((r) => !rowImage(r));
          setChildren(
            listHolder,
            withImg.length > 0
              ? el("div", { className: "ep-card-grid" }, withImg.slice(0, galleryLimit).map(renderGalleryCard))
              : null,
            renderMoreButton(withImg.length - galleryLimit, () => {
              galleryLimit += GALLERY_PAGE;
              redrawRows();
            }),
            noImg.length > 0
              ? el("div", { className: cls("sect", "data-noimg-head") }, [
                  el("h2", { text: t("data.noImageTitle", { count: formatNumber(noImg.length) }) }),
                ])
              : null,
            noImg.length > 0 ? renderRowsTable(noImg.slice(0, compactLimit), true) : null,
            renderMoreButton(noImg.length - compactLimit, () => {
              compactLimit += COMPACT_PAGE;
              redrawRows();
            })
          );
          return;
        }

        setChildren(
          listHolder,
          renderRowsTable(filtered.slice(0, tableLimit), false),
          renderMoreButton(filtered.length - tableLimit, () => {
            tableLimit += TABLE_PAGE;
            redrawRows();
          })
        );
      };

      const curTask = getCurrentTask();
      const taskAll = (curTask && curTask.catalog_totals && curTask.catalog_totals.all) || {};
      const catAll = (cat.totals && cat.totals.all) || {};

      const headerActions = state.locked
        ? [el("a", { className: "btn", href: "#/jobs?panel=export" }, [t("jobs.tab.export")])]
        : [
            el("a", { className: cls("btn", "primary"), href: "#/jobs?panel=import" }, [
              t("nav.item.import"),
            ]),
            el("a", { className: "btn", href: "#/jobs?view=pipeline" }, [t("nav.item.pipeline")]),
            el("a", { className: "btn", href: "#/jobs?panel=export" }, [t("nav.item.export")]),
          ];

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("data.title") }],
          title: t("data.title"),
          actions: headerActions,
        }),

        el("div", { className: "toolbar" }, [
          el("input", {
            type: "search",
            className: cls("field", "search"),
            "aria-label": t("data.filterSearchLabel"),
            placeholder: t("data.searchPlaceholder"),
            onInput: (ev) => {
              searchQuery = ev.target.value;
              redrawRows(true);
            },
          }),
          el(
            "select",
            {
              className: "field",
              "aria-label": t("data.filterStatusLabel"),
              title: t("data.filterStatusLabel"),
              onChange: (ev) => {
                availFilter = ev.target.value;
                redrawRows(true);
              },
            },
            [
              el("option", {
                value: "curated",
                text: t("data.filterCurated", { count: formatNumber(curatedCount) }),
              }),
              el("option", {
                value: "inspectable",
                text: t("data.filterAvailInspectable", {
                  count: formatNumber(inspectableCount),
                }),
              }),
              el("option", {
                value: "active",
                text: t("data.filterAvailActive", { count: formatNumber(activeCount) }),
              }),
              el("option", {
                value: "all",
                text: t("data.filterAvailAll", { count: formatNumber(rows.length) }),
              }),
            ]
          ),
          el(
            "select",
            {
              className: "field",
              "aria-label": t("data.filterGroupLabel"),
              title: t("data.filterGroupLabel"),
              onChange: (ev) => {
                groupFilter = ev.target.value;
                redrawRows(true);
              },
            },
            [
              el("option", { value: "all", text: t("common.all") }),
              ...groups.map((g) =>
                el("option", {
                  value: g,
                  text: hasI18nKey("cat.group." + g) ? t("cat.group." + g) : g,
                })
              ),
            ]
          ),
          el(
            "select",
            {
              className: "field",
              "aria-label": t("data.filterScopeLabel"),
              title: t("data.filterScopeLabel"),
              onChange: (ev) => {
                scopeOnlyTask = ev.target.value === "task";
                redrawRows(true);
              },
            },
            [
              el("option", { value: "all", text: t("data.scopeAllCatalog") }),
              el("option", { value: "task", text: t("data.scopeCurrentTask") }),
            ]
          ),
          el(
            "button",
            {
              type: "button",
              className: cls("btn", "btn-icon-text"),
              onClick: () =>
                setDataViewMode(state.dataViewMode === "list" ? "gallery" : "list"),
            },
            state.dataViewMode === "list"
              ? [icon("tasks"), t("data.viewGallery")]
              : [icon("menu"), t("data.viewList")]
          ),
        ]),

        listHolder,

        el("details", { className: "studio-details" }, [
          el("summary", { text: t("data.scopeCatalogStat") }),
          renderStatStrip([
            {
              label: t("data.scopeTaskStat", {
                task: curTask ? pickLang(curTask.name) || curTask.id : "-",
              }),
              value:
                taskAll.episodes != null
                  ? t("tasks.unitEpisodes", { val: formatNumber(taskAll.episodes) })
                  : t("state.na"),
              sub: t("data.setsHoursSub", {
                sets: formatNumber(taskAll.sets),
                hours:
                  taskAll.hours != null
                    ? t("tasks.unitHours", {
                        val: formatNumber(taskAll.hours, { maximumFractionDigits: 2 }),
                      })
                    : t("state.na"),
              }),
            },
            {
              label: t("data.scopeCatalogStat"),
              value:
                catAll.episodes != null
                  ? t("tasks.unitEpisodes", { val: formatNumber(catAll.episodes) })
                  : t("state.na"),
              sub: t("data.generatedSub", { date: cat.generated || t("state.na") }),
            },
            {
              label: t("data.colDataset"),
              value: formatNumber(curatedCount),
              sub: t("data.filterAvailAll", { count: formatNumber(rows.length) }),
            },
          ]),

          renderQuickFormatStrip(),

        ]),
        edges.length ? el("details", { className: "studio-details", onToggle: (event) => {
          const drawer = event.currentTarget;
          if (drawer.open && drawer.childElementCount === 1) {
            drawer.appendChild(renderLineageSankeyCard(edges, rowMap) || el("p", { text: t("state.empty") }));
          }
        } }, [el("summary", { text: t("ds.tab.lineage") })]) : null
      );

      redrawRows();
    } catch (err) {
      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("data.title") }],
          title: t("data.title"),
        }),
        renderErrorBlock(err, load)
      );
    }
  };

  load();
  return wrap;
}

// Compact 3-column visual schema rows (Field | Shape/Type | Chips/Sample) — zero prose bloat!
function buildCompactSchemaRows({ row, sampleEp, egoItem, robotTs, qaChecksSample }) {
  const out = [];

  if (robotTs && robotTs.action) {
    const tArr = Array.isArray(robotTs.t) ? robotTs.t : [];
    out.push({
      name: "timestamp",
      shape: `float32[${robotTs.n || tArr.length}] · ${robotTs.fps || 50} Hz`,
      chips: [`0.0 → ${tArr.length ? formatNumber(tArr[tArr.length - 1], { maximumFractionDigits: 1 }) : "-"} s`],
    });
    for (const [grp, gData] of Object.entries(robotTs.action)) {
      const names = Array.isArray(gData.names) ? gData.names : [];
      const flat = (gData.v || []).flat().filter((x) => typeof x === "number");
      const rangeTxt = flat.length
        ? `[${formatNumber(Math.min(...flat), { maximumFractionDigits: 2 })} .. ${formatNumber(Math.max(...flat), { maximumFractionDigits: 2 })}]`
        : "-";
      const shortNames = names.slice(0, 3).map((n) => n.replace(/_joint$/, ""));
      if (names.length > 3) shortNames.push(`+${names.length - 3}`);
      out.push({
        name: `action.${grp}`,
        shape: `float32[T, ${names.length}]`,
        chips: [rangeTxt, ...shortNames],
        tooltip: names.join(", "),
      });
    }
    for (const [grp, gData] of Object.entries(robotTs.state || {})) {
      const names = Array.isArray(gData.names) ? gData.names : [];
      const flat = (gData.v || []).flat().filter((x) => typeof x === "number");
      const rangeTxt = flat.length
        ? `[${formatNumber(Math.min(...flat), { maximumFractionDigits: 2 })} .. ${formatNumber(Math.max(...flat), { maximumFractionDigits: 2 })}]`
        : "-";
      out.push({
        name: `state.${grp}`,
        shape: `float32[T, ${names.length}]`,
        chips: [rangeTxt, `${names[0] || ""}..${names[names.length - 1] || ""}`],
      });
    }
    out.push({
      name: "video.egocentric",
      shape: `H.264 MP4 · ${row.fps || 50} fps`,
      chips: ["episode_000000.mp4"],
    });
    return out;
  }

  if (sampleEp && !Object.prototype.hasOwnProperty.call(sampleEp, "i")) {
    out.push({
      name: "id / title",
      shape: "string",
      chips: [sampleEp.id, (egoItem && egoItem.title) || sampleEp.title].filter(Boolean),
    });
    if (egoItem && egoItem.task) {
      out.push({
        name: "task",
        shape: "prompt",
        chips: [egoItem.task.length > 78 ? `${egoItem.task.slice(0, 76)}…` : egoItem.task],
      });
    }
    if (egoItem && Array.isArray(egoItem.subtasks) && egoItem.subtasks.length > 0) {
      out.push({
        name: "subtasks[]",
        shape: `timed[${egoItem.subtasks.length}]`,
        chips: egoItem.subtasks.slice(0, 2).map((s, idx) => `${idx + 1}) ${s.length > 44 ? `${s.slice(0, 42)}…` : s}`),
      });
    }
    if (egoItem) {
      out.push({
        name: "hands2d / hands3d",
        shape: "float[T, 21, 2..3] × 2",
        chips: ["left (21 joints)", "right (21 joints)", sampleEp.pose || egoItem.pose || "E-A"],
      });
    }
    out.push({
      name: "frames / duration",
      shape: `${row.fps || 30} fps`,
      chips: [
        sampleEp.n != null ? `${formatNumber(sampleEp.n)} fr` : null,
        sampleEp.s != null ? `${formatNumber(sampleEp.s, { maximumFractionDigits: 2 })} s` : null,
        sampleEp.hands != null ? `hands ${formatPercent(sampleEp.hands)}` : null,
      ].filter(Boolean),
    });
    if (sampleEp.out != null || sampleEp.jit != null) {
      out.push({
        name: "qa.metrics",
        shape: "float",
        chips: [
          sampleEp.out != null ? `out ${formatNumber(sampleEp.out, { maximumFractionDigits: 3 })}` : null,
          sampleEp.jit != null ? `jitter ${formatNumber(sampleEp.jit, { maximumFractionDigits: 1 })} °/s` : null,
          sampleEp.lowc != null ? `lowc ${formatNumber(sampleEp.lowc, { maximumFractionDigits: 3 })}` : null,
        ].filter(Boolean),
      });
    }
    if (Array.isArray(qaChecksSample) && qaChecksSample.length > 0) {
      out.push({
        name: `qa.checks[${qaChecksSample.length}]`,
        shape: "(value, thr, pass)",
        chips: qaChecksSample.slice(0, 4).map(([nm, val, , ok]) => `${nm}: ${formatNumber(val, { maximumFractionDigits: 2 })} ${ok ? "✓" : "✕"}`),
      });
    }
    return out;
  }

  out.push(
    {
      name: "format",
      shape: row.fps ? `${row.fps} fps` : "container",
      chips: [row.format || row.data_type || t("state.na")],
    },
    {
      name: "volume",
      shape: "counts",
      chips: [
        row.episodes != null ? `${formatNumber(row.episodes)} ep` : null,
        row.frames != null ? `${formatNumber(row.frames)} fr` : null,
        row.hours != null ? `${formatNumber(row.hours, { maximumFractionDigits: 2 })} h` : null,
      ].filter(Boolean),
    },
    {
      name: "qa",
      shape: "summary",
      chips: [row.qa || t("state.na")],
    }
  );
  return out;
}

function renderJumpToEpisodeBar(dsId, maxEpisodes, includeEpZeroCta = true) {
  let targetEp = "0";
  const maxIdx = maxEpisodes && maxEpisodes > 0 ? maxEpisodes - 1 : 0;
  const go = () => {
    const n = Math.max(0, Math.min(maxIdx, parseInt(targetEp, 10) || 0));
    window.location.hash = `#/data/${encodeURIComponent(dsId)}/ep/${n}`;
  };
  return el("div", { className: "toolbar" }, [
    includeEpZeroCta
      ? el(
          "a",
          { className: cls("btn", "primary"), href: `#/data/${encodeURIComponent(dsId)}/ep/0` },
          [t("ds.openEpZero")]
        )
      : null,
    el("span", { className: "tiny", text: `${t("ds.jumpEpLabel")} (0..${maxIdx})` }),
    el("input", {
      type: "number",
      className: "field",
      style: "width:96px",
      min: "0",
      max: String(maxIdx),
      value: "0",
      onInput: (ev) => {
        targetEp = ev.target.value;
      },
      onKeydown: (ev) => {
        if (ev.key === "Enter") go();
      },
    }),
    el("button", { type: "button", className: "btn", onClick: go }, [t("ds.jumpEpGo")]),
  ]);
}

function renderMethodStructuredCard(methodData, titleText) {
  if (!methodData || typeof methodData !== "object") return null;
  const info = methodData.info || {};
  const files = Array.isArray(methodData.files) ? methodData.files : [];
  const reportFiles = Array.isArray(methodData.report_files) ? methodData.report_files : [];
  const summaryAll = methodData.summary && methodData.summary.all ? methodData.summary.all : null;

  const kvPairs = [
    ["root", methodData.root],
    ["version", info.codebase_version || methodData.config_version || (methodData.summary && methodData.summary.config)],
    ["fps", info.fps || (summaryAll && summaryAll.fps && summaryAll.fps.join(", "))],
    [
      "resolution",
      summaryAll && Array.isArray(summaryAll.resolutions)
        ? summaryAll.resolutions.join(", ")
        : null,
    ],
  ].filter(([, v]) => v != null && v !== "");

  return el("section", { className: "card" }, [
    el("h2", { text: titleText }),
    kvPairs.length > 0
      ? el(
          "div",
          { className: "meta-strip", style: "margin-top:10px" },
          kvPairs.map(([k, v]) =>
            el("div", { className: "meta-box" }, [
              el("span", { className: "mono", text: k }),
              el("b", { className: "mono", style: "font-size:12px;overflow-wrap:anywhere", text: scrubPath(String(v)) }),
            ])
          )
        )
      : null,
    files.length > 0 || reportFiles.length > 0
      ? el(
          "div",
          { className: "step-tags", style: "margin-top:10px" },
          [...files, ...reportFiles.map((f) => `report/${f}`)].map((f) =>
            el("span", { className: cls("step-tag", "mono"), text: f })
          )
        )
      : null,
    el("details", { style: "margin-top:10px" }, [
      el("summary", { className: "link", style: "cursor:pointer;font-size:12px", text: t("ds.rawJsonToggle") }),
      el("pre", {
        className: cls("log-box", "mono"),
        style: "margin-top:8px",
        text: scrubPath(JSON.stringify(methodData, null, 2)),
      }),
    ]),
  ]);
}

// ============================================================================
// #/data/:id — Dataset Workspace (visual & uncluttered)
// ============================================================================
export function renderDatasetDetailPage(ctx) {
  const dsId = ctx.params.id;
  const activeTab = DS_TABS.includes(ctx.query.get("tab")) ? ctx.query.get("tab") : "overview";
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(dsId));
  setSelection({ dataset_id: dsId }, true);

  const load = async () => {
    try {
      const cat = await ensureCatalog();
      const rows = Array.isArray(cat.rows) ? cat.rows : [];
      const row = rows.find((r) => String(r.id) === String(dsId));

      if (!row) {
        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [
              { label: t("app.crumbRoot"), href: "#/tasks" },
              { label: t("data.title"), href: "#/data" },
              { label: dsId },
            ],
            title: dsId,
          }),
          el("div", { className: "empty" }, [
            el("p", { text: t("ds.notFound", { id: dsId }) }),
            el("a", { className: cls("btn", "primary"), href: "#/data" }, [t("ds.backCatalog")]),
          ])
        );
        return;
      }

      const tabsBar = el(
        "nav",
        { className: "tabs" },
        DS_TABS.map((tb) =>
          el(
            "a",
            {
              href: `#/data/${encodeURIComponent(dsId)}?tab=${tb}`,
              className: cls("tab", activeTab === tb && "active"),
            },
            [t("ds.tab." + tb)]
          )
        )
      );

      const isRobotDs = Boolean(row.lerobot) || row.view === "robot" || row.view === "lerobot";
      let hasLiveOnDisk = isInspectableOnLaptop(row);
      let tabBody = null;

      if (activeTab === "overview") {
        const qaDsId = resolveQaDatasetId(dsId, row);
        const [epRes, methodRes, qaRes, egoIdx, robotEp0Res] = await Promise.all([
          tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/episodes.json`),
          tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/method.json`),
          tryGetJSON(`data/ds/${encodeURIComponent(qaDsId)}/qa.json`),
          row.ego_viewer ? ensureEgoViewerIndex() : Promise.resolve({ map: new Map() }),
          isRobotDs
            ? tryGetJSON(`/api/episode?ds=${encodeURIComponent(dsId)}&ep=0`)
            : Promise.resolve({ ok: false }),
        ]);

        const episodes = epRes.ok && Array.isArray(epRes.data) ? epRes.data : [];
        const sampleEp = episodes[0] || null;
        const sampleEpKey = sampleEp
          ? Object.prototype.hasOwnProperty.call(sampleEp, "i")
            ? String(sampleEp.i)
            : String(sampleEp.id)
          : null;
        const egoItem = sampleEpKey && egoIdx.map.has(sampleEpKey) ? egoIdx.map.get(sampleEpKey) : null;
        const qaChecksSample =
          qaRes.ok && qaRes.data
            ? (sampleEpKey && qaRes.data[sampleEpKey]) || Object.values(qaRes.data)[0] || null
            : null;
        const robotTs = robotEp0Res.ok && robotEp0Res.data ? robotEp0Res.data : null;
        if (episodes.length > 0 || robotTs) hasLiveOnDisk = true;

        const schemaRows = buildCompactSchemaRows({
          row,
          sampleEp,
          egoItem,
          robotTs,
          qaChecksSample,
        });

        let samplePreviewSection = null;
        if (episodes.length > 0) {
          const isRobotEp = Object.prototype.hasOwnProperty.call(episodes[0], "i");
          samplePreviewSection = el("section", { className: "card" }, [
            el("div", { className: "task-head", style: "margin-bottom:10px" }, [
              el("h2", { text: t("ds.samplePreviewTitle") }),
              el(
                "a",
                {
                  className: "link",
                  href: `#/data/${encodeURIComponent(dsId)}?tab=content`,
                },
                [t("ds.samplePreviewOpenAll")]
              ),
            ]),
            el(
              "div",
              { className: "sample-grid-4" },
              episodes.slice(0, 4).map((ep) => {
                const epKey = isRobotEp ? String(ep.i) : String(ep.id);
                const posterUrl = isRobotEp
                  ? `data/ds/${encodeURIComponent(dsId)}/posters/${encodeURIComponent(epKey)}.jpg`
                  : safeThumbUrl(ep.poster) ||
                    (dsId.startsWith("src_")
                      ? `/api/poster?work=${encodeURIComponent(dsId)}&ep=${encodeURIComponent(epKey)}&w=320`
                      : null);
                const rich = egoIdx.map.get(epKey);
                return el(
                  "a",
                  {
                    className: "ep-visual-card",
                    href: `#/data/${encodeURIComponent(dsId)}/ep/${encodeURIComponent(epKey)}`,
                  },
                  [
                    posterUrl
                      ? el("img", {
                          src: posterUrl,
                          alt: epKey,
                          loading: "lazy",
                          onError: (ev) => {
                            ev.target.hidden = true;
                          },
                        })
                      : el("div", { className: "thumb" }, [
                          el("span", { className: "mono", text: epKey }),
                        ]),
                    el("div", { className: "ep-visual-body" }, [
                      el("div", {
                        className: "ep-visual-title",
                        text: (rich && rich.title) || ep.title || `#${epKey}`,
                      }),
                      el("div", { className: "tag-row" }, [
                        ep.s != null
                          ? el("span", {
                              className: cls("mini-tag", "mono"),
                              text: `${formatNumber(ep.s, { maximumFractionDigits: 1 })} s`,
                            })
                          : null,
                        ep.hands != null
                          ? el("span", {
                              className: cls("mini-tag", "mono"),
                              text: t("ego.handsChip", { pct: formatPercent(ep.hands) }),
                            })
                          : null,
                        ep.qa ? renderStateChip(ep.qa) : null,
                      ]),
                    ]),
                  ]
                );
              })
            ),
          ]);
        } else if (robotTs) {
          samplePreviewSection = el("section", { className: "card" }, [
            el("h2", { style: "margin-bottom:8px", text: t("ds.samplePreviewTitle") }),
            el("img", {
              className: "filmstrip",
              src: `/api/strip?ds=${encodeURIComponent(dsId)}&ep=0`,
              alt: `${dsId} ep 0`,
              onError: (ev) => {
                ev.target.hidden = true;
              },
            }),
            renderJumpToEpisodeBar(dsId, row.episodes || 1, true),
          ]);
        }

        const metaPairs = [
          [t("common.id"), row.id],
          [t("ds.attrKind"), `${row.group || "-"} · ${row.kind || "-"}`],
          [t("ds.attrTask"), row.task],
          [t("ds.attrFormat"), row.format],
          ["FPS", row.fps],
          [t("ds.attrLicence"), row.licence],
          [t("data.colClass"), row.data_class],
          ["QA", row.qa],
        ].filter(([, v]) => v !== null && v !== undefined && v !== "");

        tabBody = el("div", { className: "stack" }, [
          samplePreviewSection,

          el("section", { className: cls("card", "table-wrap") }, [
            el("h2", { style: "margin-bottom:8px", text: t("ds.schemaSectionTitle") }),
            el("table", { className: "table" }, [
              el("thead", {}, [
                el("tr", {}, [
                  el("th", { text: t("ds.colFieldName") }),
                  el("th", { text: t("ds.colFieldType") }),
                  el("th", { text: t("ds.colSampleCompact") }),
                ]),
              ]),
              el(
                "tbody",
                {},
                schemaRows.map((sr) =>
                  el("tr", { title: sr.tooltip || "" }, [
                    el("td", { className: "mono", style: "font-weight:650", text: sr.name }),
                    el("td", { className: "mono", style: "white-space:nowrap", text: sr.shape }),
                    el("td", {}, [
                      el(
                        "div",
                        { className: "tag-row" },
                        (sr.chips || []).map((c) =>
                          el("span", { className: cls("mini-tag", "mono"), text: String(c) })
                        )
                      ),
                    ]),
                  ])
                )
              ),
            ]),
          ]),

          el("section", { className: "card" }, [
            el("h2", { text: t("ds.metaTitle") }),
            el(
              "div",
              { className: "meta-strip", style: "margin-top:10px" },
              metaPairs.map(([k, v]) =>
                el("div", { className: "meta-box" }, [
                  el("span", { text: k }),
                  el("b", {
                    className: "mono",
                    style: "font-size:12px;overflow-wrap:anywhere",
                    text: scrubPath(String(v)),
                  }),
                ])
              )
            ),
          ]),

          methodRes.ok && methodRes.data
            ? renderMethodStructuredCard(methodRes.data, t("ds.filesOnDiskTitle"))
            : null,

          el("section", { className: "card" }, [
            el("h2", { text: t("ds.locationsTitle") }),
            !(Array.isArray(row.locations) && row.locations.length > 0)
              ? el("p", { className: "muted", text: t("state.na") })
              : el(
                  "div",
                  { className: "row-list" },
                  row.locations.map((loc) =>
                    el("div", { className: "row" }, [
                      el("div", { className: "row-body" }, [
                        el("b", { text: loc.where || "-" }),
                        el("p", {
                          className: cls("muted", "mono"),
                          text: scrubPath(loc.path || loc.raw || ""),
                        }),
                      ]),
                      renderStateChip(loc.exists ? "ok" : "missing"),
                    ])
                  )
                ),
          ]),
        ]);
      } else if (activeTab === "content") {
        const [epRes, egoIdx, robotProbe] = await Promise.all([
          tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/episodes.json`),
          row.ego_viewer ? ensureEgoViewerIndex() : Promise.resolve({ map: new Map() }),
          isRobotDs
            ? tryGetJSON(`/api/episode?ds=${encodeURIComponent(dsId)}&ep=0`)
            : Promise.resolve({ ok: false }),
        ]);
        const episodes = epRes.ok && Array.isArray(epRes.data) ? epRes.data : [];
        if (episodes.length > 0 || robotProbe.ok) hasLiveOnDisk = true;

        let qaFilter = "all";
        let epSearch = "";
        let contentMode =
          episodes.length > 0 &&
          (Object.prototype.hasOwnProperty.call(episodes[0], "i") ||
            episodes.some((e) => e.poster || e.ego))
            ? "cards"
            : "table";
        let visibleLimit = 80;
        const contentBox = el("div", {});

        const renderEpList = () => {
          if (episodes.length === 0) {
            if (robotProbe.ok) {
              const totalN = row.episodes || 12;
              const sampleIndices = Array.from({ length: Math.min(12, totalN) }, (_, k) => k);
              setChildren(
                contentBox,
                el("section", { className: "card" }, [
                  renderJumpToEpisodeBar(dsId, totalN, true),
                  el(
                    "div",
                    { className: "sample-grid-4", style: "margin-top:12px" },
                    sampleIndices.map((idx) =>
                      el(
                        "a",
                        {
                          className: "sample-ep-card",
                          href: `#/data/${encodeURIComponent(dsId)}/ep/${idx}`,
                        },
                        [
                          el("img", {
                            className: "filmstrip",
                            src: `/api/strip?ds=${encodeURIComponent(dsId)}&ep=${idx}`,
                            alt: `ep ${idx}`,
                            loading: "lazy",
                          }),
                          el("b", { className: "mono", text: `${t("ds.colEp")} #${idx}` }),
                        ]
                      )
                    )
                  ),
                ])
              );
              return;
            }
            setChildren(
              contentBox,
              el("div", { className: "empty", text: t("ds.episodesEmpty") })
            );
            return;
          }

          const isRobot = Object.prototype.hasOwnProperty.call(episodes[0], "i");
          const isSrc = !isRobot && Object.prototype.hasOwnProperty.call(episodes[0], "jit");
          const sq = epSearch.trim().toLowerCase();

          const filtered = episodes.filter((e) => {
            if (qaFilter !== "all" && e.qa && e.qa !== qaFilter) return false;
            if (sq) {
              const k = isRobot ? String(e.i) : String(e.id);
              const rich = egoIdx.map.get(k);
              const blob = `${k} ${e.title || ""} ${(e.reasons || []).join(" ")} ${rich ? `${rich.task || ""} ${(rich.subtasks || []).join(" ")}` : ""}`.toLowerCase();
              if (!blob.includes(sq)) return false;
            }
            return true;
          });

          const shown = filtered.slice(0, visibleLimit);

          if (contentMode === "cards") {
            setChildren(
              contentBox,
              el("div", { className: "tiny", style: "margin-bottom:8px" }, [
                t("ds.showingCount", {
                  shown: formatNumber(shown.length),
                  total: formatNumber(filtered.length),
                }),
              ]),
              el(
                "div",
                { className: "ep-card-grid" },
                shown.map((ep) => {
                  const epKey = isRobot ? String(ep.i) : String(ep.id);
                  const href = `#/data/${encodeURIComponent(dsId)}/ep/${encodeURIComponent(epKey)}`;
                  const posterUrl = isRobot
                    ? `data/ds/${encodeURIComponent(dsId)}/posters/${encodeURIComponent(epKey)}.jpg`
                    : safeThumbUrl(ep.poster) ||
                      (ep.ego && dsId.startsWith("src_")
                        ? `/api/poster?work=${encodeURIComponent(dsId)}&ep=${encodeURIComponent(epKey)}&w=320`
                        : null);
                  const rich = egoIdx.map.get(epKey);

                  return el("a", { className: "ep-visual-card", href }, [
                    posterUrl
                      ? el("img", {
                          src: posterUrl,
                          alt: epKey,
                          loading: "lazy",
                          onError: (ev) => {
                            ev.target.hidden = true;
                          },
                        })
                      : el("div", { className: "thumb" }, [
                          el("span", { className: "mono", text: epKey }),
                        ]),
                    el("div", { className: "ep-visual-body" }, [
                      el("div", {
                        className: "ep-visual-title",
                        text: (rich && rich.title) || ep.title || `#${epKey}`,
                      }),
                      el("div", { className: "tag-row" }, [
                        ep.s != null
                          ? el("span", {
                              className: cls("mini-tag", "mono"),
                              text: `${formatNumber(ep.s, { maximumFractionDigits: 1 })} s`,
                            })
                          : null,
                        isRobot && ep.lv != null
                          ? el("span", { className: cls("mini-tag", "mono"), text: `L${ep.lv}` })
                          : null,
                        ep.hands != null
                          ? el("span", {
                              className: cls("mini-tag", "mono"),
                              text: t("ego.handsChip", { pct: formatPercent(ep.hands) }),
                            })
                          : null,
                        ep.pose
                          ? el("span", { className: cls("mini-tag", "mono"), text: ep.pose })
                          : null,
                        ep.qa ? renderStateChip(ep.qa) : null,
                      ]),
                    ]),
                  ]);
                })
              ),
              filtered.length > visibleLimit
                ? el("div", { className: "toolbar" }, [
                    el(
                      "button",
                      {
                        type: "button",
                        className: "btn",
                        onClick: () => {
                          visibleLimit += 80;
                          renderEpList();
                        },
                      },
                      [t("ds.loadMoreEps")]
                    ),
                  ])
                : null
            );
            return;
          }

          setChildren(
            contentBox,
            el("div", { className: "tiny", style: "margin-bottom:8px" }, [
              t("ds.showingCount", {
                shown: formatNumber(shown.length),
                total: formatNumber(filtered.length),
              }),
            ]),
            el("div", { className: cls("card", "table-wrap") }, [
              el("table", { className: "table" }, [
                el("thead", {}, [
                  isRobot
                    ? el("tr", {}, [
                        el("th", { text: t("ds.colEp") }),
                        el("th", { className: "num", text: t("ds.colFrames") }),
                        el("th", { className: "num", text: t("ds.colDuration") }),
                        el("th", { text: t("ds.colLevelSeed") }),
                        el("th", { text: t("ds.colPart") }),
                        el("th", { text: "" }),
                      ])
                    : isSrc
                      ? el("tr", {}, [
                          el("th", { text: t("ds.colEp") }),
                          el("th", { className: "num", text: t("ds.colFrames") }),
                          el("th", { className: "num", text: t("ds.colDuration") }),
                          el("th", { className: "num", text: t("ds.colOutJitLowc") }),
                          el("th", { text: t("ds.colQa") }),
                          el("th", { text: "" }),
                        ])
                      : el("tr", {}, [
                          el("th", { text: t("ds.colEp") }),
                          el("th", { className: "num", text: t("ds.colDuration") }),
                          el("th", { text: t("ds.colHandsPose") }),
                          el("th", { text: t("ds.colQa") }),
                          el("th", { text: "" }),
                        ]),
                ]),
                el(
                  "tbody",
                  {},
                  shown.map((ep) => {
                    const epKey = isRobot ? String(ep.i) : String(ep.id);
                    const href = `#/data/${encodeURIComponent(dsId)}/ep/${encodeURIComponent(epKey)}`;
                    if (isRobot) {
                      return el("tr", {}, [
                        el("td", { className: "mono" }, [
                          el("a", { className: "link", href }, [`#${epKey}`]),
                        ]),
                        el("td", { className: "num", text: formatNumber(ep.n) }),
                        el("td", {
                          className: "num",
                          text:
                            ep.s != null
                              ? `${formatNumber(ep.s, { maximumFractionDigits: 1 })} s`
                              : t("state.na"),
                        }),
                        el("td", {
                          className: "mono",
                          text: `L${ep.lv ?? "-"} · seed ${ep.seed ?? "-"}`,
                        }),
                        el("td", { className: "mono", text: ep.part || "-" }),
                        el("td", { style: "white-space:nowrap" }, [
                          el("a", { className: "link", href }, [t("common.view")]),
                        ]),
                      ]);
                    }
                    if (isSrc) {
                      return el("tr", {}, [
                        el("td", { className: "mono" }, [
                          el("a", { className: "link", href }, [epKey]),
                        ]),
                        el("td", { className: "num", text: formatNumber(ep.n) }),
                        el("td", {
                          className: "num",
                          text:
                            ep.s != null
                              ? `${formatNumber(ep.s, { maximumFractionDigits: 1 })} s`
                              : t("state.na"),
                        }),
                        el("td", {
                          className: cls("num", "mono"),
                          text: `${formatNumber(ep.out, { maximumFractionDigits: 2 })} / ${formatNumber(ep.jit, { maximumFractionDigits: 1 })}° / ${formatNumber(ep.lowc, { maximumFractionDigits: 2 })}`,
                        }),
                        el("td", {}, [renderStateChip(ep.qa || "na")]),
                        el("td", { style: "white-space:nowrap" }, [
                          el("a", { className: "link", href }, [t("common.view")]),
                        ]),
                      ]);
                    }
                    return el("tr", {}, [
                      el("td", {}, [
                        el("a", { className: "link", href }, [ep.title || epKey]),
                        el("div", { className: cls("tiny", "mono"), text: epKey }),
                      ]),
                      el("td", {
                        className: "num",
                        text:
                          ep.s != null
                            ? `${formatNumber(ep.s, { maximumFractionDigits: 1 })} s`
                            : t("state.na"),
                      }),
                      el("td", {
                        className: "mono",
                        style: "white-space:nowrap",
                        text: [
                          ep.hands != null ? formatPercent(ep.hands) : null,
                          ep.pose || null,
                          ep.nsub != null ? `${ep.nsub} sub` : null,
                        ]
                          .filter(Boolean)
                          .join(" · "),
                      }),
                      el("td", {}, [renderStateChip(ep.qa || "na")]),
                      el("td", { style: "white-space:nowrap" }, [
                        el("a", { className: "link", href }, [t("common.view")]),
                      ]),
                    ]);
                  })
                ),
              ]),
            ])
          );
        };

        const hasQaField = episodes.some((e) => e.qa);
        const modeBtn = el(
          "button",
          {
            type: "button",
            className: "btn",
            onClick: () => {
              contentMode = contentMode === "cards" ? "table" : "cards";
              modeBtn.textContent =
                contentMode === "cards" ? t("ds.viewTable") : t("ds.viewCards");
              renderEpList();
            },
          },
          [contentMode === "cards" ? t("ds.viewTable") : t("ds.viewCards")]
        );

        tabBody = el("div", { className: "stack" }, [
          episodes.length > 0
            ? el("div", { className: "toolbar" }, [
                el("input", {
                  type: "search",
                  className: cls("field", "search"),
                  placeholder: t("ds.searchEpPlaceholder"),
                  onInput: (ev) => {
                    epSearch = ev.target.value;
                    visibleLimit = 80;
                    renderEpList();
                  },
                }),
                hasQaField
                  ? el(
                      "select",
                      {
                        className: "field",
                        onChange: (ev) => {
                          qaFilter = ev.target.value;
                          visibleLimit = 80;
                          renderEpList();
                        },
                      },
                      [
                        el("option", { value: "all", text: t("ds.filterQaAll") }),
                        el("option", { value: "pass", text: formatStateLabel("pass") }),
                        el("option", { value: "flag", text: formatStateLabel("flag") }),
                        el("option", { value: "reject", text: formatStateLabel("reject") }),
                      ]
                    )
                  : null,
                modeBtn,
              ])
            : null,
          contentBox,
        ]);
        renderEpList();
      } else if (activeTab === "quality") {
        const qaDsId = resolveQaDatasetId(dsId, row);
        const [qualRes, qaRes] = await Promise.all([
          tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/quality.json`),
          tryGetJSON(`data/ds/${encodeURIComponent(qaDsId)}/qa.json`),
        ]);
        const qual = qualRes.ok ? qualRes.data : null;
        const hists = qual && Array.isArray(qual.hists) ? qual.hists : [];
        const reasons = qual && Array.isArray(qual.reasons) ? qual.reasons : [];

        tabBody =
          !qual && !(qaRes.ok && qaRes.data) && !row.qa_counts
            ? el("div", { className: "empty", text: t("ds.qualityEmpty") })
            : el("div", { className: "stack" }, [
                (qual && qual.qa) || row.qa_counts
                  ? el("section", { className: "card" }, [
                      el("h2", { text: "QA" }),
                      el(
                        "div",
                        { className: "meta-strip", style: "margin-top:10px" },
                        Object.entries((qual && qual.qa) || row.qa_counts || {}).map(([k, v]) =>
                          el("div", { className: "meta-box" }, [
                            el("span", { text: formatStateLabel(k) }),
                            el("b", { text: formatNumber(v) }),
                          ])
                        )
                      ),
                      reasons.length > 0
                        ? el(
                            "div",
                            { className: "step-tags", style: "margin-top:10px" },
                            reasons.map(([rk, rv]) =>
                              el("span", {
                                className: cls("step-tag", "mono"),
                                text: `${rk}: ${formatNumber(rv)}`,
                              })
                            )
                          )
                        : null,
                    ])
                  : null,
                ...hists.slice(0, 6).map((h) =>
                  renderChartBlock({
                    title: h.label || h.field,
                    height: 220,
                    buildOption: ({ soft, line, colors }) => ({
                      grid: { left: 46, right: 18, top: 18, bottom: 32 },
                      tooltip: { trigger: "axis" },
                      xAxis: {
                        type: "category",
                        data: (h.bins || []).map((b) => `${b.lo}`),
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
                          data: (h.bins || []).map((b) => b.c),
                          itemStyle: { color: colors[0], borderRadius: [4, 4, 0, 0] },
                        },
                      ],
                    }),
                    tableNode: el("table", { className: "table" }, [
                      el(
                        "tbody",
                        {},
                        (h.bins || []).map((b) =>
                          el("tr", {}, [
                            el("td", { className: "mono", text: `${b.lo} – ${b.hi}` }),
                            el("td", { className: "num", text: formatNumber(b.c) }),
                          ])
                        )
                      ),
                    ]),
                  })
                ),
              ]);
      } else if (activeTab === "lineage") {
        const methodRes = await tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/method.json`);
        const parents = Array.isArray(row.parents) ? row.parents : [];
        const children = Array.isArray(row.children) ? row.children : [];
        const rowMap = new Map(rows.map((r) => [r.id, r]));

        const renderRelList = (ids) =>
          ids.length === 0
            ? el("p", { className: "muted", text: t("state.empty") })
            : el(
                "div",
                { className: "step-tags" },
                ids.map((rid) =>
                  rowMap.has(rid)
                    ? el(
                        "a",
                        {
                          className: cls("step-tag", "mono"),
                          href: `#/data/${encodeURIComponent(rid)}`,
                        },
                        [rid]
                      )
                    : el("span", {
                        className: cls("step-tag", "mono"),
                        text: t("data.lineageMissingNode", { id: rid }),
                      })
                )
              );

        const localEdges = [
          ...parents.map((p) => [p, dsId]),
          ...children.map((c) => [dsId, c]),
        ];
        tabBody = el("div", { className: "stack" }, [
          renderLineageSankeyCard(localEdges, rowMap, dsId),
          el("div", { className: "grid" }, [
            el("section", { className: "card" }, [
              el("h2", { text: t("ds.parentsTitle") }),
              renderRelList(parents),
            ]),
            el("section", { className: "card" }, [
              el("h2", { text: t("ds.childrenTitle") }),
              renderRelList(children),
            ]),
          ]),
          methodRes.ok && methodRes.data
            ? renderMethodStructuredCard(methodRes.data, t("ds.methodTitle"))
            : null,
        ]);
      } else {
        const jobs = await getJSON("/api/jobs?limit=100");
        const needles = [dsId, row.laptop_dir].filter(Boolean);
        const matches = (jobs || []).filter((j) => {
          const blob = JSON.stringify([j.params, j.outputs, j.argv]);
          return needles.some((n) => blob.includes(n));
        });

        tabBody = el("section", { className: "card" }, [
          el("p", { className: "muted", text: t("ds.jobsRelatedNote") }),
          matches.length === 0
            ? el("p", { className: "muted", text: t("state.empty") })
            : el(
                "div",
                { className: "row-list" },
                matches.map((j) =>
                  el("div", { className: "row" }, [
                    el("div", { className: "row-body" }, [
                      el(
                        "a",
                        {
                          className: cls("link", "mono"),
                          href: `#/jobs?job=${encodeURIComponent(j.id)}`,
                        },
                        [`${j.id} · ${j.kind}`]
                      ),
                      el("p", { className: "muted", text: formatDateTime(j.created) }),
                    ]),
                    el("span", { className: cls("chip", "warning"), text: t("ds.maybeRelated") }),
                    renderStateChip(j.state),
                  ])
                )
              ),
        ]);
      }

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [
            { label: t("app.crumbRoot"), href: "#/tasks" },
            { label: t("data.title"), href: "#/data" },
            { label: row.title || dsId },
          ],
          title: row.title || dsId,
          lead: `${row.id} · ${row.format || row.kind || "-"} · ${locationLabel(row, hasLiveOnDisk)}`,
          actions: !state.locked
            ? [
                el("a", { className: cls("btn", "primary"), href: "#/jobs?view=pipeline" }, [
                  t("nav.item.pipeline"),
                ]),
              ]
            : [],
        }),
        renderStatStrip([
          {
            label: t("data.colEpisodes"),
            value: formatNumber(row.episodes),
            sub: [
              row.frames != null ? t("data.framesShort", { val: formatNumber(row.frames) }) : null,
              row.hours != null
                ? t("tasks.unitHours", {
                    val: formatNumber(row.hours, { maximumFractionDigits: 3 }),
                  })
                : null,
            ]
              .filter(Boolean)
              .join(" · "),
          },
          {
            label: t("ds.attrFormat"),
            value: row.fps ? `${row.fps} fps` : row.data_type || t("state.na"),
            sub: row.format || row.licence || "",
          },
          {
            label: t("common.status"),
            value: formatStateLabel(row.status),
            sub: `${row.data_class || "-"} · ${locationLabel(row, hasLiveOnDisk)}`,
          },
        ]),
        tabsBar,
        tabBody
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/data/:id/ep/:n — Robot or Native Egocentric 2D/3D Episode Inspector
// ============================================================================
export function renderEpisodeDetailPage(ctx) {
  const dsId = ctx.params.id;
  const epParam = ctx.params.n;
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(`${dsId} / ${epParam}`));
  setSelection({ dataset_id: dsId, episode_id: epParam }, true);

  const load = async () => {
    try {
      const [cat, epListRes] = await Promise.all([
        ensureCatalog(),
        tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/episodes.json`),
      ]);
      const row = (cat.rows || []).find((r) => String(r.id) === String(dsId));
      const episodes = epListRes.ok && Array.isArray(epListRes.data) ? epListRes.data : [];

      const isRobot =
        (row && Boolean(row.lerobot)) ||
        (row && (row.view === "robot" || row.view === "lerobot")) ||
        (episodes[0] && Object.prototype.hasOwnProperty.call(episodes[0], "i"));

      const idx = episodes.findIndex((e) =>
        isRobot ? String(e.i) === String(epParam) : String(e.id) === String(epParam)
      );
      const epMeta = idx >= 0 ? episodes[idx] : null;
      const totalRobotEps = row && row.episodes ? Number(row.episodes) : episodes.length;
      const epNum = Number(epParam);

      let prevHref = null;
      let nextHref = null;
      if (idx > 0) {
        const p = episodes[idx - 1];
        prevHref = `#/data/${encodeURIComponent(dsId)}/ep/${encodeURIComponent(isRobot ? p.i : p.id)}`;
      } else if (isRobot && episodes.length === 0 && Number.isInteger(epNum) && epNum > 0) {
        prevHref = `#/data/${encodeURIComponent(dsId)}/ep/${epNum - 1}`;
      }
      if (idx >= 0 && idx < episodes.length - 1) {
        const nx = episodes[idx + 1];
        nextHref = `#/data/${encodeURIComponent(dsId)}/ep/${encodeURIComponent(isRobot ? nx.i : nx.id)}`;
      } else if (
        isRobot &&
        episodes.length === 0 &&
        Number.isInteger(epNum) &&
        epNum + 1 < totalRobotEps
      ) {
        nextHref = `#/data/${encodeURIComponent(dsId)}/ep/${epNum + 1}`;
      }

      const navButtons = [
        el("a", { className: "btn", href: `#/data/${encodeURIComponent(dsId)}?tab=content` }, [
          t("ep.backDataset", { id: dsId }),
        ]),
        prevHref ? el("a", { className: "btn", href: prevHref }, [t("ep.prev")]) : null,
        nextHref ? el("a", { className: "btn", href: nextHref }, [t("ep.next")]) : null,
      ].filter(Boolean);

      if (isRobot) {
        const [tsRes, envRes] = await Promise.all([
          tryGetJSON(
            `/api/episode?ds=${encodeURIComponent(dsId)}&ep=${encodeURIComponent(epParam)}`
          ),
          tryGetJSON(`data/ds/${encodeURIComponent(dsId)}/env.json`),
        ]);
        const envEp =
          envRes.ok && envRes.data ? envRes.data[String(epParam)] || null : null;
        const stripUrl = `/api/strip?ds=${encodeURIComponent(dsId)}&ep=${encodeURIComponent(epParam)}`;
        const padded = Number.isInteger(epNum) && epNum >= 0 ? String(epNum).padStart(6, "0") : null;
        const videoUrl = padded ? `/media/${encodeURIComponent(dsId)}/episode_${padded}.mp4` : null;

        const stripHolder = el("div", {}, [
          el("img", {
            className: "filmstrip",
            src: stripUrl,
            alt: epParam,
            onError: () => {
              setChildren(
                stripHolder,
                el("div", { className: "empty", text: t("error.mediaMissing") })
              );
            },
          }),
        ]);

        const videoHolder = videoUrl
          ? el("div", {}, [
              el("video", {
                className: "video-player",
                controls: true,
                preload: "metadata",
                src: videoUrl,
                onError: () => {
                  setChildren(
                    videoHolder,
                    el("div", { className: "empty", text: t("error.mediaMissing") })
                  );
                },
              }),
            ])
          : el("div", { className: "empty", text: t("error.mediaMissing") });

        const player = videoHolder.querySelector("video");
        if (player) {
          const scrubber = el("input", {
            type: "range", min: 0, step: "any", value: 0, disabled: true,
            className: "filmstrip-scrubber", "aria-label": t("ep.filmstripTitle"),
            onInput: (event) => { player.currentTime = Number(event.target.value); },
          });
          player.addEventListener("durationchange", () => {
            scrubber.disabled = !Number.isFinite(player.duration) || player.duration <= 0;
            if (!scrubber.disabled) scrubber.max = String(player.duration);
          });
          player.addEventListener("timeupdate", () => { scrubber.value = String(player.currentTime); });
          player.addEventListener("error", () => { scrubber.disabled = true; });
          stripHolder.appendChild(scrubber);
        }

        const signalCharts = [];
        const signalPanel = el("section", { className: "signal-panel" });
        const channelSummaryRows = [];

        if (tsRes.ok && tsRes.data) {
          const ts = tsRes.data.t || [];
          const groups = [
            ...Object.entries(tsRes.data.action || {}).map(([g, d]) => [`action.${g}`, d]),
            ...Object.entries(tsRes.data.state || {}).map(([g, d]) => [`state.${g}`, d]),
          ];
          for (const [gTitle, gData] of groups) {
            const names = gData.names || [];
            const vals = gData.v || [];
            const flat = vals.flat().filter((v) => typeof v === "number");
            const mnAll = flat.length ? Math.min(...flat) : null;
            const mxAll = flat.length ? Math.max(...flat) : null;
            const shortChips = names.slice(0, 4).map((n) => n.replace(/_joint$/, ""));
            // Plot the eight channels that move most and show the three that move most, so the
            // chart never opens on one flat line at 0 (design audit P2-8).
            const spanOf = (sIdx) => {
              const arr = (vals[sIdx] || []).filter((v) => typeof v === "number");
              return arr.length ? Math.max(...arr) - Math.min(...arr) : 0;
            };
            const plotIdx = names
              .map((_, sIdx) => [sIdx, spanOf(sIdx)])
              .sort((a, b) => b[1] - a[1] || a[0] - b[0])
              .slice(0, 8)
              .map(([sIdx]) => sIdx);
            if (names.length > 4) shortChips.push(`+${names.length - 4}`);

            channelSummaryRows.push({
              group: gTitle,
              dims: names.length,
              chips: shortChips,
              tooltip: names.join(", "),
              range:
                mnAll !== null
                  ? `[${formatNumber(mnAll, { maximumFractionDigits: 3 })} .. ${formatNumber(mxAll, { maximumFractionDigits: 3 })}]`
                  : "-",
            });

            signalCharts.push(
              () => renderChartBlock({
                title: `${gTitle} (${names.length})`,
                height: 205,
                buildOption: ({ soft, line, colors }) => ({
                  grid: { left: 48, right: 18, top: 28, bottom: 26 },
                  tooltip: { trigger: "axis" },
                  legend: {
                    type: "scroll", top: 0,
                    selected: Object.fromEntries(plotIdx.map((sIdx, rank) => [names[sIdx], rank < 3])),
                    textStyle: { color: soft, fontSize: 12 },
                  },
                  xAxis: {
                    type: "category",
                    data: ts,
                    axisLabel: {
                      color: soft,
                      formatter: (v) => formatNumber(Number(v), { maximumFractionDigits: 1 }),
                    },
                  },
                  yAxis: {
                    type: "value",
                    axisLabel: {
                      color: soft,
                      formatter: (v) => formatNumber(v, { maximumFractionDigits: 2 }),
                    },
                    splitLine: { lineStyle: { color: line } },
                  },
                  series: plotIdx.map((sIdx, rank) => ({
                    name: names[sIdx],
                    type: "line",
                    showSymbol: false,
                    data: vals[sIdx] || [],
                    itemStyle: { color: colors[rank % colors.length] },
                    lineStyle: { width: 1.5, color: colors[rank % colors.length] },
                  })),
                }),
                onChartClick: ({ dataIndex }) => {
                  const time = ts[dataIndex];
                  if (player && Number.isFinite(player.duration) && Number.isFinite(time)) {
                    player.currentTime = Math.max(0, Math.min(time, player.duration));
                  }
                },
                tableNode: el("table", { className: "table" }, [
                  el(
                    "tbody",
                    {},
                    names.map((nm, sIdx) => {
                      const arr = (vals[sIdx] || []).filter((v) => v !== null);
                      const mn = arr.length ? Math.min(...arr) : null;
                      const mx = arr.length ? Math.max(...arr) : null;
                      return el("tr", {}, [
                        el("td", { className: "mono", text: nm }),
                        el("td", {
                          className: "num",
                          text: formatNumber(mn, { maximumFractionDigits: 3 }),
                        }),
                        el("td", {
                          className: "num",
                          text: formatNumber(mx, { maximumFractionDigits: 3 }),
                        }),
                      ]);
                    })
                  ),
                ]),
              })
            );
          }
        }

        if (signalCharts.length) {
          const charts = new Map();
          const holder = el("div");
          const selectSignal = (index) => {
            if (!charts.has(index)) charts.set(index, signalCharts[index]());
            setChildren(holder, charts.get(index));
          };
          signalPanel.append(el("label", { className: "analysis-picker" }, [
            t("ep.robotSignals"),
            el("select", { className: "field", onChange: (event) => selectSignal(event.target.selectedIndex) },
              channelSummaryRows.map((row) => el("option", { text: row.group }))),
          ]), holder);
          selectSignal(0);
        }

        const durSec =
          epMeta && epMeta.s != null
            ? epMeta.s
            : tsRes.ok && tsRes.data && tsRes.data.n
              ? tsRes.data.n / (tsRes.data.fps || 50)
              : null;

        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [
              { label: t("app.crumbRoot"), href: "#/tasks" },
              { label: t("data.title"), href: "#/data" },
              { label: dsId, href: `#/data/${encodeURIComponent(dsId)}` },
              { label: `${t("ds.colEp")} ${epParam}` },
            ],
            title: `${dsId} · ${t("ds.colEp")} #${epParam}`,
            lead: [
              durSec != null ? `${formatNumber(durSec, { maximumFractionDigits: 1 })} s` : null,
              tsRes.ok && tsRes.data ? `${formatNumber(tsRes.data.n)} fr @ ${tsRes.data.fps || 50} fps` : null,
              epMeta ? `L${epMeta.lv ?? "-"} · seed ${epMeta.seed ?? "-"}` : null,
            ]
              .filter(Boolean)
              .join(" · "),
            actions: navButtons,
          }),
          totalRobotEps > 1 ? renderJumpToEpisodeBar(dsId, totalRobotEps, false) : null,
          el("div", { className: "episode-screen" }, [
            el("section", { className: "card" }, [
              el("h2", { text: t("ep.videoTitle") }),
              videoHolder,
            ]),
            el("section", { className: "card" }, [
              el("h2", { text: t("ep.filmstripTitle") }),
              stripHolder,
            ]),
          ]),
          tsRes.ok
            ? signalPanel
            : el("div", {
                className: "empty",
                text:
                  tsRes.status === 404
                    ? t("error.mediaMissing")
                    : (tsRes.error && tsRes.error.serverMessage) || t("state.na"),
              }),
          envEp
            ? el("section", { className: "card" }, [
                el("h2", { text: t("ep.envSummaryTitle") }),
                el(
                  "div",
                  { className: "meta-strip", style: "margin-top:8px" },
                  [
                    ["level", envEp.sample && envEp.sample.level],
                    ["seed", envEp.sample && envEp.sample.seed],
                    ["table_gap", envEp.sample && envEp.sample.table_gap],
                    ["light_scale", envEp.sample && envEp.sample.light_scale],
                    [
                      "success",
                      envEp.report ? t(envEp.report.success ? "ep.env.successYes" : "ep.env.successNo") : null,
                    ],
                  ]
                    .filter(([, v]) => v != null)
                    .map(([k, v]) =>
                      el("div", { className: "meta-box" }, [
                        el("span", { title: k, text: t(`ep.env.${k}`) }),
                        el("b", {
                          className: "mono",
                          text:
                            typeof v === "number" && k !== "seed"
                              ? formatNumber(v, { maximumFractionDigits: 3 })
                              : String(v),
                        }),
                      ])
                    )
                ),
              ])
            : null,
          channelSummaryRows.length > 0
            ? el("section", { className: cls("card", "table-wrap"), style: "margin-top:14px" }, [
                el("h2", { style: "margin-bottom:8px", text: t("ep.channelSummaryTitle") }),
                el("table", { className: "table" }, [
                  el("thead", {}, [
                    el("tr", {}, [
                      el("th", { text: t("ep.colGroup") }),
                      el("th", { className: "num", text: t("ep.colDimCount") }),
                      el("th", { text: t("ep.colJointNames") }),
                      el("th", { text: t("ep.colMinMax") }),
                    ]),
                  ]),
                  el(
                    "tbody",
                    {},
                    channelSummaryRows.map((cr) =>
                      el("tr", { title: cr.tooltip }, [
                        el("td", { className: "mono", style: "font-weight:650", text: cr.group }),
                        el("td", { className: "num", text: formatNumber(cr.dims) }),
                        el("td", {}, [
                          el(
                            "div",
                            { className: "tag-row" },
                            cr.chips.map((c) =>
                              el("span", { className: cls("mini-tag", "mono"), text: c })
                            )
                          ),
                        ]),
                        el("td", { className: "mono", style: "white-space:nowrap", text: cr.range }),
                      ])
                    )
                  ),
                ]),
              ])
            : null
        );
        return;
      }

      // Egocentric episode: load rich 2D/3D hand track natively if available!
      const qaDsId = resolveQaDatasetId(dsId, row);
      const [qaRes, egoTrack] = await Promise.all([
        tryGetJSON(`data/ds/${encodeURIComponent(qaDsId)}/qa.json`),
        fetchEgoEpisodeTrack(epParam),
      ]);
      const qaChecks = qaRes.ok && qaRes.data && qaRes.data[epParam] ? qaRes.data[epParam] : [];

      const qaSection =
        qaChecks.length > 0
          ? el("section", { className: cls("card", "table-wrap") }, [
              el("h2", { style: "margin-bottom:8px", text: t("ep.qaChecksTitle") }),
              el("table", { className: "table" }, [
                el("thead", {}, [
                  el("tr", {}, [
                    el("th", { text: t("ep.colCheck") }),
                    el("th", { className: "num", text: t("ep.colValue") }),
                    el("th", { className: "num", text: t("ep.colThreshold") }),
                    el("th", { text: t("ep.colPassed") }),
                  ]),
                ]),
                el(
                  "tbody",
                  {},
                  qaChecks.map(([nm, val, thr, ok]) =>
                    el("tr", {}, [
                      el("td", { className: "mono", text: nm }),
                      el("td", {
                        className: "num",
                        text: formatNumber(val, { maximumFractionDigits: 3 }),
                      }),
                      el("td", { className: "num", text: String(thr ?? "-") }),
                      el("td", {}, [renderStateChip(ok ? "pass" : "reject")]),
                    ])
                  )
                ),
              ]),
            ])
          : null;

      // Native 2D + 3D Studio Player when track exists (no iframe, no external link!)
      if (egoTrack) {
        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [
              { label: t("app.crumbRoot"), href: "#/tasks" },
              { label: t("data.title"), href: "#/data" },
              { label: dsId, href: `#/data/${encodeURIComponent(dsId)}` },
              { label: epParam },
            ],
            title: egoTrack.title || (epMeta && epMeta.title) || epParam,
            lead: egoTrack.task || t("ep.egoDeidNotice"),
            actions: navButtons,
          }),
          renderNativeEgoStudioPlayer(egoTrack),
          qaSection
        );
        return;
      }

      // Pipeline work-dir episode fallback (/api/poster & /api/ego_strip from .deid.mp4 only)
      const hasRealWork = dsId.startsWith("src_") || Boolean(row && row.ego_viewer);
      const posterHolder = el("div", {});
      const stripHolder = el("div", {});
      if (hasRealWork) {
        const posterUrl = `/api/poster?work=${encodeURIComponent(dsId)}&ep=${encodeURIComponent(epParam)}&w=480`;
        const stripUrl = `/api/ego_strip?work=${encodeURIComponent(dsId)}&ep=${encodeURIComponent(epParam)}&n=8`;
        posterHolder.appendChild(
          el("img", {
            className: "filmstrip",
            src: posterUrl,
            alt: epParam,
            onError: () => {
              setChildren(
                posterHolder,
                el("div", { className: "empty", text: t("error.deidMissing") })
              );
            },
          })
        );
        stripHolder.appendChild(
          el("img", {
            className: "filmstrip",
            src: stripUrl,
            alt: epParam,
            onError: () => {
              setChildren(
                stripHolder,
                el("div", { className: "empty", text: t("error.deidMissing") })
              );
            },
          })
        );
      } else {
        posterHolder.appendChild(el("div", { className: "empty", text: t("error.deidMissing") }));
        stripHolder.appendChild(el("div", { className: "empty", text: t("error.deidMissing") }));
      }

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [
            { label: t("app.crumbRoot"), href: "#/tasks" },
            { label: t("data.title"), href: "#/data" },
            { label: dsId, href: `#/data/${encodeURIComponent(dsId)}` },
            { label: epParam },
          ],
          title: (epMeta && epMeta.title) || epParam,
          lead: t("ep.egoDeidNotice"),
          actions: navButtons,
        }),
        el("div", { className: "grid" }, [
          el("section", { className: "card" }, [
            el("h2", { text: t("ep.posterTitle") }),
            posterHolder,
          ]),
          el("section", { className: "card" }, [
            el("h2", { text: t("ep.filmstripTitle") }),
            stripHolder,
          ]),
        ]),
        qaSection
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/egoflow — Native Egocentric Gallery + Pipeline Work Dirs (zero external link)
// ============================================================================
export function renderEgoflowPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("ego.title")));

  let srcFilter = "all";
  let qaFilter = "all";
  let qSearch = "";

  const load = async () => {
    try {
      const [works, rawStory, egoIdx, catDoc] = await Promise.all([
        getJSON("/api/works"),
        ensureStoryRaw(),
        ensureEgoViewerIndex(),
        ensureCatalog().catch(() => null),
      ]);
      const catRows = catDoc && Array.isArray(catDoc.rows) ? catDoc.rows : [];
      const story = scopeStoryForTask(rawStory);
      const h1m = story.h1m || null;
      const exportedEps = egoIdx.episodes || [];
      const galleryHolder = el("div", {});
      const episodesPane = el("div", {});

      const sources = Array.from(new Set(exportedEps.map((e) => e.source).filter(Boolean)));

      const redrawGallery = () => {
        if (exportedEps.length === 0) return;
        const sq = qSearch.trim().toLowerCase();
        const shown = exportedEps.filter((e) => {
          if (srcFilter !== "all" && e.source !== srcFilter) return false;
          if (qaFilter !== "all" && e.qa !== qaFilter) return false;
          if (sq) {
            const hay = `${e.title || ""} ${e.task || ""} ${(e.subtasks || []).join(" ")}`.toLowerCase();
            if (!hay.includes(sq)) return false;
          }
          return true;
        });

        setChildren(
          galleryHolder,
          el(
            "div",
            { className: "ep-card-grid" },
            shown.slice(0, 24).map((e) => {
              const dsTarget = e.source === "Team tray" ? "h1m-team" : "h1m-egodex";
              const poster = safeThumbUrl(e.poster);
              return el(
                "a",
                {
                  className: "ep-visual-card",
                  href: `#/data/${dsTarget}/ep/${encodeURIComponent(e.id)}`,
                },
                [
                  poster
                    ? el("img", { src: poster, alt: e.title || e.id, loading: "lazy" })
                    : el("div", { className: "thumb" }, [el("span", { text: e.id })]),
                  el("div", { className: "ep-visual-body" }, [
                    el("div", { className: "ep-visual-title", text: e.title || e.id }),
                    el("div", { className: "tag-row" }, [
                      el("span", { className: cls("mini-tag", "mono"), text: e.source || "-" }),
                      e.seconds != null
                        ? el("span", {
                            className: cls("mini-tag", "mono"),
                            text: `${formatNumber(e.seconds, { maximumFractionDigits: 1 })} s`,
                          })
                        : null,
                      e.hands != null
                        ? el("span", {
                            className: cls("mini-tag", "mono"),
                            text: t("ego.handsChip", { pct: formatPercent(e.hands) }),
                          })
                        : null,
                      e.qa ? renderStateChip(e.qa) : null,
                    ]),
                  ]),
                ]
              );
            })
          )
        );
      };

      const showWorkEpisodes = async (workName, workObj = null) => {
        const eps = await getJSON(`/api/work_episodes?work=${encodeURIComponent(workName)}`);
        const humanTitle = friendlyBatchTitle(
          workName,
          workObj ? workObj.source_detail : "",
          catRows
        );
        setChildren(
          episodesPane,
          el("section", { className: "card" }, [
            el("div", { className: "task-head" }, [
              el("h2", { text: humanTitle }),
              el("span", {
                className: cls("short-hash", "mono"),
                title: workName,
                text: shortHashId(workName),
              }),
            ]),
            el(
              "div",
              { className: "grid-3", style: "margin-top:10px" },
              (eps || []).slice(0, 12).map((ep) => {
                const stripBox = el("div", {});
                if (ep.deid) {
                  stripBox.appendChild(
                    el("img", {
                      className: "filmstrip",
                      src: `/api/ego_strip?work=${encodeURIComponent(workName)}&ep=${encodeURIComponent(ep.episode_id)}&n=6`,
                      alt: ep.episode_id,
                      loading: "lazy",
                      onError: () => {
                        setChildren(
                          stripBox,
                          el("div", { className: "empty", text: t("ego.deidPending") })
                        );
                      },
                    })
                  );
                } else {
                  stripBox.appendChild(
                    el("div", { className: "empty", text: t("ego.deidPending") })
                  );
                }
                return el("div", { className: "meta-box" }, [
                  el("div", { className: "task-head" }, [
                    el(
                      "a",
                      {
                        className: cls("link", "mono"),
                        href: `#/data/${encodeURIComponent(workName)}/ep/${encodeURIComponent(ep.episode_id)}`,
                      },
                      [ep.episode_id]
                    ),
                    renderStateChip(ep.qa || (ep.deid ? "done" : "waiting")),
                  ]),
                  el("small", {
                    text: `${ep.deid ? t("ego.deidReady") : t("ego.deidPending")} · ${t("ego.framesUnit", { count: formatNumber(ep.frames) })}`,
                  }),
                  stripBox,
                ]);
              })
            ),
          ])
        );
      };

      const tierIds = ["ingest", "deid", "ea", "pose", "annotate", "qa", "report"];
      const workList = Array.isArray(works) ? works : [];

      const conveyorNode =
        workList.length > 0
          ? el("div", {}, [
              el("div", { className: "sect" }, [el("h2", { text: t("ego.conveyorTitle") })]),
              el(
                "div",
                { className: "conveyor-grid" },
                tierIds.map((tid, idx) => {
                  let doneN = 0;
                  for (const w of workList) {
                    const tr = (w.tiers || []).find((x) => x.id === tid);
                    if (tr && (tr.state === "done" || tr.state === "pass" || tr.state === "ok")) {
                      doneN += 1;
                    }
                  }
                  const pct = (doneN / Math.max(1, workList.length)) * 100;
                  const lbl = hasI18nKey("ego.tier." + tid) ? t("ego.tier." + tid) : tid;
                  return el("div", { className: "conveyor-step" }, [
                    el("div", { className: "task-head" }, [
                      el("span", { className: "conveyor-step-num", text: `0${idx + 1}` }),
                      el("span", {
                        className: cls("tiny", "mono"),
                        text: `${doneN}/${workList.length}`,
                      }),
                    ]),
                    el("b", { text: lbl }),
                    el("div", { className: "conveyor-mini-bar" }, [
                      el("span", { style: `width:${pct.toFixed(0)}%` }),
                    ]),
                  ]);
                })
              ),
            ])
          : null;

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("ego.title") }],
          title: t("ego.title"),
          actions: !state.locked
            ? [
                el("a", { className: cls("btn", "primary"), href: "#/jobs?panel=import" }, [
                  t("nav.item.import"),
                ]),
              ]
            : [],
        }),

        h1m
          ? renderStatStrip([
              {
                label: t("ego.h1mClips"),
                value: formatNumber(h1m.clips),
                sub: `${t("ego.h1mExported")}: ${formatNumber(h1m.exported)}`,
              },
              {
                label: t("ego.h1mHours"),
                value: formatNumber(h1m.exported_hours, { maximumFractionDigits: 2 }),
                sub: "30 fps",
              },
              {
                label: t("ego.h1mHands"),
                value: formatPercent(h1m.exported_hands_visible_ge_95),
                sub: "21×2 joints",
              },
            ])
          : null,

        conveyorNode,

        workList.length === 0
          ? el("div", { className: "empty", text: t("state.empty") })
          : el("section", { className: "card" }, [
              el("h2", { text: t("ego.batchesCompactTitle") }),
              el(
                "div",
                { style: "margin-top:8px" },
                workList.map((w) => {
                  const humanTitle = friendlyBatchTitle(w.name, w.source_detail, catRows);
                  return el("div", { className: "batch-row" }, [
                    el("div", {}, [
                      el(
                        "button",
                        {
                          type: "button",
                          className: "link",
                          onClick: () => showWorkEpisodes(w.name, w),
                        },
                        [humanTitle]
                      ),
                      el("div", { className: "tag-row", style: "margin-top:3px" }, [
                        el("span", {
                          className: cls("short-hash", "mono"),
                          title: w.name,
                          text: shortHashId(w.name),
                        }),
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `${formatNumber(w.episodes)} ep`,
                        }),
                      ]),
                    ]),
                    el(
                      "div",
                      { className: "seg7-track" },
                      tierIds.map((tid, idx) => {
                        const tr = (w.tiers || []).find((x) => x.id === tid) || {};
                        const st = String(tr.state || "idle").toLowerCase();
                        const isDone = st === "done" || st === "pass" || st === "ok";
                        const isWarn = st === "waiting" || st === "running" || st === "flag";
                        const tierTitle = hasI18nKey("ego.tier." + tid)
                          ? t("ego.tier." + tid)
                          : tid;
                        const tipMetric =
                          tr.result ||
                          tr.note ||
                          (tr.total != null ? `${tr.n ?? 0}/${tr.total}` : formatStateLabel(st));
                        return el("div", {
                          className: cls("seg7-cell", "mono", isDone && "done", isWarn && "warn"),
                          title: `0${idx + 1} ${tierTitle}: ${tipMetric}`,
                          text: `0${idx + 1}`,
                        });
                      })
                    ),
                    el(
                      "button",
                      {
                        type: "button",
                        className: "topbtn",
                        onClick: () => showWorkEpisodes(w.name, w),
                      },
                      [t("common.open")]
                    ),
                  ]);
                })
              ),
            ]),

        episodesPane,

        exportedEps.length > 0
          ? el("div", {}, [
              el("div", { className: "sect" }, [el("h2", { text: t("ego.galleryTitle") })]),
              exportedEps.some((e) => e.qa === "flag")
                ? el("p", { className: cls("tiny", "ego-flag-legend") }, [
                    renderStateChip("flag"),
                    el("span", { text: t("ego.flagLegend") }),
                  ])
                : null,
              el("div", { className: "toolbar" }, [
                el("input", {
                  type: "search",
                  className: cls("field", "search"),
                  "aria-label": t("ds.searchEpPlaceholder"),
                  placeholder: t("ds.searchEpPlaceholder"),
                  onInput: (ev) => {
                    qSearch = ev.target.value;
                    redrawGallery();
                  },
                }),
                el(
                  "select",
                  {
                    className: "field",
                    "aria-label": t("ego.filterSourceLabel"),
                    onChange: (ev) => {
                      srcFilter = ev.target.value;
                      redrawGallery();
                    },
                  },
                  [
                    el("option", { value: "all", text: t("common.all") }),
                    ...sources.map((s) => el("option", { value: s, text: s })),
                  ]
                ),
                el(
                  "select",
                  {
                    className: "field",
                    "aria-label": t("ds.filterQaAll"),
                    onChange: (ev) => {
                      qaFilter = ev.target.value;
                      redrawGallery();
                    },
                  },
                  [
                    el("option", { value: "all", text: t("ds.filterQaAll") }),
                    el("option", { value: "pass", text: formatStateLabel("pass") }),
                    el("option", { value: "flag", text: formatStateLabel("flag") }),
                  ]
                ),
              ]),
              galleryHolder,
            ])
          : null
      );

      redrawGallery();
      if (workList[0]) {
        showWorkEpisodes(workList[0].name, workList[0]);
      }
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

// ============================================================================
// #/sim & #/sim/:i — Simulation Library & Episode Detail
// ============================================================================
const simBrowseByTask = new Map();

export function renderSimLibraryPage() {
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(t("sim.title")));

  // Browse state per task and round: rounds grant different sim keys (cut vs rollouts).
  const scope = `${state.taskId}:${state.roundId || ""}`;
  const saved = simBrowseByTask.get(scope) || {};
  let activeMode = saved.activeMode || null;
  let page = saved.page || 1;
  let lvFilter = saved.lvFilter || "all";
  let clusterFilter = saved.clusterFilter || "all";
  let mediaFilter = saved.mediaFilter || null;
  let rPage = saved.rPage || 1;
  let rLvFilter = saved.rLvFilter || "all";
  let rOutFilter = saved.rOutFilter || "all";
  let rSeedQuery = saved.rSeedQuery || "";
  const pageSize = typeof window !== "undefined" && window.innerWidth < 600 ? 8 : 24;

  const load = async () => {
    try {
      const [rawSim, rawStory] = await Promise.all([
        ensureSimRaw(),
        ensureStoryRaw().catch(() => null),
      ]);
      const sim = scopeSimForTask(rawSim);
      const scopedStory = rawStory ? scopeStoryForTask(rawStory) : {};
      // The rollout viewer needs only `story.jig`; the cut tab needs `sim`. A round may
      // grant either one, both or neither (design audit P0-2).
      const jig = hasIndexAccess("story.jig") && scopedStory.jig ? scopedStory.jig : null;
      const rollouts = jig && Array.isArray(jig.rollouts) ? jig.rollouts : [];
      const stepNames = jig && Array.isArray(jig.steps) ? jig.steps : taskStageIds();
      const hasCut = !sim.simLockedByScope;

      const episodes = Array.isArray(sim.episodes) ? sim.episodes : [];
      const mediaEpisodes = episodes.filter((e) => Boolean(e.video || e.poster));
      const teleop = Array.isArray(sim.teleop) ? sim.teleop : [];

      if (!activeMode || (activeMode === "rollouts" && rollouts.length === 0) || (activeMode === "cut" && !hasCut)) {
        activeMode = rollouts.length > 0 ? "rollouts" : "cut";
      }
      if (!mediaFilter) {
        mediaFilter = mediaEpisodes.length > 0 ? "media" : "all";
      }

      const saveState = () => {
        const prev = simBrowseByTask.get(scope) || {};
        simBrowseByTask.set(scope, {
          ...prev,
          activeMode,
          page,
          lvFilter,
          clusterFilter,
          mediaFilter,
          rPage,
          rLvFilter,
          rOutFilter,
          rSeedQuery,
        });
      };

      const modeHolder = el("div", {});
      const levels = Array.from(new Set(episodes.map((e) => e.level).filter((v) => v != null)));
      const clusters = Array.from(new Set(episodes.map((e) => e.cluster).filter(Boolean)));
      const rLevels = Array.from(new Set(rollouts.map((r) => r.level).filter((v) => v != null)));
      const failCounts = new Map();
      let okTotal = 0;
      let failTotal = 0;
      for (const r of rollouts) {
        if (r.success) {
          okTotal += 1;
        } else {
          failTotal += 1;
          if (r.failure) {
            failCounts.set(r.failure, (failCounts.get(r.failure) || 0) + 1);
          }
        }
      }

      const renderPager = (curPage, totalPages, totalItems, onStep) =>
        el("nav", { className: "sim-pager", "aria-label": t("sim.title") }, [
          el("button", {
            type: "button",
            className: "btn",
            disabled: curPage <= 1,
            text: t("analysis.prev"),
            onClick: () => onStep(curPage - 1),
          }),
          el("span", {
            text: t("analysis.page", {
              page: curPage,
              pages: totalPages,
              total: formatNumber(totalItems),
            }),
          }),
          el("button", {
            type: "button",
            className: "btn",
            disabled: curPage >= totalPages,
            text: t("analysis.next"),
            onClick: () => onStep(curPage + 1),
          }),
        ]);

      const redrawMode = () => {
        saveState();
        if (activeMode === "rollouts" && rollouts.length > 0) {
          const gridHolder = el("div", {});
          const redrawRollouts = () => {
            const q = rSeedQuery.trim().toLowerCase();
            const filtered = rollouts.filter((r) => {
              if (rLvFilter !== "all" && String(r.level) !== rLvFilter) return false;
              if (rOutFilter === "ok" && !r.success) return false;
              if (rOutFilter === "fail" && r.success) return false;
              if (
                rOutFilter !== "all" &&
                rOutFilter !== "ok" &&
                rOutFilter !== "fail" &&
                String(r.failure || "") !== rOutFilter
              ) {
                return false;
              }
              if (q && !String(r.seed ?? "").toLowerCase().includes(q) && !String(r.ep ?? "").toLowerCase().includes(q)) {
                return false;
              }
              return true;
            });

            const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
            rPage = Math.min(rPage, pages);
            saveState();
            const start = (rPage - 1) * pageSize;

            if (filtered.length === 0) {
              setChildren(gridHolder, el("div", { className: "empty", text: t("state.empty") }));
              return;
            }

            const stepTo = (nextP) => {
              rPage = nextP;
              redrawRollouts();
            };

            setChildren(
              gridHolder,
              renderPager(rPage, pages, filtered.length, stepTo),
              el(
                "div",
                { className: "rollout-card-grid" },
                filtered.slice(start, start + pageSize).map((r) => {
                  const stepsArr = Array.isArray(r.steps) ? r.steps : [];
                  const latchArr = Array.isArray(r.latch_t) ? r.latch_t : [];
                  return el(
                    "article",
                    { className: cls("rollout-card", r.success ? "is-ok" : "is-fail") },
                    [
                      el(
                        "div",
                        { style: "display:flex;align-items:center;gap:6px;flex-wrap:wrap" },
                        [
                          el("b", { className: "mono", text: r.ep || `#${r.i}` }),
                          el("span", {
                            className: cls("mini-tag", "mono"),
                            text: `#${r.repeat ?? 0}`,
                          }),
                          el("span", { className: "grow" }),
                          // W1: a successful rollout reads "thành công", not "đạt".
                          el("span", {
                            className: cls("chip", !r.success && "danger"),
                            text: t(r.success ? "exp.rolloutSuccess" : "exp.rolloutFail"),
                          }),
                        ]
                      ),
                      el("div", { className: "tag-row" }, [
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `L${r.level ?? "-"}`,
                        }),
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `seed:${r.seed ?? "-"}`,
                        }),
                        r.failure
                          ? el("span", {
                              className: cls("chip", "danger"),
                              title: r.failure,
                              text: failureLabel(r.failure),
                            })
                          : null,
                      ]),
                      el("div", { className: "tag-row" }, [
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `Δxy ${r.dist_cm != null ? `${formatNumber(r.dist_cm, { maximumFractionDigits: 1 })} cm` : "-"}`,
                        }),
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `Δyaw ${r.yaw_deg != null ? `${formatNumber(r.yaw_deg, { maximumFractionDigits: 1 })}°` : "-"}`,
                        }),
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `t ${r.sim_s != null ? `${formatNumber(r.sim_s, { maximumFractionDigits: 1 })} s` : "-"}`,
                        }),
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `z ${r.tray_z != null ? `${formatNumber(r.tray_z, { maximumFractionDigits: 2 })} m` : "-"}`,
                        }),
                      ]),
                      el("div", {}, [
                        el("div", {
                          className: "tiny",
                          style: "margin-bottom:3px",
                          text: t("exp.rolloutStepTimeline"),
                        }),
                        el(
                          "div",
                          { className: "latch-strip" },
                          Array.from({ length: 7 }, (_, idx) => {
                            const ok = stepsArr[idx] === true;
                            const failed = stepsArr[idx] === false;
                            const lt = latchArr[idx];
                            const sName = stepNames[idx] ? stageLabel(stepNames[idx]) : String(idx + 1);
                            return el(
                              "div",
                              {
                                className: cls("latch-cell", ok && "pass", failed && "fail"),
                                title: `${idx + 1}. ${sName}: ${lt != null ? `${formatNumber(lt, { maximumFractionDigits: 2 })} s` : "-"}`,
                              },
                              [
                                el("div", { className: "mono", text: String(idx + 1) }),
                                el("div", {
                                  className: "mono",
                                  text:
                                    lt != null
                                      ? `${formatNumber(lt, { maximumFractionDigits: 1 })}s`
                                      : ok
                                        ? "✓"
                                        : "✕",
                                }),
                              ]
                            );
                          })
                        ),
                      ]),
                      el(
                        "div",
                        { style: "display:flex;justify-content:flex-end;margin-top:auto" },
                        [
                          el(
                            "a",
                            {
                              className: "link",
                              href: `#/follow?level=${encodeURIComponent(r.level ?? "")}&seed=${encodeURIComponent(r.seed ?? "")}`,
                            },
                            [t("exp.inspectSeedLink")]
                          ),
                        ]
                      ),
                    ]
                  );
                })
              ),
              pages > 1 ? renderPager(rPage, pages, filtered.length, stepTo) : null
            );
          };

          // Descriptive outcome row of the shown run, and its results.json Wilson when ready.
          const jigOutcomes = jig && Array.isArray(jig.outcomes) ? jig.outcomes : [];
          const latestRun =
            jigOutcomes.find((o) => jig && o.run === jig.featured) ||
            jigOutcomes[jigOutcomes.length - 1] ||
            null;
          const latestEval =
            latestRun && Array.isArray(jig.evals)
              ? jig.evals.find((e) => e.run === latestRun.run && e.status === "ready") || null
              : null;
          const latestWilson =
            latestEval && latestEval.headline ? latestEval.headline.wilson : null;

          setChildren(
            modeHolder,
            renderStatStrip([
              {
                label: t("eval.colSuccN"),
                value: `${formatNumber(okTotal)} / ${formatNumber(rollouts.length)}`,
                sub: latestRun ? `${latestRun.run} · ${latestRun.eval_id}` : "",
              },
              {
                label: t("eval.colRate"),
                value: rollouts.length ? formatPercent(okTotal / rollouts.length) : t("state.na"),
                sub: Array.isArray(latestWilson)
                  ? `${t("exp.wilsonDescr")} ${formatPercent(latestWilson[0])}–${formatPercent(latestWilson[1])}`
                  : "",
              },
              {
                label: t("common.source"),
                value: latestRun ? latestRun.eval_id : t("state.na"),
                sub: latestRun ? scrubPath(latestRun.source || "") : "",
              },
            ]),
            el("div", { className: "toolbar", style: "margin-top:12px" }, [
              el(
                "select",
                {
                  className: "field",
                  "aria-label": t("sim.filterLevelAll"),
                  onChange: (ev) => {
                    rPage = 1;
                    rLvFilter = ev.target.value;
                    redrawRollouts();
                  },
                },
                [
                  el("option", { value: "all", text: t("sim.filterLevelAll") }),
                  ...rLevels.map((lv) =>
                    el("option", {
                      value: String(lv),
                      selected: String(lv) === rLvFilter,
                      text: t("sim.levelItem", { lv }),
                    })
                  ),
                ]
              ),
              el(
                "select",
                {
                  className: "field",
                  "aria-label": t("exp.filterOutcomeAll"),
                  onChange: (ev) => {
                    rPage = 1;
                    rOutFilter = ev.target.value;
                    redrawRollouts();
                  },
                },
                [
                  el("option", {
                    value: "all",
                    selected: rOutFilter === "all",
                    text: t("exp.filterOutcomeAll"),
                  }),
                  el("option", {
                    value: "ok",
                    selected: rOutFilter === "ok",
                    text: t("exp.filterOutcomeOk", { count: formatNumber(okTotal) }),
                  }),
                  el("option", {
                    value: "fail",
                    selected: rOutFilter === "fail",
                    text: t("exp.filterOutcomeFail", { count: formatNumber(failTotal) }),
                  }),
                  ...Array.from(failCounts.entries()).map(([code, cnt]) =>
                    el("option", {
                      value: code,
                      selected: rOutFilter === code,
                      text: `${failureLabel(code)} (${formatNumber(cnt)})`,
                    })
                  ),
                ]
              ),
              el("input", {
                type: "search",
                className: "field",
                value: rSeedQuery,
                "aria-label": t("exp.searchSeedPlaceholder"),
                placeholder: t("exp.searchSeedPlaceholder"),
                onInput: (ev) => {
                  rPage = 1;
                  rSeedQuery = ev.target.value || "";
                  redrawRollouts();
                },
              }),
            ]),
            renderStepLegend(stepNames),
            gridHolder
          );
          redrawRollouts();
          return;
        }

        // Cut media / episodes mode
        const gridHolder = el("div", {});
        const redrawCut = () => {
          const filtered = episodes.filter((e) => {
            if (mediaFilter === "media" && !e.video && !e.poster) return false;
            if (lvFilter !== "all" && String(e.level) !== lvFilter) return false;
            if (clusterFilter !== "all" && String(e.cluster) !== clusterFilter) return false;
            return true;
          });

          const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
          page = Math.min(page, pages);
          saveState();
          const start = (page - 1) * pageSize;

          const focusPage = () => {
            const link = gridHolder.querySelector(".ep-visual-card");
            if (link) link.focus();
          };
          const stepTo = (nextP) => {
            page = nextP;
            redrawCut();
            focusPage();
          };

          if (filtered.length === 0) {
            setChildren(gridHolder, el("div", { className: "empty", text: t("state.empty") }));
            return;
          }

          setChildren(
            gridHolder,
            renderPager(page, pages, filtered.length, stepTo),
            el(
              "div",
              { className: "ep-card-grid" },
              filtered.slice(start, start + pageSize).map((ep) => {
                const epSteps = Array.isArray(ep.steps) ? ep.steps : [];
                const passCnt = epSteps.filter(Boolean).length;
                return el(
                  "a",
                  {
                    className: "ep-visual-card",
                    href: `#/sim/${encodeURIComponent(ep.i)}`,
                    "data-episode": String(ep.i),
                    onClick: () => {
                      const st = simBrowseByTask.get(scope) || {};
                      st.returnEpisode = String(ep.i);
                      simBrowseByTask.set(scope, st);
                    },
                  },
                  [
                    ep.poster
                      ? el("img", {
                          src: `/simmedia/${ep.poster}`,
                          alt: `#${ep.i}`,
                          loading: "lazy",
                          onError: (ev) => {
                            ev.target.hidden = true;
                          },
                        })
                      : el("div", { className: "thumb" }, [
                          el("span", { className: "mono", text: `#${ep.i}` }),
                        ]),
                    el("div", { className: "ep-visual-body" }, [
                      el("div", {
                        style: "display:flex;justify-content:space-between;align-items:center",
                      }, [
                        el("div", { className: cls("ep-visual-title", "mono"), text: `#${ep.i}` }),
                        epSteps.length > 0
                          ? el("span", {
                              className: cls("mini-tag", "mono"),
                              text: `${passCnt}/${epSteps.length}`,
                            })
                          : null,
                      ]),
                      el("div", { className: "tag-row" }, [
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `L${ep.level ?? "-"}`,
                        }),
                        el("span", {
                          className: cls("mini-tag", "mono"),
                          text: `seed:${ep.seed ?? "-"}`,
                        }),
                        ep.cluster
                          ? el("span", { className: cls("mini-tag", "mono"), text: ep.cluster })
                          : ep.purpose
                            ? el("span", { className: cls("mini-tag", "mono"), text: ep.purpose })
                            : null,
                      ]),
                    ]),
                  ]
                );
              })
            ),
            pages > 1 ? renderPager(page, pages, filtered.length, stepTo) : null
          );
        };

        setChildren(
          modeHolder,
          renderStatStrip([
            {
              label: t("common.source"),
              value: sim.sha8 || t("state.na"),
              sub: scrubPath(sim.source || ""),
            },
            {
              label: t("data.colEpisodes"),
              value: `${formatNumber(mediaEpisodes.length)} / ${formatNumber(episodes.length)}`,
              sub: sim.format || "",
            },
            {
              label: t("sim.batchQaPass"),
              value: formatNumber(sim.batch && sim.batch.qa_pass),
              sub: t("sim.batchAttempts", { count: formatNumber(sim.batch && sim.batch.attempts) }),
            },
          ]),
          episodes.length > 0
            ? el("div", { className: "toolbar", style: "margin-top:12px" }, [
                mediaEpisodes.length > 0
                  ? el(
                      "select",
                      {
                        className: "field",
                        "aria-label": t("exp.mediaFilterLabel"),
                        onChange: (ev) => {
                          page = 1;
                          mediaFilter = ev.target.value;
                          redrawCut();
                        },
                      },
                      [
                        el("option", {
                          value: "media",
                          selected: mediaFilter === "media",
                          text: t("exp.mediaOnlyOpt", { count: formatNumber(mediaEpisodes.length) }),
                        }),
                        el("option", {
                          value: "all",
                          selected: mediaFilter === "all",
                          text: t("exp.allCutEpsOpt", { count: formatNumber(episodes.length) }),
                        }),
                      ]
                    )
                  : null,
                el(
                  "select",
                  {
                    className: "field",
                    "aria-label": t("sim.filterLevelAll"),
                    onChange: (ev) => {
                      page = 1;
                      lvFilter = ev.target.value;
                      redrawCut();
                    },
                  },
                  [
                    el("option", { value: "all", text: t("sim.filterLevelAll") }),
                    ...levels.map((lv) =>
                      el("option", {
                        value: String(lv),
                        selected: String(lv) === lvFilter,
                        text: t("sim.levelItem", { lv }),
                      })
                    ),
                  ]
                ),
                el(
                  "select",
                  {
                    className: "field",
                    "aria-label": t("sim.filterClusterAll"),
                    onChange: (ev) => {
                      page = 1;
                      clusterFilter = ev.target.value;
                      redrawCut();
                    },
                  },
                  [
                    el("option", { value: "all", text: t("sim.filterClusterAll") }),
                    ...clusters.map((c) =>
                      el("option", { value: c, selected: c === clusterFilter, text: c })
                    ),
                  ]
                ),
              ])
            : null,
          gridHolder
        );
        redrawCut();
        if (saved.returnEpisode != null) {
          requestAnimationFrame(() =>
            gridHolder
              .querySelector(`[data-episode="${CSS.escape(saved.returnEpisode)}"]`)
              ?.focus()
          );
        }
      };

      const renderTabsBar = () => {
        if (!hasCut || rollouts.length === 0) return null;
        return el("div", { className: "tabs", role: "tablist", style: "margin-bottom:12px" }, [
          el(
            "button",
            {
              type: "button",
              role: "tab",
              className: cls("tab", activeMode === "rollouts" && "active"),
              "aria-selected": String(activeMode === "rollouts"),
              onClick: () => {
                activeMode = "rollouts";
                redrawAll();
              },
            },
            [t("exp.simTabRollouts", { count: formatNumber(rollouts.length) })]
          ),
          el(
            "button",
            {
              type: "button",
              role: "tab",
              className: cls("tab", activeMode === "cut" && "active"),
              "aria-selected": String(activeMode === "cut"),
              onClick: () => {
                activeMode = "cut";
                redrawAll();
              },
            },
            [
              t("exp.simTabCutMedia", {
                mediaCount: formatNumber(mediaEpisodes.length),
                total: formatNumber(episodes.length),
              }),
            ]
          ),
        ]);
      };

      const tabsSlot = el("div", {});
      const redrawAll = () => {
        setChildren(tabsSlot, renderTabsBar());
        if (hasCut || rollouts.length > 0) redrawMode();
      };

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [{ label: t("app.crumbRoot"), href: "#/tasks" }, { label: t("sim.title") }],
          title: t("sim.title"),
        }),
        tabsSlot,
        hasCut || rollouts.length > 0
          ? modeHolder
          : renderRoundEmpty({
              keys: ["sim", "story.jig"],
              text: roundsWithIndex(["sim", "story.jig"]).length > 0 ? null : t("sim.teleopOnlyNotice"),
            }),
        teleop.length > 0
          ? el("section", { className: "card" }, [
              el("h2", { text: t("sim.teleopSection") }),
              el(
                "div",
                { className: "grid-3", style: "margin-top:10px" },
                teleop.map((tp) =>
                  el("div", { className: "meta-box" }, [
                    el("b", { className: "mono", text: `#${tp.i} · ${tp.task}` }),
                    tp.video
                      ? el("video", {
                          className: "video-player",
                          controls: true,
                          preload: "metadata",
                          poster: tp.poster ? `/simmedia/${tp.poster}` : null,
                          src: `/simmedia/${tp.video}`,
                        })
                      : null,
                  ])
                )
              ),
            ])
          : null
      );

      redrawAll();
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}

export function renderSimDetailPage(ctx) {
  const simId = ctx.params.i;
  const wrap = el("div", {});
  wrap.appendChild(renderLoadingView(`#${simId}`));

  const fmtPose = (pose) => {
    if (!pose || typeof pose !== "object") return "-";
    const x = pose.x != null ? formatNumber(pose.x, { maximumFractionDigits: 2 }) : "-";
    const y = pose.y != null ? formatNumber(pose.y, { maximumFractionDigits: 2 }) : "-";
    const yaw = pose.yaw != null ? formatNumber(pose.yaw, { maximumFractionDigits: 2 }) : "-";
    // " · " between parts: vi numbers already use a comma as the decimal mark (A19).
    return `x ${x} · y ${y} · yaw ${yaw}`;
  };

  const load = async () => {
    try {
      const rawSim = await ensureSimRaw();
      const sim = scopeSimForTask(rawSim);
      const episodes = Array.isArray(sim.episodes) ? sim.episodes : [];
      const ep = !sim.simLockedByScope
        ? episodes.find((e) => String(e.i) === String(simId))
        : null;

      if (!ep) {
        setChildren(
          wrap,
          ...renderCrumbHeading({
            crumbs: [
              { label: t("app.crumbRoot"), href: "#/tasks" },
              { label: t("sim.title"), href: "#/sim" },
              { label: `#${simId}` },
            ],
            title: `#${simId}`,
          }),
          el("div", { className: "empty" }, [
            el("p", { text: t("sim.detailNotFound", { id: simId }) }),
            el("a", { className: cls("btn", "primary"), href: "#/sim" }, [t("sim.detailBack")]),
          ])
        );
        return;
      }

      const navPool = ep.video || ep.poster
        ? episodes.filter((e) => Boolean(e.video || e.poster))
        : episodes;
      const curIdx = navPool.findIndex((e) => String(e.i) === String(ep.i));
      const prevEp = curIdx > 0 ? navPool[curIdx - 1] : null;
      const nextEp = curIdx >= 0 && curIdx < navPool.length - 1 ? navPool[curIdx + 1] : null;
      const epSteps = Array.isArray(ep.steps) ? ep.steps : [];
      const stageIds = taskStageIds();

      setChildren(
        wrap,
        ...renderCrumbHeading({
          crumbs: [
            { label: t("app.crumbRoot"), href: "#/tasks" },
            { label: t("sim.title"), href: "#/sim" },
            { label: `#${ep.i}` },
          ],
          title: `${t("ds.colEp")} #${ep.i}`,
          lead: `L${ep.level ?? "-"} · seed:${ep.seed ?? "-"}${ep.cluster ? ` · ${ep.cluster}` : ep.purpose ? ` · ${ep.purpose}` : ""}`,
          actions: [
            prevEp
              ? el("a", { className: "btn", href: `#/sim/${encodeURIComponent(prevEp.i)}` }, [
                  `${t("analysis.prev")} (#${prevEp.i})`,
                ])
              : null,
            nextEp
              ? el("a", { className: "btn", href: `#/sim/${encodeURIComponent(nextEp.i)}` }, [
                  `${t("analysis.next")} (#${nextEp.i})`,
                ])
              : null,
            el("a", { className: cls("btn", "primary"), href: "#/sim" }, [t("sim.detailBack")]),
          ].filter(Boolean),
        }),
        el("section", { className: "card" }, [
          ep.video
            ? el("video", {
                className: "video-player",
                controls: true,
                poster: ep.poster ? `/simmedia/${ep.poster}` : null,
                src: `/simmedia/${ep.video}`,
              })
            : el("div", { className: "empty", text: t("error.mediaMissing") }),
          el("details", { className: "studio-details" }, [
            el("summary", { text: t("common.source") }),
            el("code", { text: `${scrubPath(sim.source || "-")} (${sim.sha8 || "-"})` }),
          ]),
        ]),
        el("section", { className: "card" }, [
          el("h2", { text: t("exp.simGeometryTitle") }),
          el("div", { className: "meta-strip", style: "margin-top:10px" }, [
            el("div", { className: "meta-box" }, [
              el("span", { text: t("exp.colFrames") }),
              el("b", { className: "mono", text: formatNumber(ep.len) }),
            ]),
            el("div", { className: "meta-box" }, [
              el("span", { text: t("exp.poseSpawn") }),
              el("b", { className: "mono", text: fmtPose(ep.spawn) }),
            ]),
            el("div", { className: "meta-box" }, [
              el("span", { text: t("exp.poseTray") }),
              el("b", { className: "mono", text: fmtPose(ep.tray) }),
            ]),
            el("div", { className: "meta-box" }, [
              el("span", { text: t("exp.poseTarget") }),
              el("b", { className: "mono", text: fmtPose(ep.target) }),
            ]),
          ]),
          epSteps.length > 0
            ? el(
                "ol",
                { className: "sim-step-list", "aria-label": t("exp.simStepsTitle") },
                epSteps.map((ok, idx) => {
                  const sid = stageIds[idx];
                  return el(
                    "li",
                    { className: cls("latch-cell", ok ? "pass" : "fail"), title: sid || null },
                    [
                      el("span", { className: "mono", text: `${idx + 1}` }),
                      el("span", { text: sid ? stageLabel(sid) : t("state.na") }),
                      el("span", { "aria-hidden": "true", text: ok ? "✓" : "✕" }),
                    ]
                  );
                })
              )
            : null,
        ])
      );
    } catch (err) {
      setChildren(wrap, renderErrorBlock(err, load));
    }
  };

  load();
  return wrap;
}
