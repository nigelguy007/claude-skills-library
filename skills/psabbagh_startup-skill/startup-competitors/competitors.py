#!/usr/bin/env python3
"""Competitor table for startup-competitors. Python 3.8+, standard library only, no network.

The research is done by reading public pages. This tool keeps it honest: it checks
that every competitor has a link and the date it was checked, and turns the CSV into
the table and price summary that go in startup/competitors.md.

    python3 competitors.py check startup/competitors.csv
    python3 competitors.py table startup/competitors.csv [--out startup/competitors-table.md] [--json]

The CSV has one row per competitor, with these columns:

    name        the competitor, or the do-it-yourself way ("a spreadsheet", "nothing")
    type        direct    the same thing, sold to the same buyer
                indirect  a different product for the same job
                diy       how buyers solve it without buying anything new
    url         the public page every fact in the row comes from (required, even for diy:
                link where you saw that buyers do it this way)
    price       the price of the item closest to what the new business sells, as a
                number; leave it empty when there is no public price
    price_unit  what the price is per: month, year, purchase, hour, user...
    includes    what that price includes, so prices compare like with like
    headline    their own headline or tagline, copied word for word
    rating      their public rating out of 5, if there is one
    reviews     how many reviews that rating is based on
    checked     the date the page was read, YYYY-MM-DD
"""

import argparse
import csv
import json
import re
import sys

COLUMNS = ["name", "type", "url", "price", "price_unit", "includes", "headline", "rating", "reviews", "checked"]
TYPES = ["direct", "indirect", "diy"]
TYPE_WORDS = {"direct": "Direct", "indirect": "Indirect", "diy": "Do it yourself"}


class CompetitorsError(Exception):
    pass


def _number(text):
    text = (text or "").strip().replace(",", "").lstrip("$£€")
    if not text:
        return None
    return float(text)


def read(path):
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise CompetitorsError("%s is missing the column(s): %s" % (path, ", ".join(missing)))
            return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    except FileNotFoundError:
        raise CompetitorsError("no such file: %s" % path)


def problems(rows):
    """Every rule a row breaks, as (row number, name, problem)."""
    out = []
    seen = set()
    for i, r in enumerate(rows, start=2):  # row 1 is the header
        name = r.get("name", "")
        label = name or "(no name)"
        if not name:
            out.append((i, label, "no name"))
        elif name.lower() in seen:
            out.append((i, label, "listed twice"))
        seen.add(name.lower())
        if r.get("type") not in TYPES:
            out.append((i, label, "type %r is not one of %s" % (r.get("type"), ", ".join(TYPES))))
        if not re.match(r"^https?://\S+$", r.get("url", "")):
            out.append((i, label, "no link: every row needs the public page its facts come from"))
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", r.get("checked", "")):
            out.append((i, label, "checked must be the date the page was read, YYYY-MM-DD"))
        try:
            price = _number(r.get("price"))
            if price is not None and price < 0:
                out.append((i, label, "price cannot be negative"))
            if price is not None and not r.get("price_unit"):
                out.append((i, label, "a price needs a price_unit (month, purchase, ...)"))
        except ValueError:
            out.append((i, label, "price %r is not a number (leave it empty when there is no public price)"
                        % r.get("price")))
        try:
            rating = _number(r.get("rating"))
            if rating is not None and not 0 <= rating <= 5:
                out.append((i, label, "rating must be out of 5"))
        except ValueError:
            out.append((i, label, "rating %r is not a number" % r.get("rating")))
        if r.get("reviews") and not r["reviews"].replace(",", "").isdigit():
            out.append((i, label, "reviews must be a whole number"))
    return out


def _median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def summary(rows):
    """Counts by type and the price range for each price unit."""
    counts = {t: sum(1 for r in rows if r["type"] == t) for t in TYPES}
    units, direct_units = {}, {}
    unpriced = 0
    for r in rows:
        if r["type"] == "diy":
            continue
        price = _number(r.get("price"))
        if price is None:
            unpriced += 1
            continue
        units.setdefault(r["price_unit"], []).append(price)
        if r["type"] == "direct":
            direct_units.setdefault(r["price_unit"], []).append(price)

    def stats(groups):
        return {u: {"count": len(v), "lowest": min(v), "median": _median(v), "highest": max(v)}
                for u, v in groups.items()}

    prices, direct_prices = stats(units), stats(direct_units)
    notes = []
    if counts["direct"] == 0:
        notes.append("No direct competitor found. Say so plainly: it can mean nobody wants this as easily as it "
                     "means an open market.")
    if counts["diy"] == 0:
        notes.append("No do-it-yourself row. Most buyers already solve the problem somehow, even if it is "
                     "\"nothing, they live with it\"; add how.")
    return {"count": len(rows), "by_type": counts, "prices": prices, "direct_prices": direct_prices,
            "no_public_price": unpriced, "notes": notes}


def table_md(rows, currency="$"):
    money = lambda v: "%s%s" % (currency, ("{:,.0f}" if v == int(v) else "{:,.2f}").format(v))
    order = {t: i for i, t in enumerate(TYPES)}
    s = summary(rows)
    L = ["| competitor | type | price | includes | their headline | rating | checked |",
         "| --- | --- | ---: | --- | --- | --- | --- |"]
    for r in sorted(rows, key=lambda r: (order.get(r["type"], 9), r["name"].lower())):
        price = _number(r["price"])
        L.append("| [%s](%s) | %s | %s | %s | %s | %s | %s |" % (
            r["name"].replace("|", "/"), r["url"], TYPE_WORDS.get(r["type"], r["type"]),
            "no public price" if price is None else "%s a %s" % (money(price), r["price_unit"]),
            r["includes"].replace("|", "/"), ('"%s"' % r["headline"].replace("|", "/")) if r["headline"] else "",
            ("%s (%s reviews)" % (r["rating"], r["reviews"])) if r["rating"] else "", r["checked"]))
    L += ["", "%d alternatives: %d direct, %d indirect, %d do-it-yourself." % (
        s["count"], s["by_type"]["direct"], s["by_type"]["indirect"], s["by_type"]["diy"])]
    for unit, p in sorted(s["direct_prices"].items()):
        L.append("**Direct competitors, per %s** (%d with a public price): lowest %s, median %s, highest %s." % (
            unit, p["count"], money(p["lowest"]), money(p["median"]), money(p["highest"])))
    for unit, p in sorted(s["prices"].items()):
        L.append("All priced alternatives, per %s (%d): lowest %s, median %s, highest %s." % (
            unit, p["count"], money(p["lowest"]), money(p["median"]), money(p["highest"])))
    if s["no_public_price"]:
        L.append("%d %s no public price." % (s["no_public_price"], "has" if s["no_public_price"] == 1 else "have"))
    for note in s["notes"]:
        L += ["", note]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    c = sub.add_parser("check")
    c.add_argument("csv")
    t = sub.add_parser("table")
    t.add_argument("csv")
    t.add_argument("--out")
    t.add_argument("--json", action="store_true")
    t.add_argument("--currency", default="$")
    a = ap.parse_args(argv)
    try:
        rows = read(a.csv)
        found = problems(rows)
        if a.cmd == "check":
            if not found:
                print("%d rows, every one linked and dated." % len(rows))
            for line, name, p in found:
                print("row %d (%s): %s" % (line, name, p))
            for note in summary(rows)["notes"] if not found else []:
                print("note: %s" % note)
            return 1 if found else 0
        if found:
            raise CompetitorsError("fix these first (run check): " + "; ".join(
                "row %d (%s): %s" % f for f in found[:5]))
        if a.json:
            print(json.dumps(summary(rows), indent=1))
            return 0
        text = table_md(rows, a.currency)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print("Wrote %s" % a.out)
        else:
            sys.stdout.write(text)
    except CompetitorsError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
