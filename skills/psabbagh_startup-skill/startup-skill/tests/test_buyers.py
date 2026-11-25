import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _paths import load, skill

buyers = load("startup-buyers", "buyers")
EXAMPLE = skill("startup-buyers", "customer.example.json")
PITCH = skill("startup-buyers", "pitch.example.md")


def example():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


def quiet(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = fn(*args)
    return rc, out.getvalue(), err.getvalue()


class Allocate(unittest.TestCase):
    def test_exact_total_and_proportions(self):
        counts = buyers.allocate([{"share": 0.5}, {"share": 0.3}, {"share": 0.2}], 100)
        self.assertEqual(counts, [50, 30, 20])
        counts = buyers.allocate([{"share": 1}, {"share": 1}, {"share": 1}], 20)
        self.assertEqual(sum(counts), 20)
        self.assertLessEqual(max(counts) - min(counts), 1)

    def test_zero_shares_is_an_error(self):
        with self.assertRaises(buyers.BuyersError):
            buyers.allocate([{"share": 0}], 10)


class Deal(unittest.TestCase):
    def test_same_seed_same_cards(self):
        self.assertEqual(buyers.deal(example(), 30, 9), buyers.deal(example(), 30, 9))
        self.assertNotEqual(buyers.deal(example(), 30, 9), buyers.deal(example(), 30, 10))

    def test_cards_follow_the_profile(self):
        c = example()
        cards = buyers.deal(c, 100, 3)
        self.assertEqual(len(cards), 100)
        self.assertEqual(cards[0]["id"], "B001")
        self.assertEqual(cards[-1]["id"], "B100")
        self.assertEqual(len({x["name"] for x in cards}), 100)
        segments = {s["name"]: s for s in c["segments"]}
        expected = dict(zip(segments, buyers.allocate(c["segments"], 100)))
        for name, k in expected.items():
            self.assertEqual(sum(1 for x in cards if x["segment"] == name), k)
        for x in cards:
            seg = segments[x["segment"]]
            self.assertGreaterEqual(x["budget"], seg["budget"][0] - 5)
            self.assertLessEqual(x["budget"], seg["budget"][1] + 5)
            self.assertGreaterEqual(x["income"], seg["income"][0] - 500)
            self.assertLessEqual(x["income"], seg["income"][1] + 500)
            self.assertIn(x["today"], [t["name"] for t in c["today"]])

    def test_default_pain_when_none_given(self):
        cards = buyers.deal(example(), 40, 1)
        levels = {p["level"] for p in buyers.DEFAULT_PAIN}
        self.assertTrue(all(x["pain"] in levels for x in cards))
        self.assertGreater(sum(1 for x in cards if x["pain"] == buyers.DEFAULT_PAIN[0]["level"]), 0)

    def test_a_new_offer_is_judged_by_the_same_buyers(self):
        # "Improve the pitch and re-test" relies on this: the price, the free trial and the pitch
        # do not change who is dealt; the number of buyers does.
        before = buyers.deal(example(), 20, 77)
        c = example()
        c["offer_price"] = 19
        c["free_trial"] = True
        self.assertEqual(buyers.deal(c, 20, 77), before)
        self.assertNotEqual(buyers.deal(example(), 21, 77)[:20], before)

    def test_more_buyers_than_names(self):
        cards = buyers.deal(example(), 300, 2)
        self.assertEqual(len({x["name"] for x in cards}), 300)

    def test_profile_errors(self):
        for change in ({"budget_period": "week"}, {"today": []}, {"category": ""}):
            c = example()
            c.update(change)
            with self.assertRaises(buyers.BuyersError):
                buyers.check_customer(c)
        c = example()
        del c["segments"][0]["budget"]
        with self.assertRaises(buyers.BuyersError):
            buyers.check_customer(c)
        c = example()
        c["segments"][0]["income"] = [90000, 10000]
        with self.assertRaises(buyers.BuyersError):
            buyers.check_customer(c)


class Panel(unittest.TestCase):
    def setUp(self):
        self.d = os.path.join(tempfile.mkdtemp(), "buyers")
        self.seed, self.cards = buyers.init(self.d, EXAMPLE, PITCH, 20, 11)

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.d))

    def answer(self, buyer_id, decision="no", reason_code="price", **extra):
        a = {"id": buyer_id, "decision": decision, "first_month": 1 if decision == "buy_now" else 0,
             "reason_code": reason_code, "reason": "because %s" % buyer_id, "objection": "doubt %s" % buyer_id,
             "would_change_my_mind": "a free month", "instead": "keep texting clients",
             "price_too_cheap": 5, "price_bargain": 15, "price_expensive": 30, "price_too_expensive": 45}
        a.update(extra)
        with open(os.path.join(self.d, "answers", buyer_id + ".json"), "w", encoding="utf-8") as fh:
            json.dump(a, fh)

    def test_init_records_the_seed_and_pitch(self):
        with open(os.path.join(self.d, "panel.json"), encoding="utf-8") as fh:
            state = json.load(fh)
        self.assertEqual(state["seed"], 11)
        self.assertIn("$29 a month", state["pitch"])

    def test_briefs_are_complete_and_not_primed(self):
        waves = buyers.write_briefs(self.d, 10)
        self.assertEqual([len(w) for w in waves], [10, 10])
        with open(waves[0][0][1], encoding="utf-8") as fh:
            text = fh.read()
        card = self.cards[0]
        with open(PITCH, encoding="utf-8") as fh:
            self.assertIn(fh.read().strip(), text)
        self.assertIn(card["name"], text)
        self.assertIn("about $%s a month" % "{:,}".format(card["budget"]), text)
        self.assertIn("only pay more if you were convinced it brings in or saves you more than it costs", text)
        self.assertNotIn("taking money from something else", text)
        self.assertIn(os.path.abspath(os.path.join(self.d, "answers", "B001.json")), text)
        self.assertNotIn("$name", text)
        self.assertNotIn("$pitch", text)
        for objection in example()["known_objections"]:
            self.assertNotIn(objection, text)

    def test_brief_keeps_the_buyer_to_two_tools(self):
        waves = buyers.write_briefs(self.d, 10)
        with open(waves[0][0][1], encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Use only two tools", text)
        self.assertIn("the folder for your answer already exists", text)
        self.assertIn(buyers.DECIDE_PAY, text)
        self.assertNotIn("free trial", text)

    def test_free_trial_changes_what_a_buy_means(self):
        c = example()
        c["free_trial"] = True
        path = os.path.join(os.path.dirname(self.d), "trial.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(c, fh)
        d = os.path.join(os.path.dirname(self.d), "trial")
        buyers.init(d, path, PITCH, 10, 3)
        waves = buyers.write_briefs(d, 10)
        with open(waves[0][0][1], encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(buyers.DECIDE_TRIAL, text)
        self.assertNotIn(buyers.DECIDE_PAY, text)
        for i in range(1, 11):
            a = {"id": "B%03d" % i, "decision": "buy_now" if i <= 3 else "probably", "reason_code": "trust",
                 "reason": "r", "first_month": 1}
            with open(os.path.join(d, "answers", "B%03d.json" % i), "w") as fh:
                json.dump(a, fh)
        res = buyers.tally(d)
        self.assertTrue(res["free_trial"])
        md = buyers.results_md(res)
        self.assertIn("**3 of 10 would start the free trial today and expect to pay after it (30%).**", md)
        self.assertIn("No money changes hands in a trial", md)
        self.assertIn("| group | buyers | would start the trial |", md)

    def test_free_trial_must_be_true_or_false(self):
        c = example()
        c["free_trial"] = "yes"
        with self.assertRaises(buyers.BuyersError):
            buyers.check_customer(c)

    def test_briefs_skip_buyers_who_answered(self):
        self.answer("B001")
        waves = buyers.write_briefs(self.d, 10)
        ids = [i for w in waves for i, _ in w]
        self.assertNotIn("B001", ids)
        self.assertEqual(len(ids), 19)

    def test_problems_are_named(self):
        path = os.path.join(self.d, "answers", "B002.json")
        self.assertEqual(buyers.problem(path, "B002"), "missing")
        with open(path, "w") as fh:
            fh.write("{not json")
        self.assertEqual(buyers.problem(path, "B002"), "not valid JSON")
        self.answer("B002", decision="yes")
        self.assertIn("decision", buyers.problem(path, "B002"))
        self.answer("B002", reason_code="vibes")
        self.assertIn("reason_code", buyers.problem(path, "B002"))
        self.answer("B002", reason="  ")
        self.assertEqual(buyers.problem(path, "B002"), "reason is empty")
        self.answer("B002", id="B003")
        self.assertIn("expected B002", buyers.problem(path, "B002"))
        self.answer("B002")
        self.assertIsNone(buyers.problem(path, "B002"))

    def test_save_files_a_printed_reply(self):
        reply = 'Here is my answer:\n{"id": "B004", "decision": "not_now", "reason_code": "timing", "reason": "Busy season."}\nThanks'
        path = buyers.save(self.d, "B004", reply)
        self.assertTrue(os.path.exists(path))
        with self.assertRaises(buyers.BuyersError):
            buyers.save(self.d, "B005", '{"id": "B005", "decision": "maybe"}')
        self.assertFalse(os.path.exists(os.path.join(self.d, "answers", "B005.json")))
        with self.assertRaises(buyers.BuyersError):
            buyers.save(self.d, "B999", '{"id": "B999"}')
        with self.assertRaises(buyers.BuyersError):
            buyers.save(self.d, "B006", "no json here")

    def test_tally_counts_only_buy_now_as_a_buy(self):
        for i in range(1, 5):
            self.answer("B%03d" % i, "buy_now", "solves_my_problem")
        for i in range(5, 11):
            self.answer("B%03d" % i, "probably", "trust")
        for i in range(11, 19):
            self.answer("B%03d" % i, "no", "price")
        res = buyers.tally(self.d)
        self.assertEqual(res["answered"], 18)
        self.assertEqual(res["buy_now"], 4)
        self.assertAlmostEqual(res["buy_rate"], 4 / 18.0)
        self.assertAlmostEqual(res["interest_rate"], 10 / 18.0)
        self.assertEqual([s[0] for s in res["skipped"]], ["B019", "B020"])
        self.assertEqual(res["why_not"][0]["code"], "price")
        self.assertEqual(res["why_not"][0]["count"], 8)
        self.assertEqual(res["why_yes"][0]["code"], "solves_my_problem")
        self.assertEqual(res["first_month_per_buyer"], 1)
        self.assertEqual(len(res["flip"]), 14)
        rates = [r for _, _, r in res["by_segment"]]
        self.assertEqual(rates, sorted(rates, reverse=True))
        self.assertIsNotNone(res["over_budget"])
        under = [c["id"] for c in self.cards[:4] if c["budget"] < 29]
        self.assertEqual(res["over_budget"], under)
        md = buyers.results_md(res)
        self.assertIn("**4 of 18 would pay now (22%).**", md)
        self.assertIn("lean agreeable", md)
        self.assertIn("Acceptable range: $", md)
        json.dumps(res)

    def test_too_few_price_answers_says_so(self):
        for i in range(1, 4):
            self.answer("B%03d" % i)
        res = buyers.tally(self.d)
        self.assertIsNone(res["price_range"])
        self.assertIn("it needs at least 5 complete ones, and there are 3.", buyers.results_md(res))

    def test_init_refuses_to_mix_in_an_earlier_panel(self):
        self.answer("B001")
        with self.assertRaises(buyers.BuyersError) as e:
            buyers.init(self.d, EXAMPLE, PITCH, 100, 12)
        self.assertIn("already holds 1 answers", str(e.exception))
        self.assertIn("--replace", str(e.exception))
        with open(os.path.join(self.d, "cards.json"), encoding="utf-8") as fh:
            self.assertEqual(len(json.load(fh)), 20, "the refused init must not touch the old panel")

    def test_retest_flow_keeps_the_first_panel_and_the_same_buyers(self):
        for i in range(1, 21):
            self.answer("B%03d" % i, "no", "trust")
        quiet(buyers.main, ["--dir", self.d, "tally"])
        v1 = self.d + "-v1"
        os.rename(self.d, v1)
        os.makedirs(self.d)
        with open(os.path.join(v1, "panel.json"), encoding="utf-8") as fh:
            first = json.load(fh)
        c = dict(first["customer"], offer_price=19, free_trial=True)
        profile = os.path.join(self.d, "customer.json")
        with open(profile, "w", encoding="utf-8") as fh:
            json.dump(c, fh)
        pitch = os.path.join(self.d, "pitch.md")
        with open(pitch, "w", encoding="utf-8") as fh:
            fh.write("Chairside: $19 a month, 14-day free trial, no card.\n")
        seed, cards = buyers.init(self.d, profile, pitch, 20, first["seed"])
        with open(os.path.join(v1, "cards.json"), encoding="utf-8") as fh:
            self.assertEqual(cards, json.load(fh))
        self.assertTrue(os.path.exists(os.path.join(v1, "results.json")))
        self.assertEqual(sum(len(w) for w in buyers.write_briefs(self.d)), 20)
        shutil.rmtree(v1)

    def test_init_replace_starts_clean(self):
        for i in range(1, 6):
            self.answer("B%03d" % i)
        buyers.write_briefs(self.d)
        buyers.tally(self.d)
        with open(os.path.join(self.d, "results.json"), "w") as fh:
            fh.write("{}")
        buyers.init(self.d, EXAMPLE, PITCH, 100, 12, replace=True)
        self.assertEqual(os.listdir(os.path.join(self.d, "answers")), [])
        self.assertEqual(os.listdir(os.path.join(self.d, "briefs")), [])
        self.assertFalse(os.path.exists(os.path.join(self.d, "results.json")))
        waves = buyers.write_briefs(self.d)
        self.assertEqual(sum(len(w) for w in waves), 100)

    def test_init_into_an_empty_folder_needs_no_flag(self):
        buyers.init(self.d, EXAMPLE, PITCH, 30, 12)
        self.assertEqual(sum(len(w) for w in buyers.write_briefs(self.d)), 30)

    def test_tally_without_answers_is_an_error(self):
        with self.assertRaises(buyers.BuyersError):
            buyers.tally(self.d)


class PriceRange(unittest.TestCase):
    def test_points_are_in_order(self):
        rows = []
        for k in range(40):
            base = 10 + (k % 10)
            rows.append([base * 0.4, base * 0.8, base * 1.4, base * 2.0])
        pr = buyers.price_range(rows)
        self.assertEqual(pr["answers"], 40)
        for key in ("lowest", "ideal", "neutral", "highest"):
            self.assertIsNotNone(pr[key], key)
        self.assertLess(pr["lowest"], pr["highest"])
        self.assertLessEqual(pr["lowest"], pr["ideal"])
        self.assertLessEqual(pr["ideal"], pr["highest"])

    def test_too_few_answers(self):
        self.assertIsNone(buyers.price_range([[1, 2, 3, 4]] * 4))

    def test_bad_rows_are_dropped(self):
        answers = [
            {"price_too_cheap": 5, "price_bargain": 10, "price_expensive": 20, "price_too_expensive": 30},
            {"price_too_cheap": 30, "price_bargain": 10, "price_expensive": 20, "price_too_expensive": 5},
            {"price_too_cheap": "$5", "price_bargain": "10", "price_expensive": 20, "price_too_expensive": "1,000"},
            {"price_bargain": 10},
        ]
        rows, dropped = buyers.price_rows(answers)
        self.assertEqual(len(rows), 2)
        self.assertEqual(dropped, 2)
        self.assertEqual(rows[1][3], 1000)


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = os.path.join(self.tmp, "buyers")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_init_briefs_check_status(self):
        rc, out, _ = quiet(buyers.main, ["--dir", self.d, "init", "--customer", EXAMPLE, "--pitch", PITCH,
                                         "--n", "12", "--seed", "4"])
        self.assertEqual(rc, 0)
        self.assertIn("Dealt 12 buyers (seed 4)", out)
        rc, out, _ = quiet(buyers.main, ["--dir", self.d, "briefs"])
        self.assertEqual(rc, 0)
        self.assertIn("12 briefs in 2 waves", out)
        rc, out, _ = quiet(buyers.main, ["--dir", self.d, "check"])
        self.assertEqual(rc, 1)
        rc, out, _ = quiet(buyers.main, ["--dir", self.d, "status"])
        self.assertIn("12 to go", out)

    def test_errors_exit_2(self):
        rc, _, err = quiet(buyers.main, ["--dir", self.d, "init", "--customer", "nope.json", "--pitch", PITCH])
        self.assertEqual(rc, 2)
        self.assertIn("no such file", err)
        rc, _, err = quiet(buyers.main, ["--dir", self.d, "tally"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
