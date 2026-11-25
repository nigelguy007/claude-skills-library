import copy
import io
import json
import math
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _paths import load, skill

numbers = load("startup-numbers", "numbers")
SUB = skill("startup-numbers", "example-subscription.json")
ONE = skill("startup-numbers", "example-one-time.json")


def spec(path, **change):
    with open(path, encoding="utf-8") as fh:
        s = json.load(fh)
    s.update(change)
    return s


class OneTime(unittest.TestCase):
    def test_example(self):
        a = numbers.analyse(spec(ONE))
        self.assertAlmostEqual(a["contribution"], 12.40)
        self.assertEqual(math.ceil(a["breakeven"]), 41)
        self.assertAlmostEqual(a["month12_profit"], 220 * 12.40 - 499)
        self.assertEqual(a["payback_month"], 8)
        self.assertEqual(a["first_profit_month"], 2)
        self.assertAlmostEqual(a["cash_needed"], 3700 + 499 - 30 * 12.40)
        self.assertEqual(a["flags"], [])
        self.assertTrue(a["repeats_month_12"])
        self.assertEqual(len(a["months"]), 24)
        self.assertEqual(a["months"][23]["volume"], 220)

    def test_sales_per_day(self):
        s = spec(ONE)
        del s["sales"]
        s["sales_per_day"] = [2] * 12
        s["days_per_month"] = 25
        a = numbers.analyse(s)
        self.assertEqual(a["months"][0]["volume"], 50)
        self.assertAlmostEqual(a["breakeven_per_day"], a["breakeven"] / 25)

    def test_24_months_given(self):
        s = spec(ONE, sales=list(range(1, 25)))
        a = numbers.analyse(s)
        self.assertFalse(a["repeats_month_12"])
        self.assertEqual(a["months"][23]["volume"], 24)

    def test_marketing_is_required(self):
        s = spec(ONE)
        del s["marketing_per_sale"]
        with self.assertRaises(numbers.NumbersError):
            numbers.analyse(s)

    def test_losing_money_per_sale(self):
        a = numbers.analyse(spec(ONE, price=20))
        self.assertLess(a["contribution"], 0)
        self.assertTrue(math.isinf(a["breakeven"]))
        self.assertTrue(any("loses money before fixed costs" in f for f in a["flags"]))

    def test_capacity_flags(self):
        a = numbers.analyse(spec(ONE, capacity=30))
        joined = " ".join(a["flags"])
        self.assertIn("Break-even needs more than you can handle", joined)
        self.assertIn("goes above capacity", joined)


class Subscription(unittest.TestCase):
    def test_example(self):
        a = numbers.analyse(spec(SUB))
        self.assertAlmostEqual(a["contribution"], 29 - 3.24)
        self.assertAlmostEqual(a["lifetime_months"], 25)
        self.assertAlmostEqual(a["lifetime_value"], 25.76 * 25)
        self.assertAlmostEqual(a["value_to_cost"], 25.76 * 25 / 120)
        self.assertAlmostEqual(a["months_to_earn_back_customer"], 120 / 25.76)
        self.assertEqual(math.ceil(a["breakeven"]), 187)
        self.assertLess(a["month12_profit"], 0)
        self.assertIsNone(a["payback_month"])
        self.assertEqual(a["first_profit_month"], 14)
        joined = " ".join(a["flags"])
        self.assertIn("Month 12 still loses money", joined)
        self.assertIn("does not come back within 24 months", joined)

    def test_churn_and_starting_customers(self):
        s = spec(SUB, starting_customers=100, churn=0.1, new_customers=[0] * 12)
        a = numbers.analyse(s)
        self.assertAlmostEqual(a["months"][0]["volume"], 90)
        self.assertAlmostEqual(a["months"][1]["volume"], 81)
        self.assertAlmostEqual(a["months"][0]["revenue"], 90 * 29)

    def test_acquisition_spend_is_counted(self):
        a = numbers.analyse(spec(SUB))
        self.assertAlmostEqual(a["months"][0]["marketing"], 10 * 120)
        m = a["months"][0]
        self.assertAlmostEqual(m["profit"], m["revenue"] - m["variable"] - m["marketing"] - m["fixed"])

    def test_customer_worth_flags(self):
        weak = numbers.analyse(spec(SUB, cost_to_win_customer=400))
        self.assertTrue(any("only 1.6 times" in f for f in weak["flags"]))
        losing = numbers.analyse(spec(SUB, cost_to_win_customer=900))
        self.assertTrue(any("less than it costs to win them" in f for f in losing["flags"]))

    def test_zero_churn_and_free_customers(self):
        a = numbers.analyse(spec(SUB, churn=0, cost_to_win_customer=0))
        self.assertTrue(math.isinf(a["lifetime_value"]))
        self.assertTrue(math.isinf(a["value_to_cost"]))
        self.assertNotIn("inf", numbers.report(spec(SUB, churn=0, cost_to_win_customer=0), a))

    def test_required_fields(self):
        for key in ("churn", "cost_to_win_customer", "new_customers", "price"):
            s = spec(SUB)
            del s[key]
            with self.assertRaises(numbers.NumbersError):
                numbers.analyse(s)
        with self.assertRaises(numbers.NumbersError):
            numbers.analyse(spec(SUB, churn=1.2))
        with self.assertRaises(numbers.NumbersError):
            numbers.analyse(spec(SUB, new_customers=[1] * 13))
        with self.assertRaises(numbers.NumbersError):
            numbers.analyse(spec(SUB, model="saas"))
        with self.assertRaises(numbers.NumbersError):
            numbers.analyse(spec(SUB, price=0))
        with self.assertRaises(numbers.NumbersError):
            numbers.analyse(spec(SUB, fixed_monthly=[{"label": "rent"}]))


class WhatIfs(unittest.TestCase):
    def test_rows(self):
        rows = numbers.what_ifs(spec(SUB))
        self.assertEqual([r[0] for r in rows], ["The plan", "Price 10% lower", "20% fewer new customers",
                                                 "Every cost 15% higher", "Customers cancel 50% more often"])
        base = rows[0][1]["month12_profit"]
        for _, a in rows[1:]:
            self.assertLess(a["month12_profit"], base + 1e-9)
        self.assertEqual(len(numbers.what_ifs(spec(ONE))), 4)

    def test_cost_factor_scales_marketing_too(self):
        a = numbers.analyse(spec(ONE), cost_factor=1.15)
        self.assertAlmostEqual(a["marketing_per_sale"], 12 * 1.15)


class Report(unittest.TestCase):
    def test_estimates_use_plain_words(self):
        est = dict(numbers.estimates(spec(SUB)))
        self.assertIn("Cost to win a customer", est)
        self.assertIn("Share of customers who cancel each month", est)
        self.assertIn("Building the app", est)
        self.assertNotIn("Legal and company setup", est)

    def test_reports_read_cleanly(self):
        for path in (SUB, ONE):
            s = spec(path)
            text = numbers.report(s, numbers.analyse(s))
            self.assertNotIn("inf", text.lower().replace("information", ""))
            self.assertNotIn("nan", text.lower().replace("financial", ""))
            self.assertIn("## What if things go worse", text)
        sub = numbers.report(spec(SUB), numbers.analyse(spec(SUB)))
        self.assertIn("## Red flags", sub)
        self.assertIn("5.4 times", sub)
        one = numbers.report(spec(ONE), numbers.analyse(spec(ONE)))
        self.assertIn("No red flags", one)
        self.assertIn("**The money you put in comes back: month 8.**", one)


class CommandLine(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = numbers.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_json_and_out(self):
        rc, out, _ = self.run_main([SUB, "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["model"], "subscription")
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "numbers.md")
            rc, _, _ = self.run_main([ONE, "--out", path])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmp)

    def test_what_if_flags(self):
        _, out, _ = self.run_main([ONE, "--json", "--price", "50", "--volume", "0.5"])
        data = json.loads(out)
        self.assertEqual(data["price"], 50)
        self.assertEqual(data["months"][0]["volume"], 15)

    def test_errors_exit_2(self):
        rc, _, err = self.run_main(["missing.json"])
        self.assertEqual(rc, 2)
        self.assertIn("no such file", err)


if __name__ == "__main__":
    unittest.main()
