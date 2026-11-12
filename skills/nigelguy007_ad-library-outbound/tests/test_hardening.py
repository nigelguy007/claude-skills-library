"""Regression tests for the gaps two independent reviews found in the send-safety gates."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import _path  # noqa: F401
import adlib
import batch
import lint_draft as lint
import ob_common as c
import score

OFFER = {"sell": "I sell verified B2B lead lists.", "countries": "US", "sender_name": "Sam Rivera",
         "sending_domain": "getleadwell.com", "postal_address": "100 Main St, Austin, TX 78701, USA",
         "opt_out_line": "Not relevant? Reply no and I won't email again."}
OFFER_TEXT = ("---\nsell: I sell verified B2B lead lists.\nmax_words: 35\n"
              "postal_address: 100 Main St, Austin, TX 78701, USA\n---\n"
              "## Proof I can back up\n- 50 free verified emails as a sample\n\n## Never say\n- 90 day guarantee\n")
ADS = {"100": {"id": "100", "headline": "AI-Trained Developers From $999/Month",
               "description": "Hire vetted engineers. No contract."}}
NONE = batch.Suppression(set(), set())
NOBODY = batch.Contacted(set(), set())


def lead(n=1, **over):
    row = {"lead_id": "L-261112-%02d" % n, "company": "Northbeam %d" % n, "domain": "northbeam%d.example" % n,
           "identity_check": "verified", "country": "US", "contact_name": "Vera Lindqvist",
           "email": "vera@northbeam%d.example" % n, "email_status": "verified", "ad_id": "100",
           "ad_url": "https://www.linkedin.com/ad-library/detail/100"}
    row.update(over)
    return row


def draft(n=1, subject="your LinkedIn ad", extra="", ad_id="100"):
    return ("---\nlead_id: L-261112-%02d\nad_id: %s\nad_quote: AI-Trained Developers From $999/Month\n"
            "subject: %s\napproved: no\n---\n## Email A\n"
            "Saw your \"AI-Trained Developers From $999/Month\" LinkedIn ad.\n\n"
            "Want 50 free verified emails of CTOs who are hiring developers?\n\n%s") % (n, ad_id, subject, extra)


def codes(findings, level=None):
    return sorted(f.code for f in findings if level is None or f.level == level)


class TempDir(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.sup = self.dir / "suppression.csv"
        self.log = self.dir / "log.csv"


# ------------------------------------------------------------------ suppression must fail closed

class SuppressionFileTest(TempDir):
    def test_file_saved_with_a_byte_order_mark_still_loads(self):
        self.sup.write_bytes(b"\xef\xbb\xbfvalue,reason,date\r\nJane@X.example,optout,2026-11-01\r\n")
        self.assertIn("jane@x.example", batch.load_suppression(self.sup).emails)

    def test_file_without_a_header_is_an_error_not_an_empty_list(self):
        self.sup.write_text("a@x.example\nb@y.example\n")
        with self.assertRaises(ValueError):
            batch.load_suppression(self.sup)

    def test_capitalised_header_is_accepted(self):
        self.sup.write_text("Value,Reason,Date\nrival.example,competitor,2026-11-01\n")
        self.assertIn("rival.example", batch.load_suppression(self.sup).domains)

    def test_row_that_is_neither_address_nor_domain_is_an_error(self):
        self.sup.write_text("value,reason,date\nnot an address,optout,2026-11-01\n")
        with self.assertRaises(ValueError):
            batch.load_suppression(self.sup)

    def test_append_to_a_file_with_no_final_newline_keeps_both_rows(self):
        self.sup.write_text("value,reason,date\nold@x.example,optout,2026-01-01")
        batch.add_suppression(self.sup, "new@y.example", "optout", "2026-02-02")
        loaded = batch.load_suppression(self.sup)
        self.assertEqual(loaded.emails, {"old@x.example", "new@y.example"})

    def test_display_name_form_suppresses_the_address(self):
        batch.record_event(self.log, self.sup, lead_id="L1", email="Jane Roe <Jane@X.example>", event="optout",
                           day="2026-11-13")
        self.assertIn("jane@x.example", batch.load_suppression(self.sup).emails)
        self.assertIn("suppress", batch.eligibility(lead(email="JANE@x.example"), OFFER,
                                                    batch.load_suppression(self.sup), NOBODY))

    def test_at_domain_and_wildcard_entries_are_domains(self):
        batch.add_suppression(self.sup, "@Rival.example", "competitor", "2026-11-01")
        batch.add_suppression(self.sup, "*.other.example", "competitor", "2026-11-01")
        loaded = batch.load_suppression(self.sup)
        self.assertEqual(loaded.domains, {"rival.example", "other.example"})

    def test_garbage_is_refused_instead_of_stored(self):
        with self.assertRaises(ValueError):
            batch.add_suppression(self.sup, "please stop", "optout", "2026-11-01")

    def test_contact_files_are_private(self):
        batch.add_suppression(self.sup, "a@x.example", "optout", "2026-11-01")
        self.assertEqual(self.sup.stat().st_mode & 0o077, 0)


class DomainMatchTest(unittest.TestCase):
    def test_subdomain_of_a_suppressed_domain_is_blocked(self):
        suppression = batch.Suppression(set(), {"rival.example"})
        for address in ("bob@mail.rival.example", "bob@us.mail.rival.example", "bob@rival.example."):
            self.assertIn("suppress", batch.eligibility(lead(email=address, domain=""), OFFER, suppression, NOBODY),
                          address)

    def test_lookalike_domain_is_not_blocked(self):
        suppression = batch.Suppression(set(), {"rival.example"})
        self.assertIsNone(batch.eligibility(lead(email="bob@notrival.example", domain=""), OFFER, suppression, NOBODY))

    def test_subdomain_of_a_contacted_company_is_blocked(self):
        contacted = batch.Contacted(set(), {"northbeam1.example"})
        self.assertIn("already", batch.eligibility(lead(email="amy@eu.northbeam1.example", domain=""), OFFER,
                                                   NONE, contacted))

    def test_domain_of_ignores_userinfo_and_trailing_dot(self):
        self.assertEqual(c.domain_of("https://user:pw@Host.example./x"), "host.example")

    def test_addresses_with_list_or_formula_characters_are_invalid(self):
        for address in ("a@x.example,b@y.example", "=cmd@x.example", "a b@x.example", "<a@x.example>;"):
            self.assertIn("email", batch.eligibility(lead(email=address), OFFER, NONE, NOBODY), address)


# ------------------------------------------------------------------ approval is bound to what was read

class ApprovalTest(unittest.TestCase):
    def build(self, leads, drafts, **kw):
        args = dict(offer=OFFER, suppression=NONE, contacted=NOBODY, ads_by_id=ADS, offer_text=OFFER_TEXT,
                    size=25, batch_id="B1")
        args.update(kw)
        return batch.build_rows(leads, drafts, **args)

    def test_hand_written_approved_yes_is_not_enough(self):
        text = draft().replace("approved: no", "approved: yes")
        rows, skipped = self.build([lead()], {"L-261112-01": text})
        self.assertEqual(rows, [])
        self.assertIn("not approved", dict(skipped)["L-261112-01"])

    def test_approved_draft_is_sent(self):
        text = batch.approve_draft(draft(), lead())
        rows, skipped = self.build([lead()], {"L-261112-01": text})
        self.assertEqual(len(rows), 1, skipped)

    def test_editing_the_email_after_approval_cancels_it(self):
        text = batch.approve_draft(draft(), lead()).replace("Want 50 free", "Want 50 totally free")
        rows, skipped = self.build([lead()], {"L-261112-01": text})
        self.assertEqual(rows, [])
        self.assertIn("changed after approval", dict(skipped)["L-261112-01"])

    def test_changing_the_address_after_approval_cancels_it(self):
        text = batch.approve_draft(draft(), lead())
        rows, skipped = self.build([lead(email="someone.else@northbeam1.example")], {"L-261112-01": text})
        self.assertEqual(rows, [])
        self.assertIn("changed after approval", dict(skipped)["L-261112-01"])

    def test_duplicate_front_matter_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            c.parse_front_matter("---\napproved: no\napproved: yes\n---\nbody\n")

    def test_draft_quoting_another_leads_ad_is_left_out(self):
        text = batch.approve_draft(draft(ad_id="100"), lead(ad_id="777"))
        rows, skipped = self.build([lead(ad_id="777")], {"L-261112-01": text})
        self.assertEqual(rows, [])
        self.assertIn("different ad", dict(skipped)["L-261112-01"])

    def test_same_address_twice_in_one_batch_is_sent_once(self):
        leads = [lead(1, email="dup@gmail.com", domain=""), lead(2, email="dup@gmail.com", domain="")]
        drafts = {item["lead_id"]: batch.approve_draft(draft(n), item) for n, item in enumerate(leads, 1)}
        rows, skipped = self.build(leads, drafts)
        self.assertEqual(len(rows), 1)
        self.assertIn("already in the batch", dict(skipped)["L-261112-02"])

    def test_batch_id_cannot_escape_the_run_folder(self):
        text = batch.approve_draft(draft(), lead())
        with self.assertRaises(ValueError):
            self.build([lead()], {"L-261112-01": text}, batch_id="x/../../suppression")

    def test_honorific_is_not_used_as_a_first_name(self):
        item = lead(contact_name="Dr. Jane Smith")
        rows, _ = self.build([item], {"L-261112-01": batch.approve_draft(draft(), item)})
        self.assertEqual(rows[0]["first_name"], "Jane")


class CsvSafetyTest(TempDir):
    def test_formula_cells_are_neutralised(self):
        target = self.dir / "sheet.csv"
        c.write_csv(target, ("company", "subject", "email"),
                    [{"company": '=HYPERLINK("http://evil","x")', "subject": "+cmd", "email": "a@x.example"}])
        row = c.read_csv(target)[0]
        self.assertEqual(row["company"][0], "'")
        self.assertEqual(row["subject"][0], "'")
        self.assertEqual(row["email"], "a@x.example")

    def test_unicode_line_separator_in_ad_text_survives_a_round_trip(self):
        target = self.dir / "ads.jsonl"
        c.write_jsonl(target, [{"id": "1", "description": "line one line two\u0085end"}, {"id": "2"}])
        self.assertEqual([row["id"] for row in c.read_jsonl(target)], ["1", "2"])

    def test_non_object_line_is_a_clear_error(self):
        target = self.dir / "ads.jsonl"
        target.write_text('{"id": "1"}\nnull\n')
        with self.assertRaises(ValueError):
            c.read_jsonl(target)

    def test_quote_starting_with_a_hash_is_not_a_comment(self):
        text = '---\nad_quote: #1 CRM for SMB\nsubject: "Hi there" # note\nempty: # todo\n---\n'
        meta, _ = c.parse_front_matter(text)
        self.assertEqual(meta["ad_quote"], "#1 CRM for SMB")
        self.assertEqual(meta["subject"], "Hi there")
        self.assertEqual(meta["empty"], "")


# ------------------------------------------------------------------ lint covers everything that is sent

class LintCoverageTest(unittest.TestCase):
    def run_lint(self, text):
        return lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT)

    def test_placeholder_in_subject_is_an_error(self):
        self.assertIn("placeholder", codes(self.run_lint(draft(subject="[Company] quick q")), "error"))

    def test_placeholder_and_filler_in_a_follow_up_are_errors(self):
        findings = self.run_lint(draft(extra="## Follow-up 1\nHi {first_name}, hope you're well\n"))
        self.assertIn("placeholder", codes(findings, "error"))
        self.assertIn("banned-phrase", codes(findings, "error"))

    def test_one_word_quote_is_not_a_quote(self):
        text = draft().replace("ad_quote: AI-Trained Developers From $999/Month", "ad_quote: vetted")
        self.assertIn("quote-too-short", codes(self.run_lint(text), "error"))

    def test_short_headline_quoted_in_full_is_allowed(self):
        ads = {"100": {"id": "100", "headline": "Watch On-Demand", "description": "A webinar."}}
        text = ("---\nlead_id: L1\nad_id: 100\nad_quote: Watch On-Demand\nsubject: your LinkedIn ad\n---\n"
                "## Email A\nSaw your \"Watch On-Demand\" LinkedIn ad.\n\nWant 50 free verified emails?\n")
        self.assertNotIn("quote-too-short", codes(lint.lint_draft(text, ads_by_id=ads, offer_text=OFFER_TEXT)))

    def test_numbers_in_the_address_or_limits_do_not_back_up_a_claim(self):
        text = draft().replace("Want 50 free verified emails of CTOs who are hiring developers?",
                               "We helped 35 clients and 78701 more. Want 50 free verified emails?")
        self.assertEqual([f.message.split()[2] for f in self.run_lint(text) if f.code == "unbacked-number"],
                         ["35", "78701"])

    def test_number_from_never_say_does_not_back_up_a_claim(self):
        text = draft().replace("hiring developers?", "hiring within 90 days?")
        self.assertIn("unbacked-number", codes(self.run_lint(text), "warning"))


# ------------------------------------------------------------------ results are attributed correctly

def sends(variant, count, replies, test_id="T1", prefix=""):
    rows = []
    for i in range(count):
        lead_id = "%s%s-%s-%03d" % (prefix, test_id, variant, i)
        rows.append({"test_id": test_id, "variant": variant, "lead_id": lead_id, "event": "sent"})
        if i < replies:
            rows.append({"test_id": "", "variant": "", "lead_id": lead_id, "event": "reply"})
    return rows


class StatsAttributionTest(unittest.TestCase):
    def test_untested_sends_are_not_pooled_into_version_a(self):
        rows = sends("A", 60, 0) + sends("B", 60, 0) + sends("A", 60, 30, test_id="", prefix="u")
        result = batch.stats(rows)
        self.assertEqual(result["test_id"], "T1")
        self.assertEqual(result["variants"]["A"]["sent"], 60)
        self.assertEqual(result["variants"]["A"]["replies"], 0)
        self.assertEqual(result["untested_sends"], 60)
        self.assertNotEqual(batch.verdict(result)["status"], "leader")

    def test_several_tests_need_an_explicit_test_id(self):
        rows = sends("A", 10, 1, test_id="T1") + sends("A", 10, 1, test_id="T2")
        with self.assertRaises(ValueError):
            batch.stats(rows)

    def test_reply_logged_without_version_is_credited_to_the_version_it_was_sent_as(self):
        result = batch.stats(sends("A", 50, 1) + sends("B", 50, 9))
        self.assertEqual(result["variants"]["B"]["replies"], 9)

    def test_bounce_for_a_lead_never_sent_does_not_raise_the_alarm(self):
        rows = sends("A", 20, 0, test_id="") + [{"lead_id": "ghost-%d" % i, "event": "bounce", "test_id": "",
                                                  "variant": ""} for i in range(5)]
        self.assertEqual(batch.verdict(batch.stats(rows))["alarms"], [])

    def test_leader_message_warns_about_repeated_looks(self):
        result = batch.verdict(batch.stats(sends("A", 100, 2) + sends("B", 100, 14)))
        self.assertEqual(result["status"], "leader")
        self.assertIn("next batch", result["message"])


class LogTest(TempDir):
    def test_marking_the_same_sheet_sent_twice_logs_each_lead_once(self):
        rows = [{"lead_id": "L1", "email": "a@x.example", "batch_id": "B1", "test_id": "", "variant": "A"}]
        batch.mark_sent(rows, self.log, "2026-11-12")
        batch.mark_sent(rows, self.log, "2026-11-12")
        self.assertEqual(len(batch.read_log(self.log)), 1)

    def test_log_missing_its_columns_is_an_error(self):
        self.log.write_text("a@x.example,sent\n")
        with self.assertRaises(ValueError):
            batch.read_log(self.log)


class BuildCommandTest(TempDir):
    def run_main(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            return batch.main(argv), buffer.getvalue()

    def workspace(self):
        run = self.dir / "runs" / "r1"
        (run / "leads").mkdir(parents=True)
        (run / "drafts").mkdir()
        offer = self.dir / "offer.md"
        offer.write_text(OFFER_TEXT.replace("---\nsell", "---\ncountries: US\nsender_name: Sam Rivera\n"
                                            "sending_domain: getleadwell.com\nopt_out_line: Reply no.\nsell", 1))
        c.write_jsonl(run / "ads.jsonl", [ADS["100"]])
        (run / "leads" / "L-261112-01.md").write_text(
            "---\n" + "".join("%s: %s\n" % pair for pair in lead().items()) + "---\n")
        (run / "drafts" / "L-261112-01.md").write_text(draft())
        return run, offer

    def test_build_refuses_a_missing_suppression_file_until_init_is_run(self):
        run, offer = self.workspace()
        base = ["--suppression", str(self.sup), "--log", str(self.log)]
        code, _ = self.run_main(["build", "--run", str(run), "--offer", str(offer)] + base)
        self.assertEqual(code, 1)
        self.assertEqual(self.run_main(["init"] + base)[0], 0)
        self.assertEqual(self.run_main(["approve", "--run", str(run), "--all"])[0], 0)
        code, output = self.run_main(["build", "--run", str(run), "--offer", str(offer), "--batch-id", "B1"] + base)
        self.assertEqual(code, 0, output)
        summary = json.loads(output)
        self.assertEqual(summary["rows"], 1)
        self.assertEqual(summary["suppressed_loaded"], {"emails": 0, "domains": 0})

    def test_unreadable_lead_file_is_reported_not_dropped(self):
        run, offer = self.workspace()
        (run / "leads" / "broken.md").write_text("no front matter here\n")
        base = ["--suppression", str(self.sup), "--log", str(self.log)]
        self.run_main(["init"] + base)
        self.run_main(["approve", "--run", str(run), "--all"])
        _, output = self.run_main(["build", "--run", str(run), "--offer", str(offer), "--batch-id", "B1"] + base)
        self.assertIn("broken.md", output)


# ------------------------------------------------------------------ fetching and scoring

class AdlibHardeningTest(unittest.TestCase):
    def test_failure_on_a_later_page_keeps_the_pages_already_paid_for(self):
        calls = []

        def fetch(path, params):
            calls.append(1)
            if len(calls) == 2:
                raise adlib.ApiError(500, "Internal Server Error")
            return {"ads": [{"id": "1", "advertiser": "A"}], "paginationToken": "t", "isLastPage": False,
                    "credits_charged": 1}

        ads, meta = adlib.search_linkedin(fetch, keyword="x", company=None, countries="US", start=None, end=None,
                                          pages=3)
        self.assertEqual(len(ads), 1)
        self.assertIn("500", meta["error"])

    def test_failure_on_the_first_page_still_raises(self):
        def fetch(path, params):
            raise adlib.ApiError(401, "Invalid API key")

        with self.assertRaises(adlib.ApiError):
            adlib.search_linkedin(fetch, keyword="x", company=None, countries="US", start=None, end=None, pages=2)

    def test_company_id_is_only_read_from_a_numeric_page_link(self):
        named = adlib.normalise_linkedin({"id": "1", "advertiserLinkedinPage": "https://www.linkedin.com/company/3m"})
        numeric = adlib.normalise_linkedin(
            {"id": "2", "advertiserLinkedinPage": "https://www.linkedin.com/company/37/"})
        self.assertIsNone(named["advertiser_id"])
        self.assertEqual(numeric["advertiser_id"], "37")

    def test_ads_without_an_id_are_dropped(self):
        def fetch(path, params):
            return {"ads": [{"advertiser": "A"}, {"id": "9", "advertiser": "B"}], "isLastPage": True}

        ads, _ = adlib.search_linkedin(fetch, keyword="x", company=None, countries="US", start=None, end=None, pages=1)
        self.assertEqual([ad["id"] for ad in ads], ["9"])

    def test_redirects_are_refused_so_the_key_is_never_forwarded(self):
        handler = adlib.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "http://elsewhere.example/"))

    def test_country_with_trailing_newline_is_rejected(self):
        with self.assertRaises(ValueError):
            adlib.meta_params(keyword="x", country="US\n", start=None, end=None, cursor=None)


class ScoreHardeningTest(unittest.TestCase):
    def test_claim_patterns_do_not_fire_on_years_dates_or_chapters(self):
        for text in ("In 2024, teams love it", "Event 3/5 at noon", "Chapter 2. Customers say hi",
                     "Reply within 24 hours"):
            self.assertFalse(score.has_claim(text), text)

    def test_real_claims_still_fire(self):
        for text in ("Save 10 hours a week", "Rated 4.9 out of 5", "Trusted by 2,500 teams", "Cut costs 30%"):
            self.assertTrue(score.has_claim(text), text)

    def test_claim_regex_is_fast_on_hostile_text(self):
        import time
        started = time.perf_counter()
        score.has_claim(",".join(["1"] * 20000))
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_owner_title_edge_cases(self):
        for title in ("Vice-President of Sales", "Vice  President", "Assistant to the President", "Former CEO",
                      "Ex-Founder at Acme"):
            self.assertFalse(score.owner_role(title), title)
        for title in ("President and CEO", "Co-Founder & CTO", "Owner, Acme Plumbing"):
            self.assertTrue(score.owner_role(title), title)

    def test_advertiser_name_must_match_whole_words_in_the_title(self):
        ad = {"library": "linkedin", "id": "1", "advertiser": "Go", "advertiser_id": "5", "poster": "Al Roe",
              "poster_title": "Founder at Google", "promoted_by": "Promoted by Go"}
        self.assertIsNone(score.contact_hint(ad))

    def test_non_latin_names_are_not_merged(self):
        ads = [{"library": "linkedin", "id": "1", "advertiser": "株式会社A", "headline": "x"},
               {"library": "linkedin", "id": "2", "advertiser": "株式会社B", "headline": "y"}]
        self.assertEqual(len(score.rank(ads, today=date(2026, 11, 12))), 2)

    def test_rows_carry_their_rank(self):
        ads = [{"library": "linkedin", "id": "1", "advertiser": "A", "advertiser_id": "1", "headline": "From $9"},
               {"library": "linkedin", "id": "2", "advertiser": "B", "advertiser_id": "2", "headline": "hello"}]
        self.assertEqual([row["rank"] for row in score.rank(ads, today=date(2026, 11, 12))], [1, 2])


if __name__ == "__main__":
    unittest.main()
