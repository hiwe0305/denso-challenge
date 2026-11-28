// One inline SVG icon set (design audit P1-11): 16 px grid, 1.6 px stroke, currentColor,
// so icons follow the text colour in light and dark themes. No emoji or Unicode glyphs.
const SVG_NS = "http://www.w3.org/2000/svg";

const PATHS = {
  home: ["M2.5 7.5 8 3l5.5 4.5", "M4 6.5V13h8V6.5", "M6.5 13V9.5h3V13"],
  chat: ["M3 3.5h10v7H7l-3 2.5v-2.5H3z", "M6 7h.01M8 7h.01M10 7h.01"],
  tasks: ["M3 3h4v4H3zM9 3h4v4H9zM3 9h4v4H3zM9 9h4v4H9z"],
  data: ["M3 3h2.5v10H3zM6.5 3H9v10H6.5z", "M10.2 3.6l2.3-.6 2 9.5-2.3.5z"],
  import: ["M8 2.5v7", "M5 7l3 3 3-3", "M3 12.5h10"],
  pipeline: ["M13 8a5 5 0 0 1-8.6 3.5", "M3 8a5 5 0 0 1 8.6-3.5", "M11.5 2v2.6H9", "M4.5 14v-2.6H7"],
  qa: ["M3 8.5l3 3 7-7"],
  egoflow: ["M2.5 4.5h8v7h-8z", "M10.5 7l3-2v6l-3-2"],
  export: ["M8 10V3", "M5 5.5l3-3 3 3", "M3 12.5h10"],
  jobs: ["M5.5 4h8M5.5 8h8M5.5 12h8", "M2.5 4h.01M2.5 8h.01M2.5 12h.01"],
  runs: ["M2 9h2.5l2-5 3 8 2-4.5H14"],
  eval: ["M8 2.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11z", "M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"],
  sim: ["M5 3.5v9l7.5-4.5z"],
  diagnose: ["M7 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M10 10l3.5 3.5"],
  loop: ["M12.5 6A5 5 0 0 0 3.6 5.5", "M3.5 10a5 5 0 0 0 8.9.5", "M3.5 2.8v2.9h2.9", "M12.5 13.2v-2.9H9.6"],
  base: ["M3 3h4v10H3z", "M9 6h4v7H9z"],
  follow: ["M8 2.5v3M8 10.5v3M2.5 8h3M10.5 8h3", "M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"],
  design: ["M8 2.5 13.5 8 8 13.5 2.5 8z"],
  cost: ["M8 2.5v11", "M10.8 5.2C10.3 4.4 9.3 4 8 4 6.3 4 5.2 4.8 5.2 6s1.1 1.7 2.8 2 2.8.9 2.8 2.1S9.7 12 8 12c-1.4 0-2.5-.5-3-1.4"],
  report: ["M4 2.5h5.5L12 5v8.5H4z", "M9.5 2.5V5H12", "M6 8h4M6 10.5h4"],
  theme: ["M8 2.5a5.5 5.5 0 1 0 0 11z", "M8 2.5a5.5 5.5 0 0 1 0 11"],
  menu: ["M2.5 4.5h11M2.5 8h11M2.5 11.5h11"],
  lock: ["M4 7.5h8v6H4z", "M5.5 7.5V5.5a2.5 2.5 0 0 1 5 0v2"],
  alert: ["M8 2.5 14 13H2z", "M8 6.5v3", "M8 11.2h.01"],
  dot: ["M8 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"],
  folder: ["M2.5 4.5h4l1.5 1.5h5.5v6.5h-11z"],
};

// Filled shapes (the rest are stroked outlines).
const FILLED = new Set(["sim", "dot"]);

export function icon(name, { size = 16, className = "ico" } = {}) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("class", className);
  const filled = FILLED.has(name);
  svg.setAttribute("fill", filled ? "currentColor" : "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", filled ? "1" : "1.6");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  for (const d of PATHS[name] || PATHS.dot) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
  }
  return svg;
}

export function hasIcon(name) {
  return Object.prototype.hasOwnProperty.call(PATHS, name);
}
