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
      { cols: 14, rows: 12, xLabel: "x", yLabel: "y", unit: "", xUnit: "", yUnit: "",
        xMin: null, xMax: null, yMin: null, yMax: null, flipX: false, cell: null },
      opts
    );
    const pts = o.points;
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const xMin = o.xMin != null ? o.xMin : Math.min(0, ...xs);
    const xMax = o.xMax != null ? o.xMax : Math.max(...xs);
    const yMin = o.yMin != null ? o.yMin : Math.min(0, ...ys);
    const yMax = o.yMax != null ? o.yMax : Math.max(...ys);
    const C = o.cols, R = o.rows;
    const col = (x) => {
      let f = (x - xMin) / (xMax - xMin || 1);
      if (o.flipX) f = 1 - f;                       // lower-is-better: small x on the right
      return 1 + Math.round(f * (C - 2));            // col 0 = y-axis
    };
    const row = (y) => R - 2 - Math.round(((y - yMin) / (yMax - yMin || 1)) * (R - 2)); // last row = x-axis

    const p = panel(container, o);
    const wrap = make("pz-scatter-wrap", p);

    // y-axis label: an upright up-arrow (always points up) above vertical text.
    const yl = make("pz-ylabel", wrap);
    make("pz-yarrow", yl, "\u2191");
    make("pz-ytext", yl, (o.yLabel || "").replace(/[\u2191\u2193\u2192\u2190]/g, "").trim());

    const plot = make("pz-plot", wrap);
    const grid = make("pz-grid", plot);
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
      if (c === 0 || r === R - 1) sq.classList.add("pz-axis"); // bordered light-yellow cross
      cells[r + "," + c] = sq;
    }
    // axis ticks: centred + bold in the axis cells (like the heatmap headers),
    // placed with the same mapping as the data so spacing stays consistent.
    [0, 0.5, 1].forEach((f) => {
      const xv = xMin + f * (xMax - xMin);
      make("pz-axval", cells[(R - 1) + "," + col(xv)], fmt(xv, o.xUnit));
      const yv = yMin + f * (yMax - yMin);
      make("pz-axval", cells[row(yv) + ",0"], fmt(yv, o.yUnit));
    });

    // points: number is bottom-right + light (hint style)
    pts.forEach((pt, i) => {
      const [r, c] = place(Math.min(R - 2, Math.max(0, row(pt.y))), Math.min(C - 1, Math.max(1, col(pt.x))));
      const sq = cells[r + "," + c];
      sq.className = "pz-sq pz-pt";
      make("pz-hint", sq, String(i + 1));
    });

    // legend: overlaid top-right of the plot — just numbers + labels, no cells.
    const legend = make("pz-legend-ov", plot);
    pts.forEach((pt, i) => {
      const item = make("", legend);
      const n = document.createElement("span"); n.className = "n"; n.textContent = String(i + 1);
      const l = document.createElement("span"); l.className = "l"; l.textContent = pt.label;
      item.appendChild(n); item.appendChild(l);
    });

    make("pz-xlabel", wrap, o.xLabel);
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
      { unit: "", cell: 50, colTitle: "", rowTitle: "", min: null, max: null }, opts
    );
    const vals = o.values.flat().filter((v) => v != null);
    const lo = o.min != null ? o.min : Math.min(...vals);
    const hi = o.max != null ? o.max : Math.max(...vals);
    const p = panel(container, o);
    const cols = o.colLabels.length;

    // column-axis title, centred over the data columns (above the headers)
    if (o.colTitle) {
      const top = make("pz-hm-coltitle", p, o.colTitle);
      top.style.marginLeft = ((o.rowTitle ? 18 : 0) + o.cell) + "px";
      top.style.width = cols * o.cell + "px";
    }

    const body = make("pz-hm-body", p);
    if (o.rowTitle) make("pz-hm-rowtitle", body, o.rowTitle); // vertical row-axis title
    const hm = make("pz-hm", body);
    hm.style.setProperty("--pz-cell", o.cell + "px");
    hm.style.gridTemplateColumns = `repeat(${cols + 1}, ${o.cell}px)`; // square header + cells

    make("pz-hm-head pz-hm-corner", hm);
    o.colLabels.forEach((cl) => make("pz-hm-head", hm, cl));
    o.rowLabels.forEach((rl, r) => {
      make("pz-hm-head", hm, rl);
      o.colLabels.forEach((_, c) => {
        const v = o.values[r][c];
        const cell = make("pz-hm-cell", hm);
        if (v == null) { cell.style.background = "transparent"; cell.style.borderColor = "transparent"; return; }
        cell.style.background = ramp((v - lo) / (hi - lo || 1)); // light greyscale ramp
        make("pz-hint", cell, fmt(v, o.unit));                   // value; dark text via CSS
      });
    });
    return p;
  }

  global.PuzzleCharts = { bar, scatter, heatmap, _letter: letter };
})(typeof window !== "undefined" ? window : this);
