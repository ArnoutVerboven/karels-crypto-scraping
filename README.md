# Housing decision simulator — buy vs. rent vs. lijfrente

A small, transparent financial model that compares four housing strategies for a
couple in Belgium and produces a **Markdown report** (`REPORT.md`, renders on
GitHub with images) covering a value bridge, sensitivity analysis and a
qualitative risk assessment.

**➡️ Read the analysis: [`REPORT.md`](REPORT.md)**

## The four scenarios

| # | Strategy |
|---|----------|
| **S1** | Buy the *lijfrente* home now, rent for 5 years, then **move into** the lijfrente home and keep it. |
| **S2** | Buy the *lijfrente* home now, rent for 5 years, then **sell** it and **buy a normal home**. |
| **S3** | **Rent** for 5 years, then **buy a normal home**. |
| **S4** | **Buy a normal home now** and live in it. |

Both the lijfrente home and the normal home have the same, appreciation-adjusted
market value.

## Quick start

```bash
pip install -r requirements.txt
python generate_report.py      # writes REPORT.md + report_images/*.png
```

Then open `REPORT.md` (on GitHub or any Markdown viewer). Charts are saved as
PNGs under `report_images/` and referenced from the report.

You can also print a quick console summary of the engine:

```bash
python housing_model.py
```

## How it works

- **`config.py`** — every assumption in one place (home value, cash, budget,
  rent, the lijfrente terms, mortgage rate/term, transaction & ownership costs,
  investment return, house appreciation, horizon, and the sensitivity grid).
  Change a number here and re-run to regenerate the whole report.
- **`housing_model.py`** — a monthly cash-flow engine. Each month it pays the
  housing outflows (rent, annuity, upkeep, mortgage principal & interest) from a
  fixed monthly budget, invests any surplus and draws down on any shortfall.
  Terminal **net worth = investment portfolio + home equity**. It also produces
  an exact, reconciling **value-bridge** decomposition (self-checked to the cent).
- **`charts.py`** — renders all figures to PNGs under `report_images/`.
- **`generate_report.py`** — runs the scenarios + sensitivity and assembles
  `REPORT.md`.

## Why all four end up close in absolute terms

Over a 30-year horizon every scenario ends up owning the **same debt-free home**,
so the differences in net worth come entirely from *opportunity cost, financing
and fees* — which is exactly what the value bridge isolates.

## Key modelling choices & caveats

- **Validated (Jul 2026):** Belgian 25y fixed mortgage market average ≈ 4.0%
  (model uses the user's 3.75%); Flanders own-home transaction cost ≈ 4%,
  non-primary ≈ 13%; selling ≈ 3%; no capital-gains tax on a private main home.
- The **lijfrente transaction tax** is modelled at the non-primary rate because
  the seller keeps usufruct for 5 years (you don't occupy it). This is the single
  biggest tax assumption — confirm with a notary and adjust
  `lijfrente_buy_cost_pct` in `config.py`.
- The lijfrente **annuity** is treated as fixed and, if the home is sold (S2), as
  continuing. Toggle `lijfrente_annuity_continues_after_sale`.
- The monthly **budget is fixed in nominal terms** (no income growth) and
  portfolio surpluses/shortfalls both accrue at the investment return.
- **Financing mode** (`financing_mode`) is pivotal to the S1-vs-S3 ranking. The
  default `rational` puts down the bank minimum (`min_down_pct`, 15%) and only
  puts down more when the mortgage rate exceeds the investment return (i.e. when
  paying down debt beats investing). Alternatives: `roll_equity` (always sink
  savings + sale proceeds into the home) and `target_down` (fixed % down, keep
  the rest invested).

Not financial advice — a planning model to compare structural trade-offs.
