#!/usr/bin/env python3
"""Customer forecast for startup-marketing. Python 3.8+, standard library only, no network.

Turns a channel plan into the two numbers every forecast hangs on: how many new
customers arrive each month, and what each one costs to win. Each channel says how
many people it reaches a month, the steps from "reached" to "paid" with the share
that makes each step, what it costs, and how many of the founder's hours it takes.

    python3 funnel.py startup/marketing.json
    python3 funnel.py startup/marketing.json --out startup/marketing-forecast.md
    python3 funnel.py startup/marketing.json --buyers startup/buyers/results.json
    python3 funnel.py startup/marketing.json --apply startup/numbers.json
    python3 funnel.py startup/marketing.json --json

The input:

    business, currency (default "$")
    sales_per_customer   one-time businesses only: sales each new customer makes in the
                         month they are won (default 1)
    channels             a list of:
        name                     "Messages to plumbers the founder knows"
        reach                    people reached a month: one number, or 12 (one per month)
        reach_unit               what one unit of reach is: messages, calls, visitors, clicks
        steps                    [{name, rate}] from reached to paid; rate is a share (0.2 = 20 %)
        cost_per_month           fixed spend on the channel each month (ad budget, a tool)
        cost_per_reach           spend per unit of reach (cost per click, per letter)
        founder_hours_per_month  the founder's own time the channel takes
        delay_months             optional: months between reaching someone and their first payment
                                 (1 for a free trial that ends the next month)
        source                   where the rates come from; start it with "estimate" if guessed.
                                 A step can carry its own "source" too.

    reach, a step's rate, cost_per_month and founder_hours_per_month each take one
    number, or 12 (one per month) when they change over the year: rates usually rise as
    the founder gets better at a channel, and hours move from one channel to another.

--buyers compares each channel with the buyer panel: reaching a person and getting
them to pay cannot convert better than the panel's best case. --apply writes the
forecast into numbers.json (new_customers and cost_to_win_customer for a subscription,
sales and marketing_per_sale for one-off sales), so the numbers use the plan.
"""

import argparse
import json
import math
import sys

MONTHS = 12
FULL_TIME_HOURS = 160


class FunnelError(Exception):
    pass


def _num(value, what, minimum=0.0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise FunnelError("%s is not a number: %r" % (what, value))
    if v < minimum:
        raise FunnelError("%s must be at least %s" % (what, minimum))
    return v


def _monthly(value, what):
    if isinstance(value, list):
        if len(value) != MONTHS:
            raise FunnelError("%s needs one number, or 12 (one per month)" % what)
        return [_num(v, what) for v in value]
    return [_num(value, what)] * MONTHS


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise FunnelError("no such file: %s" % path)
    except json.JSONDecodeError as e:
        raise FunnelError("%s is not valid JSON: %s" % (path, e))


def _rates(steps, name):
    """Each step's rate for each month (a step may give one rate, or 12 as the founder improves)."""
    out = []
    for s in steps:
        what = "%s: the rate of step %r" % (name, s.get("name"))
        if "rate" not in s:
            raise FunnelError("%s is missing" % what)
        rates = _monthly(s["rate"], what)
        if any(r > 1 for r in rates):
            raise FunnelError("%s: step %r has a rate above 1 (0.2 means 20 %%)" % (name, s.get("name")))
        out.append(rates)
    return out


def forecast(spec):
    """Every number in the forecast, as a dict. A pure function of the plan."""
    channels = spec.get("channels")
    if not channels:
        raise FunnelError("'channels' is missing: name at least one way customers will find the business")
    out_channels = []
    customers = [0.0] * MONTHS
    spend = [0.0] * MONTHS
    hours = [0.0] * MONTHS
    for i, ch in enumerate(channels):
        name = ch.get("name") or "channel %d" % (i + 1)
        if "reach" not in ch:
            raise FunnelError("%s: 'reach' is missing (people reached a month)" % name)
        steps = ch.get("steps")
        if not steps:
            raise FunnelError("%s: 'steps' is missing (from reached to paid, each with a rate)" % name)
        reach = _monthly(ch["reach"], "%s: reach" % name)
        rates = _rates(steps, name)
        conversion = [1.0] * MONTHS
        for step_rates in rates:
            conversion = [c * r for c, r in zip(conversion, step_rates)]
        delay = int(_num(ch.get("delay_months", 0), "%s: delay_months" % name))
        if delay >= MONTHS:
            raise FunnelError("%s: delay_months must be under 12" % name)
        fixed = _monthly(ch.get("cost_per_month", 0), "%s: cost_per_month" % name)
        per_reach = _num(ch.get("cost_per_reach", 0), "%s: cost_per_reach" % name)
        h = _monthly(ch.get("founder_hours_per_month", 0), "%s: founder_hours_per_month" % name)
        raw = [r * c for r, c in zip(reach, conversion)]
        won = [raw[m - delay] if m >= delay else 0.0 for m in range(MONTHS)]
        cost = [f + r * per_reach for f, r in zip(fixed, reach)]
        for m in range(MONTHS):
            customers[m] += won[m]
            spend[m] += cost[m]
            hours[m] += h[m]
        total_won, total_cost = sum(won), sum(cost)
        step_sources = [str(s.get("source", "")) for s in steps if s.get("source")]
        out_channels.append({
            "name": name, "reach": reach, "reach_unit": ch.get("reach_unit", "people"),
            "steps": [{"name": s.get("name", ""), "rates": r, "source": str(s.get("source", ""))}
                      for s, r in zip(steps, rates)],
            "conversion": max(conversion), "conversion_by_month": conversion, "delay_months": delay,
            "customers": won, "spend": cost, "founder_hours": max(h), "founder_hours_by_month": h,
            "cost_per_customer": (total_cost / total_won) if total_won else math.inf,
            "source": str(ch.get("source", "")), "step_sources": step_sources,
        })

    def guessed(c):
        sources = ([c["source"]] if c["source"] else []) + c["step_sources"]
        return not sources or any(s.lower().startswith("estimate") for s in sources)

    total_customers, total_spend = sum(customers), sum(spend)
    result = {
        "business": spec.get("business", ""), "currency": spec.get("currency", "$"),
        "channels": out_channels, "customers": customers, "spend": spend,
        "year1_customers": total_customers, "year1_spend": total_spend,
        "cost_per_customer": (total_spend / total_customers) if total_customers else math.inf,
        "founder_hours": max(hours), "founder_hours_by_month": hours,
        "sales_per_customer": _num(spec.get("sales_per_customer", 1), "sales_per_customer"),
        "estimated": any(guessed(c) for c in out_channels),
    }
    result["flags"] = _flags(result)
    return result


def _flags(f, buy_rate=None):
    flags = []
    if f["founder_hours"] > FULL_TIME_HOURS:
        flags.append("The channels take up to %.0f of the founder's hours a month, more than a full-time job."
                     % f["founder_hours"])
    if f["customers"][-1] < 1:
        flags.append("Month 12 brings in fewer than one new customer.")
    for c in f["channels"]:
        if not c["source"] and not c["step_sources"]:
            flags.append("%s has no source for its rates: mark them \"estimate: ...\" at least." % c["name"])
        if buy_rate is not None and c["conversion"] > buy_rate:
            flags.append("%s turns %.1f%% of the people it reaches into customers, more than the buyer panel's best"
                         " case (%.0f%%). Lower the rates." % (c["name"], c["conversion"] * 100, buy_rate * 100))
    return flags


def check_against_buyers(f, results_path):
    with open(results_path, encoding="utf-8") as fh:
        results = json.load(fh)
    f["flags"] = _flags(f, float(results["buy_rate"]))
    return f


def apply(f, numbers_path):
    """Write the forecast into numbers.json, keeping everything else in it."""
    try:
        with open(numbers_path, encoding="utf-8") as fh:
            numbers = json.load(fh)
    except FileNotFoundError:
        raise FunnelError("no such file: %s (write the rest of the numbers first)" % numbers_path)
    if not f["year1_customers"]:
        raise FunnelError("the plan wins no customers in year 1, so there is nothing to put in the numbers. That is"
                          " the result: the plan will show it as a failing check. Improve the offer first"
                          " (startup-buyers: Improve the pitch and re-test), or find a channel that reaches more people")
    model = numbers.get("model")
    names = ", ".join(c["name"] for c in f["channels"])
    source = "%sfrom the marketing plan (startup/marketing.json: %s)" % (
        "estimate: " if f["estimated"] else "", names)
    sources = dict(numbers.get("sources") or {})
    if model == "subscription":
        numbers["new_customers"] = [round(v, 2) for v in f["customers"]]
        numbers["cost_to_win_customer"] = round(f["cost_per_customer"], 2)
        sources["new_customers"] = sources["cost_to_win_customer"] = source
    elif model == "one-time":
        sales = [v * f["sales_per_customer"] for v in f["customers"]]
        numbers.pop("sales_per_day", None)
        numbers["sales"] = [round(v, 2) for v in sales]
        numbers["marketing_per_sale"] = round(f["year1_spend"] / sum(sales), 2)
        sources["sales"] = sources["marketing_per_sale"] = source
    else:
        raise FunnelError("%s has no 'model' (subscription or one-time)" % numbers_path)
    numbers["sources"] = sources
    with open(numbers_path, "w", encoding="utf-8") as fh:
        json.dump(numbers, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return numbers


def matches(f, numbers):
    """Whether numbers.json uses this forecast. Returns (True, '') or (False, why)."""
    model = numbers.get("model")
    if model == "subscription":
        planned = [float(v) for v in (numbers.get("new_customers") or [])][:MONTHS]
        expected = f["customers"]
        what = "new customers"
        cost_ok = abs(float(numbers.get("cost_to_win_customer", -1)) - round(f["cost_per_customer"], 2)) <= 0.01
    elif model == "one-time":
        planned = [float(v) for v in (numbers.get("sales") or [])][:MONTHS]
        expected = [v * f["sales_per_customer"] for v in f["customers"]]
        what = "sales"
        sales_total = sum(expected)
        cost = (f["year1_spend"] / sales_total) if sales_total else math.inf
        cost_ok = abs(float(numbers.get("marketing_per_sale", -1)) - round(cost, 2)) <= 0.01
    else:
        return False, "the numbers have no model"
    if len(planned) != MONTHS or any(abs(p - e) > 0.01 for p, e in zip(planned, expected)):
        return False, "the numbers' %s are not the marketing plan's" % what
    if not cost_ok:
        return False, "the numbers' cost of winning a customer is not the marketing plan's"
    return True, ""


def _money(cur, v):
    return "unlimited" if math.isinf(v) else "%s%s" % (cur, "{:,.0f}".format(round(v)))


def _span(values, fmt, unit=""):
    """One value, or 'up to the peak (month 1, month 12)' when it changes over the year."""
    unit = (" " + unit) if unit else ""
    if len(set(round(v, 6) for v in values)) == 1:
        return fmt(values[0]) + unit
    return "up to %s%s (month 1: %s, month 12: %s)" % (fmt(max(values)), unit, fmt(values[0]), fmt(values[-1]))


def _range(values, fmt):
    lo, hi = min(values), max(values)
    return fmt(lo) if abs(hi - lo) < 1e-9 else "%s to %s" % (fmt(lo), fmt(hi))


def report(f):
    cur = f["currency"]
    whole = lambda v: "{:,.0f}".format(v)
    pct = lambda v: "%.0f%%" % (v * 100)
    pct1 = lambda v: "%.1f%%" % (v * 100)
    L = ["# How customers will find it: the forecast", "",
         "Every number below comes from the channel plan in marketing.json. Rates marked as estimates are"
         " guesses to replace with real results.", "",
         "| channel | reached a month | steps to paid | new customers in month 12 | cost per customer | founder hours a month |",
         "| --- | --- | --- | ---: | ---: | ---: |"]
    for c in f["channels"]:
        steps = ", then ".join("%s %s" % (s["name"], _range(s["rates"], pct)) for s in c["steps"])
        delay = ("; paying customers counted %d month%s later" % (c["delay_months"], "" if c["delay_months"] == 1 else "s")
                 if c["delay_months"] else "")
        L.append("| %s | %s | %s (%s overall%s) | %.1f | %s | %s |" % (
            c["name"].replace("|", "/"), _span(c["reach"], whole, c["reach_unit"]), steps,
            _range(c["conversion_by_month"], pct1), delay, c["customers"][-1],
            _money(cur, c["cost_per_customer"]), _span(c["founder_hours_by_month"], whole)))
    L += ["", "| month | new customers | spend | founder hours |", "| ---: | ---: | ---: | ---: |"]
    for m in range(MONTHS):
        L.append("| %d | %.1f | %s | %.0f |" % (m + 1, f["customers"][m], _money(cur, f["spend"][m]),
                                              f["founder_hours_by_month"][m]))
    L += ["",
          "- **Year 1: %.0f new customers** for %s of spend." % (f["year1_customers"], _money(cur, f["year1_spend"])),
          "- **Cost to win one customer: %s** across all channels." % _money(cur, f["cost_per_customer"]),
          "- The founder's time: %s hours a month." % _span(f["founder_hours_by_month"], whole)]
    sources = []
    for c in f["channels"]:
        if c["source"]:
            sources.append("- %s: %s" % (c["name"], c["source"]))
        for s in c["steps"]:
            if s["source"]:
                sources.append("- %s, %s: %s" % (c["name"], s["name"], s["source"]))
    if sources:
        L += ["", "## Where the rates come from", ""] + sources
    if f["flags"]:
        L += ["", "## Red flags", ""] + ["- %s" % x for x in f["flags"]]
    return "\n".join(L) + "\n"


def _jsonable(obj):
    if isinstance(obj, float) and math.isinf(obj):
        return None
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    return obj


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("plan", help="startup/marketing.json")
    ap.add_argument("--out", help="write the forecast here (markdown)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--buyers", help="startup/buyers/results.json, to check the rates against the panel")
    ap.add_argument("--apply", metavar="NUMBERS", help="write the forecast into this numbers.json")
    a = ap.parse_args(argv)
    try:
        f = forecast(load(a.plan))
        if a.buyers:
            try:
                check_against_buyers(f, a.buyers)
            except FileNotFoundError:
                raise FunnelError("no such file: %s" % a.buyers)
        if a.apply:
            apply(f, a.apply)
            print("Wrote the forecast into %s: %.0f new customers in year 1, %s each to win." % (
                a.apply, f["year1_customers"], _money(f["currency"], f["cost_per_customer"])))
        if a.json:
            print(json.dumps(_jsonable(f), indent=1))
        elif a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(report(f))
            print("Wrote %s" % a.out)
        elif not a.apply:
            sys.stdout.write(report(f))
    except FunnelError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
