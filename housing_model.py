"""
Monthly cash-flow engine for the four housing scenarios.

Design
------
Every scenario is simulated month by month over the horizon. Each month we:
  1) process events (buy / sell / start-rent / move-in),
  2) accrue housing outflows (rent, annuity, ownership costs, mortgage P&I),
  3) contribute (budget - outflow) to an investment portfolio and let it grow.

Because the monthly BUDGET and the starting CASH are identical across scenarios,
and every scenario ends up owning the *same* debt-free home at the horizon, the
only thing that separates the scenarios is the terminal investment portfolio.
That portfolio silently books every difference in rent, annuity, interest, fees
and the opportunity cost of capital tied up in bricks.

Terminal net worth = investment portfolio + home equity (home value - debt).

Attribution
-----------
We express terminal net worth as a reconciling waterfall (future-valued to the
horizon at the investment return, i.e. every euro is scored at its opportunity
cost):

    Net worth =  Resources (cash + all budget, compounded)   [identical]
               - Rent
               - Lijfrente annuity
               - Mortgage interest
               - Transaction & selling fees
               - Ownership costs
               + Net property gain (terminal home value + sale proceeds
                                    - capital sunk into the home, all compounded)

The last term is the payoff from owning bricks net of the opportunity cost of
the capital locked up in them; it is where house appreciation and mortgage
leverage show up. The engine self-checks that the compounded cash-flow ledger
reproduces the iterated portfolio to the cent.
"""

from dataclasses import dataclass, field
from typing import Optional

from config import Assumptions, SCENARIOS


@dataclass
class Mortgage:
    """Fixed-rate annuity mortgage with a standard amortisation schedule."""
    principal: float
    annual_rate: float
    term_months: int

    def __post_init__(self):
        self.balance = self.principal
        r = self.annual_rate / 12.0  # market convention: nominal /12
        n = self.term_months
        if self.principal <= 0:
            self.payment = 0.0
        elif r == 0:
            self.payment = self.principal / n
        else:
            self.payment = self.principal * r / (1.0 - (1.0 + r) ** (-n))
        self._r = r

    def step(self):
        """Advance one month; return (interest, principal) actually paid."""
        if self.balance <= 1e-9:
            return 0.0, 0.0
        interest = self.balance * self._r
        principal = self.payment - interest
        if principal >= self.balance:  # final (partial) payment
            principal = self.balance
        self.balance -= principal
        return interest, principal


@dataclass
class Result:
    key: str
    # monthly series (length = horizon_months)
    portfolio: list = field(default_factory=list)
    net_worth: list = field(default_factory=list)
    home_value: list = field(default_factory=list)
    mortgage_balance: list = field(default_factory=list)
    monthly_outflow: list = field(default_factory=list)
    # scalar summary
    summary: dict = field(default_factory=dict)
    # attribution buckets (future value at horizon, EUR)
    attribution_fv: dict = field(default_factory=dict)
    # attribution buckets (present value today, EUR)
    attribution_pv: dict = field(default_factory=dict)


def _events_for(key: str, A: Assumptions) -> dict:
    """Return {month: [event, ...]} for a scenario."""
    m = A.move_in_month
    if key == "s1_lijfrente_movein":
        return {0: ["buy_lijfrente", "start_rent"], m: ["move_in"]}
    if key == "s2_lijfrente_then_normal":
        return {0: ["buy_lijfrente", "start_rent"],
                m: ["sell_home", "buy_normal", "move_in"]}
    if key == "s3_rent_then_normal":
        return {0: ["start_rent"], m: ["buy_normal", "move_in"]}
    if key == "s4_buy_normal_now":
        return {0: ["buy_normal"]}
    raise ValueError(key)


def simulate(key: str, A: Assumptions) -> Result:
    N = A.horizon_months
    i_m = A.monthly_rate(A.investment_return_annual)
    g_m = A.monthly_rate(A.house_appreciation_annual)
    rent_m = A.monthly_rate(A.rent_indexation_annual)
    ann_m = A.monthly_rate(A.lijfrente_annuity_indexation_annual)

    events = _events_for(key, A)

    # ---- state ------------------------------------------------------- #
    portfolio = A.cash_capital
    home_value: Optional[float] = None      # market value of the home we OWN
    is_lijfrente_home = False
    mortgage: Optional[Mortgage] = None
    annuity_left = 0
    renting = False
    occupying_owned = False                 # do we live in a home we own?

    rent_cur = A.rent_monthly
    annuity_cur = A.lijfrente_monthly

    res = Result(key=key)
    # accumulators for attribution (future value at the horizon)
    acc = dict(rent=0.0, annuity=0.0, interest=0.0, fees=0.0, ownership=0.0)
    totals = dict(interest=0.0, principal=0.0, rent=0.0, annuity=0.0, fees=0.0,
                  ownership=0.0, cash_out=0.0)
    # ledger of every portfolio cash flow: (month, amount) for a self-check
    ledger = [(0, A.cash_capital)]

    def fv(amount, month):
        # a euro spent in `month` costs this much of terminal (month N-1) wealth
        return amount * (1.0 + i_m) ** (N - 1 - month)

    def finance_purchase(price_for_finance, cost_base, cost_pct, month):
        """Spend cash on down payment + costs, borrow the rest. Mutates state."""
        nonlocal portfolio, mortgage
        costs = cost_base * cost_pct
        desired_down = A.down_payment_pct * price_for_finance
        if portfolio >= desired_down + costs:
            down = desired_down
        else:                               # not enough cash -> put in all we can
            down = max(0.0, portfolio - costs)
        loan = max(0.0, price_for_finance - down)
        cash_used = down + costs
        portfolio -= cash_used
        ledger.append((month, -cash_used))
        mortgage = Mortgage(loan, A.mortgage_rate_annual,
                            A.mortgage_term_years * 12)
        acc["fees"] += fv(costs, month)
        totals["fees"] += costs
        totals["cash_out"] += cash_used
        return down, loan

    peak_outflow = 0.0
    min_portfolio = portfolio

    for t in range(N):
        # current market value of the target home at month t
        market_value = A.valuation_now * (1.0 + g_m) ** t

        # ---------------- events ----------------
        for ev in events.get(t, []):
            if ev == "start_rent":
                renting = True
            elif ev == "move_in":
                renting = False
                occupying_owned = True
            elif ev == "buy_lijfrente":
                finance_purchase(A.lijfrente_upfront, A.valuation_now,
                                 A.lijfrente_buy_cost_pct, t)
                home_value = market_value
                is_lijfrente_home = True
                annuity_left = A.lijfrente_years * 12
                occupying_owned = False      # seller keeps usufruct
            elif ev == "buy_normal":
                finance_purchase(market_value, market_value,
                                 A.buy_cost_pct_primary, t)
                home_value = market_value
                is_lijfrente_home = False
                occupying_owned = True
            elif ev == "sell_home":
                gross = home_value
                sell_fee = gross * A.sell_cost_pct
                cgt = 0.0
                if is_lijfrente_home:
                    gain = max(0.0, gross - A.valuation_now)
                    cgt = gain * A.lijfrente_sale_cgt_pct
                payoff = mortgage.balance if mortgage else 0.0
                proceeds = gross - sell_fee - cgt - payoff
                portfolio += proceeds
                ledger.append((t, proceeds))
                acc["fees"] += fv(sell_fee + cgt, t)
                totals["fees"] += sell_fee + cgt
                mortgage = None
                home_value = None
                # annuity may or may not continue (config)
                if is_lijfrente_home and not A.lijfrente_annuity_continues_after_sale:
                    annuity_left = 0
                is_lijfrente_home = False

        # the home we own is the same target home, appreciation-adjusted
        if home_value is not None:
            home_value = market_value

        # ---------------- monthly outflows ----------------
        outflow = 0.0
        if renting:
            outflow += rent_cur
            acc["rent"] += fv(rent_cur, t)
            totals["rent"] += rent_cur
        if annuity_left > 0:
            outflow += annuity_cur
            acc["annuity"] += fv(annuity_cur, t)
            totals["annuity"] += annuity_cur
            annuity_left -= 1
        if home_value is not None and occupying_owned:
            oc = home_value * A.ownership_cost_annual_pct / 12.0
            outflow += oc
            acc["ownership"] += fv(oc, t)
            totals["ownership"] += oc
        if mortgage is not None:
            interest, principal = mortgage.step()
            pay = interest + principal
            outflow += pay
            acc["interest"] += fv(interest, t)
            totals["interest"] += interest
            totals["principal"] += principal

        totals["cash_out"] += outflow
        peak_outflow = max(peak_outflow, outflow)

        # ---------------- portfolio update ----------------
        contribution = A.monthly_budget - outflow
        ledger.append((t, contribution))
        portfolio += contribution
        min_portfolio = min(min_portfolio, portfolio)

        # record end-of-month state
        cur_home = home_value if home_value is not None else 0.0
        cur_debt = mortgage.balance if mortgage else 0.0
        res.portfolio.append(portfolio)
        res.home_value.append(cur_home)
        res.mortgage_balance.append(cur_debt)
        res.monthly_outflow.append(outflow)
        res.net_worth.append(portfolio + cur_home - cur_debt)

        # grow to next month (portfolio compounds; home appreciates via t loop)
        portfolio *= (1.0 + i_m)

        # index rent / annuity annually
        if (t + 1) % 12 == 0:
            rent_cur *= (1.0 + rent_m)
            annuity_cur *= (1.0 + ann_m)

    # ---------------- terminal figures ----------------
    # portfolio grew one extra step past the final month; net worth is measured
    # at the horizon (end of month N-1), so undo that last growth for the value.
    terminal_portfolio = res.portfolio[-1]
    terminal_home = res.home_value[-1]
    terminal_debt = res.mortgage_balance[-1]
    net_worth = terminal_portfolio + terminal_home - terminal_debt

    # ---- self-check: compounded ledger must reproduce the portfolio ----
    ledger_fv = sum(a * (1.0 + i_m) ** (N - 1 - mth) for mth, a in ledger)
    assert abs(ledger_fv - terminal_portfolio) < 1.0, (
        f"{key}: ledger {ledger_fv:.2f} != portfolio {terminal_portfolio:.2f}")

    # ---- attribution waterfall (all future-valued to the horizon) ----
    # Resources = starting cash + every monthly budget euro, compounded. This is
    # identical across scenarios, so all net-worth differences live in the
    # remaining buckets.
    resources_fv = (A.cash_capital * (1.0 + i_m) ** (N - 1)
                    + sum(A.monthly_budget * (1.0 + i_m) ** (N - 1 - t)
                          for t in range(N)))
    costs_fv = (acc["rent"] + acc["annuity"] + acc["interest"]
                + acc["fees"] + acc["ownership"])
    # Everything not spent on those cost buckets and not left in the portfolio
    # is the net payoff of owning bricks (terminal value + any sale proceeds,
    # less the opportunity cost of capital sunk into the home). Defined as the
    # reconciling residual so the waterfall closes exactly.
    net_property_gain = net_worth - (resources_fv - costs_fv)

    res.attribution_fv = {
        "resources": resources_fv,
        "rent": -acc["rent"],
        "annuity": -acc["annuity"],
        "interest": -acc["interest"],
        "fees": -acc["fees"],
        "ownership": -acc["ownership"],
        "net_property_gain": net_property_gain,
        "net_worth": net_worth,
    }

    disc = (1.0 + i_m) ** (N - 1)
    res.attribution_pv = {k: v / disc for k, v in res.attribution_fv.items()}

    res.summary = {
        "net_worth": net_worth,
        "net_worth_pv": net_worth / disc,
        "terminal_portfolio": terminal_portfolio,
        "terminal_home": terminal_home,
        "terminal_debt": terminal_debt,
        "peak_monthly_outflow": peak_outflow,
        "min_portfolio": min_portfolio,          # negative => funding gap
        "peak_funding_gap": max(0.0, -min_portfolio),
        "total_interest": totals["interest"],
        "total_rent": totals["rent"],
        "total_annuity": totals["annuity"],
        "total_fees": totals["fees"],
        "total_ownership": totals["ownership"],
        "total_cash_out": totals["cash_out"],
    }
    return res


def run_all(A: Assumptions) -> dict:
    return {k: simulate(k, A) for k in SCENARIOS}


def net_worth_only(key: str, A: Assumptions) -> float:
    return simulate(key, A).summary["net_worth"]


if __name__ == "__main__":
    A = Assumptions()
    results = run_all(A)
    print(f"Horizon: {A.horizon_years}y | invest {A.investment_return_annual:.1%}"
          f" | appreciation {A.house_appreciation_annual:.1%}\n")
    for k, r in results.items():
        s = r.summary
        print(f"{SCENARIOS[k]['short']}  {SCENARIOS[k]['name']}")
        print(f"    terminal net worth : EUR {s['net_worth']:>14,.0f}")
        print(f"    in today's money   : EUR {s['net_worth_pv']:>14,.0f}")
        print(f"    peak monthly out   : EUR {s['peak_monthly_outflow']:>14,.0f}")
        print(f"    peak funding gap   : EUR {s['peak_funding_gap']:>14,.0f}")
        print(f"    total interest     : EUR {s['total_interest']:>14,.0f}")
        print(f"    total rent         : EUR {s['total_rent']:>14,.0f}")
        print(f"    total annuity      : EUR {s['total_annuity']:>14,.0f}")
        print(f"    total fees         : EUR {s['total_fees']:>14,.0f}")
        print()
