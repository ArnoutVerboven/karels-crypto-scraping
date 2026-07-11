"""
Build the Markdown report: run the four scenarios, run the sensitivity
analysis, render the charts to `report_images/`, and assemble `REPORT.md`
(renders on GitHub, images included).

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


def sc(k):
    return SCENARIOS[k]["short"]


def name(k):
    return SCENARIOS[k]["name"]


# --------------------------------------------------------------------------- #
#  Markdown assembly                                                           #
# --------------------------------------------------------------------------- #
def build_markdown(A, results, grid, sweep_inv, sweep_app):
    ranked = sorted(KEYS, key=lambda k: results[k].summary["net_worth"],
                    reverse=True)
    best, worst = ranked[0], ranked[-1]
    nw = {k: results[k].summary["net_worth"] for k in KEYS}
    spread = nw[best] - nw[worst]
    lij_total = A.lijfrente_upfront + A.lijfrente_monthly * A.lijfrente_years * 12

    # render charts (returns relative paths)
    p_bar = charts.net_worth_bar(results)
    p_bridge = charts.component_bridge(results)
    p_cash = charts.nominal_cashout(results)
    p_path = charts.net_worth_path(results, A)
    p_out = charts.outflow_path(results, A)
    p_port = charts.portfolio_path(results, A)
    p_heat = charts.sensitivity_heatmap(grid, A)
    p_lines = charts.sensitivity_lines(sweep_inv, sweep_app, A)

    today = dt.date.today().strftime("%d %b %Y")
    L = []  # lines
    def w(s=""):
        L.append(s)

    # ---------------- header ----------------
    w("# Buy, rent, or lijfrente? A four-scenario comparison")
    w()
    w(f"*Personal-finance decision analysis · prepared {today} · horizon "
      f"{A.horizon_years} years · all figures in EUR · base case: "
      f"{pct(A.investment_return_annual)} investing vs "
      f"{pct(A.house_appreciation_annual)} appreciation*")
    w()
    w("**Scenarios compared**")
    w()
    w("| | Strategy |")
    w("|---|---|")
    for k in KEYS:
        w(f"| **{sc(k)}** | {SCENARIOS[k]['desc']} |")
    w()

    # ---------------- answer up front ----------------
    rank_line = " > ".join(f"**{sc(k)}** ({eur(nw[k])})" for k in ranked)
    w("## The answer, up front")
    w()
    w(f"> Under the base-case assumptions, **{name(best)} ({sc(best)})** maximises "
      f"long-run wealth ({eur(nw[best])} at {A.horizon_years}y), and "
      f"**{name(worst)} ({sc(worst)})** is weakest ({eur(nw[worst])}).")
    w(">")
    w(f"> Ranking: {rank_line}. The gap between best and worst is **{eur(spread)}** "
      f"(~{spread / nw[worst] * 100:.0f}% of net worth). All four scenarios end owning "
      f"the **same debt-free home**, so *every difference is opportunity cost, "
      f"financing and fees — not the house itself.*")
    w()
    second = ranked[1]
    gap_top2 = nw[best] - nw[second]
    w("**Two findings dominate:**")
    w()
    w(f"1. **The lijfrente is priced attractively.** Its total outlay "
      f"({eur(lij_total)} = {eur(A.lijfrente_upfront)} up front + "
      f"{eur(A.lijfrente_monthly)} × {A.lijfrente_years * 12} months) is *below* the "
      f"{eur(A.valuation_now)} market value, is spread over {A.lijfrente_years} years, "
      f"and needs almost no mortgage — effectively cheap financing for the very same "
      f"asset. Conversely, **buying a normal home now ({sc('s4_buy_normal_now')})** is "
      f"the most expensive way to own the identical house: the biggest mortgage and the "
      f"most interest ({eur(results['s4_buy_normal_now'].summary['total_interest'])}).")
    invest_beats_rate = A.investment_return_annual > A.mortgage_rate_annual
    w(f"2. **The two leaders — {sc(best)} and {sc(second)} — are within "
      f"{eur(gap_top2)} of each other** (~{gap_top2 / nw[second] * 100:.0f}%), and which "
      f"one wins comes down to a single comparison: **your investment return "
      f"({pct(A.investment_return_annual)}) vs. your mortgage rate "
      f"({pct(A.mortgage_rate_annual)}).** With the *rational* financing rule, whenever "
      f"investing beats the mortgage you borrow the maximum and keep cash invested — "
      f"which favours the rent-and-invest route ({sc('s3_rent_then_normal')}); when the "
      f"mortgage is dearer you pay it down, which favours the near-mortgage-free lijfrente "
      f"({sc('s1_lijfrente_movein')}). Here investing "
      f"{'beats' if invest_beats_rate else 'trails'} the mortgage, so **{sc(best)} leads**. "
      f"House appreciation vs. your investment return is the second lever (it decides "
      f"rent-vs-own timing). See Exhibits 7–8.")
    w()

    # ---------------- exhibit 1 ----------------
    w("## 1 · How much wealth each path builds")
    w()
    w(f"![Exhibit 1 — terminal net worth]({p_bar})")
    w()
    w(f"*Exhibit 1 — Net worth at the {A.horizon_years}-year horizon. Left: absolute "
      f"values are nearly identical because every scenario owns the same fully paid-off "
      f"home (worth {eur(results[best].summary['terminal_home'])}). Right: the same data "
      f"as a difference vs. the weakest scenario — this is where the decision actually "
      f"matters.*")
    w()

    # ---------------- exhibit 2/3 ----------------
    w("## 2 · Why they differ — the value bridge")
    w()
    w("Only factors that **differ** between scenarios are shown, in today's money "
      "(present value, discounted at the investment return so each euro is scored at "
      "its opportunity cost). Bars below zero destroy value; the *property value vs "
      "investing* bar is the net payoff from owning bricks after charging the "
      "opportunity cost of the equity tied up in them.")
    w()
    w(f"![Exhibit 2 — value bridge]({p_bridge})")
    w()
    w("*Exhibit 2 — Present-value contribution of each driver. Note: for "
      f"{sc('s1_lijfrente_movein')}/{sc('s2_lijfrente_then_normal')} the lijfrente "
      "annuity (shown separately) is effectively the instalment price of the home, so "
      "read it together with the property-value bar.*")
    w()
    w(f"![Exhibit 3 — cash out of pocket]({p_cash})")
    w()
    w("*Exhibit 3 — Total cash actually paid out over the horizon, by category "
      "(nominal). Excludes down payment and mortgage principal, which are recoverable "
      "as home equity. Clearest view of the €2,220/mo annuity, rent and interest burden.*")
    w()
    worst_cash = (results[worst].summary['total_rent']
                  + results[worst].summary['total_annuity']
                  + results[worst].summary['total_interest']
                  + results[worst].summary['total_fees']
                  + results[worst].summary['total_ownership'])
    w(f"> **Watch the paradox:** {sc(worst)} has the *lowest* cash out of pocket "
      f"({eur(worst_cash)}) yet the *lowest* net worth — because it sinks the most "
      f"capital into a home appreciating at {pct(A.house_appreciation_annual)} instead "
      f"of investments earning {pct(A.investment_return_annual)}. Out-of-pocket cost and "
      f"wealth are not the same thing; opportunity cost is invisible in a bank statement.")
    w()

    # ---------------- numbers table ----------------
    w("## 3 · The numbers")
    w()
    w("Legend: " + " · ".join(f"**{sc(k)}** = {name(k)}" for k in KEYS) + ".")
    w()
    metrics = [
        ("Net worth at horizon (nominal)", "net_worth", eur),
        ("Net worth in today's money (PV)", "net_worth_pv", eur),
        ("Peak monthly housing outflow", "peak_monthly_outflow", eur),
        ("Peak cumulative funding gap \\*", "peak_funding_gap", eur),
        ("Total mortgage interest", "total_interest", eur),
        ("Total rent paid", "total_rent", eur),
        ("Total lijfrente annuity", "total_annuity", eur),
        ("Total transaction/selling fees", "total_fees", eur),
        ("Total upkeep & property tax", "total_ownership", eur),
    ]
    hdr = [f"**{sc(k)} ✅**" if k == best else sc(k) for k in KEYS]
    w("| Metric | " + " | ".join(hdr) + " |")
    w("|" + "---|" * (len(KEYS) + 1))
    for label, field, fmt in metrics:
        cells = [fmt(results[k].summary[field]) for k in KEYS]
        w(f"| {label} | " + " | ".join(cells) + " |")
    w()
    w(f"✅ = recommended scenario ({name(best)}). Note that lower is better for the "
      f"cost rows, so the recommended column is *not* the smallest in every row — the "
      f"whole point is that it makes the best overall trade-off.")
    w()
    w(f"\\* Peak cumulative funding gap = the largest amount by which required spending "
      f"has exceeded the {eur(A.monthly_budget)}/mo budget on a compounding basis, i.e. "
      f"extra savings/borrowing needed on top of budget. A red flag for *affordability*, "
      f"not for final wealth.")
    w()

    # ---------------- timing ----------------
    w("## 4 · Timing: wealth and cash-flow over the years")
    w()
    w(f"![Exhibit 4 — net-worth trajectory]({p_path})")
    w()
    w("*Exhibit 4 — Net-worth trajectory. Lines converge as homes are paid off and "
      "appreciate identically; the ordering is set by investing behaviour along the way.*")
    w()
    w(f"![Exhibit 5 — monthly outflow vs budget]({p_out})")
    w()
    w(f"*Exhibit 5 — Monthly housing outflow vs. the {eur(A.monthly_budget)} budget. "
      f"A high line is not the same as unaffordable: when the mortgage is cheaper than "
      f"investing, the rational choice is to keep cash invested and let it cover the gap. "
      f"{sc('s2_lijfrente_then_normal')} looks heavy (small mortgage + the continuing "
      f"{eur(A.lijfrente_monthly)}/mo annuity), but its true strain is small — its funding "
      f"gap is only {eur(results['s2_lijfrente_then_normal'].summary['peak_funding_gap'])} "
      f"because the home-1 sale proceeds sit in the portfolio (Exhibit 6) and cover it.*")
    w()
    w(f"![Exhibit 6 — investment portfolio balance]({p_port})")
    w()
    w(f"*Exhibit 6 — The investment-portfolio balance that sits behind the outflow. This "
      f"is the cushion that funds any month where housing costs exceed the "
      f"{eur(A.monthly_budget)} budget. A line dipping below zero is the real red flag "
      f"(money you'd have to borrow on top of the budget); staying well above zero means "
      f"the high outflow is comfortably self-funded.*")
    w()

    # ---------------- sensitivity ----------------
    w("## 5 · What could change the answer — sensitivity")
    w()
    w("The ranking hinges almost entirely on two uncertain numbers: what you earn "
      "investing, and how fast houses appreciate.")
    w()
    w(f"![Exhibit 7 — sensitivity grid]({p_heat})")
    w()
    w("*Exhibit 7 — Winning scenario by investment return (rows) and house appreciation "
      "(columns); your base case is outlined. When appreciation approaches or exceeds "
      "investment return, owning property earlier/cheaper (S1/S2) takes over.*")
    w()
    w(f"![Exhibit 8 — sensitivity lines]({p_lines})")
    w()
    w("*Exhibit 8 — Net worth of each scenario as one assumption varies (the other held "
      "at base). Where lines cross, the recommendation changes.*")
    w()

    # ---------------- qualitative ----------------
    quals = _qualitative(A, results)
    w("## 6 · Risks & qualitative considerations")
    w()
    w(f"Ordered best-to-worst on the base-case finances. The financial gaps are modest "
      f"(~{spread / nw[worst] * 100:.0f}%) relative to these non-financial factors, "
      f"which may matter more.")
    w()
    for k in ranked:
        w(f"### {sc(k)} · {name(k)}")
        w()
        w(f"*{SCENARIOS[k]['desc']}*")
        w()
        for title, desc in quals[k]:
            w(f"- **{title}.** {desc}")
        w()

    # ---------------- assumptions ----------------
    w("## 7 · Key assumptions")
    w()
    w("All of these live in `config.py` and can be changed centrally; re-run "
      "`python generate_report.py` to regenerate this report.")
    w()
    A_rows = [
        ("Home value today (both homes)", eur(A.valuation_now)),
        ("Own cash capital", eur(A.cash_capital)),
        ("Comfortable monthly budget", eur(A.monthly_budget) + " / month"),
        ("Rent", eur(A.rent_monthly) + f" / month, indexed {pct(A.rent_indexation_annual)}/yr"),
        ("Lijfrente up-front ('bouquet')", eur(A.lijfrente_upfront)),
        ("Lijfrente annuity", eur(A.lijfrente_monthly) + f" / month for {A.lijfrente_years} years"),
        ("Move-in delay (seller usufruct)", f"{A.move_in_delay_years} years"),
        ("Mortgage rate / term", f"{pct(A.mortgage_rate_annual)} fixed over {A.mortgage_term_years} years"),
        ("Financing mode", f"`{A.financing_mode}`" + (
            " — bank-minimum down payment; put down more only when the mortgage rate "
            "exceeds the investment return (then invest vs. pay-down is a real choice)"
            if A.financing_mode == "rational" else "")),
        ("Bank minimum down payment", pct(A.min_down_pct) + " of financed price"),
        ("Buy costs — own home (Flanders)", pct(A.buy_cost_pct_primary) + " of price"),
        ("Buy costs — lijfrente (non-primary)", pct(A.lijfrente_buy_cost_pct) + " of value"),
        ("Selling costs", pct(A.sell_cost_pct) + " of price"),
        ("Upkeep + insurance + property tax", pct(A.ownership_cost_annual_pct) + " of value / yr (while occupying)"),
        ("Investment return", pct(A.investment_return_annual) + " / yr (nominal)"),
        ("House appreciation", pct(A.house_appreciation_annual) + " / yr (nominal)"),
        ("Comparison horizon", f"{A.horizon_years} years"),
    ]
    w("| Assumption | Value |")
    w("|---|---|")
    for n, v in A_rows:
        w(f"| {n} | {v} |")
    w()

    # ---------------- method ----------------
    w("## Method & caveats")
    w()
    w("**Method.** A monthly cash-flow engine simulates each scenario: housing outflows "
      "(rent, annuity, upkeep, mortgage principal & interest) are paid from a fixed "
      "monthly budget and any surplus is invested; shortfalls draw the portfolio down. "
      "Terminal net worth = investment portfolio + home equity. Because budget and "
      "starting cash are identical and all scenarios end owning the same debt-free home, "
      "the value bridge (Exhibit 2) is an exact reconciling decomposition of the "
      "net-worth differences (verified to the cent in code).")
    w()
    w("**Validated (Jul 2026).** Belgian 25y fixed mortgage market average ≈ 4.0% (we use "
      "your 3.75%); Flanders own-home transaction cost ≈ 4%, non-primary ≈ 13%; selling "
      "costs ≈ 3%; no capital-gains tax on a private main residence.")
    w()
    w("**Simplifications.** Fixed nominal budget (no income growth); portfolio surpluses "
      "and shortfalls both accrue at the investment return; the lijfrente annuity is "
      "treated as fixed and, after a sale, as continuing. Taxes on the lijfrente construct "
      "(registration base, primary-residence eligibility, CGT on an early sale) are the "
      "largest modelling uncertainties — confirm with a notary. Each is centrally tunable "
      "in `config.py`.")
    w()
    w("*Not financial advice — a planning model to compare structural trade-offs, not a "
      "prediction.*")
    w()

    return "\n".join(L)


def _qualitative(A, results):
    def gap(k):
        return eur(results[k].summary["peak_funding_gap"])
    return {
        "s1_lijfrente_movein": [
            ("Cash-flow strain (high)", f"For 5 years you pay rent *and* the annuity "
             f"*and* a mortgage simultaneously — peak outflow "
             f"{eur(results['s1_lijfrente_movein'].summary['peak_monthly_outflow'])}/mo "
             f"and a cumulative funding gap up to {gap('s1_lijfrente_movein')} that must "
             f"come from extra savings or income beyond the €3.6k budget."),
            ("5-year lock-in (high)", "You are committed to the lijfrente home and its "
             "location years before you can live there. If your life plans change (job, "
             "family, city) you are stuck or must sell into scenario 2."),
            ("Transaction-tax risk (high)", "The home is not your occupied sole dwelling "
             "at purchase, so it likely attracts the ~12% registration duty, not the 2% "
             "own-home rate. Confirm with a notary — this is ~€75k of swing."),
            ("Counterparty / annuity risk (medium)", "The construct depends on the seller "
             "and contract terms (indexation, what happens on early death, security on the "
             "property). Have the deed reviewed."),
            ("Upside", "You lock in today's price on a €750k home for a low up-front "
             "outlay and spread payments over 15 years — attractive if prices rise or you "
             "value certainty of that specific home."),
        ],
        "s2_lijfrente_then_normal": [
            ("Worst on fees (high)", f"You pay two sets of transaction taxes plus selling "
             f"costs — {eur(results['s2_lijfrente_then_normal'].summary['total_fees'])} "
             f"total — and the largest mortgage interest bill. Double-churning property "
             f"is expensive."),
            ("Annuity may continue after sale (high)", "Unless the annuity legally "
             "transfers to the buyer, you keep paying €2,220/mo for the remaining 10 "
             "years on a home you no longer own. Model default assumes it continues; "
             "verify the contract."),
            ("Only makes sense as a fallback", "This is essentially scenario 1 gone wrong "
             "— choose it only if you deliberately want the lijfrente as a 5-year "
             "financial bridge and always intended to buy elsewhere."),
            ("Speculative CGT risk", "Selling a non-primary home within 5 years can "
             "trigger 16.5% capital-gains tax in Belgium. Timing the sale just past 5 "
             "years matters."),
        ],
        "s3_rent_then_normal": [
            ("Lowest strain, most flexible (upside)", f"Comfortably within budget (peak "
             f"{eur(results['s3_rent_then_normal'].summary['peak_monthly_outflow'])}/mo, "
             f"no funding gap). Renting keeps you mobile for 5 years and your €200k stays "
             f"invested and compounding."),
            ("Timing / price risk (high)", "You buy in 5 years at an unknown price. If "
             "homes appreciate faster than assumed you pay more and this advantage shrinks "
             "or reverses (see Exhibit 7)."),
            ("Rate risk (medium)", "The mortgage rate in 5 years is unknown; a materially "
             "higher rate would erode the edge."),
            ("Rent is 'lost' money (medium)", "≈€84k of rent over 5 years buys no equity — "
             "but the invested capital more than compensates while returns exceed "
             "appreciation."),
        ],
        "s4_buy_normal_now": [
            ("Simplest & most secure (upside)", "One transaction, no lock-in games, you "
             "own and live in your home immediately with full price certainty and "
             "stability."),
            ("Opportunity cost is the catch (high)", f"€200k plus every spare euro is tied "
             f"up in an asset appreciating at {pct(A.house_appreciation_annual)} instead "
             f"of investments at {pct(A.investment_return_annual)}; the biggest mortgage "
             f"means {eur(results['s4_buy_normal_now'].summary['total_interest'])} of "
             f"interest."),
            ("Budget is tight long-term (medium)", f"Mortgage + rising upkeep can exceed "
             f"the €3.6k budget in later years (funding gap up to "
             f"{gap('s4_buy_normal_now')}), assuming the budget is not raised with income "
             f"growth."),
            ("Wins if property outperforms", "If appreciation meets or beats your "
             "investment return, buying now becomes the strongest option — it has the "
             "most exposure to the home."),
        ],
    }


def main():
    # clear old chart files so stale (content-hashed) images don't accumulate
    import glob
    import os
    for f in glob.glob(os.path.join(charts.IMAGES_DIR, "*.png")):
        os.remove(f)

    A = Assumptions()
    results = run_all(A)
    grid = winner_grid(A)
    sweep_inv = sweep(A, "investment_return_annual",
                      [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07])
    sweep_app = sweep(A, "house_appreciation_annual",
                      [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05])
    md = build_markdown(A, results, grid, sweep_inv, sweep_app)
    with open("REPORT.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("Wrote REPORT.md and charts to report_images/")
    ranked = sorted(KEYS, key=lambda k: results[k].summary["net_worth"], reverse=True)
    for i, k in enumerate(ranked, 1):
        print(f"  {i}. {sc(k)} {name(k)}: {eur(results[k].summary['net_worth'])}")


if __name__ == "__main__":
    main()
