#!/usr/bin/env python3
"""The numbers for startup-numbers. Python 3.8+, standard library only, no network.

Reads one JSON file that describes a business and works out what a careful CFO
would check before any money is spent: what one sale (or one customer) leaves
after its own costs, what it costs to win a customer and whether they are worth
it, the break-even, 24 months month by month, the cash you need before it pays
for itself, when the money you put in comes back, and what happens if things go
worse than planned.

    python3 numbers.py startup/numbers.json
    python3 numbers.py startup/numbers.json --out startup/numbers.md
    python3 numbers.py startup/numbers.json --json
    python3 numbers.py startup/numbers.json --price 39 --volume 0.8

Two kinds of business:

  "model": "subscription"   customers pay every month and some cancel
      price                 per customer per month
      variable              [{label, cost}] cost of serving ONE customer for a month
      new_customers         12 or 24 numbers: new paying customers each month
      churn                 share of customers who cancel each month (0.05 = 5 %)
      cost_to_win_customer  marketing and sales spend to win one new customer
      starting_customers    optional, customers on day one (default 0)

  "model": "one-time"       each sale is a separate purchase
      price                 per unit
      variable              [{label, cost}] cost of ONE unit: materials, packaging, shipping, fees
      sales                 12 or 24 numbers: units sold each month
        (or sales_per_day   12 or 24 numbers, with days_per_month, default 30)
      marketing_per_sale    ad and marketing spend to make one sale (0 is allowed, but say why)

  Both:
      business, unit, currency (default "$")
      fixed_monthly         [{label, cost}] paid every month whatever you sell
      startup               [{label, cost}] one-off spend before you open
      capacity              optional: most units a month (one-time) or most customers (subscription)
      sources               optional {field: "where the number comes from"}; a line item can
                            also carry "source". Anything starting with "estimate" is listed
                            as an estimate to replace with a real quote.

With 12 monthly numbers, months 13 to 24 repeat month 12. Every number in the
report comes from the file; nothing is looked up or guessed, and a missing field
is an error, not a default.

--price replaces the price and --volume scales every sales or new-customer number
(0.8 = 20 % fewer), so you can try a what-if without editing the file.
"""

import argparse
import copy
import json
import math
import sys

HORIZON = 24


class NumbersError(Exception):
    pass


# ---- reading the file ------------------------------------------------------------

def _number(spec, key, minimum=None):
    if key not in spec:
        raise NumbersError("'%s' is missing" % key)
    try:
        v = float(spec[key])
    except (TypeError, ValueError):
        raise NumbersError("'%s' is not a number: %r" % (key, spec[key]))
    if minimum is not None and v < minimum:
        raise NumbersError("'%s' must be at least %s" % (key, minimum))
    return v


def _total(spec, key):
    items = spec.get(key, [])
    if not isinstance(items, list):
        raise NumbersError("'%s' must be a list of {label, cost}" % key)
    total = 0.0
    for i, it in enumerate(items):
        if not isinstance(it, dict) or "cost" not in it:
            raise NumbersError("%s[%d] needs a 'cost'" % (key, i))
        try:
            total += float(it["cost"])
        except (TypeError, ValueError):
            raise NumbersError("%s[%d].cost is not a number: %r" % (key, i, it["cost"]))
    return total


def _monthly(spec, key, scale=1.0):
    if key not in spec:
        raise NumbersError("'%s' is missing (12 or 24 numbers, one per month)" % key)
    values = spec[key]
    if not isinstance(values, list) or len(values) not in (12, HORIZON):
        raise NumbersError("'%s' needs 12 or 24 numbers, one per month" % key)
    try:
        values = [float(v) * scale for v in values]
    except (TypeError, ValueError):
        raise NumbersError("'%s' must contain only numbers" % key)
    if any(v < 0 for v in values):
        raise NumbersError("'%s' cannot contain negative numbers" % key)
    if len(values) == 12:
        values = values + [values[-1]] * (HORIZON - 12)
    return values


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise NumbersError("no such file: %s" % path)
    except json.JSONDecodeError as e:
        raise NumbersError("%s is not valid JSON: %s" % (path, e))


# ---- the analysis --------------------------------------------------------------

def analyse(spec, price=None, volume=1.0, cost_factor=1.0, churn_factor=1.0):
    """Every number in the report, as a dict. A pure function of its inputs."""
    model = spec.get("model")
    if model not in ("subscription", "one-time"):
        raise NumbersError("'model' must be \"subscription\" or \"one-time\"")
    p = float(price) if price is not None else _number(spec, "price")
    if p <= 0:
        raise NumbersError("'price' must be above zero")
    var = _total(spec, "variable") * cost_factor
    fixed = _total(spec, "fixed_monthly") * cost_factor
    startup = _total(spec, "startup")
    capacity = spec.get("capacity")
    capacity = float(capacity) if capacity is not None else None
    out = {
        "business": spec.get("business", ""), "model": model, "currency": spec.get("currency", "$"),
        "unit": spec.get("unit") or ("customer" if model == "subscription" else "sale"),
        "price": p, "variable": var, "fixed_monthly": fixed, "startup": startup, "capacity": capacity,
        "repeats_month_12": None,
    }
    months = []
    if model == "subscription":
        churn = _number(spec, "churn", 0) * churn_factor
        if churn >= 1:
            raise NumbersError("'churn' is a monthly share below 1 (0.05 means 5 % cancel each month)")
        cac = _number(spec, "cost_to_win_customer", 0) * cost_factor
        new = _monthly(spec, "new_customers", volume)
        out["repeats_month_12"] = len(spec["new_customers"]) == 12
        customers = float(spec.get("starting_customers", 0))
        contribution = p - var
        for m in range(HORIZON):
            lost = customers * churn
            customers = customers - lost + new[m]
            revenue = customers * p
            row = {"month": m + 1, "new": new[m], "lost": lost, "volume": customers, "revenue": revenue,
                   "variable": customers * var, "marketing": new[m] * cac, "fixed": fixed}
            months.append(row)
        out.update({
            "churn": churn, "cost_to_win_customer": cac, "contribution": contribution,
            "lifetime_months": (1 / churn) if churn > 0 else math.inf,
            "lifetime_value": (contribution / churn) if churn > 0 else math.inf,
            "breakeven": (fixed / contribution) if contribution > 0 else math.inf,
        })
        out["value_to_cost"] = (out["lifetime_value"] / cac) if cac > 0 else math.inf
        out["months_to_earn_back_customer"] = (cac / contribution) if contribution > 0 else math.inf
    else:
        per_day = "sales_per_day" in spec
        if per_day:
            days = _number(spec, "days_per_month", 1) if "days_per_month" in spec else 30.0
            sales = [v * days for v in _monthly(spec, "sales_per_day", volume)]
            out["repeats_month_12"] = len(spec["sales_per_day"]) == 12
        elif "sales" in spec:
            days = None
            sales = _monthly(spec, "sales", volume)
            out["repeats_month_12"] = len(spec["sales"]) == 12
        else:
            raise NumbersError("give 'sales' (12 or 24 monthly numbers) or 'sales_per_day'")
        marketing = _number(spec, "marketing_per_sale", 0) * cost_factor
        contribution = p - var - marketing
        for m in range(HORIZON):
            units = sales[m]
            months.append({"month": m + 1, "volume": units, "revenue": units * p, "variable": units * var,
                           "marketing": units * marketing, "fixed": fixed})
        out.update({
            "marketing_per_sale": marketing, "contribution": contribution, "days_per_month": days,
            "breakeven": (fixed / contribution) if contribution > 0 else math.inf,
        })
        out["breakeven_per_day"] = (out["breakeven"] / days) if days else None

    cumulative = -startup
    payback = first_profit = None
    lowest = cumulative
    for row in months:
        row["profit"] = row["revenue"] - row["variable"] - row["marketing"] - row["fixed"]
        cumulative += row["profit"]
        row["cumulative"] = cumulative
        lowest = min(lowest, cumulative)
        if first_profit is None and row["profit"] > 0:
            first_profit = row["month"]
        if payback is None and cumulative >= 0:
            payback = row["month"]
    year1 = months[:12]
    out.update({
        "months": months,
        "margin": out["contribution"] / p,
        "month12_profit": months[11]["profit"],
        "month12_revenue": months[11]["revenue"],
        "month12_volume": months[11]["volume"],
        "year1_revenue": sum(r["revenue"] for r in year1),
        "year1_profit": sum(r["profit"] for r in year1),
        "cumulative_24": months[-1]["cumulative"],
        "first_profit_month": first_profit,
        "payback_month": payback,
        "cash_needed": -lowest,
        "peak_volume": max(r["volume"] for r in months),
    })
    out["flags"] = _flags(out)
    return out


def _flags(a):
    unit = a["unit"]
    flags = []
    if a["contribution"] <= 0:
        flags.append("Each %s loses money before fixed costs: the price does not cover its own costs." % unit)
    if a["model"] == "subscription" and a["contribution"] > 0:
        if a["value_to_cost"] < 1:
            flags.append("A customer brings in less than it costs to win them.")
        elif a["value_to_cost"] < 3:
            flags.append("A customer brings in only %.1f times what it costs to win them (3 times or more is healthy)."
                         % a["value_to_cost"])
    if a["capacity"] is not None:
        if a["breakeven"] > a["capacity"]:
            flags.append("Break-even needs more than you can handle (capacity %s)." % _count(a["capacity"]))
        if a["peak_volume"] > a["capacity"]:
            flags.append("The plan goes above capacity (%s at the peak, capacity %s)."
                         % (_count(a["peak_volume"]), _count(a["capacity"])))
    if a["month12_profit"] <= 0:
        flags.append("Month 12 still loses money.")
    if a["payback_month"] is None:
        flags.append("The money you put in does not come back within 24 months.")
    return flags


def what_ifs(spec):
    """The bad-news scenarios every plan should survive."""
    base = analyse(spec)
    rows = [("The plan", base),
            ("Price 10% lower", analyse(spec, price=base["price"] * 0.9)),
            ("Sales 20% lower" if base["model"] == "one-time" else "20% fewer new customers", analyse(spec, volume=0.8)),
            ("Every cost 15% higher", analyse(spec, cost_factor=1.15))]
    if base["model"] == "subscription":
        rows.append(("Customers cancel 50% more often", analyse(spec, churn_factor=1.5)))
    return rows


FIELD_WORDS = {
    "price": "Price", "churn": "Share of customers who cancel each month",
    "cost_to_win_customer": "Cost to win a customer", "marketing_per_sale": "Marketing per sale",
    "new_customers": "New customers each month", "sales": "Sales each month", "sales_per_day": "Sales each day",
    "starting_customers": "Customers on day one", "capacity": "Capacity", "days_per_month": "Selling days a month",
}


def estimates(spec):
    """Inputs marked as estimates, as (what, source) pairs."""
    out = []
    for key in ("variable", "fixed_monthly", "startup"):
        for it in spec.get(key, []):
            src = str(it.get("source", ""))
            if src.lower().startswith("estimate"):
                out.append((it.get("label", key), src))
    for key, src in (spec.get("sources") or {}).items():
        if str(src).lower().startswith("estimate"):
            out.append((FIELD_WORDS.get(key, key), str(src)))
    return out


# ---- the report ------------------------------------------------------------------

def _count(v):
    return "never" if math.isinf(v) else "{:,.0f}".format(math.ceil(v - 1e-9))


def money(a, v, cents=False):
    if math.isinf(v):
        return "unlimited"
    sign = "-" if v < 0 else ""
    fmt = "{:,.2f}" if cents else "{:,.0f}"
    return "%s%s%s" % (sign, a["currency"], fmt.format(abs(v) if cents else abs(round(v))))


def _month(m):
    return "month %d" % m if m else "not within 24 months"


def report(spec, a):
    sub = a["model"] == "subscription"
    unit = a["unit"]
    L = ["# The numbers: %s" % (a["business"] or "your business"), "",
         "Every number below comes from the input file. Nothing is looked up or guessed.", ""]
    if sub:
        L += ["## One %s, one month" % unit, "", "| line | per %s per month |" % unit, "| --- | ---: |",
              "| Price | %s |" % money(a, a["price"], True)]
    else:
        L += ["## One %s" % unit, "", "| line | per %s |" % unit, "| --- | ---: |",
              "| Price | %s |" % money(a, a["price"], True)]
    for it in spec.get("variable", []):
        L.append("| %s | -%s |" % (it.get("label", "cost"), money(a, float(it["cost"]), True)))
    if not sub:
        L.append("| Marketing to make the sale | -%s |" % money(a, a["marketing_per_sale"], True))
    L.append("| **What it leaves to pay the fixed costs** | **%s** (%.0f%%) |"
             % (money(a, a["contribution"], True), a["margin"] * 100))
    L.append("")
    if sub:
        L += ["## Winning a customer", "",
              "- It costs **%s** to win one customer." % money(a, a["cost_to_win_customer"]),
              "- %.1f%% cancel each month, so a customer stays about **%s months** on average." % (
                  a["churn"] * 100, "forever" if math.isinf(a["lifetime_months"]) else "%.0f" % a["lifetime_months"]),
              "- Over that time a customer leaves **%s** after their own costs." % money(a, a["lifetime_value"]),
              "- So a customer is worth **%s** what it costs to win them (3 times or more is healthy)." % (
                  "unlimited times" if math.isinf(a["value_to_cost"]) else "%.1f times" % a["value_to_cost"]),
              "- It takes **%s months** of their payments to earn back what it cost to win them." % (
                  "never" if math.isinf(a["months_to_earn_back_customer"])
                  else "%.1f" % a["months_to_earn_back_customer"]),
              ""]
    L += ["## Break-even", "", "Fixed costs: %s a month (%s)." % (money(a, a["fixed_monthly"]), ", ".join(
        "%s %s" % (it.get("label", "cost"), money(a, float(it["cost"]))) for it in spec.get("fixed_monthly", []))
        or "none given"), ""]
    if sub:
        L.append("- **You need %s paying customers** to cover the fixed costs, not counting what you spend to win"
                 " new ones." % _count(a["breakeven"]))
    else:
        L.append("- **You need %s %ss a month** to cover the fixed costs%s." % (
            _count(a["breakeven"]), unit,
            (" (%s a day)" % _count(a["breakeven_per_day"])) if a.get("breakeven_per_day") is not None else ""))
    if a["capacity"] is not None:
        L.append("- Capacity: %s." % _count(a["capacity"]))
    L += ["", "## Month by month", ""]
    head = "customers" if sub else "%ss" % unit
    L += ["| month | %s | revenue | profit | running total (after %s startup) |" % (head, money(a, a["startup"])),
          "| ---: | ---: | ---: | ---: | ---: |"]
    for row in a["months"]:
        if row["month"] <= 12 or row["month"] % 6 == 0:
            L.append("| %d | %s | %s | %s | %s |" % (row["month"], "{:,.0f}".format(row["volume"]),
                                                    money(a, row["revenue"]), money(a, row["profit"]),
                                                    money(a, row["cumulative"])))
    if a["repeats_month_12"]:
        L.append("")
        L.append("Months 13 to 24 repeat month 12's %s." % ("new customers" if sub else "sales"))
    L += ["",
          "- **Month 12: %s profit** on %s of revenue." % (money(a, a["month12_profit"]), money(a, a["month12_revenue"])),
          "- Year 1 in total: %s profit on %s of revenue." % (money(a, a["year1_profit"]), money(a, a["year1_revenue"])),
          "- First month in profit: %s." % _month(a["first_profit_month"]),
          "- **Cash you need before it pays for itself: %s** (the startup spend plus the early losses)."
          % money(a, a["cash_needed"]),
          "- **The money you put in comes back: %s.**" % _month(a["payback_month"]), ""]
    L += ["## What if things go worse", "",
          "| scenario | month 12 profit | cash needed | money back |", "| --- | ---: | ---: | ---: |"]
    for name, s in what_ifs(spec):
        L.append("| %s | %s | %s | %s |" % (name, money(s, s["month12_profit"]), money(s, s["cash_needed"]),
                                           _month(s["payback_month"])))
    L.append("")
    est = estimates(spec)
    if est:
        L += ["## Estimates to replace with real quotes", ""]
        L += ["- %s: %s" % pair for pair in est]
        L.append("")
    if a["flags"]:
        L += ["## Red flags", ""] + ["- %s" % f for f in a["flags"]]
    else:
        L.append("No red flags in these numbers. They are only as good as the inputs, so check each cost against a"
                 " real quote.")
    return "\n".join(L) + "\n"


def _jsonable(a):
    out = {}
    for k, v in a.items():
        if isinstance(v, float) and math.isinf(v):
            out[k] = None
        else:
            out[k] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("numbers", help="the business's numbers.json")
    ap.add_argument("--out", help="write the report here (markdown)")
    ap.add_argument("--json", action="store_true", help="print the numbers as JSON")
    ap.add_argument("--price", type=float, help="what-if price")
    ap.add_argument("--volume", type=float, default=1.0, help="what-if: scale every sales or new-customer number")
    a = ap.parse_args(argv)
    try:
        spec = load(a.numbers)
        if a.price is not None:
            spec = dict(spec, price=a.price)
        if a.volume != 1.0:
            spec = copy.deepcopy(spec)
            for key in ("sales", "sales_per_day", "new_customers"):
                if key in spec:
                    spec[key] = [float(v) * a.volume for v in spec[key]]
        result = analyse(spec)
        text = report(spec, result)
    except NumbersError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(_jsonable(result), indent=1))
    elif a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Wrote %s" % a.out)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
