"""
Central assumptions for the housing scenario simulation.

EVERYTHING that drives the analysis lives here. Change a number, re-run
`python generate_report.py`, and the whole report (numbers + charts) updates.

All monetary values are in EUR. All rates are annual unless the name says
"_monthly". Percentages are expressed as decimals (0.03 == 3%).

Sources / validation (checked Jul 2026):
  - Belgian 25y fixed mortgage: market average ~4.0% (best profiles ~3.7%).
    We default to the user's 3.75% (a strong-profile rate). Sensitivity below.
  - Flanders transaction cost for your SOLE OWN home: ~4% of price
    (2% registration duty since 2025 + notary honoraria + admin + 21% VAT).
  - Flanders/Belgium transaction cost for a NON-primary / not-occupied home:
    ~13% (12% registration duty + notary/admin). This is the relevant rate for
    the "lijfrente" home because the seller keeps usufruct for 5 years, so it
    does not qualify as your sole-own-and-occupied dwelling at purchase.
  - Selling costs (agent + EPC + admin): ~3% of sale price. Belgium levies no
    capital-gains tax on a private main residence; a non-primary home sold
    within 5 years can be taxed at 16.5% (see LIJFRENTE_SALE_CGT_PCT).
"""

from dataclasses import dataclass, field


@dataclass
class Assumptions:
    # ------------------------------------------------------------------ #
    #  HOUSE & CASH                                                        #
    # ------------------------------------------------------------------ #
    # Today's market value of the target home. Identical ("value") for the
    # lijfrente home and a normal home, appreciation-adjusted over time.
    valuation_now: float = 750_000.0
    # Own cash available for the project.
    cash_capital: float = 200_000.0

    # ------------------------------------------------------------------ #
    #  MONTHLY BUDGET & RENT                                               #
    # ------------------------------------------------------------------ #
    # Monthly amount you can comfortably direct at housing. Any surplus vs the
    # actual housing outflow is INVESTED; any shortfall is drawn from savings.
    monthly_budget: float = 3_600.0
    # Rent while you do not (yet) live in an owned home.
    rent_monthly: float = 1_400.0
    # Annual rent indexation (Belgian leases are index-linked).
    rent_indexation_annual: float = 0.02

    # ------------------------------------------------------------------ #
    #  LIJFRENTE CONSTRUCT                                                 #
    # ------------------------------------------------------------------ #
    lijfrente_upfront: float = 300_000.0        # "bouquet" paid now
    lijfrente_monthly: float = 2_220.0          # annuity paid monthly
    lijfrente_years: int = 15                   # duration of the annuity
    lijfrente_annuity_indexation_annual: float = 0.0  # user says fixed; risk if >0
    move_in_delay_years: int = 5                # seller keeps usufruct this long
    # If you SELL the lijfrente home (scenario 2) do you still owe the annuity?
    # True  = you keep paying the annuity after the sale (conservative default).
    # False = the annuity obligation transfers to the buyer / is settled at sale.
    lijfrente_annuity_continues_after_sale: bool = True

    # ------------------------------------------------------------------ #
    #  MORTGAGE                                                            #
    # ------------------------------------------------------------------ #
    mortgage_rate_annual: float = 0.0375        # user estimate; market avg ~4.0%
    mortgage_term_years: int = 25
    # How the down payment is sized at each purchase:
    #   "rational"    -> put down the bank minimum (`min_down_pct`), and put down
    #                    MORE only when it pays to: if the mortgage rate exceeds
    #                    the investment return, sink all spare cash into the home
    #                    (paying 3.75% debt beats earning less); otherwise borrow
    #                    the maximum and keep the rest invested. This is the
    #                    default and matches how a rational household behaves.
    #   "roll_equity" -> always put down all available cash beyond `cash_buffer`
    #                    (savings + any sale proceeds roll into the home).
    #   "target_down" -> put down a fixed `down_payment_pct`, keep the rest invested.
    financing_mode: str = "rational"
    min_down_pct: float = 0.15                   # bank's minimum own-funds share
    down_payment_pct: float = 0.20               # used only in "target_down" mode
    # Liquid cash kept invested when sinking spare cash into the home (buffer).
    cash_buffer: float = 25_000.0

    # ------------------------------------------------------------------ #
    #  TRANSACTION & OWNERSHIP COSTS                                       #
    # ------------------------------------------------------------------ #
    buy_cost_pct_primary: float = 0.04          # Flanders, sole own home
    lijfrente_buy_cost_pct: float = 0.13        # not occupied -> non-primary rate
    sell_cost_pct: float = 0.03                 # agent + EPC + admin
    lijfrente_sale_cgt_pct: float = 0.0         # set 0.165 to stress a <5y sale
    # Recurring owner costs (maintenance + insurance + property tax) as a share
    # of current home value per year, charged only while you OWN AND OCCUPY.
    ownership_cost_annual_pct: float = 0.010

    # ------------------------------------------------------------------ #
    #  MARKET RETURNS (the two biggest swing factors)                     #
    # ------------------------------------------------------------------ #
    investment_return_annual: float = 0.0375     # set equal to the mortgage rate
                                                  # (treat investing at the risk-free
                                                  # /mortgage hurdle: no risk premium)
    house_appreciation_annual: float = 0.03     # Belgian long-run nominal

    # ------------------------------------------------------------------ #
    #  HORIZON                                                             #
    # ------------------------------------------------------------------ #
    # Compare wealth this many years out. 30y lets every 25y mortgage fully
    # amortise, so all scenarios end owning the same debt-free home.
    horizon_years: int = 30

    # ------------------------------------------------------------------ #
    #  SENSITIVITY GRID (used for the tornado / heat-map)                  #
    # ------------------------------------------------------------------ #
    sensitivity_investment_returns: tuple = (0.03, 0.04, 0.05, 0.06, 0.07)
    sensitivity_appreciation_rates: tuple = (0.01, 0.02, 0.03, 0.04, 0.05)

    # ---- convenience -------------------------------------------------- #
    @property
    def horizon_months(self) -> int:
        return self.horizon_years * 12

    @property
    def move_in_month(self) -> int:
        return self.move_in_delay_years * 12

    def monthly_rate(self, annual: float) -> float:
        """Convert an annual rate to an equivalent monthly compounding rate."""
        return (1.0 + annual) ** (1.0 / 12.0) - 1.0


# Scenario metadata (labels used across the model and the report).
SCENARIOS = {
    "s1_lijfrente_movein": {
        "short": "S1",
        "name": "Lijfrente + rent, then move in",
        "desc": "Buy the lijfrente home now, rent for 5 years, then move into "
                "the lijfrente home and keep it.",
    },
    "s2_lijfrente_then_normal": {
        "short": "S2",
        "name": "Lijfrente + rent, then sell & buy normal",
        "desc": "Buy the lijfrente home now, rent for 5 years, then sell the "
                "lijfrente home and buy a normal home.",
    },
    "s3_rent_then_normal": {
        "short": "S3",
        "name": "Rent, then buy normal",
        "desc": "Rent for 5 years, then buy a normal home.",
    },
    "s4_buy_normal_now": {
        "short": "S4",
        "name": "Buy normal now",
        "desc": "Buy a normal home now and live in it.",
    },
}
