#!/usr/bin/env python3
"""The business plan for startup-plan. Python 3.8+, standard library only, no network.

Reads what the other startup skills wrote into startup/ and assembles one
document, startup/plan.md, with a verdict at the top. The verdict is computed
from the numbers and the buyer panel, never written by hand:

    Profitable   every check passes
    Not yet      at least one check fails (each failing number is shown)
    Incomplete   the numbers or the buyer panel are missing

The checks:
    1. each sale (or each customer, each month) leaves money after its own costs
    2. subscriptions: a customer brings in more than it costs to win them
    3. by month 12 the business makes money every month
    4. the money put in (startup spend plus early losses) comes back within 24 months
    5. break-even fits within capacity, if a capacity is given
    6. enough simulated buyers would pay now, or start the free trial meaning to pay after it when the
       offer has one (default 20 %, change with --min-buy-rate)
    7. the buyers were shown the same price the numbers use
    8. if there is a marketing plan, the numbers use its forecast of new customers and their cost

    python3 plan.py                      reads ./startup, writes ./startup/plan.md
    python3 plan.py --dir path/to/startup --min-buy-rate 0.25
    python3 plan.py --check              print the verdict only; exit 0 if Profitable, 1 if not
"""

import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_BUY_RATE = 0.20
SECTIONS = [  # (file inside startup/, heading, the skill that writes it)
    ("summary.md", "Summary", "startup-plan"),
    ("board.md", "What the board said", "startup-board"),
    ("competitors.md", "The competition", "startup-competitors"),
    ("buyers/results.md", "The buyer panel", "startup-buyers"),
    ("marketing.md", "How customers will find it", "startup-marketing"),
    ("numbers.md", "The numbers", "startup-numbers"),
    ("real-test.md", "Test it on real people", "startup-plan"),
]


_MODULES = {}


def _module(folder, name):
    """A sibling skill's tool, loaded once (the folder names have hyphens, so no plain import)."""
    if name not in _MODULES:
        path = os.path.join(HERE, "..", folder, name + ".py")
        spec = importlib.util.spec_from_file_location("startup_" + name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULES[name] = mod
    return _MODULES[name]


def _numbers_module():
    return _module("startup-numbers", "numbers")


def _funnel_module():
    return _module("startup-marketing", "funnel")


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read().strip()
    except FileNotFoundError:
        return None
    return text or None


def _nest(text):
    """Drop a leading title and push every heading down one level, to sit under the section heading."""
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(("#" + l) if l.startswith("#") else l for l in lines).strip()


def verdict(d, min_buy_rate=MIN_BUY_RATE):
    """Return (verdict, checks, numbers, buyers, missing, notes). checks are (passed, sentence)."""
    nm = _numbers_module()
    checks, missing, notes = [], [], []
    numbers = buyers = None
    raw = _read(os.path.join(d, "numbers.json"))
    if raw is None:
        missing.append(("the numbers", "startup-numbers"))
    else:
        try:
            spec = json.loads(raw)
            numbers = nm.analyse(spec)
        except ValueError as e:
            raise nm.NumbersError("numbers.json is not valid JSON: %s" % e)
        a = numbers
        unit = a["unit"]
        money = lambda v, cents=False: nm.money(a, v, cents)
        sub = a["model"] == "subscription"
        each = "Each %s, each month," % unit if sub else "Each %s" % unit
        if a["contribution"] > 0:
            checks.append((True, "%s leaves %s after its own costs%s." % (
                each, money(a["contribution"], True), "" if sub else " and marketing")))
        else:
            checks.append((False, "%s LOSES %s after its own costs%s." % (
                each, money(-a["contribution"], True), "" if sub else " and marketing")))
        if sub:
            ratio = a["value_to_cost"]
            if math.isinf(ratio):
                checks.append((True, "Winning a customer costs nothing, by these numbers."))
            else:
                checks.append((ratio > 1, "A customer brings in %.1f times what it costs to win them." % ratio))
        checks.append((a["month12_profit"] > 0, "Month 12 %s %s." % (
            "makes" if a["month12_profit"] > 0 else "still loses", money(abs(a["month12_profit"])))))
        if a["payback_month"]:
            checks.append((True, "The money you put in (%s at the lowest point) comes back in month %d." % (
                money(a["cash_needed"]), a["payback_month"])))
        else:
            checks.append((False, "The money you put in (%s at the lowest point) does not come back within"
                                  " 24 months." % money(a["cash_needed"])))
        if a["capacity"] is not None:
            fits = a["breakeven"] <= a["capacity"]
            what = "paying customers" if sub else "%ss a month" % unit
            checks.append((fits, "Break-even (%s %s) %s what you can handle (%s)." % (
                nm._count(a["breakeven"]), what, "fits within" if fits else "is above", nm._count(a["capacity"]))))
        worse = nm.analyse(spec, volume=0.8)
        if worse["month12_profit"] <= 0 or worse["payback_month"] is None:
            notes.append("Fragile: with 20%% fewer %s, month 12 %s and the money %s." % (
                "new customers" if sub else "sales",
                "loses %s" % money(-worse["month12_profit"]) if worse["month12_profit"] <= 0
                else "makes %s" % money(worse["month12_profit"]),
                "does not come back within 24 months" if worse["payback_month"] is None
                else "comes back in month %d" % worse["payback_month"]))
    raw = _read(os.path.join(d, "buyers", "results.json"))
    if raw is None:
        missing.append(("the buyer panel", "startup-buyers"))
    else:
        buyers = json.loads(raw)
        rate = buyers["buy_rate"]
        buy = ("would start the free trial and expect to pay after it" if buyers.get("free_trial")
               else "would pay now")
        checks.append((rate >= min_buy_rate, "%d of %d simulated buyers %s (%.0f%%; the bar is %.0f%%)." % (
            buyers["buy_now"], buyers["answered"], buy, rate * 100, min_buy_rate * 100)))
        shown = buyers.get("offer_price")
        if numbers is not None and shown is not None and abs(float(shown) - numbers["price"]) > 0.005:
            checks.append((False, "The buyers were shown %s but the numbers use %s, so the panel has not tested this"
                                  " price. Run /startup-buyers again at %s with the same seed." % (
                                      nm.money(numbers, float(shown), True), nm.money(numbers, numbers["price"], True),
                                      nm.money(numbers, numbers["price"], True))))
    raw = _read(os.path.join(d, "marketing.json"))
    if numbers is not None:
        if raw is None:
            notes.append("No marketing plan yet, so the new customers in the numbers are a guess. Run"
                         " /startup-marketing to build them from real channels.")
        else:
            fm = _funnel_module()
            try:
                forecast = fm.forecast(json.loads(raw))
            except (ValueError, fm.FunnelError) as e:
                raise nm.NumbersError("marketing.json: %s" % e)
            ok, why = fm.matches(forecast, spec)
            if not forecast["year1_customers"]:
                checks.append((False, "The marketing plan wins no customers in year 1. Improve the offer"
                                      " (/startup-buyers) or find channels that reach more people."))
            elif ok:
                checks.append((True, "The numbers use the marketing plan: %.0f new customers in year 1, %s each to"
                                     " win." % (forecast["year1_customers"],
                                                fm._money(numbers["currency"], forecast["cost_per_customer"]))))
            else:
                checks.append((False, "%s%s. Run funnel.py --apply (see /startup-marketing), then build the plan"
                                      " again." % (why[0].upper(), why[1:])))
    if missing:
        v = "Incomplete"
    elif all(ok for ok, _ in checks):
        v = "Profitable"
    else:
        v = "Not yet"
    return v, checks, numbers, buyers, missing, notes


def build(d, min_buy_rate=MIN_BUY_RATE):
    nm = _numbers_module()
    v, checks, numbers, buyers, missing, notes = verdict(d, min_buy_rate)
    idea = _read(os.path.join(d, "idea.md"))
    name = None
    if idea and idea.splitlines()[0].startswith("# "):
        name = idea.splitlines()[0][2:].strip()
    if not name and numbers and numbers.get("business"):
        name = numbers["business"]
    L = ["# %s: business plan" % (name or "Your business"), "", "**Verdict: %s**" % v, ""]
    for ok, text in checks:
        L.append("- %s %s" % ("✓" if ok else "✗", text))
    for what, skill in missing:
        L.append("- Missing: %s. Run /%s, then build the plan again." % (what, skill))
    for note in notes:
        L += ["", note]
    L.append("")
    if numbers:
        a = numbers
        sub = a["model"] == "subscription"
        money = lambda val, cents=False: nm.money(a, val, cents)
        L += ["| key number | |", "| --- | ---: |",
              "| Price | %s %s |" % (money(a["price"], True), "a month per %s" % a["unit"] if sub else "a %s" % a["unit"]),
              "| What each %s leaves after its own costs%s | %s (%.0f%%) |" % (
                  a["unit"], "" if sub else " and marketing", money(a["contribution"], True), a["margin"] * 100)]
        if sub:
            L.append("| A customer is worth | %s what it costs to win them |" % (
                "unlimited times" if math.isinf(a["value_to_cost"]) else "%.1f times" % a["value_to_cost"]))
            L.append("| Break-even | %s paying customers |" % nm._count(a["breakeven"]))
        else:
            L.append("| Break-even | %s %ss a month |" % (nm._count(a["breakeven"]), a["unit"]))
        L += ["| Month 12 profit | %s |" % money(a["month12_profit"]),
              "| Year 1 profit | %s |" % money(a["year1_profit"]),
              "| Cash needed before it pays for itself | %s |" % money(a["cash_needed"]),
              "| Money back | %s |" % ("month %d" % a["payback_month"] if a["payback_month"] else "not within 24 months")]
        if buyers:
            L.append("| Buyer panel | %d of %d %s |" % (
                buyers["buy_now"], buyers["answered"],
                "would start the free trial" if buyers.get("free_trial") else "would pay now"))
        L.append("")
    not_done = []
    for fname, heading, skill in SECTIONS[:1]:
        text = _read(os.path.join(d, fname))
        if text:
            L += ["## %s" % heading, "", _nest(text), ""]
        else:
            not_done.append((heading, skill))
    if idea:
        L += ["## The idea", "", _nest(idea), ""]
    for fname, heading, skill in SECTIONS[1:]:
        text = _read(os.path.join(d, fname))
        if text:
            L += ["## %s" % heading, "", _nest(text), ""]
        else:
            not_done.append((heading, skill))
    if not_done:
        L += ["## Not done yet", ""]
        L += ["- %s: /%s" % pair for pair in not_done]
        L.append("")
    L.append("_The buyer panel is simulated buyers and the numbers are projections from your inputs. Confirm demand"
             " with real customers and costs with real quotes before you spend. Not financial, legal or tax advice._")
    return v, "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default="startup")
    ap.add_argument("--min-buy-rate", type=float, default=MIN_BUY_RATE)
    ap.add_argument("--check", action="store_true", help="print the verdict only; exit 0 if Profitable")
    ap.add_argument("--out", help="default: <dir>/plan.md")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.dir):
        print("error: no %s/ folder here. Run /startup-board first." % a.dir, file=sys.stderr)
        return 2
    nm = _numbers_module()
    try:
        if a.check:
            v, checks, _, _, missing, notes = verdict(a.dir, a.min_buy_rate)
            print("Verdict: %s" % v)
            for ok, text in checks:
                print("  %s %s" % ("✓" if ok else "✗", text))
            for what, skill in missing:
                print("  Missing: %s (run /%s)" % (what, skill))
            for note in notes:
                print("  %s" % note)
            return 0 if v == "Profitable" else 1
        v, text = build(a.dir, a.min_buy_rate)
    except nm.NumbersError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    out = a.out or os.path.join(a.dir, "plan.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("Verdict: %s. Wrote %s" % (v, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
