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

funnel = load("startup-marketing", "funnel")
EXAMPLE = skill("startup-marketing", "marketing.example.json")
SUB = skill("startup-numbers", "example-subscription.json")
ONE = skill("startup-numbers", "example-one-time.json")


def plan(**change):
    with open(EXAMPLE, encoding="utf-8") as fh:
        p = json.load(fh)
    p.update(change)
    return p


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = funnel.main(argv)
    return rc, out.getvalue(), err.getvalue()


class Forecast(unittest.TestCase):
    def test_example(self):
        f = funnel.forecast(plan())
        walk, ads = f["channels"]
        self.assertAlmostEqual(walk["conversion"], 0.5 * 0.3 * 0.5)
        self.assertAlmostEqual(walk["customers"][0], 30 * 0.075)
        self.assertEqual(walk["cost_per_customer"], 0)
        self.assertAlmostEqual(ads["conversion"], 0.04 * 0.4)
        self.assertEqual(ads["customers"][0], 0)
        self.assertAlmostEqual(ads["spend"][5], 1500 * 0.9)
        self.assertAlmostEqual(f["customers"][11], 2.25 + 24)
        self.assertAlmostEqual(f["year1_spend"], 0.9 * sum([0, 0, 600, 900, 1200] + [1500] * 7))
        self.assertAlmostEqual(f["cost_per_customer"], f["year1_spend"] / f["year1_customers"])
        self.assertEqual(f["founder_hours"], 26)
        self.assertTrue(f["estimated"])
        self.assertEqual(f["flags"], [])

    def test_bad_plans(self):
        for bad in (plan(channels=[]),
                    plan(channels=[{"name": "x", "steps": [{"name": "pay", "rate": 0.1}]}]),
                    plan(channels=[{"name": "x", "reach": 10}]),
                    plan(channels=[{"name": "x", "reach": 10, "steps": [{"name": "pay", "rate": 20}]}]),
                    plan(channels=[{"name": "x", "reach": [1, 2, 3], "steps": [{"name": "pay", "rate": 0.1}]}]),
                    plan(channels=[{"name": "x", "reach": -5, "steps": [{"name": "pay", "rate": 0.1}]}])):
            with self.assertRaises(funnel.FunnelError):
                funnel.forecast(bad)

    def test_flags(self):
        p = plan()
        p["channels"][0]["founder_hours_per_month"] = 200
        p["channels"][1]["source"] = ""
        flags = " ".join(funnel.forecast(p)["flags"])
        self.assertIn("more than a full-time job", flags)
        self.assertIn("has no source for its rates", flags)
        tiny = plan(channels=[{"name": "x", "reach": 5, "steps": [{"name": "pay", "rate": 0.01}], "source": "estimate"}])
        self.assertIn("Month 12 brings in fewer than one new customer.", funnel.forecast(tiny)["flags"])

    def test_rates_can_rise_over_the_year(self):
        ramp = [0.1] * 6 + [0.2] * 6
        p = plan(channels=[{"name": "x", "reach": 100, "steps": [{"name": "pay", "rate": ramp}], "source": "s"}])
        c = funnel.forecast(p)["channels"][0]
        self.assertEqual(c["customers"][0], 10)
        self.assertEqual(c["customers"][11], 20)
        self.assertAlmostEqual(c["conversion"], 0.2)
        self.assertIn("pay 10% to 20%", funnel.report(funnel.forecast(p)))

    def test_trial_delay_moves_customers_to_when_they_pay(self):
        p = plan(channels=[{"name": "x", "reach": [10] + [0] * 11, "delay_months": 1,
                            "steps": [{"name": "pay", "rate": 0.5}], "cost_per_reach": 2, "source": "s"}])
        f = funnel.forecast(p)
        self.assertEqual(f["customers"][:3], [0, 5, 0])
        self.assertEqual(f["spend"][:2], [20, 0], "the spend stays in the month the people were reached")
        self.assertIn("paying customers counted 1 month later", funnel.report(f))
        with self.assertRaises(funnel.FunnelError):
            funnel.forecast(plan(channels=[{"name": "x", "reach": 1, "delay_months": 12,
                                            "steps": [{"name": "pay", "rate": 0.5}]}]))

    def test_hours_moving_between_channels_are_not_counted_twice(self):
        first = {"name": "network", "reach": 10, "steps": [{"name": "pay", "rate": 0.1}], "source": "s",
                 "founder_hours_per_month": [100] * 6 + [0] * 6}
        second = {"name": "strangers", "reach": 10, "steps": [{"name": "pay", "rate": 0.1}], "source": "s",
                  "founder_hours_per_month": [0] * 6 + [100] * 6}
        f = funnel.forecast(plan(channels=[first, second]))
        self.assertEqual(f["founder_hours"], 100)
        self.assertEqual(f["flags"], [])
        second["founder_hours_per_month"] = [100] * 12
        flags = funnel.forecast(plan(channels=[first, second]))["flags"]
        self.assertTrue(any("up to 200 of the founder's hours" in x for x in flags))

    def test_step_sources(self):
        p = plan(channels=[{"name": "x", "reach": 50, "steps": [
            {"name": "reply", "rate": 0.2, "source": "the founder's last 40 messages"},
            {"name": "pay", "rate": 0.3, "source": "https://example.com/benchmark"}]}])
        f = funnel.forecast(p)
        self.assertEqual(f["flags"], [])
        self.assertFalse(f["estimated"])
        self.assertIn("- x, reply: the founder's last 40 messages", funnel.report(f))
        p["channels"][0]["steps"][1]["source"] = "estimate: no data yet"
        self.assertTrue(funnel.forecast(p)["estimated"])

    def test_report_shows_the_peak(self):
        text = funnel.report(funnel.forecast(plan()))
        self.assertIn("up to 1,500 clicks (month 1: 0, month 12: 1,500)", text)
        self.assertIn("| founder hours |", text)

    def test_no_channel_beats_the_panel(self):
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "results.json")
            with open(path, "w") as fh:
                json.dump({"buy_rate": 0.05}, fh)
            f = funnel.check_against_buyers(funnel.forecast(plan()), path)
            flags = " ".join(f["flags"])
            self.assertIn("Walking into salons nearby and showing it turns 7.5% of the people it reaches into"
                          " customers, more than the buyer panel's best case (5%)", flags)
            self.assertNotIn("Instagram ads", flags)
        finally:
            shutil.rmtree(d)


class Apply(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def numbers(self, src):
        path = os.path.join(self.d, "numbers.json")
        shutil.copy(src, path)
        return path

    def test_subscription(self):
        path = self.numbers(SUB)
        f = funnel.forecast(plan())
        n = funnel.apply(f, path)
        self.assertEqual(n["new_customers"][11], 26.25)
        self.assertEqual(n["cost_to_win_customer"], round(f["cost_per_customer"], 2))
        self.assertTrue(n["sources"]["new_customers"].startswith("estimate: from the marketing plan"))
        self.assertEqual(n["price"], 29, "everything else in the file is kept")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), n)
        self.assertEqual(funnel.matches(f, n), (True, ""))
        n["new_customers"][0] = 9
        ok, why = funnel.matches(f, n)
        self.assertFalse(ok)
        self.assertIn("new customers", why)

    def test_one_time(self):
        path = self.numbers(ONE)
        f = funnel.forecast(plan(sales_per_customer=2))
        n = funnel.apply(f, path)
        self.assertEqual(n["sales"][11], 52.5)
        self.assertEqual(n["marketing_per_sale"], round(f["year1_spend"] / (2 * f["year1_customers"]), 2))
        self.assertEqual(funnel.matches(f, n), (True, ""))
        n["marketing_per_sale"] = 1
        self.assertFalse(funnel.matches(f, n)[0])

    def test_numbers_module_reads_the_result(self):
        numbers = load("startup-numbers", "numbers")
        path = self.numbers(SUB)
        n = funnel.apply(funnel.forecast(plan()), path)
        a = numbers.analyse(n)
        self.assertAlmostEqual(a["months"][11]["new"], 26.25)
        self.assertIn("New customers each month", dict(numbers.estimates(n)))

    def test_nothing_to_apply(self):
        path = self.numbers(SUB)
        zero = plan(channels=[{"name": "x", "reach": 0, "steps": [{"name": "pay", "rate": 0.5}], "source": "s"}])
        with self.assertRaises(funnel.FunnelError) as e:
            funnel.apply(funnel.forecast(zero), path)
        self.assertIn("the plan will show it as a failing check", str(e.exception))


class CommandLine(unittest.TestCase):
    def test_report_json_and_errors(self):
        rc, out, _ = run([EXAMPLE])
        self.assertEqual(rc, 0)
        self.assertIn("**Year 1: 238 new customers**", out)
        self.assertIn("**Cost to win one customer: $50**", out)
        self.assertNotIn("inf", out.lower())
        rc, out, _ = run([EXAMPLE, "--json"])
        self.assertEqual(json.loads(out)["channels"][0]["cost_per_customer"], 0)
        rc, _, err = run(["nope.json"])
        self.assertEqual(rc, 2)
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "numbers.json")
            shutil.copy(SUB, path)
            rc, out, _ = run([EXAMPLE, "--apply", path])
            self.assertEqual(rc, 0)
            self.assertIn("Wrote the forecast into", out)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
