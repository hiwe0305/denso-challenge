/* Egocentric Explorer: gallery, episode, quality, all clips. Plain script (works on file://). */
(function () {
  "use strict";
  var INDEX = window.H1M_INDEX || { episodes: [], summary: {}, status: [] };
  var BONES = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[0,9],[9,10],[10,11],[11,12],
               [0,13],[13,14],[14,15],[15,16],[0,17],[17,18],[18,19],[19,20],[5,9],[9,13],[13,17]];
  var app = document.getElementById("app");
  var cleanup = [];

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return node;
  }
  function pct(x) { return x == null ? "–" : (100 * x).toFixed(1) + " %"; }
  function num(x, d) { return x == null ? "–" : Number(x).toFixed(d == null ? 2 : d); }
  function secs(x) { return x == null ? "–" : Number(x).toFixed(2) + " s"; }
  function qaTag(q) { return el("span", { "class": "tag " + (q || ""), text: "QA " + (q || "none") }); }

  /* ---------- gallery ---------- */
  var state = { q: "", source: "all", qa: "all" };
  function matches(e) {
    if (state.source !== "all" && e.source !== state.source) return false;
    if (state.qa !== "all" && e.qa !== state.qa) return false;
    if (!state.q) return true;
    var hay = (e.title + " " + e.task + " " + e.subtasks.join(" ") + " " + e.source).toLowerCase();
    return state.q.toLowerCase().split(/\s+/).filter(Boolean).every(function (w) { return hay.indexOf(w) >= 0; });
  }
  function gallery() {
    var sources = ["all"].concat(Array.from(new Set(INDEX.episodes.map(function (e) { return e.source; }))));
    var grid = el("div", { "class": "grid" });
    var count = el("span", { "class": "count" });
    function draw() {
      grid.innerHTML = "";
      var shown = INDEX.episodes.filter(matches);
      count.textContent = shown.length + " of " + INDEX.episodes.length + " episodes";
      shown.forEach(function (e) {
        grid.appendChild(el("a", { "class": "card", href: "#/ep/" + e.id }, [
          el("img", { src: e.poster, alt: e.title, loading: "lazy" }),
          el("div", { "class": "body" }, [
            el("div", { "class": "t", text: e.title }),
            el("div", { "class": "d", text: e.task }),
            el("div", { "class": "tags" }, [
              el("span", { "class": "tag", text: e.source }),
              el("span", { "class": "tag", text: e.seconds.toFixed(1) + " s" }),
              el("span", { "class": "tag" + (e.hands != null && e.hands < 0.95 ? " flag" : ""), text: "hands " + pct(e.hands) }),
              qaTag(e.qa)
            ])
          ])
        ]));
      });
    }
    function chips(values, key) {
      return values.map(function (v) {
        return el("button", { "class": "chip" + (state[key] === v ? " on" : ""), text: v === "all" ? "All" : v,
          onclick: function () { state[key] = v; render(); } });
      });
    }
    var search = el("input", { type: "search", placeholder: "Search tasks and subtasks, e.g. \"tray left hand\", \"stack cups\"", value: state.q,
      oninput: function () { state.q = search.value; draw(); } });
    var s = INDEX.summary.all || {};
    app.appendChild(el("h1", { text: "Gallery" }));
    app.appendChild(el("p", { "class": "lede", text: (s.exported || 0) + " exported episodes (" + num((s.exported_hours || 0) * 60, 1) +
      " min) of " + (s.clips || 0) + " clips. Each episode has a task sentence, timed subtasks that name the hand, 21-joint hands per frame, masks and confidence. Select one to play it with its hand tracks." }));
    app.appendChild(el("div", { "class": "controls" }, [search].concat(chips(sources, "source")).concat(chips(["all", "pass", "flag"], "qa")).concat([count])));
    app.appendChild(grid);
    draw();
    search.focus();
  }

  /* ---------- episode ---------- */
  function loadEpisode(id, done) {
    window.H1M_EPISODES = window.H1M_EPISODES || {};
    if (window.H1M_EPISODES[id]) return done(window.H1M_EPISODES[id]);
    var s = el("script", { src: "data/ep/" + id + ".js" });
    s.onload = function () { done(window.H1M_EPISODES[id]); };
    s.onerror = function () { app.appendChild(el("p", { text: "Episode data missing: data/ep/" + id + ".js" })); };
    document.body.appendChild(s);
  }

  function episode(id) {
    app.appendChild(el("a", { "class": "back", href: "#/", text: "← Gallery" }));
    loadEpisode(id, function (ep) { if (ep) drawEpisode(ep); });
  }

  function drawEpisode(ep) {
    var fps = ep.fps, n = ep.frames;
    var video = el("video", { src: ep.video, playsinline: "", muted: "", preload: "auto" });
    video.muted = true;
    var canvas = el("canvas", { width: ep.size[0], height: ep.size[1] });
    var timeline = el("div", { "class": "timeline", title: "Click to jump" });
    var head = el("div", { "class": "head" });
    var list = el("ul", { "class": "subs" });
    var time = el("span", { "class": "time" });
    var overlay = true;
    var play = el("button", { text: "Play", onclick: function () { if (video.paused) video.play(); else video.pause(); } });
    video.addEventListener("play", function () { play.textContent = "Pause"; });
    video.addEventListener("pause", function () { play.textContent = "Play"; });
    var rate = el("select", { onchange: function () { video.playbackRate = Number(rate.value); } },
      ["0.25", "0.5", "1"].map(function (r) { var o = el("option", { value: r, text: r + "×" }); if (r === "1") o.selected = true; return o; }));
    var toggle = el("button", { text: "Hide hands", onclick: function () { overlay = !overlay; toggle.textContent = overlay ? "Hide hands" : "Show hands"; tick(true); } });
    var step = function (d) { return el("button", { text: d < 0 ? "◀ frame" : "frame ▶", onclick: function () { video.pause(); seekFrame(frameNow() + d); } }); };

    function seekFrame(f) { f = Math.max(0, Math.min(n - 1, f)); video.currentTime = (f + 0.5) / fps; tick(true); }
    function frameNow() { return Math.max(0, Math.min(n - 1, Math.floor(video.currentTime * fps + 1e-3))); }

    ep.subtasks.forEach(function (s, i) {
      var seg = el("div", { "class": "seg", style: "width:" + (100 * (s.end - s.start) / n) + "%", title: s.text, text: s.text,
        onclick: function (e) { e.stopPropagation(); seekFrame(s.start); } });
      timeline.appendChild(seg);
      list.appendChild(el("li", { onclick: function () { seekFrame(s.start); video.play(); } }, [
        el("span", { "class": "when", text: (s.start / fps).toFixed(2) + "–" + (s.end / fps).toFixed(2) + " s" }),
        el("span", { text: s.text })
      ]));
    });
    timeline.appendChild(head);
    timeline.addEventListener("click", function (e) {
      var r = timeline.getBoundingClientRect(); seekFrame(Math.floor((e.clientX - r.left) / r.width * n));
    });

    var ctx = canvas.getContext("2d");
    function drawHands(f) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!overlay) return;
      var lw = Math.max(2, canvas.width / 320);
      ["left", "right"].forEach(function (side) {
        var k = ep.hands2d[side][f];
        if (!k) return;
        var color = css(side === "left" ? "--left" : "--right");
        ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = lw;
        function off(j) { return k[2 * j] <= -9999 || k[2 * j + 1] <= -9999; }  // behind the camera
        BONES.forEach(function (b) {
          if (off(b[0]) || off(b[1])) return;
          ctx.beginPath(); ctx.moveTo(k[2 * b[0]], k[2 * b[0] + 1]); ctx.lineTo(k[2 * b[1]], k[2 * b[1] + 1]); ctx.stroke();
        });
        for (var j = 0; j < 21; j++) { if (off(j)) continue; ctx.beginPath(); ctx.arc(k[2 * j], k[2 * j + 1], lw * 1.4, 0, 6.3); ctx.fill(); }
      });
    }

    var three = el("div", { "class": "three" });
    var view3d = null;
    var last = -1;
    function tick(force) {
      var f = frameNow();
      if (f === last && !force) return;
      last = f;
      drawHands(f);
      head.style.left = (100 * (f + 0.5) / n) + "%";
      time.textContent = "frame " + f + " / " + (n - 1) + " · " + (f / fps).toFixed(2) + " s";
      ep.subtasks.forEach(function (s, i) {
        var on = f >= s.start && f < s.end;
        timeline.children[i].classList.toggle("on", on);
        list.children[i].classList.toggle("on", on);
      });
      if (view3d) view3d.update(f);
    }
    var raf = 0;
    (function loop() { tick(false); raf = requestAnimationFrame(loop); })();
    cleanup.push(function () { cancelAnimationFrame(raf); video.pause(); if (view3d) view3d.dispose(); });

    var m = ep.meta;
    var rows = [
      ["Episode", ep.id], ["Source", m.source + " · " + (m.source_id || "")], ["Clip", m.source_clip],
      ["Frames", n + " at " + fps + " fps (" + (n / fps).toFixed(2) + " s)"], ["Video", ep.size[0] + "×" + ep.size[1] + " H.264 (source " + m.source_width + "×" + m.source_height + ")"],
      ["Pose", m.pose_source + " (" + m.action_quality + "), " + (ep.space === "world" ? "camera pose recorded" : "camera pose not measured")],
      ["Intrinsics fx fy cx cy", m.intrinsic.join(", ")],
      ["Environment", m.environment], ["Scene", m.scene + " (" + m.scene_id + ")"], ["Collector", m.collector_id],
      ["QA", (m.qa_decision || "none") + (m.qa_reasons && m.qa_reasons.length ? ": " + m.qa_reasons.join("; ") : "")],
      ["Hands in frame", pct(m.hands_visible) + " (left " + pct(m.left_visible) + ", right " + pct(m.right_visible) + ")"],
      ["Bone-length CV", num(m.left_bone_cv, 3) + " left, " + num(m.right_bone_cv, 3) + " right"],
      ["Joint acceleration", num(m.left_accel_m_s2, 1) + " / " + num(m.right_accel_m_s2, 1) + " m/s² (median)"],
      ["Human-1M checks", ["fps", "resolution", "hands_visible", "subtask_seconds"].map(function (k) { return k + " " + (m["meets_" + k] ? "✓" : "✗"); }).join(" · ")],
      ["Robot instruction", m.instruction]
    ];
    var kv = el("table", { "class": "kv" }, rows.map(function (r) { return el("tr", {}, [el("td", { text: r[0] }), el("td", { text: String(r[1] == null ? "–" : r[1]) })]); }));

    app.appendChild(el("h1", { text: ep.title }));
    app.appendChild(el("p", { "class": "lede", text: ep.task }));
    app.appendChild(el("div", { "class": "episode" }, [
      el("div", {}, [
        el("div", { "class": "panel" }, [
          el("div", { "class": "stage" }, [video, canvas]),
          el("div", { "class": "bar" }, [play, step(-1), step(1), rate, toggle, time]),
          timeline,
          el("div", { "class": "legend" }, [
            el("span", {}, [el("i", { style: "background:" + css("--left") }), "left hand"]),
            el("span", {}, [el("i", { style: "background:" + css("--right") }), "right hand"]),
            el("span", { text: "Subtasks: " + Array.from(new Set(ep.subtasks.map(function (s) { return s.source; }))).join(", ") })
          ]),
          list
        ])
      ]),
      el("div", {}, [
        el("div", { "class": "panel" }, [three,
          el("div", { "class": "legend" }, [
            el("span", {}, [el("i", { style: "background:" + css("--left") }), "left wrist path"]),
            el("span", {}, [el("i", { style: "background:" + css("--right") }), "right wrist path"]),
            ep.head ? el("span", {}, [el("i", { style: "background:" + css("--head") }), "head path and view direction"]) : el("span", { text: "Camera frame: the head is the origin (pose not measured)" })
          ])]),
        el("h2", { text: "Episode metadata" }),
        el("div", { "class": "panel" }, [kv])
      ])
    ]));
    view3d = makeThree(three, ep);
    tick(true);
  }

  /* Points of the 3D view in a y-up display frame, metres. */
  function displayPoint(ep, a, i) {
    var x = a[i] / 1000, y = a[i + 1] / 1000, z = a[i + 2] / 1000;
    return ep.space === "world" ? [x, y, z] : [x, -y, -z];
  }

  function hasWebGL() {
    try { var c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch (e) { return false; }
  }

  function makeThree(box, ep) {
    if (window.THREE && hasWebGL()) {
      try { return makeWebGL(box, ep); } catch (e) { box.innerHTML = ""; }
    }
    return makeCanvas3D(box, ep);
  }

  /* Fallback without WebGL (or without three.js): the same scene drawn on a 2D canvas
     with a perspective projection; drag to turn, wheel to zoom. */
  function makeCanvas3D(box, ep) {
    var canvas = el("canvas");
    box.appendChild(canvas);
    box.appendChild(el("div", { "class": "note", text: "2D-canvas 3D view (no WebGL here): drag to turn, scroll to zoom" }));
    var ctx = canvas.getContext("2d");
    var pts = [];
    ["left", "right"].forEach(function (s) { ep.hands3d[s].forEach(function (k) { if (k) pts.push(displayPoint(ep, k, 0)); }); });
    if (ep.head) ep.head.position.forEach(function (p) { pts.push(displayPoint(ep, p, 0)); });
    if (ep.space !== "world") pts.push([0, 0, 0]);
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    pts.forEach(function (p) { for (var i = 0; i < 3; i++) { lo[i] = Math.min(lo[i], p[i]); hi[i] = Math.max(hi[i], p[i]); } });
    var c = [0, 1, 2].map(function (i) { return (lo[i] + hi[i]) / 2; });
    var size = Math.max(0.3, Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]));
    var yaw = 0.7, pitch = 0.45, dist = size * 1.6, frame = 0, drag = null;
    function fit() { var r = window.devicePixelRatio || 1; canvas.width = box.clientWidth * r; canvas.height = box.clientHeight * r; canvas.style.width = box.clientWidth + "px"; canvas.style.height = box.clientHeight + "px"; }
    function proj(p) {
      var x = p[0] - c[0], y = p[1] - c[1], z = p[2] - c[2];
      var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
      var x1 = cy * x + sy * z, z1 = -sy * x + cy * z;
      var y2 = cp * y - sp * z1, z2 = sp * y + cp * z1;
      var d = dist - z2, f = Math.min(canvas.width, canvas.height) * 0.9;
      return d <= 0.01 ? null : [canvas.width / 2 + f * x1 / d, canvas.height / 2 - f * y2 / d];
    }
    function line(a, b, color, width, alpha) {
      var p = proj(a), q = proj(b); if (!p || !q) return;
      ctx.globalAlpha = alpha == null ? 1 : alpha; ctx.strokeStyle = color; ctx.lineWidth = width;
      ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); ctx.stroke(); ctx.globalAlpha = 1;
    }
    function draw() {
      var r = window.devicePixelRatio || 1;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      var g = Math.ceil(size * 5) / 5, floor = lo[1] - 0.02, step = g / 5;
      for (var i = -5; i <= 5; i++) {
        line([c[0] + i * step, floor, c[2] - g], [c[0] + i * step, floor, c[2] + g], css("--line"), r);
        line([c[0] - g, floor, c[2] + i * step], [c[0] + g, floor, c[2] + i * step], css("--line"), r);
      }
      ["left", "right"].forEach(function (s) {
        var col = css(s === "left" ? "--left" : "--right"), prev = null;
        ep.hands3d[s].forEach(function (k) { var p = k ? displayPoint(ep, k, 0) : null; if (p && prev) line(prev, p, col, 1.5 * r, 0.55); prev = p; });
        var k = ep.hands3d[s][frame];
        if (k) BONES.forEach(function (b) { line(displayPoint(ep, k, 3 * b[0]), displayPoint(ep, k, 3 * b[1]), col, 2.5 * r); });
      });
      var hc = css("--head");
      if (ep.head) {
        var prev = null;
        ep.head.position.forEach(function (p) { var q = displayPoint(ep, p, 0); if (prev) line(prev, q, hc, 1.5 * r, 0.7); prev = q; });
        var h = displayPoint(ep, ep.head.position[frame], 0), fw = ep.head.forward[frame];
        line(h, [h[0] + 0.15 * fw[0], h[1] + 0.15 * fw[1], h[2] + 0.15 * fw[2]], hc, 3 * r);
      } else {
        line([0, 0, 0], [0, 0, -0.15], hc, 3 * r);
      }
    }
    canvas.addEventListener("mousedown", function (e) { drag = [e.clientX, e.clientY, yaw, pitch]; });
    window.addEventListener("mouseup", function () { drag = null; });
    canvas.addEventListener("mousemove", function (e) {
      if (!drag) return;
      yaw = drag[2] + (e.clientX - drag[0]) * 0.01;
      pitch = Math.max(-1.5, Math.min(1.5, drag[3] + (e.clientY - drag[1]) * 0.01)); draw();
    });
    canvas.addEventListener("wheel", function (e) { e.preventDefault(); dist = Math.max(size * 0.3, dist * (e.deltaY > 0 ? 1.1 : 0.9)); draw(); }, { passive: false });
    function onResize() { fit(); draw(); }
    window.addEventListener("resize", onResize);
    fit(); draw();
    return { update: function (f) { frame = f; draw(); }, dispose: function () { window.removeEventListener("resize", onResize); } };
  }

  function makeWebGL(box, ep) {
    var T = window.THREE;
    var w = box.clientWidth || 500, h = box.clientHeight || 420;
    var renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setSize(w, h);
    box.appendChild(renderer.domElement);
    var scene = new T.Scene();
    var cam = new T.PerspectiveCamera(45, w / h, 0.01, 50);
    var world = ep.space === "world";
    // display frame is y up: camera frame (x right, y down, z forward) -> (x, -y, -z)
    function P(a, i) { var p = displayPoint(ep, a, i); return new T.Vector3(p[0], p[1], p[2]); }
    var all = [];
    ["left", "right"].forEach(function (s) { ep.hands3d[s].forEach(function (k) { if (k) all.push(P(k, 0)); }); });
    if (ep.head) ep.head.position.forEach(function (p) { all.push(P(p, 0)); });
    if (!world) all.push(new T.Vector3(0, 0, 0));
    var box3 = new T.Box3().setFromPoints(all.length ? all : [new T.Vector3()]);
    var center = box3.getCenter(new T.Vector3());
    var size = Math.max(0.3, box3.getSize(new T.Vector3()).length());
    var grid = new T.GridHelper(Math.ceil(size * 2), Math.ceil(size * 10), 0x888888, 0xcccccc);
    grid.position.set(center.x, box3.min.y - 0.02, center.z);
    grid.material.opacity = 0.35; grid.material.transparent = true;
    scene.add(grid);
    function color(name) { return new T.Color(css(name)); }
    function path(points, c) {
      var g = new T.BufferGeometry().setFromPoints(points);
      var line = new T.Line(g, new T.LineBasicMaterial({ color: c, transparent: true, opacity: 0.55 }));
      scene.add(line); return line;
    }
    ["left", "right"].forEach(function (s) {
      var runs = [], cur = [];
      ep.hands3d[s].forEach(function (k) { if (k) cur.push(P(k, 0)); else if (cur.length) { runs.push(cur); cur = []; } });
      if (cur.length) runs.push(cur);
      runs.forEach(function (r) { if (r.length > 1) path(r, color(s === "left" ? "--left" : "--right")); });
    });
    var headDot = null, headDir = null;
    if (ep.head) {
      path(ep.head.position.map(function (p) { return P(p, 0); }), color("--head"));
      headDot = new T.Mesh(new T.SphereGeometry(0.02, 16, 12), new T.MeshBasicMaterial({ color: color("--head") }));
      scene.add(headDot);
      headDir = new T.ArrowHelper(new T.Vector3(0, 0, -1), new T.Vector3(), 0.18, color("--head").getHex(), 0.05, 0.03);
      scene.add(headDir);
    } else {
      var frustum = new T.ArrowHelper(new T.Vector3(0, 0, -1), new T.Vector3(), 0.15, color("--head").getHex(), 0.04, 0.025);
      scene.add(frustum);
    }
    var skel = {};
    ["left", "right"].forEach(function (s) {
      var g = new T.BufferGeometry();
      g.setAttribute("position", new T.BufferAttribute(new Float32Array(BONES.length * 6), 3));
      var seg = new T.LineSegments(g, new T.LineBasicMaterial({ color: color(s === "left" ? "--left" : "--right") }));
      var pg = new T.BufferGeometry();
      pg.setAttribute("position", new T.BufferAttribute(new Float32Array(21 * 3), 3));
      var pts = new T.Points(pg, new T.PointsMaterial({ color: color(s === "left" ? "--left" : "--right"), size: 0.012 }));
      scene.add(seg); scene.add(pts);
      skel[s] = { seg: seg, pts: pts };
    });
    cam.position.copy(center).add(world ? new T.Vector3(size * 0.6, size * 0.5, size * 0.8) : new T.Vector3(size * 0.7, size * 0.4, size * 0.5));
    var controls = T.OrbitControls ? new T.OrbitControls(cam, renderer.domElement) : null;
    if (controls) { controls.target.copy(center); controls.update(); } else cam.lookAt(center);
    var running = true;
    (function loop() { if (!running) return; if (controls) controls.update(); renderer.render(scene, cam); requestAnimationFrame(loop); })();
    function onResize() { var w2 = box.clientWidth, h2 = box.clientHeight; renderer.setSize(w2, h2); cam.aspect = w2 / h2; cam.updateProjectionMatrix(); }
    window.addEventListener("resize", onResize);
    return {
      update: function (f) {
        ["left", "right"].forEach(function (s) {
          var k = ep.hands3d[s][f], o = skel[s];
          o.seg.visible = o.pts.visible = !!k;
          if (!k) return;
          var a = o.seg.geometry.attributes.position, b = o.pts.geometry.attributes.position;
          BONES.forEach(function (bn, i) {
            var p = P(k, 3 * bn[0]), q = P(k, 3 * bn[1]);
            a.setXYZ(2 * i, p.x, p.y, p.z); a.setXYZ(2 * i + 1, q.x, q.y, q.z);
          });
          for (var j = 0; j < 21; j++) { var p = P(k, 3 * j); b.setXYZ(j, p.x, p.y, p.z); }
          a.needsUpdate = true; b.needsUpdate = true;
          o.seg.geometry.computeBoundingSphere(); o.pts.geometry.computeBoundingSphere();
        });
        if (ep.head && headDot) {
          var hp = P(ep.head.position[f], 0), fw = ep.head.forward[f];
          headDot.position.copy(hp); headDir.position.copy(hp);
          headDir.setDirection(new T.Vector3(fw[0], fw[1], fw[2]).normalize());
        }
      },
      dispose: function () { running = false; window.removeEventListener("resize", onResize); renderer.dispose(); }
    };
  }

  /* ---------- quality ---------- */
  function stats() {
    var S = INDEX.summary, A = S.all || {};
    app.appendChild(el("h1", { text: "Quality" }));
    app.appendChild(el("p", { "class": "lede", text: "Every clip went through de-identification, hand pose and QA. The checks below are Human-1M's episode requirements (≥ 30 fps, ≥ 480p, one or more hands in frame for ≥ 95 % of the episode, 1–10 s subtasks), measured here and reported; an episode that misses one is still exported with the result in its metadata." }));
    var cards = [["Clips", A.clips], ["Exported", A.exported], ["Hours (all)", num(A.hours, 2)], ["Exported minutes", num((A.exported_hours || 0) * 60, 1)],
      ["Hands in frame, median", pct(A.hands_visible_median)], ["Clips with hands ≥ 95 %", pct(A.hands_visible_ge_95)],
      ["Subtasks", (S.subtasks || {}).count], ["Subtasks in 1–10 s", pct((S.subtasks || {}).in_1_10_s)]];
    app.appendChild(el("div", { "class": "cards" }, cards.map(function (c) { return el("div", { "class": "stat" }, [el("div", { "class": "v", text: String(c[1] == null ? "–" : c[1]) }), el("div", { "class": "k", text: c[0] })]); })));
    app.appendChild(el("h2", { text: "By source" }));
    var keys = Object.keys(S.sources || {});
    var label = { ego_video: "Team tray (480p + 1080p)", egodex: "EgoDex sample" };
    var lines = [["Clips", "clips"], ["Hours", "hours", 3], ["Exported", "exported"], ["Excluded", function (b) { return (b.decisions || {}).excluded || 0; }],
      ["Rejected by QA", function (b) { return (b.decisions || {}).rejected_qa || 0; }], ["QA pass / flag / reject", function (b) { return [(b.qa || {}).pass || 0, (b.qa || {}).flag || 0, (b.qa || {}).reject || 0].join(" / "); }],
      ["fps", function (b) { return (b.fps || []).join(", "); }], ["Resolution", function (b) { return (b.resolutions || []).join(", "); }],
      ["Median clip length", function (b) { return secs(b.seconds_median); }], ["Hands in frame, median", function (b) { return pct(b.hands_visible_median); }],
      ["Clips with hands ≥ 95 %", function (b) { return pct(b.hands_visible_ge_95); }], ["Bone-length CV, median", function (b) { return num(b.bone_cv_median, 3); }]];
    app.appendChild(el("div", { "class": "panel scroll" }, [el("table", {}, [
      el("tr", {}, [el("th", { text: "" })].concat(keys.map(function (k) { return el("th", { "class": "num", text: label[k] || k }); }))),
    ].concat(lines.map(function (l) {
      return el("tr", {}, [el("td", { text: l[0] })].concat(keys.map(function (k) {
        var b = S.sources[k], v = typeof l[1] === "function" ? l[1](b) : (l[2] ? num(b[l[1]], l[2]) : b[l[1]]);
        return el("td", { "class": "num", text: String(v) });
      })));
    })))]));
    app.appendChild(el("h2", { text: "Shards (LeRobot v3.0)" }));
    var sh = S.shards || {};
    app.appendChild(el("div", { "class": "panel scroll" }, [el("table", {}, [
      el("tr", {}, ["Shard", "Episodes", "Frames", "Tasks", "Subtask texts", "Schema check"].map(function (t, i) { return el("th", { "class": i ? "num" : "", text: t }); }))
    ].concat(Object.keys(sh).map(function (k) {
      var x = sh[k];
      return el("tr", {}, [el("td", { text: k }), el("td", { "class": "num", text: String(x.episodes) }), el("td", { "class": "num", text: String(x.frames) }),
        el("td", { "class": "num", text: String(x.tasks) }), el("td", { "class": "num", text: String(x.subtasks) }),
        el("td", { "class": "num " + (x.problems.length ? "no" : "ok"), text: x.problems.length ? x.problems.length + " problems" : "ok" })]);
    })))]));
    app.appendChild(el("h2", { text: "QA reasons (all clips)" }));
    var reasons = A.qa_reasons || {};
    app.appendChild(el("div", { "class": "panel scroll" }, [el("table", {}, [el("tr", {}, [el("th", { text: "Reason" }), el("th", { "class": "num", text: "Clips" })])].concat(
      Object.keys(reasons).map(function (r) { return el("tr", {}, [el("td", { text: r }), el("td", { "class": "num", text: String(reasons[r]) })]); })))]));
    app.appendChild(el("h2", { text: "Exported episode length" }));
    app.appendChild(hist(INDEX.episodes.map(function (e) { return e.seconds; }), 24, " s"));
    app.appendChild(el("h2", { text: "Hands in frame per exported episode" }));
    app.appendChild(hist(INDEX.episodes.map(function (e) { return 100 * (e.hands || 0); }), 20, " %"));
  }
  function hist(values, bins, unit) {
    if (!values.length) return el("p", { text: "–" });
    var lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
    if (hi === lo) hi = lo + 1;
    var counts = new Array(bins).fill(0);
    values.forEach(function (v) { counts[Math.min(bins - 1, Math.floor((v - lo) / (hi - lo) * bins))]++; });
    var top = Math.max.apply(null, counts);
    return el("div", { "class": "panel" }, [
      el("div", { "class": "hist" }, counts.map(function (c, i) {
        var a = lo + i * (hi - lo) / bins, b = lo + (i + 1) * (hi - lo) / bins;
        return el("div", { style: "height:" + (100 * c / top) + "%", title: c + " episodes, " + a.toFixed(1) + "–" + b.toFixed(1) + unit });
      })),
      el("div", { "class": "hist-axis" }, [el("span", { text: lo.toFixed(1) + unit }), el("span", { text: hi.toFixed(1) + unit })])
    ]);
  }

  /* ---------- all clips ---------- */
  function clips() {
    var rows = INDEX.status;
    app.appendChild(el("h1", { text: "All clips" }));
    app.appendChild(el("p", { "class": "lede", text: "Every clip of every source, with what happened to it: exported, or excluded, blocked or rejected with the reason." }));
    var q = el("input", { type: "search", placeholder: "Filter by clip, decision, reason…" });
    var body = el("tbody");
    var count = el("span", { "class": "count" });
    function draw() {
      body.innerHTML = "";
      var words = q.value.toLowerCase().split(/\s+/).filter(Boolean);
      var shown = rows.filter(function (r) { var h = JSON.stringify(r).toLowerCase(); return words.every(function (w) { return h.indexOf(w) >= 0; }); });
      count.textContent = shown.length + " of " + rows.length + " clips";
      shown.forEach(function (r) {
        var link = r.decision === "exported" ? el("a", { href: "#/ep/" + r.episode_id, text: r.clip }) : document.createTextNode(r.clip);
        body.appendChild(el("tr", {}, [el("td", {}, [link]), el("td", { text: r.source }), el("td", { "class": "num", text: secs(r.seconds) }),
          el("td", { "class": "num", text: r.fps + " · " + r.width + "×" + r.height }), el("td", { text: r.deid }), el("td", { text: r.pose_source }),
          el("td", { text: r.qa || "–" }), el("td", { "class": "num", text: pct(r.hands_visible) }),
          el("td", { "class": r.decision === "exported" ? "ok" : "no", text: r.decision }), el("td", { text: r.reason })]));
      });
    }
    q.addEventListener("input", draw);
    app.appendChild(el("div", { "class": "controls" }, [q, count]));
    app.appendChild(el("div", { "class": "panel scroll" }, [el("table", {}, [
      el("thead", {}, [el("tr", {}, ["Clip", "Source", "Length", "fps · size", "De-identification", "Pose", "QA", "Hands", "Decision", "Reason"].map(function (t) { return el("th", { text: t }); }))]), body])]));
    draw();
  }

  /* ---------- router ---------- */
  function render() {
    cleanup.forEach(function (f) { f(); }); cleanup = [];
    app.innerHTML = "";
    var h = location.hash.replace(/^#\/?/, "");
    var route = h.indexOf("ep/") === 0 ? "ep" : (h || "gallery");
    document.querySelectorAll("nav a").forEach(function (a) { a.classList.toggle("on", a.getAttribute("data-route") === (route === "ep" ? "gallery" : route)); });
    if (route === "ep") episode(h.slice(3));
    else if (route === "stats") stats();
    else if (route === "clips") clips();
    else gallery();
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", render);
  render();
})();
