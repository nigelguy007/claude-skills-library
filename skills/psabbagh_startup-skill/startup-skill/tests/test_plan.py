import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _paths import load, skill

plan = load("startup-plan", "plan")
SUB = skill("startup-numbers", "example-subscription.json")
ONE = skill("startup-numbers", "example-one-time.json")


class Plan(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "idea.md"), "w", encoding="utf-8") as fh:
            fh.write("# Rise & Crumb\n\n- What it is: a sourdough starter kit sold online.\n")

    def tearDown(self):
        shutil.rmtree(self.d)

    def numbers(self, path=ONE, **change):
        with open(path, encoding="utf-8") as fh:
            s = json.load(fh)
        s.update(change)
        with open(os.path.join(self.d, "numbers.json"), "w", encoding="utf-8") as fh:
            json.dump(s, fh)

    def buyers(self, buy_now, n=100, **extra):
        os.makedirs(os.path.join(self.d, "buyers"), exist_ok=True)
        res = {"buy_now": buy_now, "answered": n, "buy_rate": buy_now / float(n)}
        res.update(extra)
        with open(os.path.join(self.d, "buyers", "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh)

    def section(self, name, text):
        path = os.path.join(self.d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_nothing_yet_is_incomplete(self):
        v, text = plan.build(self.d)
        self.assertEqual(v, "Incomplete")
        self.assertIn("Missing: the numbers. Run /startup-numbers", text)
        self.assertIn("Missing: the buyer panel. Run /startup-buyers", text)

    def test_numbers_without_buyers_is_incomplete(self):
        self.numbers()
        v, _ = plan.build(self.d)
        self.assertEqual(v, "Incomplete")

    def test_buyers_without_numbers_is_incomplete(self):
        self.buyers(40)
        v, _ = plan.build(self.d)
        self.assertEqual(v, "Incomplete")

    def test_good_numbers_and_buyers_is_profitable(self):
        self.numbers()
        self.buyers(30)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Profitable")
        self.assertTrue(text.startswith("# Rise & Crumb: business plan\n\n**Verdict: Profitable**"))
        self.assertIn("✓ Each kit leaves $12.40 after its own costs and marketing.", text)
        self.assertIn("✓ The money you put in ($3,827 at the lowest point) comes back in month 8.", text)
        self.assertIn("✓ Break-even (41 kits a month) fits within what you can handle (400).", text)
        self.assertIn("| Money back | month 8 |", text)
        self.assertIn("| Buyer panel | 30 of 100 would pay now |", text)
        self.assertIn("Not financial, legal or tax advice", text)

    def test_weak_panel_is_not_yet(self):
        self.numbers()
        self.buyers(12)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("✗ 12 of 100 simulated buyers would pay now (12%; the bar is 20%).", text)

    def test_buyers_shown_a_different_price_is_not_yet(self):
        self.numbers()
        self.buyers(30, offer_price=59)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("✗ The buyers were shown $59.00 but the numbers use $45.00", text)
        self.assertIn("Run /startup-buyers again at $45.00 with the same seed.", text)

    def test_buyers_shown_the_same_price_passes(self):
        self.numbers()
        self.buyers(30, offer_price=45)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Profitable")
        self.assertNotIn("were shown", text)

    def test_free_trial_wording_in_the_verdict(self):
        self.numbers()
        self.buyers(30, free_trial=True)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Profitable")
        self.assertIn("✓ 30 of 100 simulated buyers would start the free trial and expect to pay after it (30%;"
                      " the bar is 20%).", text)
        self.assertIn("| Buyer panel | 30 of 100 would start the free trial |", text)

    def test_no_marketing_plan_is_a_note(self):
        self.numbers()
        self.buyers(30)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Profitable")
        self.assertIn("No marketing plan yet, so the new customers in the numbers are a guess.", text)

    def test_numbers_must_use_the_marketing_plan(self):
        funnel = load("startup-marketing", "funnel")
        shutil.copy(skill("startup-marketing", "marketing.example.json"), os.path.join(self.d, "marketing.json"))
        self.numbers()
        self.buyers(30)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("✗ The numbers' sales are not the marketing plan's. Run funnel.py --apply", text)
        with open(os.path.join(self.d, "marketing.json"), encoding="utf-8") as fh:
            f = funnel.forecast(json.load(fh))
        funnel.apply(f, os.path.join(self.d, "numbers.json"))
        v, text = plan.build(self.d)
        self.assertIn("✓ The numbers use the marketing plan: 238 new customers in year 1, $50 each to win.", text)
        self.assertNotIn("No marketing plan yet", text)

    def test_a_plan_with_no_customers_is_reported_not_looped(self):
        with open(os.path.join(self.d, "marketing.json"), "w", encoding="utf-8") as fh:
            json.dump({"channels": [{"name": "x", "reach": 0, "steps": [{"name": "pay", "rate": 0}],
                                     "source": "estimate"}]}, fh)
        self.numbers()
        self.buyers(0)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("✗ The marketing plan wins no customers in year 1.", text)
        self.assertNotIn("Run funnel.py --apply", text)

    def test_competition_and_marketing_sections(self):
        self.numbers()
        self.buyers(30)
        self.section("board.md", "# Board\n\nvote\n")
        self.section("competitors.md", "# Competitors\n\nthree rivals\n")
        self.section("buyers/results.md", "# Buyers\n\n30 buy\n")
        self.section("marketing.md", "# Marketing\n\nwalk-ins\n")
        self.section("numbers.md", "# Numbers\n\nmargins\n")
        v, text = plan.build(self.d)
        order = [text.index(h) for h in ("## What the board said", "## The competition", "## The buyer panel",
                                         "## How customers will find it", "## The numbers")]
        self.assertEqual(order, sorted(order))

    def test_the_bar_can_move(self):
        self.numbers()
        self.buyers(12)
        v, _ = plan.build(self.d, min_buy_rate=0.10)
        self.assertEqual(v, "Profitable")

    def test_subscription_that_burns_cash_is_not_yet(self):
        self.numbers(SUB)
        self.buyers(40)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("✓ A customer brings in 5.4 times what it costs to win them.", text)
        self.assertIn("✗ Month 12 still loses $2,172.", text)
        self.assertIn("does not come back within 24 months", text)
        self.assertIn("| A customer is worth | 5.4 times what it costs to win them |", text)

    def test_customer_worth_less_than_its_cost_fails(self):
        self.numbers(SUB, cost_to_win_customer=900)
        self.buyers(40)
        v, checks, _, _, _, _ = plan.verdict(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn((False, "A customer brings in 0.7 times what it costs to win them."), checks)

    def test_losing_money_per_sale_is_not_yet(self):
        self.numbers(price=25)
        self.buyers(40)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("LOSES", text)

    def test_breakeven_above_capacity_is_not_yet(self):
        self.numbers(capacity=30)
        self.buyers(40)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Not yet")
        self.assertIn("is above what you can handle (30)", text)

    def test_fragile_note(self):
        self.numbers(sales=[50] * 12, startup=[{"label": "Equipment", "cost": 200}])
        self.buyers(40)
        v, text = plan.build(self.d)
        self.assertEqual(v, "Profitable")
        self.assertIn("Fragile: with 20% fewer sales, month 12 loses", text)

    def test_sections_in_order_and_missing_listed(self):
        self.numbers()
        self.buyers(30)
        self.section("summary.md", "# Summary\n\nIt works.\n")
        self.section("board.md", "# Board\n\n## Vote\n2 fund\n")
        v, text = plan.build(self.d)
        order = [text.index(h) for h in ("## Summary", "## The idea", "## What the board said")]
        self.assertEqual(order, sorted(order))
        self.assertIn("### Vote", text)
        self.assertIn("## Not done yet", text)
        self.assertIn("- The buyer panel: /startup-buyers", text)
        self.assertIn("- Test it on real people: /startup-plan", text)


class CommandLine(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = plan.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_check_exit_codes(self):
        d = tempfile.mkdtemp()
        try:
            shutil.copy(ONE, os.path.join(d, "numbers.json"))
            os.makedirs(os.path.join(d, "buyers"))
            with open(os.path.join(d, "buyers", "results.json"), "w") as fh:
                json.dump({"buy_now": 30, "answered": 100, "buy_rate": 0.3}, fh)
            rc, out, _ = self.run_main(["--dir", d, "--check"])
            self.assertEqual(rc, 0)
            self.assertIn("Verdict: Profitable", out)
            rc, out, _ = self.run_main(["--dir", d, "--check", "--min-buy-rate", "0.5"])
            self.assertEqual(rc, 1)
            rc, out, _ = self.run_main(["--dir", d])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(d, "plan.md")))
            with open(os.path.join(d, "numbers.json"), "w") as fh:
                fh.write("{broken")
            rc, _, err = self.run_main(["--dir", d])
            self.assertEqual(rc, 2)
            self.assertIn("not valid JSON", err)
        finally:
            shutil.rmtree(d)

    def test_missing_folder(self):
        rc, _, err = self.run_main(["--dir", os.path.join(tempfile.gettempdir(), "no-such-startup-folder")])
        self.assertEqual(rc, 2)
        self.assertIn("Run /startup-board first", err)


if __name__ == "__main__":
    unittest.main()
