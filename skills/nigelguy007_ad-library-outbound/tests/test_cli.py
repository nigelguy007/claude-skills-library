"""End-to-end runs of the four commands against a temporary workspace. No network."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import adlib
import batch
import lint_draft
import score
from ob_common import read_csv, read_jsonl

OFFER = """---
sell: I sell verified B2B lead lists.
countries: US
sender_name: Sam Rivera
sender_company: Leadwell
sending_domain: getleadwell.com
main_domain: leadwell.com
postal_address: 100 Main St, Austin, TX 78701, USA
opt_out_line: Not relevant? Reply no and I won't email again.
max_words: 35
---
## Proof I can back up
- 50 free verified emails as a sample
"""

LEAD = """---
lead_id: L-261112-%02d
company: Northbeam Data %d
domain: northbeam%d.example
identity_check: verified
country: US
contact_name: Vera Lindqvist
email: vera@northbeam%d.example
email_status: verified
ad_id: 100
ad_url: https://www.linkedin.com/ad-library/detail/100
---
Notes.
"""

DRAFT = """---
lead_id: L-261112-%02d
ad_id: 100
ad_quote: AI-Trained Developers From $999/Month
subject: your LinkedIn ad
approved: no
---
## Email A
Saw your "AI-Trained Developers From $999/Month" LinkedIn ad.

Want 50 free verified emails of CTOs who are hiring developers?

## Follow-up 1
Did this land?
"""

RAW_AD = {"id": "100", "headline": "AI-Trained Developers From $999/Month", "description": "Hire vetted engineers.",
          "poster": "Northbeam Data", "advertiser": "Northbeam Data",
          "advertiserLinkedinPage": "https://www.linkedin.com/company/555",
          "url": "https://www.linkedin.com/ad-library/detail/100"}


def run(main, argv, **kw):
    """Run a command's main() and return (exit code, stdout)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        code = main(argv, **kw)
    return code, buffer.getvalue()


class Workspace(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "outbound"
        self.run_dir = self.root / "runs" / "261112-developers"
        (self.run_dir / "leads").mkdir(parents=True)
        (self.run_dir / "drafts").mkdir()
        self.offer = self.root / "offer.md"
        self.offer.write_text(OFFER)
        self.log = self.root / "log.csv"
        self.suppression = self.root / "suppression.csv"
        self.ads = self.run_dir / "ads.jsonl"
        run(batch.main, ["init", "--suppression", str(self.suppression), "--log", str(self.log)])

    def fake_fetch(self, path, params):
        return {"ads": [RAW_AD], "isLastPage": True, "totalAds": 1, "credits_charged": 1, "credits_remaining": 9}

    def pull_ads(self):
        return run(adlib.main, ["search", "--keyword", "developers", "--out", str(self.ads)], fetch=self.fake_fetch)

    def add_leads(self, count):
        for n in range(1, count + 1):
            (self.run_dir / "leads" / ("L-261112-%02d.md" % n)).write_text(LEAD % (n, n, n, n))
            (self.run_dir / "drafts" / ("L-261112-%02d.md" % n)).write_text(DRAFT % n)
        code, _ = run(batch.main, ["approve", "--run", str(self.run_dir), "--all"])  # as if the user said yes
        self.assertEqual(code, 0)

    def build(self, *extra):
        return run(batch.main, ["build", "--run", str(self.run_dir), "--offer", str(self.offer), "--suppression",
                                str(self.suppression), "--log", str(self.log), "--batch-id", "B1", *extra])


class SearchCommandTest(Workspace):
    def test_search_saves_ads_with_their_search_context_and_does_not_duplicate(self):
        code, output = self.pull_ads()
        self.assertEqual(code, 0)
        summary = json.loads(output)
        self.assertEqual(summary["new_ads_saved"], 1)
        saved = read_jsonl(self.ads)
        self.assertEqual(saved[0]["keyword"], "developers")
        self.assertRegex(saved[0]["window"], r"^\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}$")
        _, again = self.pull_ads()
        self.assertEqual(json.loads(again)["new_ads_saved"], 0)
        self.assertEqual(len(read_jsonl(self.ads)), 1)

    def test_bad_country_fails_cleanly(self):
        code, _ = run(adlib.main, ["search", "--keyword", "x", "--countries", "usa", "--out", str(self.ads)],
                      fetch=self.fake_fetch)
        self.assertEqual(code, 1)
        self.assertFalse(self.ads.exists())

    def test_api_failure_fails_cleanly(self):
        def failing(path, params):
            raise adlib.ApiError(402, "out of credits")

        code, _ = run(adlib.main, ["search", "--keyword", "x", "--out", str(self.ads)], fetch=failing)
        self.assertEqual(code, 1)

    def test_company_lookup_reports_whether_it_is_the_advertiser(self):
        def fetch(path, params):
            return {"id": 24354757, "name": "NORTHBEAM", "employeeCount": 3}

        code, output = run(adlib.main, ["company", "--url", "https://www.linkedin.com/company/northbeam/",
                                        "--expect-id", "555"], fetch=fetch)
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(output)["id_match"])

    def test_presence_reports_meta_and_google_and_survives_one_failing(self):
        def fetch(path, params):
            if "facebook" in path:
                return {"searchResults": [{"page_id": "3", "name": "Northbeam Data, Inc."},
                                          {"page_id": "4", "name": "Northbeam Dating"}]}
            raise adlib.ApiError(500, "Internal Server Error")

        code, output = run(adlib.main, ["presence", "--name", "Northbeam Data", "--domain", "northbeam.example"],
                           fetch=fetch)
        result = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(result["meta"]["status"], "page_found")
        self.assertEqual(result["meta"]["similar_names_ignored"], 1)
        self.assertEqual(result["google"]["status"], "error")


class ScoreCommandTest(Workspace):
    def test_score_writes_ranked_advertisers_and_prints_a_table(self):
        self.pull_ads()
        target = self.run_dir / "advertisers.json"
        code, output = run(score.main, ["--ads", str(self.ads), "--out", str(target), "--md"])
        self.assertEqual(code, 0)
        self.assertIn("| # | Advertiser |", output)
        self.assertEqual(json.loads(target.read_text())[0]["advertiser"], "Northbeam Data")

    def test_score_with_no_ads_fails(self):
        code, _ = run(score.main, ["--ads", str(self.ads)])
        self.assertEqual(code, 1)


class LintCommandTest(Workspace):
    def test_lint_passes_good_drafts_and_fails_bad_ones(self):
        self.pull_ads()
        self.add_leads(1)
        good = self.run_dir / "drafts" / "L-261112-01.md"
        code, output = run(lint_draft.main, [str(good), "--ads", str(self.ads), "--offer", str(self.offer)])
        self.assertEqual(code, 0)
        self.assertIn("1 of 1 drafts pass", output)
        bad = self.run_dir / "drafts" / "bad.md"
        bad.write_text((DRAFT % 9).replace("$999", "$499"))
        code, output = run(lint_draft.main, [str(bad), "--ads", str(self.ads), "--offer", str(self.offer), "--json"])
        self.assertEqual(code, 1)
        self.assertIn("quote-not-in-ad", output)


class BatchCommandTest(Workspace):
    def test_full_cycle_build_send_reply_opt_out_stats(self):
        self.pull_ads()
        self.add_leads(3)
        code, output = self.build()
        self.assertEqual(code, 0)
        summary = json.loads(output)
        self.assertEqual(summary["rows"], 3)
        sheet = Path(summary["sheet"])
        self.assertIn("100 Main St, Austin, TX 78701, USA", read_csv(sheet)[0]["body"])

        code, _ = run(batch.main, ["mark-sent", "--sheet", str(sheet), "--log", str(self.log), "--date", "2026-11-12"])
        self.assertEqual(code, 0)
        base = ["record", "--log", str(self.log), "--suppression", str(self.suppression), "--date", "2026-11-13"]
        self.assertEqual(run(batch.main, base + ["--lead-id", "L-261112-01", "--event", "positive"])[0], 0)
        self.assertEqual(run(batch.main, base + ["--lead-id", "L-261112-02", "--event", "optout"])[0], 0)

        self.assertIn("vera@northbeam2.example", batch.load_suppression(self.suppression).emails)
        code, output = run(batch.main, ["stats", "--log", str(self.log)])
        result = json.loads(output)
        self.assertEqual(result["stats"]["variants"]["A"]["sent"], 3)
        self.assertEqual(result["stats"]["variants"]["A"]["replies"], 1)
        self.assertEqual(result["verdict"]["status"], "single")

    def test_second_build_does_not_email_the_same_people_again(self):
        self.pull_ads()
        self.add_leads(2)
        sheet = Path(json.loads(self.build()[1])["sheet"])
        run(batch.main, ["mark-sent", "--sheet", str(sheet), "--log", str(self.log)])
        code, output = self.build()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["rows"], 0)
        self.assertTrue(all("already contacted" in item["why"] for item in json.loads(output)["left_out"]))

    def test_build_refuses_an_offer_without_an_address(self):
        self.offer.write_text(OFFER.replace("postal_address: 100 Main St, Austin, TX 78701, USA", "postal_address:"))
        self.pull_ads()
        self.add_leads(1)
        code, output = self.build()
        self.assertEqual(code, 1)
        self.assertIn("postal_address", output)

    def test_suppress_command_blocks_a_domain(self):
        self.pull_ads()
        self.add_leads(1)
        run(batch.main, ["suppress", "--suppression", str(self.suppression), "--value", "Northbeam1.example",
                         "--reason", "competitor"])
        code, output = self.build()
        self.assertEqual(code, 1)
        self.assertIn("suppressed", json.loads(output)["left_out"][0]["why"])

    def test_opt_out_without_a_known_email_is_refused(self):
        code, _ = run(batch.main, ["record", "--log", str(self.log), "--suppression", str(self.suppression),
                                   "--lead-id", "L-unknown", "--event", "optout"])
        self.assertEqual(code, 1)

    def test_oversized_batch_fails_cleanly(self):
        self.pull_ads()
        self.add_leads(1)
        self.assertEqual(self.build("--size", "200")[0], 1)


if __name__ == "__main__":
    unittest.main()
