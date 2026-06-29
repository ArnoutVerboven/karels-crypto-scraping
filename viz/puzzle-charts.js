/* Karel's Crypto — puzzle-themed charts (vanilla JS, no dependencies).
 *
 * Usage:
 *   PuzzleCharts.bar(el, { title, data: [{label, value}], step, unit });
 *   PuzzleCharts.scatter(el, { title, points: [{label, x, y}], xLabel, yLabel });
 *   PuzzleCharts.heatmap(el, { title, rowLabels, colLabels, values });
 *
 * `el` is a container element or a CSS selector. See README.md for all options.
 */
(function (global) {
  "use strict";

  function resolve(el) {
    const node = typeof el === "string" ? document.querySelector(el) : el;
    if (!node) throw new Error("PuzzleCharts: container not found: " + el);
    return node;
  }
  function make(cls, parent, text) {
    const d = document.createElement("div");
    if (cls) d.className = cls;
    if (text != null) d.textContent = text;
    if (parent) parent.appendChild(d);
    return d;
  }
  function letter(i) {
    // A..Z, then AA, AB, ... for long lists.
    let s = "";
    i += 1;
    while (i > 0) { const r = (i - 1) % 26; s = String.fromCharCode(65 + r) + s; i = Math.floor((i - 1) / 26); }
    return s;
  }
  function panel(container, opts) {
    container.classList.add("pz");
    const p = make("pz-panel", container);
    if (opts.cell) p.style.setProperty("--pz-cell", opts.cell + "px");
    if (opts.title) make("pz-title", p, opts.title);
    if (opts.subtitle) make("pz-subtitle", p, opts.subtitle);
    return p;
  }
  function fmt(v, unit) {
    const n = Math.round(v * 100) / 100;
    return (Number.isInteger(n) ? n : n.toFixed(unit === "%" ? 0 : 2)) + (unit || "");
  }

  /* ------------------------------------------------------------------ bar */
  function bar(el, opts) {
    const container = resolve(el);
    container.innerHTML = "";
    const o = Object.assign(
      { step: 10, hintEvery: 2, unit: "%", labelWidth: 240, showValues: true, cell: null, sort: true },
      opts
    );
    const data = o.data.slice();
    if (o.sort) data.sort((a, b) => b.value - a.value);
    const p = panel(container, o);
    p.style.setProperty("--pz-label-w", o.labelWidth + "px");

    data.forEach((d, i) => {
      const row = make("pz-bar-row", p);
      const lab = make("pz-bar-label", row);
      const ltr = document.createElement("span");
      ltr.className = "pz-letter";
      ltr.textContent = letter(i) + ".";
      lab.appendChild(ltr);
      lab.appendChild(document.createTextNode(" " + d.label));

      const track = make("pz-track", row);
      const full = Math.floor(d.value / o.step + 1e-9);
      const frac = (d.value - full * o.step) / o.step;
      for (let c = 0; c < full; c++) {
        const sq = make("pz-sq", track);
        if (c % o.hintEvery === 0) make("pz-hint", sq, fmt(c * o.step, ""));
      }
      if (frac > 1e-6) {
        const sq = make("pz-sq", track);
        sq.style.width = Math.max(2, frac * (o.cell || 30)) + "px"; // cropped last cell
        // hint only if the cropped cell is wide enough to fit it (avoids crowding)
        if (full % o.hintEvery === 0 && frac > 0.55) make("pz-hint", sq, fmt(full * o.step, ""));
      }
      if (o.showValues) make("pz-bar-val", row, fmt(d.value, o.unit));
    });
    return p;
  }

  /* -------------------------------------------------------------- scatter */
  function niceMin(v) { return v; }
  function scatter(el, opts) {
    const container = resolve(el);
    container.innerHTML = "";
    const o = Object.assign(
      { cols: 14, rows: 11, xLabel: "x", yLabel: "y", unit: "", xUnit: "", yUnit: "",
        xMin: null, xMax: null, yMin: null, yMax: null, legendCols: 2, cell: null },
      opts
    );
    const pts = o.points;
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const xMin = o.xMin != null ? o.xMin : Math.min(0, ...xs);
    const xMax = o.xMax != null ? o.xMax : Math.max(...xs);
    const yMin = o.yMin != null ? o.yMin : Math.min(0, ...ys);
    const yMax = o.yMax != null ? o.yMax : Math.max(...ys);
    const C = o.cols, R = o.rows;
    const col = (x) => 1 + Math.round(((x - xMin) / (xMax - xMin || 1)) * (C - 2)); // col 0 = y-axis
    const row = (y) => R - 2 - Math.round(((y - yMin) / (yMax - yMin || 1)) * (R - 2)); // last row = x-axis

    const p = panel(container, o);
    const wrap = make("pz-scatter-wrap", p);
    const yl = make("pz-ylabel", wrap, o.yLabel);
    yl.style.gridRow = "1"; yl.style.gridColumn = "1";

    const grid = make("pz-grid", wrap);
    grid.style.gridColumn = "2"; grid.style.gridRow = "1";
    const cs = o.cell || 30;
    grid.style.gridTemplateColumns = `repeat(${C}, ${cs}px)`;
    grid.style.gridTemplateRows = `repeat(${R}, ${cs}px)`;

    // taken cells -> nearest-free placement
    const taken = {};
    const place = (r, c) => {
      for (let rad = 0; rad < Math.max(R, C); rad++) {
        for (let dr = -rad; dr <= rad; dr++) for (let dc = -rad; dc <= rad; dc++) {
          const rr = r + dr, cc = c + dc;
          if (rr < 0 || rr >= R - 1 || cc < 1 || cc >= C) continue;
          if (!taken[rr + "," + cc]) { taken[rr + "," + cc] = true; return [rr, cc]; }
        }
      }
      return [r, c];
    };

    const cells = {};
    for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {
      const sq = make("pz-sq", grid);
      if (c === 0 || r === R - 1) sq.classList.add("pz-axis"); // the light-yellow cross
      cells[r + "," + c] = sq;
    }
    // axis ticks (hint numbers) at min/mid/max
    const xtick = (frac, val) => {
      const c = 1 + Math.round(frac * (C - 2));
      const t = document.createElement("div"); t.className = "pz-tick x"; t.textContent = fmt(val, o.xUnit);
      cells[(R - 1) + "," + c].appendChild(t);
    };
    const ytick = (frac, val) => {
      const r = R - 2 - Math.round(frac * (R - 2));
      const t = document.createElement("div"); t.className = "pz-tick y"; t.textContent = fmt(val, o.yUnit);
      cells[r + ",0"].appendChild(t);
    };
    [0, 0.5, 1].forEach((f) => { xtick(f, xMin + f * (xMax - xMin)); ytick(f, yMin + f * (yMax - yMin)); });

    // points
    pts.forEach((pt, i) => {
      const [r, c] = place(Math.min(R - 2, Math.max(0, row(pt.y))), Math.min(C - 1, Math.max(1, col(pt.x))));
      const sq = cells[r + "," + c];
      sq.className = "pz-sq pz-pt";
      sq.textContent = String(i + 1);
    });

    make("pz-xlabel", wrap, o.xLabel);

    // legend
    const legend = make("pz-legend", p);
    legend.style.setProperty("--pz-legend-cols", o.legendCols);
    pts.forEach((pt, i) => {
      const item = make("pz-legend-item", legend);
      make("pz-chip", item, String(i + 1));
      const txt = pt.label +
        (o.showCoords === false ? "" : `  (${fmt(pt.x, o.xUnit)}, ${fmt(pt.y, o.yUnit)})`);
      item.appendChild(document.createTextNode(txt));
    });
    return p;
  }

  /* -------------------------------------------------------------- heatmap */
  function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
  function ramp(t) {
    const lo = getComputedStyle(document.documentElement).getPropertyValue("--pz-hm-low").split(",").map(Number);
    const hi = getComputedStyle(document.documentElement).getPropertyValue("--pz-hm-high").split(",").map(Number);
    const L = lo.length === 3 ? lo : [255, 248, 209];
    const H = hi.length === 3 ? hi : [226, 150, 0];
    return `rgb(${lerp(L[0], H[0], t)}, ${lerp(L[1], H[1], t)}, ${lerp(L[2], H[2], t)})`;
  }
  function heatmap(el, opts) {
    const container = resolve(el);
    container.innerHTML = "";
    const o = Object.assign(
      { unit: "", cell: 46, rowTitle: "", colTitle: "", min: null, max: null }, opts
    );
    const vals = o.values.flat().filter((v) => v != null);
    const lo = o.min != null ? o.min : Math.min(...vals);
    const hi = o.max != null ? o.max : Math.max(...vals);
    const p = panel(container, o);

    const cols = o.colLabels.length;
    const hm = make("pz-hm", p);
    hm.style.gridTemplateColumns = `auto repeat(${cols}, ${o.cell}px)`;

    // header row: corner + column labels
    const corner = make("pz-hm-head pz-hm-corner", hm);
    corner.textContent = o.colTitle && o.rowTitle ? "" : "";
    o.colLabels.forEach((cl) => make("pz-hm-head", hm, cl));

    o.rowLabels.forEach((rl, r) => {
      make("pz-hm-head", hm, rl);
      o.colLabels.forEach((_, c) => {
        const v = o.values[r][c];
        const cell = make("pz-hm-cell", hm);
        cell.style.height = o.cell + "px";
        if (v == null) { cell.style.background = "transparent"; cell.style.borderColor = "transparent"; return; }
        const t = (v - lo) / (hi - lo || 1);
        cell.style.background = ramp(t);
        make("pz-hint", cell, fmt(v, o.unit)); // the "hint value" = the number
      });
    });
    if (o.colTitle) make("pz-hm-axis-title", p, o.colTitle).style.marginTop = "8px";
    return p;
  }

  global.PuzzleCharts = { bar, scatter, heatmap, _letter: letter };
})(typeof window !== "undefined" ? window : this);
