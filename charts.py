"""Chart rendering for the housing report. Every figure is written to a PNG
file under `report_images/` and the function returns the relative path, so the
Markdown report renders correctly on GitHub."""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from config import SCENARIOS

IMAGES_DIR = "report_images"

# One colour per scenario, reused everywhere for instant recognition.
COLORS = {
    "s1_lijfrente_movein": "#1f6feb",
    "s2_lijfrente_then_normal": "#e3a008",
    "s3_rent_then_normal": "#2ea043",
    "s4_buy_normal_now": "#cf222e",
}
SHORT = {k: v["short"] for k, v in SCENARIOS.items()}
KEYS = list(SCENARIOS.keys())

plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "figure.dpi": 110,
})


def _eur(x, _=None):
    ax = abs(x)
    if ax >= 1e6:
        return f"€{x/1e6:.2f}M"
    if ax >= 1e3:
        return f"€{x/1e3:.0f}k"
    return f"€{x:.0f}"


def _save(fig, name):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    rel = f"{IMAGES_DIR}/{name}.png"
    fig.savefig(rel, format="png", bbox_inches="tight")
    plt.close(fig)
    return rel


def net_worth_bar(results):
    """Terminal net worth: absolute (left) + difference vs weakest (right)."""
    vals = [results[k].summary["net_worth"] for k in KEYS]
    best, worst = max(vals), min(vals)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.6),
                                  gridspec_kw={"width_ratios": [1.15, 1]})

    bars = ax.bar([SHORT[k] for k in KEYS], vals,
                  color=[COLORS[k] for k in KEYS], width=0.62)
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.set_ylabel("Net worth at horizon (nominal €)")
    ax.set_ylim(0, best * 1.16)
    for k, b, v in zip(KEYS, bars, vals):
        lbl = _eur(v) + ("\n(best)" if v == best else "")
        ax.text(b.get_x() + b.get_width() / 2, v, lbl, ha="center",
                va="bottom", fontsize=10, fontweight="bold")
    ax.set_title("Absolute — dominated by the identical home",
                 fontweight="bold", loc="left", fontsize=11)

    deltas = [v - worst for v in vals]
    b2 = ax2.bar([SHORT[k] for k in KEYS], deltas,
                 color=[COLORS[k] for k in KEYS], width=0.62)
    ax2.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax2.set_ylabel("Extra net worth vs. weakest")
    ax2.set_ylim(0, max(deltas) * 1.2)
    for b, d in zip(b2, deltas):
        ax2.text(b.get_x() + b.get_width() / 2, d, _eur(d), ha="center",
                 va="bottom", fontsize=10, fontweight="bold")
    ax2.set_title("Difference — where the decision actually matters",
                  fontweight="bold", loc="left", fontsize=11)
    fig.suptitle("Terminal net worth by scenario", fontweight="bold",
                 x=0.02, ha="left", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return _save(fig, "01_net_worth")


def component_bridge(results):
    """Grouped bars: PV of each value driver that DIFFERS between scenarios."""
    comps = [("rent", "Rent"), ("annuity", "Lijfrente\nannuity"),
             ("interest", "Mortgage\ninterest"), ("fees", "Fees &\nselling"),
             ("ownership", "Upkeep &\nprop. tax"),
             ("net_property_gain", "Property value\nvs investing")]
    fig, ax = plt.subplots(figsize=(11, 5.2))
    n = len(KEYS)
    w = 0.8 / n
    x = range(len(comps))
    for j, k in enumerate(KEYS):
        vals = [results[k].attribution_pv[c] / 1e3 for c, _ in comps]
        ax.bar([xi + (j - (n - 1) / 2) * w for xi in x], vals, width=w,
               color=COLORS[k], label=SHORT[k])
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([lbl for _, lbl in comps])
    ax.set_ylabel("Contribution to net worth (today's €, thousands)")
    ax.set_title("What drives the differences — value bridge (present value)",
                 fontweight="bold", loc="left")
    ax.legend(ncol=4, loc="lower center", frameon=False, bbox_to_anchor=(0.5, -0.22))
    return _save(fig, "02_value_bridge")


def nominal_cashout(results):
    """Stacked bars: total euros paid out over the horizon, by category."""
    cats = [("total_rent", "Rent", "#8bc7ff"),
            ("total_annuity", "Lijfrente annuity", "#1f6feb"),
            ("total_interest", "Mortgage interest", "#cf222e"),
            ("total_fees", "Transaction & selling fees", "#e3a008"),
            ("total_ownership", "Upkeep & property tax", "#8250df")]
    fig, ax = plt.subplots(figsize=(9.5, 5))
    labels = [SHORT[k] for k in KEYS]
    bottoms = [0.0] * len(KEYS)
    for field, name, col in cats:
        vals = [results[k].summary[field] for k in KEYS]
        ax.bar(labels, vals, bottom=bottoms, label=name, color=col, width=0.6)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.set_ylabel("Total paid over horizon (nominal €)")
    for i, tot in enumerate(bottoms):
        ax.text(i, tot, _eur(tot), ha="center", va="bottom", fontweight="bold")
    ax.set_ylim(0, max(bottoms) * 1.15)
    ax.set_title("Cash out of pocket over the horizon (excludes recoverable capital)",
                 fontweight="bold", loc="left")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    return _save(fig, "03_cash_out")


def net_worth_path(results, A):
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    months = range(A.horizon_months)
    yrs = [m / 12 for m in months]
    for k in KEYS:
        ax.plot(yrs, results[k].net_worth, color=COLORS[k], label=SHORT[k], lw=2)
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.set_xlabel("Years from now")
    ax.set_ylabel("Net worth (nominal €)")
    ax.axvline(A.move_in_delay_years, color="#999", ls="--", lw=1)
    ax.text(A.move_in_delay_years + 0.1, ax.get_ylim()[1] * 0.05,
            "year 5\n(move / buy)", fontsize=8, color="#666")
    ax.set_title("Net-worth trajectory", fontweight="bold", loc="left")
    ax.legend(frameon=False, ncol=4, fontsize=9)
    return _save(fig, "04_net_worth_path")


def outflow_path(results, A):
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    yrs = [m / 12 for m in range(A.horizon_months)]
    for k in KEYS:
        ax.plot(yrs, results[k].monthly_outflow, color=COLORS[k],
                label=SHORT[k], lw=1.8)
    ax.axhline(A.monthly_budget, color="#111", ls=":", lw=1.6)
    ax.text(A.horizon_years * 0.55, A.monthly_budget * 1.02,
            f"comfortable budget €{A.monthly_budget:,.0f}/mo", fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.set_xlabel("Years from now")
    ax.set_ylabel("Housing outflow (€/month)")
    ax.set_title("Monthly housing outflow vs. budget (cash-flow strain)",
                 fontweight="bold", loc="left")
    ax.legend(frameon=False, ncol=4, fontsize=9)
    return _save(fig, "05_outflow")


def sensitivity_heatmap(grid, A):
    """grid[(inv, app)] -> winning scenario key."""
    invs = list(A.sensitivity_investment_returns)
    apps = list(A.sensitivity_appreciation_rates)
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    for i, inv in enumerate(invs):
        for j, app in enumerate(apps):
            k = grid[(inv, app)]
            ax.add_patch(plt.Rectangle((j, i), 1, 1, color=COLORS[k], alpha=0.85))
            ax.text(j + 0.5, i + 0.5, SHORT[k], ha="center", va="center",
                    color="white", fontweight="bold", fontsize=11)
    ax.set_xlim(0, len(apps))
    ax.set_ylim(0, len(invs))
    ax.set_xticks([j + 0.5 for j in range(len(apps))])
    ax.set_xticklabels([f"{a:.0%}" for a in apps])
    ax.set_yticks([i + 0.5 for i in range(len(invs))])
    ax.set_yticklabels([f"{v:.0%}" for v in invs])
    ax.set_xlabel("House appreciation (per year)")
    ax.set_ylabel("Investment return (per year)")
    ax.grid(False)
    ax.set_title("Which scenario wins? (highest net worth)",
                 fontweight="bold", loc="left")
    # base-case marker
    if A.house_appreciation_annual in apps and A.investment_return_annual in invs:
        j = apps.index(A.house_appreciation_annual)
        i = invs.index(A.investment_return_annual)
        ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=False, edgecolor="black", lw=3))
        ax.text(j + 0.5, i + 0.14, "base", ha="center", va="center",
                color="white", fontsize=8)
    return _save(fig, "06_sensitivity_grid")


def sensitivity_lines(sweep_inv, sweep_app, A):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    xs, series = sweep_inv
    for k in KEYS:
        axes[0].plot([x * 100 for x in xs], [v / 1e6 for v in series[k]],
                     color=COLORS[k], label=SHORT[k], lw=2, marker="o", ms=3)
    axes[0].axvline(A.investment_return_annual * 100, color="#999", ls="--", lw=1)
    axes[0].set_xlabel("Investment return (%/yr)")
    axes[0].set_ylabel("Net worth (€M)")
    axes[0].set_title(f"Vs. investment return (appreciation "
                      f"{A.house_appreciation_annual:.0%})",
                      fontweight="bold", loc="left", fontsize=10)
    axes[0].legend(frameon=False, ncol=2, fontsize=8)

    xs, series = sweep_app
    for k in KEYS:
        axes[1].plot([x * 100 for x in xs], [v / 1e6 for v in series[k]],
                     color=COLORS[k], label=SHORT[k], lw=2, marker="o", ms=3)
    axes[1].axvline(A.house_appreciation_annual * 100, color="#999", ls="--", lw=1)
    axes[1].set_xlabel("House appreciation (%/yr)")
    axes[1].set_ylabel("Net worth (€M)")
    axes[1].set_title(f"Vs. house appreciation (investment "
                      f"{A.investment_return_annual:.0%})",
                      fontweight="bold", loc="left", fontsize=10)
    axes[1].legend(frameon=False, ncol=2, fontsize=8)
    return _save(fig, "07_sensitivity_lines")
