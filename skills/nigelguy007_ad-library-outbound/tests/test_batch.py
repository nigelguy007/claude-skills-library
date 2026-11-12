import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import batch

OFFER = {
    "sell": "I sell verified B2B lead lists.",
    "countries": "US",
    "sender_name": "Sam Rivera",
    "sender_company": "Leadwell",
    "sending_domain": "getleadwell.com",
    "main_domain": "leadwell.com",
    "postal_address": "100 Main St, Austin, TX 78701, USA",
    "opt_out_line": "Not relevant? Reply no and I won't email again.",
}
OFFER_TEXT = "I sell verified B2B lead lists.\n## Proof I can back up\n- 50 free verified emails\n"
ADS = {"100": {"library": "linkedin", "id": "100", "headline": "AI-Trained Developers From $999/Month",
               "description": "Hire vetted engineers."}}


def lead(n=1, **over):
    row = {
        "lead_id": "L-261112-%02d" % n,
        "company": "Northbeam Data %d" % n,
        "domain": "northbeam%d.example" % n,
        "identity_check": "verified",
        "country": "US",
        "contact_name": "Vera Lindqvist",
        "email": "vera@northbeam%d.example" % n,
        "email_status": "verified",
        "ad_id": "100",
        "ad_url": "https://www.linkedin.com/ad-library/detail/100",
    }
    row.update(over)
    return row


def draft(n=1, with_b=False, subject="your LinkedIn ad"):
    text = (
        "---\nlead_id: L-261112-%02d\nad_id: 100\napproved: no\n"
        "ad_quote: AI-Trained Developers From $999/Month\nsubject: %s\n%s---\n"
        "## Email A\nSaw your \"AI-Trained Developers From $999/Month\" LinkedIn ad.\n\n"
        "Want 50 free verified emails of CTOs who are hiring developers?\n\n"
        "## Follow-up 1\nDid this land?\n"
    ) % (n, subject, "test_id: T1-first-line\n" if with_b else "")
    if with_b:
        text += (
            "## Email B\nYour \"AI-Trained Developers From $999/Month\" ad caught my eye.\n\n"
            "Want 50 free verified emails of CTOs who are hiring developers?\n"
        )
    return text


def build(leads, drafts, approve=True, **kw):
    """Build a batch. Unless approve=False, each draft is first approved the way the user would."""
    args = dict(offer=OFFER, suppression=batch.Suppression(set(), set()), contacted=batch.Contacted(set(), set()),
                ads_by_id=ADS, offer_text=OFFER_TEXT, size=25, batch_id="B-261112-1")
    args.update(kw)
    by_id = {item["lead_id"]: item for item in leads}
    if approve:
        drafts = {lead_id: batch.approve_draft(text, by_id[lead_id]) if lead_id in by_id else text
                  for lead_id, text in drafts.items()}
    return batch.build_rows(leads, drafts, **args)


class OfferTest(unittest.TestCase):
    def test_complete_offer_has_no_errors(self):
        errors, warnings = batch.validate_offer(OFFER)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_postal_address_and_opt_out_are_errors(self):
        offer = dict(OFFER, postal_address="", opt_out_line="")
        errors, _ = batch.validate_offer(offer)
        self.assertTrue(any("postal_address" in e for e in errors))
        self.assertTrue(any("opt_out_line" in e for e in errors))

    def test_sending_from_the_main_domain_is_a_warning(self):
        _, warnings = batch.validate_offer(dict(OFFER, sending_domain="leadwell.com"))
        self.assertTrue(any("main domain" in w for w in warnings))

    def test_non_us_country_is_a_warning(self):
        _, warnings = batch.validate_offer(dict(OFFER, countries="US,DE"))
        self.assertTrue(any("DE" in w for w in warnings))

    def test_footer_carries_identity_address_and_opt_out(self):
        text = batch.footer(OFFER)
        for part in ("Sam Rivera", "Leadwell", "100 Main St, Austin, TX 78701, USA", "Reply no"):
            self.assertIn(part, text)


class EligibilityTest(unittest.TestCase):
    def check(self, row, suppression=None, contacted=None):
        return batch.eligibility(row, OFFER, suppression or batch.Suppression(set(), set()),
                                 contacted or batch.Contacted(set(), set()))

    def test_verified_us_lead_is_eligible(self):
        self.assertIsNone(self.check(lead()))

    def test_unverified_company_identity_blocks_sending(self):
        self.assertIn("identity", self.check(lead(identity_check="unverified")))

    def test_guessed_email_blocks_sending(self):
        self.assertIn("guessed", self.check(lead(email_status="guessed")))

    def test_published_email_is_sendable(self):
        self.assertIsNone(self.check(lead(email_status="published")))

    def test_missing_or_malformed_email_blocks_sending(self):
        self.assertIn("email", self.check(lead(email="")))
        self.assertIn("email", self.check(lead(email="not-an-email")))

    def test_country_outside_offer_blocks_sending(self):
        self.assertIn("DE", self.check(lead(country="DE")))
        self.assertIn("country", self.check(lead(country="")))

    def test_suppressed_email_or_domain_blocks_sending(self):
        by_email = batch.Suppression({"vera@northbeam1.example"}, set())
        by_domain = batch.Suppression(set(), {"northbeam1.example"})
        self.assertIn("suppress", self.check(lead(), suppression=by_email))
        self.assertIn("suppress", self.check(lead(), suppression=by_domain))

    def test_already_contacted_company_blocks_sending(self):
        contacted = batch.Contacted(set(), {"northbeam1.example"})
        self.assertIn("already", self.check(lead(email="other@northbeam1.example"), contacted=contacted))

    def test_free_mail_domain_only_blocks_the_same_address(self):
        contacted = batch.contacted_from_log([{"event": "sent", "email": "a@gmail.com", "lead_id": "x"}])
        self.assertIsNone(self.check(lead(email="b@gmail.com", domain=""), contacted=contacted))
        self.assertIn("already", self.check(lead(email="a@gmail.com", domain=""), contacted=contacted))


class VariantTest(unittest.TestCase):
    def test_split_is_even_deterministic_and_not_in_lead_order(self):
        ids = ["L-261112-%02d" % n for n in range(1, 21)]
        first = batch.assign_variants(ids)
        self.assertEqual(first, batch.assign_variants(list(reversed(ids))))
        self.assertEqual(sorted(first.values()).count("A"), 10)
        in_order = [first[i] for i in ids]
        self.assertNotEqual(in_order, ["A", "B"] * 10)


class BuildTest(unittest.TestCase):
    def test_row_has_two_lines_then_footer(self):
        rows, skipped = build([lead()], {"L-261112-01": draft()})
        self.assertEqual(skipped, [])
        row = rows[0]
        self.assertEqual(row["email"], "vera@northbeam1.example")
        self.assertEqual(row["first_name"], "Vera")
        self.assertEqual(row["subject"], "your LinkedIn ad")
        self.assertEqual(row["variant"], "A")
        self.assertEqual(row["followup_1"], "Did this land?")
        self.assertTrue(row["body"].startswith("Saw your"))
        self.assertIn("\n\nWant 50 free verified emails", row["body"])
        self.assertIn("100 Main St, Austin, TX 78701, USA", row["body"])
        self.assertIn("Reply no", row["body"])

    def test_ineligible_leads_are_skipped_with_reasons(self):
        leads = [lead(1), lead(2, email_status="guessed"), lead(3)]
        drafts = {"L-261112-01": draft(1), "L-261112-02": draft(2)}
        rows, skipped = build(leads, drafts)
        self.assertEqual([r["lead_id"] for r in rows], ["L-261112-01"])
        reasons = dict(skipped)
        self.assertIn("guessed", reasons["L-261112-02"])
        self.assertIn("no draft", reasons["L-261112-03"])

    def test_draft_the_user_has_not_approved_is_never_sent(self):
        rows, skipped = build([lead()], {"L-261112-01": draft()}, approve=False)
        self.assertEqual(rows, [])
        self.assertIn("not approved", dict(skipped)["L-261112-01"])

    def test_draft_that_fails_lint_is_skipped(self):
        rows, skipped = build([lead()], {"L-261112-01": draft(subject="Re: your ad")})
        self.assertEqual(rows, [])
        self.assertIn("subject-fake-thread", dict(skipped)["L-261112-01"])

    def test_batch_size_holds_the_rest(self):
        leads = [lead(n) for n in range(1, 6)]
        drafts = {item["lead_id"]: draft(n) for n, item in enumerate(leads, 1)}
        rows, skipped = build(leads, drafts, size=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len([s for s in skipped if "held" in s[1]]), 2)

    def test_two_versions_are_split_evenly_and_carry_the_test_id(self):
        leads = [lead(n) for n in range(1, 11)]
        drafts = {item["lead_id"]: draft(n, with_b=True) for n, item in enumerate(leads, 1)}
        rows, _ = build(leads, drafts)
        self.assertEqual(sorted(r["variant"] for r in rows).count("B"), 5)
        self.assertEqual({r["test_id"] for r in rows}, {"T1-first-line"})
        b_row = next(r for r in rows if r["variant"] == "B")
        self.assertTrue(b_row["body"].startswith("Your \"AI-Trained"))

    def test_size_above_thirty_needs_an_explicit_override(self):
        with self.assertRaises(ValueError):
            build([lead()], {"L-261112-01": draft()}, size=31)
        rows, _ = build([lead()], {"L-261112-01": draft()}, size=31, allow_large=True)
        self.assertEqual(len(rows), 1)


class LogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "log.csv"
        self.sup = Path(self.tmp.name) / "suppression.csv"

    def test_mark_sent_writes_one_sent_row_per_sheet_row(self):
        rows, _ = build([lead(1), lead(2)], {"L-261112-01": draft(1), "L-261112-02": draft(2)})
        batch.mark_sent(rows, self.log, "2026-11-12")
        log = batch.read_log(self.log)
        self.assertEqual([r["event"] for r in log], ["sent", "sent"])
        self.assertEqual(log[0]["batch_id"], "B-261112-1")

    def test_opt_out_is_logged_and_suppressed(self):
        batch.record_event(self.log, self.sup, lead_id="L-261112-01", email="Vera@Northbeam1.example",
                           event="optout", day="2026-11-13")
        suppression = batch.load_suppression(self.sup)
        self.assertIn("vera@northbeam1.example", suppression.emails)
        self.assertEqual(batch.read_log(self.log)[0]["event"], "optout")

    def test_bounce_is_suppressed_and_reply_is_not(self):
        batch.record_event(self.log, self.sup, lead_id="a", email="a@x.example", event="bounce", day="2026-11-13")
        batch.record_event(self.log, self.sup, lead_id="b", email="b@x.example", event="reply", day="2026-11-13")
        suppression = batch.load_suppression(self.sup)
        self.assertIn("a@x.example", suppression.emails)
        self.assertNotIn("b@x.example", suppression.emails)

    def test_unknown_event_is_rejected(self):
        with self.assertRaises(ValueError):
            batch.record_event(self.log, self.sup, lead_id="a", email="a@x.example", event="opened",
                               day="2026-11-13")

    def test_suppression_file_accepts_domains(self):
        self.sup.write_text("value,reason,date\ncompetitor.example,competitor,2026-11-01\n")
        suppression = batch.load_suppression(self.sup)
        self.assertIn("competitor.example", suppression.domains)


def log_rows(variant, sent, replies, positive=0, bounces=0, test_id="T1"):
    rows = []
    for i in range(sent):
        lead_id = "%s-%s-%03d" % (test_id, variant, i)  # a lead belongs to one test
        rows.append({"test_id": test_id, "variant": variant, "lead_id": lead_id, "event": "sent"})
        if i < replies:
            rows.append({"test_id": test_id, "variant": variant, "lead_id": lead_id,
                         "event": "positive" if i < positive else "reply"})
        if sent - i <= bounces:
            rows.append({"test_id": test_id, "variant": variant, "lead_id": lead_id, "event": "bounce"})
    return rows


class StatsTest(unittest.TestCase):
    def test_counts_distinct_leads_and_positive_counts_as_a_reply(self):
        rows = log_rows("A", sent=20, replies=3, positive=1)
        rows.append(dict(rows[1]))  # the same reply logged twice
        result = batch.stats(rows)["variants"]["A"]
        self.assertEqual(result["sent"], 20)
        self.assertEqual(result["replies"], 3)
        self.assertEqual(result["positive"], 1)
        self.assertAlmostEqual(result["reply_rate"], 0.15)

    def test_filters_by_test_id(self):
        rows = log_rows("A", 10, 1, test_id="T1") + log_rows("A", 30, 2, test_id="T2")
        self.assertEqual(batch.stats(rows, test_id="T2")["variants"]["A"]["sent"], 30)

    def test_wilson_interval_matches_reference_values(self):
        low, high = batch.wilson(10, 100)
        self.assertAlmostEqual(low, 0.0552, places=3)
        self.assertAlmostEqual(high, 0.1744, places=3)
        self.assertEqual(batch.wilson(0, 0), (0.0, 0.0))

    def test_fisher_two_sided_matches_reference_value(self):
        self.assertAlmostEqual(batch.fisher_two_sided(1, 9, 11, 3), 0.002759, places=5)
        self.assertAlmostEqual(batch.fisher_two_sided(5, 5, 5, 5), 1.0, places=6)


class VerdictTest(unittest.TestCase):
    def test_guide_sized_batch_is_too_early_to_call(self):
        rows = log_rows("A", 13, 1) + log_rows("B", 12, 2)
        result = batch.verdict(batch.stats(rows))
        self.assertEqual(result["status"], "too_early")
        self.assertIn("50", result["message"])

    def test_clear_gap_with_enough_sends_names_a_leader(self):
        rows = log_rows("A", 100, 2) + log_rows("B", 100, 12)
        result = batch.verdict(batch.stats(rows))
        self.assertEqual(result["status"], "leader")
        self.assertEqual(result["winner"], "B")
        self.assertLess(result["p_value"], 0.10)

    def test_small_gap_with_enough_sends_is_no_difference(self):
        rows = log_rows("A", 100, 4) + log_rows("B", 100, 5)
        self.assertEqual(batch.verdict(batch.stats(rows))["status"], "no_difference")

    def test_single_version_reports_rate_without_a_winner(self):
        result = batch.verdict(batch.stats(log_rows("A", 25, 1)))
        self.assertEqual(result["status"], "single")
        self.assertNotIn("winner", result)

    def test_high_bounce_rate_raises_an_alarm(self):
        result = batch.verdict(batch.stats(log_rows("A", 40, 1, bounces=4)))
        self.assertTrue(any("bounce" in a for a in result["alarms"]))

    def test_no_sends_is_reported_plainly(self):
        self.assertEqual(batch.verdict(batch.stats([]))["status"], "no_data")


if __name__ == "__main__":
    unittest.main()
