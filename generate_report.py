"""
Build the self-contained HTML report: run the four scenarios, run the
sensitivity analysis, render the charts, and assemble everything into
`report.html`.

Run:  python generate_report.py
"""

import dataclasses
import datetime as dt

import charts
from config import Assumptions, SCENARIOS
from housing_model import run_all, net_worth_only

KEYS = list(SCENARIOS.keys())


# --------------------------------------------------------------------------- #
#  Sensitivity                                                                 #
# --------------------------------------------------------------------------- #
def winner_grid(A):
    grid = {}
    for inv in A.sensitivity_investment_returns:
        for app in A.sensitivity_appreciation_rates:
            AA = dataclasses.replace(A, investment_return_annual=inv,
                                     house_appreciation_annual=app)
            nws = {k: net_worth_only(k, AA) for k in KEYS}
            grid[(inv, app)] = max(nws, key=nws.get)
    return grid


def sweep(A, attr, values):
    series = {k: [] for k in KEYS}
    for v in values:
        AA = dataclasses.replace(A, **{attr: v})
        for k in KEYS:
            series[k].append(net_worth_only(k, AA))
    return list(values), series


# --------------------------------------------------------------------------- #
#  Formatting helpers                                                          #
# --------------------------------------------------------------------------- #
def eur(x):
    return f"€{x:,.0f}"


def pct(x):
    return f"{x * 100:g}%"


# --------------------------------------------------------------------------- #
#  HTML assembly                                                               #
# --------------------------------------------------------------------------- #
def build_html(A, results, grid, sweep_inv, sweep_app):
    ranked = sorted(KEYS, key=lambda k: results[k].summary["net_worth"],
                    reverse=True)
    best, worst = ranked[0], ranked[-1]
    nw = {k: results[k].summary["net_worth"] for k in KEYS}
    nwpv = {k: results[k].summary["net_worth_pv"] for k in KEYS}
    spread = nw[best] - nw[worst]

    c_bar = charts.net_worth_bar(results)
    c_bridge = charts.component_bridge(results)
    c_cash = charts.nominal_cashout(results)
    c_path = charts.net_worth_path(results, A)
    c_out = charts.outflow_path(results, A)
    c_heat = charts.sensitivity_heatmap(grid, A)
    c_lines = charts.sensitivity_lines(sweep_inv, sweep_app, A)

    def img(b64, cap):
        return (f'<figure><img src="data:image/png;base64,{b64}"/>'
                f'<figcaption>{cap}</figcaption></figure>')

    # ----- headline / recommendation -----
    invest_beats = A.investment_return_annual > A.house_appreciation_annual
    lij_total = A.lijfrente_upfront + A.lijfrente_monthly * A.lijfrente_years * 12
    pivot = (
        f"Two findings dominate. <b>(1) The lijfrente is priced attractively:</b> its total "
        f"outlay ({eur(lij_total)} = {eur(A.lijfrente_upfront)} up front + "
        f"{eur(A.lijfrente_monthly)}×{A.lijfrente_years*12} months) is <i>below</i> the "
        f"{eur(A.valuation_now)} market value and is spread over {A.lijfrente_years} years — "
        f"effectively cheap financing for the very same asset. That is why simply "
        f"<b>buying a normal home now (S4) is dominated</b> — it is the most expensive way to "
        f"own the identical house. <b>(2) The tie-breaker between the two front-runners</b> "
        f"(S1 lijfrente vs S3 rent-then-buy) is whether your investment return "
        f"({pct(A.investment_return_annual)}) beats house appreciation "
        f"({pct(A.house_appreciation_annual)}): it does in the base case, so keeping the "
        f"€200k invested longer (S3) edges ahead. Flip that relationship and the lijfrente "
        f"(S1) wins. See the sensitivity grid (Exhibit 6).")

    # ----- summary table -----
    metrics = [
        ("Net worth at horizon (nominal)", "net_worth", eur),
        ("Net worth in today's money (PV)", "net_worth_pv", eur),
        ("Peak monthly housing outflow", "peak_monthly_outflow", eur),
        ("Peak cumulative funding gap*", "peak_funding_gap", eur),
        ("Total mortgage interest", "total_interest", eur),
        ("Total rent paid", "total_rent", eur),
        ("Total lijfrente annuity", "total_annuity", eur),
        ("Total transaction/selling fees", "total_fees", eur),
        ("Total upkeep & property tax", "total_ownership", eur),
    ]
    rows = ""
    for label, field, fmt in metrics:
        cells = "".join(
            f'<td class="{ "best" if k==best else "" }">{fmt(results[k].summary[field])}</td>'
            for k in KEYS)
        rows += f"<tr><th>{label}</th>{cells}</tr>"
    head = "".join(
        f'<th class="sc {SCENARIOS[k]["short"].lower()}">{SCENARIOS[k]["short"]}'
        f'<span>{SCENARIOS[k]["name"]}</span></th>' for k in KEYS)

    rank_line = " &gt; ".join(
        f'<b>{SCENARIOS[k]["short"]}</b> ({eur(nw[k])})' for k in ranked)

    # ----- assumptions table -----
    A_rows = [
        ("Home value today (both homes)", eur(A.valuation_now)),
        ("Own cash capital", eur(A.cash_capital)),
        ("Comfortable monthly budget", eur(A.monthly_budget) + " / month"),
        ("Rent", eur(A.rent_monthly) + f" / month, indexed {pct(A.rent_indexation_annual)}/yr"),
        ("Lijfrente up-front ('bouquet')", eur(A.lijfrente_upfront)),
        ("Lijfrente annuity", eur(A.lijfrente_monthly) + f" / month for {A.lijfrente_years} years"),
        ("Move-in delay (seller usufruct)", f"{A.move_in_delay_years} years"),
        ("Mortgage rate / term", f"{pct(A.mortgage_rate_annual)} fixed over {A.mortgage_term_years} years"),
        ("Target down payment", pct(A.down_payment_pct) + " of financed price"),
        ("Buy costs — own home (Flanders)", pct(A.buy_cost_pct_primary) + " of price"),
        ("Buy costs — lijfrente (non-primary)", pct(A.lijfrente_buy_cost_pct) + " of value"),
        ("Selling costs", pct(A.sell_cost_pct) + " of price"),
        ("Upkeep + insurance + property tax", pct(A.ownership_cost_annual_pct) + " of value / yr (while occupying)"),
        ("Investment return", pct(A.investment_return_annual) + " / yr (nominal)"),
        ("House appreciation", pct(A.house_appreciation_annual) + " / yr (nominal)"),
        ("Comparison horizon", f"{A.horizon_years} years"),
    ]
    a_html = "".join(f"<tr><th>{n}</th><td>{v}</td></tr>" for n, v in A_rows)

    # ----- qualitative cards -----
    def gap(k):
        return eur(results[k].summary["peak_funding_gap"])
    quals = {
        "s1_lijfrente_movein": [
            ("Cash-flow strain (high)", f"For 5 years you pay rent <i>and</i> the "
             f"annuity <i>and</i> a mortgage simultaneously — peak outflow "
             f"{eur(results['s1_lijfrente_movein'].summary['peak_monthly_outflow'])}/mo "
             f"and a cumulative funding gap up to {gap('s1_lijfrente_movein')} that must "
             f"come from extra savings or income beyond the €3.6k budget."),
            ("5-year lock-in (high)", "You are committed to the lijfrente home and its "
             "location years before you can live there. If your life plans change "
             "(job, family, city) you are stuck or must sell into scenario 2."),
            ("Transaction-tax risk (high)", "The home is not your occupied sole dwelling "
             "at purchase, so it likely attracts the ~12% registration duty, not the 2% "
             "own-home rate. Confirm with a notary — this is ~€75k of swing."),
            ("Counterparty / annuity risk (medium)", "The construct depends on the seller "
             "and contract terms (indexation, what happens on early death, security on the "
             "property). Have the deed reviewed."),
            ("Upside", "You lock in today's price on a €750k home for a low up-front outlay "
             "and spread payments over 15 years — attractive if prices rise or you value "
             "certainty of that specific home."),
        ],
        "s2_lijfrente_then_normal": [
            ("Worst on fees (high)", f"You pay two sets of transaction taxes plus selling "
             f"costs — {eur(results['s2_lijfrente_then_normal'].summary['total_fees'])} total — "
             f"and the largest mortgage interest bill. Double-churning property is expensive."),
            ("Annuity may continue after sale (high)", "Unless the annuity legally transfers to "
             "the buyer, you keep paying €2,220/mo for the remaining 10 years on a home you no "
             "longer own. Model default assumes it continues; verify the contract."),
            ("Only makes sense as a fallback", "This is essentially scenario 1 gone wrong — "
             "choose it only if you deliberately want the lijfrente as a 5-year financial "
             "bridge and always intended to buy elsewhere."),
            ("Speculative CGT risk", "Selling a non-primary home within 5 years can trigger "
             "16.5% capital-gains tax in Belgium. Timing the sale just past 5 years matters."),
        ],
        "s3_rent_then_normal": [
            ("Lowest strain, most flexible (upside)", f"Comfortably within budget "
             f"(peak {eur(results['s3_rent_then_normal'].summary['peak_monthly_outflow'])}/mo, "
             f"no funding gap). Renting keeps you mobile for 5 years and your €200k stays "
             f"invested and compounding."),
            ("Timing / price risk (high)", "You buy in 5 years at an unknown price. If homes "
             "appreciate faster than assumed you pay more and this advantage shrinks or reverses "
             "(see Exhibit 6)."),
            ("Rate risk (medium)", "The mortgage rate in 5 years is unknown; a materially higher "
             "rate would erode the edge."),
            ("Rent is 'lost' money (medium)", "≈€84k of rent over 5 years buys no equity — but "
             "the invested capital more than compensates while returns exceed appreciation."),
        ],
        "s4_buy_normal_now": [
            ("Simplest & most secure (upside)", "One transaction, no lock-in games, you own and "
             "live in your home immediately with full price certainty and stability."),
            ("Opportunity cost is the catch (high)", f"€200k plus every spare euro is tied up in "
             f"an asset appreciating at {pct(A.house_appreciation_annual)} instead of investments at "
             f"{pct(A.investment_return_annual)}; the biggest mortgage means "
             f"{eur(results['s4_buy_normal_now'].summary['total_interest'])} of interest."),
            ("Budget is tight long-term (medium)", f"Mortgage + rising upkeep can exceed the €3.6k "
             f"budget in later years (funding gap up to {gap('s4_buy_normal_now')}), assuming the "
             f"budget is not raised with income growth."),
            ("Wins if property outperforms", "If appreciation meets or beats your investment "
             "return, buying now becomes the strongest option — it has the most exposure to the home."),
        ],
    }
    cards = ""
    for k in ranked:
        items = "".join(f"<li><b>{t}.</b> {d}</li>" for t, d in quals[k])
        cards += (f'<div class="card" style="border-top:5px solid {charts.COLORS[k]}">'
                  f'<h3>{SCENARIOS[k]["short"]} · {SCENARIOS[k]["name"]}</h3>'
                  f'<p class="desc">{SCENARIOS[k]["desc"]}</p><ul>{items}</ul></div>')

    today = dt.date.today().strftime("%d %b %Y")
    css = """
    :root{--ink:#0b1f33;--mut:#5b6b7b;--line:#e4e9ee;--bg:#f6f8fa;}
    *{box-sizing:border-box}
    body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink);background:#fff;line-height:1.5}
    .wrap{max-width:1040px;margin:0 auto;padding:44px 30px 90px}
    header{border-bottom:3px solid var(--ink);padding-bottom:18px;margin-bottom:8px}
    .kicker{letter-spacing:.16em;text-transform:uppercase;font-size:12px;color:var(--mut)}
    h1{font-size:30px;margin:6px 0 2px}
    h2{font-size:21px;margin:44px 0 6px;padding-bottom:6px;border-bottom:1px solid var(--line)}
    h3{font-size:16px;margin:0 0 4px}
    .sub{color:var(--mut);font-size:14px}
    .answer{background:var(--bg);border-left:5px solid #2ea043;padding:18px 22px;
            margin:22px 0;border-radius:0 8px 8px 0}
    .answer h2{border:0;margin:0 0 8px;font-size:18px}
    .answer .rec{font-size:17px;font-weight:600}
    table{border-collapse:collapse;width:100%;font-size:13.5px;margin:14px 0}
    th,td{border:1px solid var(--line);padding:8px 10px;text-align:right}
    th:first-child,td:first-child{text-align:left}
    thead th{background:var(--ink);color:#fff;vertical-align:top;font-weight:600}
    thead th.sc span{display:block;font-weight:400;font-size:11px;opacity:.85;max-width:150px}
    tbody th{background:var(--bg);font-weight:600}
    td.best{background:#e9f7ee;font-weight:700}
    figure{margin:18px 0}
    figure img{width:100%;border:1px solid var(--line);border-radius:8px}
    figcaption{color:var(--mut);font-size:12.5px;margin-top:6px}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
    .cards{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:14px}
    .card{border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:#fff;
          box-shadow:0 1px 3px rgba(0,0,0,.04)}
    .card .desc{color:var(--mut);font-size:13px;margin:2px 0 10px}
    .card ul{margin:0;padding-left:18px}.card li{margin:7px 0;font-size:13.5px}
    .note{font-size:12.5px;color:var(--mut)}
    .foot{margin-top:60px;border-top:1px solid var(--line);padding-top:16px;
          font-size:12.5px;color:var(--mut)}
    code{background:var(--bg);padding:1px 5px;border-radius:4px}
    @media(max-width:820px){.cards,.grid2{grid-template-columns:1fr}}
    """

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Housing decision — scenario analysis</title><style>{css}</style></head>
<body><div class="wrap">
<header>
  <div class="kicker">Personal finance · decision analysis</div>
  <h1>Buy, rent, or lijfrente? A four-scenario comparison</h1>
  <div class="sub">Prepared {today} · horizon {A.horizon_years} years · all figures in EUR ·
  base case: {pct(A.investment_return_annual)} investing vs {pct(A.house_appreciation_annual)} appreciation</div>
</header>

<div class="answer">
  <h2>The answer, up front</h2>
  <p class="rec">Under the base-case assumptions, <b>{SCENARIOS[best]["name"]} ({SCENARIOS[best]["short"]})</b>
  maximises long-run wealth ({eur(nw[best])} at {A.horizon_years}y), and <b>{SCENARIOS[worst]["name"]}
  ({SCENARIOS[worst]["short"]})</b> is weakest ({eur(nw[worst])}).</p>
  <p>Ranking: {rank_line}. The gap between best and worst is <b>{eur(spread)}</b>
  (~{spread/nw[worst]*100:.0f}% of net worth). All four scenarios end owning the
  same debt-free home, so <b>every difference is opportunity cost, financing and fees — not the house itself.</b></p>
  <p>{pivot}</p>
</div>

<h2>1 · How much wealth each path builds</h2>
{img(c_bar, "Exhibit 1 — Net worth at the "+str(A.horizon_years)+"-year horizon. Labels show the shortfall vs. the best scenario. Every scenario owns an identical, fully paid-off home worth "+eur(results[best].summary['terminal_home'])+", so the bars differ only by the investment portfolio built alongside it.")}

<h2>2 · Why they differ — the value bridge</h2>
<p class="sub">Only factors that <b>differ</b> between scenarios are shown, expressed in today's money
(present value, discounted at the investment return so each euro is scored at its opportunity cost).
Bars below zero destroy value; the green "property value vs investing" bar is the net payoff from
owning bricks after charging the opportunity cost of the equity tied up in them.</p>
{img(c_bridge, "Exhibit 2 — Present-value contribution of each driver. Note: for S1/S2 the lijfrente annuity (shown separately) is effectively the instalment price of the home, so read it together with the property-value bar.")}
{img(c_cash, "Exhibit 3 — Total cash actually paid out over the horizon, by category (nominal). This excludes down payment and mortgage principal, which are recoverable as home equity. It is the clearest view of the €2,220/mo annuity, rent and interest burden.")}
<p class="note"><b>Watch the paradox:</b> {SCENARIOS[worst]["short"]} has the <i>lowest</i> cash out of pocket
({eur(results[worst].summary['total_rent']+results[worst].summary['total_annuity']+results[worst].summary['total_interest']+results[worst].summary['total_fees']+results[worst].summary['total_ownership'])})
yet the <i>lowest</i> net worth — because it sinks the most capital into a home appreciating at
{pct(A.house_appreciation_annual)} instead of investments earning {pct(A.investment_return_annual)}.
Out-of-pocket cost and wealth are not the same thing; opportunity cost is invisible in a bank statement.</p>

<h2>3 · The numbers</h2>
<table><thead><tr><th>Metric</th>{head}</tr></thead><tbody>{rows}</tbody></table>
<p class="note">*Peak cumulative funding gap = the largest amount by which required spending has
exceeded the €{A.monthly_budget:,.0f}/mo budget on a compounding basis, i.e. extra savings/borrowing
needed on top of budget. A positive number is a red flag for affordability, not for final wealth.</p>

<h2>4 · Timing: wealth and cash-flow over the years</h2>
<div class="grid2">
{img(c_path, "Exhibit 4 — Net-worth trajectory. Lines converge as homes are paid off and appreciate identically; the ordering is set by investing behaviour along the way.")}
{img(c_out, "Exhibit 5 — Monthly housing outflow vs. the €"+f"{A.monthly_budget:,.0f}"+" budget. S1/S2 breach the budget heavily in the first 5 years (rent + annuity + mortgage at once).")}
</div>

<h2>5 · What could change the answer — sensitivity</h2>
<p class="sub">The ranking hinges almost entirely on two uncertain numbers: what you earn investing,
and how fast houses appreciate. The grid shows the winning scenario across a realistic range.</p>
<div class="grid2">
{img(c_heat, "Exhibit 6 — Winning scenario by investment return (rows) and house appreciation (columns). Your base case is outlined. When appreciation approaches or exceeds investment return, buying earlier/more property (S4/S1) takes over.")}
{img(c_lines, "Exhibit 7 — Net worth of each scenario as one assumption varies (the other held at base). Where lines cross, the recommendation changes.")}
</div>

<h2>6 · Risks &amp; qualitative considerations</h2>
<p class="sub">Ordered best-to-worst on the base-case finances. The financial gaps are modest
(~{spread/nw[worst]*100:.0f}%) relative to these non-financial factors, which may matter more.</p>
<div class="cards">{cards}</div>

<h2>7 · Key assumptions</h2>
<p class="sub">All of these live in <code>config.py</code> and can be changed centrally; re-run
<code>python generate_report.py</code> to regenerate this report.</p>
<table><tbody>{a_html}</tbody></table>

<div class="foot">
<p><b>Method.</b> A monthly cash-flow engine simulates each scenario: housing outflows (rent,
annuity, upkeep, mortgage principal &amp; interest) are paid from a fixed monthly budget and any
surplus is invested; shortfalls draw the portfolio down. Terminal net worth = investment portfolio +
home equity. Because budget and starting cash are identical and all scenarios end owning the same
debt-free home, the value bridge (Exhibit 2) is an exact reconciling decomposition of the net-worth
differences (verified to the cent in code).</p>
<p><b>Validated (Jul 2026).</b> Belgian 25y fixed mortgage market average ≈4.0% (we use your 3.75%);
Flanders own-home transaction cost ≈4%, non-primary ≈13%; selling costs ≈3%; no CGT on a private
main residence. <b>Simplifications:</b> fixed nominal budget (no income growth); portfolio surpluses
and shortfalls both accrue at the investment return; the lijfrente annuity is treated as fixed and,
after a sale, as continuing. Taxes on the lijfrente construct (registration base, primary-residence
eligibility, CGT on an early sale) are the largest modelling uncertainties — confirm with a notary.</p>
<p>Not financial advice. A planning model to compare structural trade-offs, not a prediction.</p>
</div>

</div></body></html>"""
    return html


def main():
    A = Assumptions()
    results = run_all(A)
    grid = winner_grid(A)
    sweep_inv = sweep(A, "investment_return_annual",
                      [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07])
    sweep_app = sweep(A, "house_appreciation_annual",
                      [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05])
    html = build_html(A, results, grid, sweep_inv, sweep_app)
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote report.html")
    ranked = sorted(KEYS, key=lambda k: results[k].summary["net_worth"], reverse=True)
    for i, k in enumerate(ranked, 1):
        print(f"  {i}. {SCENARIOS[k]['short']} {SCENARIOS[k]['name']}: "
              f"{eur(results[k].summary['net_worth'])}")


if __name__ == "__main__":
    main()
