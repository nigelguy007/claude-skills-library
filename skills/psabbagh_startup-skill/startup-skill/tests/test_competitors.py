import csv
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _paths import load, skill

competitors = load("startup-competitors", "competitors")
EXAMPLE = skill("startup-competitors", "competitors.example.csv")


def rows():
    return competitors.read(EXAMPLE)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = competitors.main(argv)
    return rc, out.getvalue(), err.getvalue()


class Rules(unittest.TestCase):
    def test_example_is_clean(self):
        self.assertEqual(competitors.problems(rows()), [])

    def test_every_rule(self):
        bad = rows()
        bad[0]["url"] = ""
        bad[1]["checked"] = "last week"
        bad[2]["type"] = "rival"
        bad[3]["price"] = "-5"
        bad.append(dict(bad[4], name="SalonDesk (made-up example)"))
        bad[4]["price"] = "cheap"
        found = [p for _, _, p in competitors.problems(bad)]
        self.assertTrue(any(p.startswith("no link") for p in found))
        self.assertTrue(any(p.startswith("checked must be") for p in found))
        self.assertTrue(any("is not one of direct, indirect, diy" in p for p in found))
        self.assertIn("price cannot be negative", found)
        self.assertTrue(any("is not a number" in p for p in found))
        self.assertIn("listed twice", found)

    def test_price_needs_a_unit_and_rating_is_out_of_5(self):
        bad = rows()
        bad[0]["price_unit"] = ""
        bad[1]["rating"] = "9"
        bad[2]["reviews"] = "lots"
        found = [p for _, _, p in competitors.problems(bad)]
        self.assertTrue(any("needs a price_unit" in p for p in found))
        self.assertIn("rating must be out of 5", found)
        self.assertIn("reviews must be a whole number", found)


class Summary(unittest.TestCase):
    def test_prices_and_counts(self):
        s = competitors.summary(rows())
        self.assertEqual(s["by_type"], {"direct": 3, "indirect": 1, "diy": 1})
        self.assertEqual(s["prices"]["month"], {"count": 3, "lowest": 0, "median": 16, "highest": 35})
        self.assertEqual(s["no_public_price"], 1)
        self.assertEqual(s["notes"], [])

    def test_direct_range_leaves_out_unlike_products(self):
        s = competitors.summary(rows())
        self.assertEqual(s["direct_prices"]["month"], {"count": 2, "lowest": 0, "median": 17.5, "highest": 35})

    def test_notes_when_no_direct_or_diy(self):
        only = [r for r in rows() if r["type"] == "indirect"]
        notes = " ".join(competitors.summary(only)["notes"])
        self.assertIn("No direct competitor found", notes)
        self.assertIn("No do-it-yourself row", notes)

    def test_table(self):
        md = competitors.table_md(rows())
        self.assertIn("| [SalonDesk (made-up example)](https://example.com/salondesk/pricing) | Direct | $35 a month |", md)
        self.assertIn("| no public price |", md)
        self.assertIn("**Direct competitors, per month** (2 with a public price): lowest $0, median $17.50, highest"
                      " $35.", md)
        self.assertIn("All priced alternatives, per month (3): lowest $0, median $16, highest $35.", md)
        self.assertIn("1 has no public price.", md)
        self.assertLess(md.index("| Direct |"), md.index("| Indirect |"))
        self.assertLess(md.index("| Indirect |"), md.index("| Do it yourself |"))


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def write(self, rows_, name="c.csv", columns=None):
        path = os.path.join(self.d, name)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=columns or competitors.COLUMNS)
            w.writeheader()
            for r in rows_:
                w.writerow({k: r.get(k, "") for k in (columns or competitors.COLUMNS)})
        return path

    def test_check_and_table(self):
        rc, out, _ = run(["check", EXAMPLE])
        self.assertEqual(rc, 0)
        self.assertIn("5 rows, every one linked and dated.", out)
        path = os.path.join(self.d, "table.md")
        self.assertEqual(run(["table", EXAMPLE, "--out", path])[0], 0)
        self.assertTrue(os.path.exists(path))
        rc, out, _ = run(["table", EXAMPLE, "--json"])
        self.assertEqual(json.loads(out)["count"], 5)

    def test_problems_block_the_table(self):
        bad = rows()
        bad[0]["url"] = ""
        path = self.write(bad)
        rc, out, _ = run(["check", path])
        self.assertEqual(rc, 1)
        self.assertIn("row 2 (SalonDesk (made-up example)): no link", out)
        rc, _, err = run(["table", path])
        self.assertEqual(rc, 2)
        self.assertIn("fix these first", err)

    def test_missing_file_or_column(self):
        self.assertEqual(run(["check", os.path.join(self.d, "nope.csv")])[0], 2)
        path = self.write(rows(), columns=[c for c in competitors.COLUMNS if c != "checked"])
        rc, _, err = run(["check", path])
        self.assertEqual(rc, 2)
        self.assertIn("missing the column(s): checked", err)


if __name__ == "__main__":
    unittest.main()
