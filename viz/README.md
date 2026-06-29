# Puzzle-themed research visuals

Dependency-free HTML/CSS/JS to render the research charts in the **Karel's Crypto**
puzzle theme (yellow ground, white puzzle cells with shared gridlines, corner
"hint" numbers, clue-style labels). Drop in your own data — no build step.

## Files
- `puzzle-charts.css` — the theme (colors via CSS variables at the top).
- `puzzle-charts.js` — `PuzzleCharts.bar / scatter / heatmap`.
- `index.html` — gallery + copy-paste template wired to example data.
- `_shot.html` — single-chart page used to render the PNGs in `screenshots/`.

## Quick start
Open `index.html` in a browser, or copy the `<link>`, `<script>`, and a render
call into your page. Each render call takes a container (element or selector) and
an options object.

```html
<link rel="stylesheet" href="puzzle-charts.css" />
<div id="chart"></div>
<script src="puzzle-charts.js"></script>
<script>
  PuzzleCharts.bar("#chart", { title: "Model accuracy", unit: "%", step: 10, data: [
    { label: "gemini-3.5-flash", value: 46.7 },
    { label: "gpt-5.5", value: 43.3 },
  ]});
</script>
```

## Bar chart — `PuzzleCharts.bar(el, opts)`
Looks like a puzzle row: sorted high→low, each bar is a run of white squares
(longer = higher), the last square cropped for the fraction. Row labels are
clue-style (`A.`, `B.`, … auto-prefixed). No x-axis; corner **hint** numbers mark
intervals.

| option | default | meaning |
| --- | --- | --- |
| `data` | — | `[{label, value}]` |
| `step` | `10` | value per square (e.g. 10%) |
| `hintEvery` | `2` | a hint number every N squares (0, 20, …) |
| `unit` | `"%"` | appended to value labels |
| `labelWidth` | `240` | px width of the clue column |
| `showValues` | `true` | exact value after each bar |
| `sort` | `true` | sort descending |
| `title`, `subtitle`, `cell` | — | header text; cell size in px |

## Scatter — `PuzzleCharts.scatter(el, opts)`
A light-yellow **cross** (the "solution word") forms the axes; each point is a
numbered white cell; a legend maps numbers → labels (+ coordinates).

| option | default | meaning |
| --- | --- | --- |
| `points` | — | `[{label, x, y}]` |
| `xLabel`, `yLabel` | `"x"`,`"y"` | axis titles |
| `xUnit`, `yUnit` | `""` | tick/legend units |
| `xMin/xMax/yMin/yMax` | auto | axis range |
| `cols`, `rows` | `14`, `11` | grid resolution |
| `legendCols` | `2` | legend columns |
| `showCoords` | `true` | show `(x, y)` in the legend |

## Heatmap — `PuzzleCharts.heatmap(el, opts)`
A grid shaded in yellows (pale→gold); the **hint value is the number** in each
cell.

| option | default | meaning |
| --- | --- | --- |
| `rowLabels`, `colLabels` | — | axis headers |
| `values` | — | 2-D array `[rows][cols]` (use `null` to blank a cell) |
| `unit` | `""` | appended to each value |
| `min`, `max` | auto | color-ramp bounds |
| `colTitle` | `""` | label under the grid |
| `cell` | `46` | cell size in px |

## Plugging in the real research data
The example data mirrors the report:
- **bar** / **scatter** ← `karels-crypto-solving/research/cross_provider/benchmark.json`
  (`results[].model`, `.accuracy`, `.est_cost_usd`, `.correct` → cost/correct).
- **heatmap** ← `karels-crypto-solving/research/reveal/reveal_analysis.json`
  (`models[].by_cell["{bucket}@{frac}"].accuracy`).

## Regenerating the screenshots
```bash
google-chrome-stable --headless=new --hide-scrollbars --force-device-scale-factor=2 \
  --screenshot=screenshots/bar.png --window-size=470,560 "file://$PWD/_shot.html?c=bar"
# c=scatter (600,720), c=heatmap (380,420)
```
