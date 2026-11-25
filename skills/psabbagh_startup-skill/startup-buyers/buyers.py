#!/usr/bin/env python3
"""Simulated buyer panel for startup-buyers. Python 3.8+, standard library only, no network.

Deals one card per simulated buyer from a target-customer profile, writes the brief
each buyer sub-agent reads, checks the answers the buyers write, and counts them:
who would pay now, who passes and why, what would change their mind, and the price
range they would accept.

    python3 buyers.py init --customer startup/buyers/customer.json --pitch startup/buyers/pitch.md [--n 100] [--seed 41] [--replace]
    python3 buyers.py briefs [--wave 10]   a brief for every buyer still without a valid answer, listed in waves
    python3 buyers.py check                which answers are missing or broken
    python3 buyers.py save B007 < reply    file a buyer's own JSON when it printed it instead of writing the file
    python3 buyers.py tally                write results.md and results.json
    python3 buyers.py status

Everything lives in startup/buyers/ (change it with --dir before the command).

The tool never writes an answer for a buyer. Every count in results.md comes from
answer files the buyers wrote themselves.
"""

import argparse
import json
import os
import random
import string
import sys

DECISIONS = ["buy_now", "probably", "not_now", "no"]
DECISION_WORDS = {
    "buy_now": "would pay now",
    "probably": "probably, later",
    "not_now": "not now",
    "no": "no",
}
REASONS = [
    "solves_my_problem", "price", "budget", "no_need", "happy_with_today", "trust",
    "missing_info", "switching_effort", "quality", "convenience", "timing", "other",
]
REQUIRED = ("id", "decision", "reason_code", "reason")
PRICE_KEYS = ("price_too_cheap", "price_bargain", "price_expensive", "price_too_expensive")
WAVE = 10
DEFAULT_PAIN = [
    {"level": "You don't really feel this problem", "share": 0.25},
    {"level": "It annoys you now and then, but you live with it", "share": 0.40},
    {"level": "It costs you time or money most weeks, and you have tried to fix it", "share": 0.25},
    {"level": "It is urgent: you are looking for a fix right now", "share": 0.10},
]
NAMES = [
    "Abel", "Adele", "Aiko", "Alba", "Alexei", "Amani", "Anouk", "Arash", "Astrid", "Aurelio",
    "Bea", "Bjorn", "Bruno", "Camila", "Carmen", "Cedric", "Chidi", "Cora", "Dalia", "Dante",
    "Delphine", "Dmitri", "Eamon", "Edith", "Elif", "Emeka", "Enzo", "Esther", "Fabian", "Femi",
    "Fiona", "Gael", "Gemma", "Gideon", "Greta", "Gustavo", "Halima", "Hector", "Helga", "Hiro",
    "Ida", "Ibrahim", "Ilse", "Imani", "Ingrid", "Ismael", "Jamal", "Jana", "Javier", "Joelle",
    "Jorge", "Juno", "Kamal", "Karin", "Kasia", "Kemal", "Kenzo", "Lara", "Laszlo", "Layla",
    "Lorenzo", "Lucie", "Magnus", "Malia", "Manon", "Marek", "Maribel", "Matteo", "Mehmet", "Mila",
    "Moses", "Nadine", "Naveen", "Nell", "Niamh", "Nils", "Odette", "Olu", "Orla", "Otto",
    "Paloma", "Paolo", "Petra", "Pilar", "Quentin", "Radhika", "Ramon", "Renata", "Reza", "Rina",
    "Romy", "Ruth", "Salma", "Santiago", "Saoirse", "Sergei", "Shira", "Simone", "Soren", "Stellan",
    "Sunita", "Tamsin", "Teodor", "Thandi", "Tobias", "Ulla", "Umar", "Valentina", "Vera", "Viktor",
    "Wanjiru", "Wendell", "Xavier", "Yasmin", "Yosef", "Yuki", "Zainab", "Zeno", "Zofia", "Zuri",
]


class BuyersError(Exception):
    pass


# ---- dealing the cards ---------------------------------------------------------

def allocate(items, n):
    """Split n slots across items in proportion to their 'share', exactly, by largest remainder."""
    weights = [float(it.get("share", 1)) for it in items]
    total = sum(weights)
    if total <= 0:
        raise BuyersError("shares must add up to more than zero")
    exact = [n * w / total for w in weights]
    counts = [int(x) for x in exact]
    leftovers = sorted(range(len(items)), key=lambda i: exact[i] - counts[i], reverse=True)
    for i in leftovers[: n - sum(counts)]:
        counts[i] += 1
    return counts


def _need(c, key, what):
    if key not in c or c[key] in ("", [], None):
        raise BuyersError("customer.json needs '%s' (%s)" % (key, what))


def check_customer(c):
    _need(c, "business", "the business name")
    _need(c, "target", "who the customer is, in one line")
    _need(c, "category", "what the buyer is spending on, in their words")
    _need(c, "segments", "2 to 4 groups, each with a share, an income range and a budget range")
    _need(c, "behaviours", "how these people shop, each with a share")
    _need(c, "today", "what they use today instead, each with a share")
    period = c.get("budget_period", "month")
    if period not in ("month", "year", "purchase"):
        raise BuyersError("budget_period must be month, year or purchase")
    if not isinstance(c.get("free_trial", False), bool):
        raise BuyersError("free_trial must be true or false")
    for s in c["segments"]:
        for key in ("name", "income", "budget"):
            if key not in s:
                raise BuyersError("every segment needs a name, an income [low, high] and a budget [low, high]")
        for key in ("income", "budget"):
            if not isinstance(s[key], list) or len(s[key]) != 2 or float(s[key][0]) > float(s[key][1]):
                raise BuyersError("segment %r: %s must be [low, high]" % (s["name"], key))
    for b in c["behaviours"]:
        if "name" not in b:
            raise BuyersError("every behaviour needs a name")
    for t in c["today"]:
        if "name" not in t:
            raise BuyersError("every entry in 'today' needs a name")
    for p in c.get("pain") or []:
        if "level" not in p:
            raise BuyersError("every pain entry needs a level")


def _spread(items, n, rng):
    out = []
    for item, k in zip(items, allocate(items, n)):
        out.extend([item] * k)
    rng.shuffle(out)
    return out


def _names(n, rng):
    pool = NAMES[:]
    rng.shuffle(pool)
    out = []
    round_ = 0
    while len(out) < n:
        round_ += 1
        out.extend(pool if round_ == 1 else ["%s %d" % (x, round_) for x in pool])
    return out[:n]


def deal(customer, n=100, seed=41):
    """Deal n buyer cards. The same profile, n and seed always give the same cards."""
    check_customer(customer)
    if n < 1:
        raise BuyersError("--n must be at least 1")
    rng = random.Random(seed)
    lo_age, hi_age = customer.get("age", [25, 55])
    segments = _spread(customer["segments"], n, rng)
    behaviours = _spread(customer["behaviours"], n, rng)
    today = _spread(customer["today"], n, rng)
    pain = _spread(customer.get("pain") or DEFAULT_PAIN, n, rng)
    situations = customer.get("situations") or []
    names = _names(n, rng)
    cards = []
    for i in range(n):
        seg = segments[i]
        income = rng.uniform(float(seg["income"][0]), float(seg["income"][1]))
        budget = rng.uniform(float(seg["budget"][0]), float(seg["budget"][1]))
        cards.append({
            "id": "B%03d" % (i + 1),
            "name": names[i],
            "age": rng.randint(int(lo_age), int(hi_age)),
            "segment": seg["name"],
            "income": int(round(income, -3)),
            "budget": _round_budget(budget),
            "behaviour": behaviours[i]["name"],
            "behaviour_how": behaviours[i].get("how", ""),
            "today": today[i]["name"],
            "pain": pain[i]["level"],
            "situation": situations[rng.randrange(len(situations))] if situations else "",
        })
    return cards


def _round_budget(v):
    if v >= 1000:
        return int(round(v, -2))
    if v >= 100:
        return int(round(v, -1))
    return int(round(v))


# ---- files ---------------------------------------------------------------------

def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path, obj):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def _clear_previous(d, replace):
    """Refuse to deal over an earlier panel's answers, or clear them when asked to.

    Old answers were written against old cards and an old pitch; `briefs` would treat them
    as done and mix them into the new panel.
    """
    answers = os.path.join(d, "answers")
    old = sorted(f for f in os.listdir(answers) if f.endswith(".json")) if os.path.isdir(answers) else []
    if old and not replace:
        raise BuyersError(
            "%s already holds %d answers from an earlier panel. To keep them, move the folder aside first "
            "(for example mv %s %s-v1) and copy its customer.json back; to delete them and start again, add "
            "--replace." % (d, len(old), d, d.rstrip("/")))
    if replace:
        for sub, ext in (("answers", ".json"), ("briefs", ".md")):
            folder = os.path.join(d, sub)
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    if f.endswith(ext):
                        os.remove(os.path.join(folder, f))
        for f in ("results.md", "results.json"):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))


def init(d, customer_path, pitch_path, n=100, seed=None, replace=False):
    _clear_previous(d, replace)
    try:
        customer = _read_json(customer_path)
    except FileNotFoundError:
        raise BuyersError("no such file: %s" % customer_path)
    except json.JSONDecodeError as e:
        raise BuyersError("%s is not valid JSON: %s" % (customer_path, e))
    try:
        with open(pitch_path, encoding="utf-8") as fh:
            pitch = fh.read().strip()
    except FileNotFoundError:
        raise BuyersError("no such file: %s (write the pitch first: what it is, the price, how to get it)" % pitch_path)
    if not pitch:
        raise BuyersError("the pitch is empty")
    if seed is None:
        seed = random.SystemRandom().randrange(1, 1000000)
    cards = deal(customer, n, seed)
    _write_json(os.path.join(d, "panel.json"), {"n": n, "seed": seed, "customer": customer, "pitch": pitch})
    _write_json(os.path.join(d, "cards.json"), cards)
    os.makedirs(os.path.join(d, "briefs"), exist_ok=True)
    os.makedirs(os.path.join(d, "answers"), exist_ok=True)
    return seed, cards


def load(d):
    try:
        return _read_json(os.path.join(d, "panel.json")), _read_json(os.path.join(d, "cards.json"))
    except FileNotFoundError:
        raise BuyersError("no panel in %s yet: run init first" % d)


# ---- the brief each buyer reads ------------------------------------------------

BRIEF = string.Template("""You are one buyer on a simulated customer panel. Someone is thinking about starting a business and wants to know, before they spend money, whether people like you would actually pay. A polite yes would mislead them. Most people pass on most offers, and a clear no is a useful answer.

WHO YOU ARE
$name, $age. $segment. You earn about $income a year.
What you spend on $category today, or would spend without thinking twice: about $budget a $period. You would only pay more if you were convinced it brings in or saves you more than it costs.
How you shop: $behaviour. $behaviour_how
What you do about this today: $today.
How much this problem bothers you: $pain.
$situation_line
You are one of these people: $target.

THE OFFER (you are seeing it for the first time, the way you would see an ad or a post)
$pitch

HOW TO DECIDE
- Decide as $name would, in an ordinary week, with $name's money, habits and budget.
- You were not looking for this, unless the line about how much the problem bothers you says you are.
- Buying means changing what you do today. Count that effort.
- Use only what the offer says. If something you would need to know is missing, react the way a real buyer would, which is usually to wait.
- Your doubts are your own. Say what would really stop you, in your own words.

YOUR ANSWER
Use only two tools: one to read this brief, one to write your answer. Do not call any other tool, and do not create folders: the folder for your answer already exists.
Create the file $out with your file-writing tool. Do not only print the answer in your reply. The file must contain only this JSON, with no code fence and nothing else:
{
  "id": "$id",
  "decision": one of "buy_now", "probably", "not_now", "no",
  "first_month": how many times you would pay in your first month as a paying customer, as a number (0 if you would not buy),
  "reason_code": one of $reasons,
  "reason": "why, in one or two sentences, in your own voice",
  "objection": "the doubt that weighs most for you, in your own words",
  "would_change_my_mind": "the one thing that would change your answer, or an empty string",
  "instead": "what you will do instead, or what you would stop using if you bought",
  "price_too_cheap": the price at which it would seem too cheap to be any good, as a number,
  "price_bargain": the price at which it would feel like a bargain, as a number,
  "price_expensive": the price at which it starts to feel expensive, though you might still buy, as a number,
  "price_too_expensive": the price at which you would not buy it at all, as a number
}
What the decisions mean: $decisions not_now = maybe one day, not now. no = it is not for you.
Give the four prices per $period, the same way the offer is priced.
""")

DECIDE_PAY = ("buy_now = you would pay for it today, at this price. probably = you are interested, but you would"
              " wait or want to see more first.")
DECIDE_TRIAL = ("The offer starts with a free trial. buy_now = you would start the free trial today, and you expect"
                " to keep paying the price after it if it does what the offer says. probably = you are interested,"
                " but you would wait, or want to see more, before even starting the trial.")


def buy_words(customer_or_results):
    """How a buy reads in the results, which depends on the first step the offer asks for."""
    if customer_or_results.get("free_trial"):
        return "would start the free trial today and expect to pay after it"
    return "would pay now"


def _money(customer, v):
    return "%s%s" % (customer.get("currency", "$"), "{:,}".format(v))


def brief_text(state, card, out_path):
    c = state["customer"]
    return BRIEF.substitute(
        name=card["name"], age=card["age"], segment=card["segment"],
        income=_money(c, card["income"]), budget=_money(c, card["budget"]),
        period=c.get("budget_period", "month"), category=c["category"],
        behaviour=card["behaviour"], behaviour_how=card["behaviour_how"],
        today=card["today"], pain=card["pain"],
        situation_line=("Your days: %s." % card["situation"]) if card.get("situation") else "",
        target=c["target"], pitch=state["pitch"], out=os.path.abspath(out_path),
        id=card["id"], reasons=", ".join('"%s"' % r for r in REASONS),
        decisions=DECIDE_TRIAL if c.get("free_trial") else DECIDE_PAY,
    )


def write_briefs(d, wave=WAVE):
    state, cards = load(d)
    todo = []
    for card in cards:
        out = os.path.join(d, "answers", card["id"] + ".json")
        if problem(out, card["id"]) is None:
            continue
        path = os.path.join(d, "briefs", card["id"] + ".md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(brief_text(state, card, out))
        todo.append((card["id"], os.path.abspath(path)))
    return [todo[i:i + wave] for i in range(0, len(todo), wave)]


# ---- checking answers ----------------------------------------------------------

def problem(path, buyer_id):
    """None if the answer file is usable, otherwise what is wrong with it."""
    if not os.path.exists(path):
        return "missing"
    try:
        a = _read_json(path)
    except (ValueError, UnicodeDecodeError):
        return "not valid JSON"
    if not isinstance(a, dict):
        return "not a JSON object"
    absent = [k for k in REQUIRED if k not in a]
    if absent:
        return "missing " + ", ".join(absent)
    if a["id"] != buyer_id:
        return "id is %r, expected %s" % (a["id"], buyer_id)
    if a["decision"] not in DECISIONS:
        return "decision %r is not one of %s" % (a["decision"], ", ".join(DECISIONS))
    if a["reason_code"] not in REASONS:
        return "reason_code %r is not one of %s" % (a["reason_code"], ", ".join(REASONS))
    if not isinstance(a["reason"], str) or not a["reason"].strip():
        return "reason is empty"
    return None


def check(d):
    _, cards = load(d)
    out = []
    for card in cards:
        p = problem(os.path.join(d, "answers", card["id"] + ".json"), card["id"])
        if p:
            out.append((card["id"], p))
    return out


def save(d, buyer_id, reply):
    """File a buyer's OWN reply when it printed the JSON instead of writing it. Never used to answer for one."""
    _, cards = load(d)
    if buyer_id not in {c["id"] for c in cards}:
        raise BuyersError("no buyer %s on this panel" % buyer_id)
    start = reply.find("{")
    if start < 0:
        raise BuyersError("no JSON object in the reply")
    try:
        obj, _ = json.JSONDecoder().raw_decode(reply[start:])
    except ValueError as e:
        raise BuyersError("the reply's JSON does not parse: %s" % e)
    path = os.path.join(d, "answers", buyer_id + ".json")
    _write_json(path, obj)
    p = problem(path, buyer_id)
    if p:
        os.remove(path)
        raise BuyersError("%s's reply is not a valid answer (%s): run its brief again instead" % (buyer_id, p))
    return path


# ---- price range (Van Westendorp price sensitivity) ----------------------------

def _num(v):
    try:
        x = float(str(v).replace(",", "").strip().lstrip("$£€"))
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def price_rows(answers):
    """The usable four-price answers, plus how many were dropped (missing or out of order)."""
    rows, dropped = [], 0
    for a in answers:
        r = [_num(a.get(k)) for k in PRICE_KEYS]
        if any(v is None for v in r) or not (r[0] <= r[1] <= r[2] <= r[3]):
            dropped += 1
            continue
        rows.append(r)
    return rows, dropped


def _first_crossing(prices, down, up):
    """First price where the rising curve reaches the falling one, interpolated between grid points."""
    for i in range(1, len(prices)):
        before, after = up[i - 1] - down[i - 1], up[i] - down[i]
        if before == 0:
            return prices[i - 1]
        if before < 0 <= after:
            return prices[i - 1] + (prices[i] - prices[i - 1]) * (-before / (after - before))
    return None


def price_range(rows, steps=400):
    """The four Van Westendorp points from answers [too_cheap, bargain, expensive, too_expensive]."""
    if len(rows) < 5:
        return None
    lo = min(r[0] for r in rows)
    hi = max(r[3] for r in rows)
    if hi <= lo:
        return None
    prices = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    n = float(len(rows))

    def share(test):
        return [sum(1 for r in rows if test(r, p)) / n for p in prices]

    too_cheap = share(lambda r, p: r[0] >= p)
    bargain = share(lambda r, p: r[1] >= p)
    expensive = share(lambda r, p: r[2] <= p)
    too_expensive = share(lambda r, p: r[3] <= p)
    not_bargain = [1 - v for v in bargain]
    not_expensive = [1 - v for v in expensive]
    return {
        "answers": len(rows),
        "lowest": _first_crossing(prices, too_cheap, not_bargain),
        "ideal": _first_crossing(prices, too_cheap, too_expensive),
        "neutral": _first_crossing(prices, bargain, expensive),
        "highest": _first_crossing(prices, not_expensive, too_expensive),
    }


# ---- counting --------------------------------------------------------------------

def _rate(rows):
    return sum(1 for r in rows if r["decision"] == "buy_now") / float(len(rows)) if rows else 0.0


def _groups(rows, key):
    out = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    table = [(k, len(v), _rate(v)) for k, v in out.items()]
    return sorted(table, key=lambda t: (-t[2], -t[1], t[0]))


def _reasons(rows):
    out = {}
    for r in rows:
        out.setdefault(r["reason_code"], []).append(r)
    ranked = sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [{"code": k, "count": len(v), "quotes": [[r["id"], r["reason"]] for r in v[:3]]} for k, v in ranked]


def tally(d):
    state, cards = load(d)
    customer = state["customer"]
    rows, skipped = [], []
    for card in cards:
        path = os.path.join(d, "answers", card["id"] + ".json")
        p = problem(path, card["id"])
        if p:
            skipped.append([card["id"], p])
            continue
        answer = _read_json(path)
        row = dict(card)
        row.update({k: v for k, v in answer.items() if k not in card})
        rows.append(row)
    if not rows:
        raise BuyersError("no valid answers yet: run the briefs first (buyers.py briefs)")

    incomes = sorted(r["income"] for r in rows)
    third, two_thirds = incomes[len(incomes) // 3], incomes[2 * len(incomes) // 3]
    for r in rows:
        if r["income"] < third:
            r["income_band"] = "under %s" % _money(customer, third)
        elif r["income"] >= two_thirds:
            r["income_band"] = "%s and up" % _money(customer, two_thirds)
        else:
            r["income_band"] = "%s to %s" % (_money(customer, third), _money(customer, two_thirds))

    counts = {k: sum(1 for r in rows if r["decision"] == k) for k in DECISIONS}
    buyers = [r for r in rows if r["decision"] == "buy_now"]
    passers = [r for r in rows if r["decision"] != "buy_now"]

    over_budget = None
    price = _num(customer.get("offer_price"))
    if price is not None:
        over_budget = [r["id"] for r in buyers if r["budget"] < price]

    first_month = [_num(r.get("first_month")) for r in buyers]
    first_month = [v for v in first_month if v is not None]
    prices, dropped = price_rows(rows)

    return {
        "business": customer["business"],
        "free_trial": bool(customer.get("free_trial", False)),
        "seed": state["seed"],
        "dealt": len(cards),
        "answered": len(rows),
        "skipped": skipped,
        "counts": counts,
        "buy_now": counts["buy_now"],
        "buy_rate": counts["buy_now"] / float(len(rows)),
        "interest_rate": (counts["buy_now"] + counts["probably"]) / float(len(rows)),
        "by_segment": _groups(rows, "segment"),
        "by_pain": _groups(rows, "pain"),
        "by_today": _groups(rows, "today"),
        "by_behaviour": _groups(rows, "behaviour"),
        "by_income": _groups(rows, "income_band"),
        "why_not": _reasons(passers),
        "why_yes": _reasons(buyers),
        "objections": [[r["id"], r["objection"]] for r in passers if str(r.get("objection") or "").strip()],
        "flip": [[r["id"], r["would_change_my_mind"]] for r in passers
                 if str(r.get("would_change_my_mind") or "").strip()],
        "instead": [[r["id"], r["instead"]] for r in passers if str(r.get("instead") or "").strip()],
        "first_month_per_buyer": (sum(first_month) / len(first_month)) if first_month else None,
        "offer_price": price,
        "over_budget": over_budget,
        "price_range": price_range(prices),
        "price_answers": len(prices),
        "price_dropped": dropped,
        "currency": customer.get("currency", "$"),
        "period": customer.get("budget_period", "month"),
    }


def results_md(res):
    pct = lambda v: "%.0f%%" % (v * 100)
    cur = res.get("currency", "$")
    money = lambda v: "n/a" if v is None else "%s%s" % (cur, "{:,.2f}".format(v))
    c = res["counts"]
    L = ["# Buyer panel: %s" % res["business"], ""]
    buy = buy_words(res)
    L.append("**%d of %d %s (%s).** %d more said probably, later; %d said not now; %d said no."
             % (c["buy_now"], res["answered"], buy, pct(res["buy_rate"]), c["probably"], c["not_now"], c["no"]))
    L.append("")
    L.append("Only \"%s\" counts as a buy. Seed %s: the same profile and seed deal the same buyers again."
             % (buy, res["seed"]))
    if res.get("free_trial"):
        L += ["", "The offer starts with a free trial, so a buy here means starting the trial and meaning to pay after it."
                  " No money changes hands in a trial: expect fewer real trials to turn into paying customers than this."]
    if res["skipped"]:
        L.append("")
        L.append("%d of %d buyers gave no valid answer and are left out: %s." % (
            len(res["skipped"]), res["dealt"], ", ".join("%s (%s)" % tuple(s) for s in res["skipped"][:10])))
    L += ["", "These are simulated buyers, not customers. Language models lean agreeable, so read the buy rate as the"
              " best case. Use this to find objections and weak spots, then check the big ones with real people."]
    sections = (("By segment", "by_segment"), ("By how much the problem bothers them", "by_pain"),
                ("By what they use today", "by_today"), ("By how they shop", "by_behaviour"),
                ("By income", "by_income"))
    for title, key in sections:
        L += ["", "## %s" % title, "", "| group | buyers | %s |" % ("would start the trial" if res.get("free_trial") else "would pay now"),
              "| --- | ---: | ---: |"]
        for name, n, rate in res[key]:
            L.append("| %s | %d | %s%s |" % (name, n, pct(rate), " (few buyers)" if n < 8 else ""))
    for title, key in (("Why the others don't buy", "why_not"), ("Why the buyers buy", "why_yes")):
        if not res[key]:
            continue
        L += ["", "## %s" % title, "", "| reason | buyers | in their words |", "| --- | ---: | --- |"]
        for item in res[key]:
            quotes = " / ".join('"%s" (%s)' % (q.replace("|", "/"), i) for i, q in item["quotes"][:2])
            L.append("| %s | %d | %s |" % (item["code"].replace("_", " "), item["count"], quotes))
    if res["flip"]:
        L += ["", "## What would change their mind", ""]
        L += ["- %s (%s)" % (text, i) for i, text in res["flip"][:15]]
    if res["instead"]:
        L += ["", "## What they will do instead", ""]
        L += ["- %s (%s)" % (text, i) for i, text in res["instead"][:10]]
    if res["first_month_per_buyer"] is not None:
        L += ["", "Buyers who %s say they would pay **%.1f times** in their first month as customers, on average."
              % (buy, res["first_month_per_buyer"])]
    if res["over_budget"] is not None and res["buy_now"]:
        L += ["", "Budget check: %d of the %d who %s have a budget below the %s price%s." % (
            len(res["over_budget"]), res["buy_now"], buy, money(res["offer_price"]),
            (" (%s)" % ", ".join(res["over_budget"][:10])) if res["over_budget"] else "")]
    pr = res["price_range"]
    L += ["", "## The price range they would accept", ""]
    if pr is None:
        L.append("Not enough price answers to draw a range: it needs at least 5 complete ones, and there are %d%s."
                 % (res["price_answers"], (" (%d more dropped as missing or out of order)" % res["price_dropped"])
                    if res["price_dropped"] else ""))
    else:
        L += ["Prices per %s, from %d buyers' four price answers%s." % (
                  res["period"], pr["answers"],
                  (" (%d dropped as missing or out of order)" % res["price_dropped"]) if res["price_dropped"] else ""),
              "", "| point | price | what it means |", "| --- | ---: | --- |",
              "| Lowest | %s | below this, too many think it is too cheap to be any good |" % money(pr["lowest"]),
              "| Least resistance | %s | as many call it too cheap as too expensive |" % money(pr["ideal"]),
              "| Neutral | %s | as many call it a bargain as call it expensive |" % money(pr["neutral"]),
              "| Highest | %s | above this, too many would not buy at all |" % money(pr["highest"]),
              "", "**Acceptable range: %s to %s.**" % (money(pr["lowest"]), money(pr["highest"]))]
        price = res["offer_price"]
        if price is not None and pr["lowest"] is not None and pr["highest"] is not None:
            where = "inside" if pr["lowest"] <= price <= pr["highest"] else (
                "below" if price < pr["lowest"] else "above")
            L.append("Your price, %s, is **%s** that range." % (money(price), where))
        L.append("Simulated price answers pick which prices to test. Only real buyers prove one.")
    return "\n".join(L) + "\n"


# ---- command line --------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default=os.path.join("startup", "buyers"))
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    i = sub.add_parser("init")
    i.add_argument("--customer", required=True)
    i.add_argument("--pitch", required=True)
    i.add_argument("--n", type=int, default=100)
    i.add_argument("--seed", type=int)
    i.add_argument("--replace", action="store_true", help="delete an earlier panel's answers in this folder first")
    b = sub.add_parser("briefs")
    b.add_argument("--wave", type=int, default=WAVE)
    sub.add_parser("check")
    s = sub.add_parser("save")
    s.add_argument("id")
    sub.add_parser("tally")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "init":
            seed, cards = init(a.dir, a.customer, a.pitch, a.n, a.seed, a.replace)
            print("Dealt %d buyers (seed %s) into %s. Next: buyers.py briefs" % (len(cards), seed, a.dir))
        elif a.cmd == "briefs":
            waves = write_briefs(a.dir, a.wave)
            total = sum(len(w) for w in waves)
            if not total:
                print("Every buyer has a valid answer. Next: buyers.py tally")
            else:
                print("%d briefs in %d waves of up to %d. Run one wave at a time:" % (total, len(waves), a.wave))
                for k, w in enumerate(waves, 1):
                    print("wave %d: %s" % (k, " ".join("%s=%s" % job for job in w)))
        elif a.cmd == "check":
            problems = check(a.dir)
            if not problems:
                print("All answers present and valid.")
            for buyer_id, p in problems:
                print("%s: %s" % (buyer_id, p))
            return 1 if problems else 0
        elif a.cmd == "save":
            print("Saved %s" % save(a.dir, a.id, sys.stdin.read()))
        elif a.cmd == "tally":
            res = tally(a.dir)
            path = os.path.join(a.dir, "results.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(results_md(res))
            _write_json(os.path.join(a.dir, "results.json"), res)
            print("%d of %d %s (%.0f%%). Wrote %s" % (
                res["buy_now"], res["answered"], buy_words(res), res["buy_rate"] * 100, path))
        elif a.cmd == "status":
            state, cards = load(a.dir)
            left = len(check(a.dir))
            print("%d buyers dealt (seed %s): %d answered, %d to go." % (
                len(cards), state["seed"], len(cards) - left, left))
    except BuyersError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
