/* demo mode (?demo=1): zoom, public-only flag (UI.demo), one-line caption bar, ring intro.
   Captions are Vietnamese, at most 12 words each. The legacy shims at the bottom keep unconverted v4 pages running. */
"use strict";
const DEMO = (() => {
  /* @budget-skip-start captions */
  const STEPS = [
    ["home", "Vòng flywheel: thu dữ liệu, xử lý, train, đánh giá, tìm lỗi."],
    ["data", "Mọi tập dữ liệu trong một bảng; bấm cột để lọc."],
    ["data/S70", "Một tập: số episode, chất lượng, nguồn gốc."],
    ["data/h1m-team/ep/ep_77abee2eee5cfbb7", "Một clip người: video đã che mặt, tư thế tay, chia bước."],
    ["jobs", "Việc đang chạy: log thật và lệnh tái lập."],
    ["runs", "Năm run train, cùng màu ở mọi trang."],
    ["eval", "Eval: năm run, robot hỏng ở bước nào, nhãn lỗi nào."],
    ["loop", "Lỗi → Dữ liệu: sinh nhắm lỗi, dạy lại; luật viết trước bảo dừng."],
    ["qa", "Bộ kiểm bằng code quyết định; agent chỉ đề xuất."],
  ];
  /* @budget-skip-end */
  let i = 0;
  const bar = () => $("#cap");
  function draw() {
    const b = bar(); if (!b) return; b.innerHTML = "";
    b.appendChild(h("span", { class: "st", text: (i + 1) + "/" + STEPS.length })); b.appendChild(h("span", { class: "tx", text: STEPS[i][1] }));
    b.appendChild(h("button", { class: "u-btn sm", text: "←", onclick: () => step(-1) })); b.appendChild(h("button", { class: "u-btn sm pri", text: "→", onclick: () => step(1) }));
  }
  function step(d) { const n = Math.max(0, Math.min(STEPS.length - 1, i + d)); if (n === i && d) return; i = n; const s = STEPS[i]; if (window.CHAT) CHAT.close(true); go(s[0]); draw(); }
  function sync() { const r = chatRoute(); const k = STEPS.findIndex(s => s[0] === r); if (k >= 0 && STEPS[i][0] !== r) { i = k; } draw(); }
  return {
    steps: STEPS,
    init() {
      if (!UI.demo) return;
      if (window.CHAT) CHAT.close(true);
      UI.keys.bind({ ArrowRight: () => step(1), ArrowLeft: () => step(-1) });
      window.addEventListener("hashchange", sync); draw();
      let seen = false; try { seen = sessionStorage.getItem("v5intro") === "1"; } catch (e) {}
      if (!seen) { try { sessionStorage.setItem("v5intro", "1"); } catch (e) {} setTimeout(() => ringIntro(() => { go("home"); }), 400); }
    },
  };
})();

/* ---- legacy shims for unconverted v4 pages (they render prose; v5 shows none of it) ---- */
const isDemo = () => UI.demo;
const qaHead = () => h("span");
const whereRan = () => h("span");
const termize = x => x;
const term = (k, t) => t || k;
const pubOnly = () => UI.demo;
const nonPublicIds = () => (CAT ? new Set(CAT.rows.filter(r => r.data_class !== "public").map(r => r.id)) : new Set());
const visRows = () => (CAT ? CAT.rows.filter(r => !UI.demo || r.data_class === "public") : []);
window.DEMO = DEMO;
