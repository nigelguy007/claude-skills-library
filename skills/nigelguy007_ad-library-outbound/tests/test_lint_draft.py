import unittest

import _path  # noqa: F401
import lint_draft as lint

AD = {
    "library": "linkedin",
    "id": "100",
    "headline": "AI-Trained Developers From $999/Month",
    "description": "Hire vetted engineers. No contract.",
}
ADS = {"100": AD}
OFFER_TEXT = "I sell verified B2B lead lists.\n\n## Proof I can back up\n- 50 free verified emails as a sample\n"

GOOD = """---
lead_id: L-261112-01
ad_id: 100
ad_quote: AI-Trained Developers From $999/Month
subject: your LinkedIn ad
---
## Email A
Saw your “AI-Trained Developers From $999/Month” LinkedIn ad.

Want 50 free verified emails of CTOs who are hiring developers?

## Follow-up 1
Did this land?
"""


def codes(findings, level=None):
    return sorted(f.code for f in findings if level is None or f.level == level)


def draft(email_a=None, extra="", **meta):
    fields = {"lead_id": "L-261112-01", "ad_id": "100",
              "ad_quote": "AI-Trained Developers From $999/Month", "subject": "your LinkedIn ad"}
    fields.update(meta)
    head = "".join("%s: %s\n" % (k, v) for k, v in fields.items() if v is not None)
    body = email_a if email_a is not None else (
        "Saw your \"AI-Trained Developers From $999/Month\" LinkedIn ad.\n\n"
        "Want 50 free verified emails of CTOs who are hiring developers?"
    )
    return "---\n%s---\n## Email A\n%s\n%s" % (head, body, extra)


class GoodDraftTest(unittest.TestCase):
    def test_guide_style_email_has_no_errors_or_warnings(self):
        findings = lint.lint_draft(GOOD, ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertEqual(codes(findings), [])

    def test_curly_quotes_around_the_ad_line_still_match(self):
        findings = lint.lint_draft(GOOD, ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertNotIn("quote-missing", codes(findings))


class ShapeTest(unittest.TestCase):
    def test_missing_email_section_is_an_error(self):
        findings = lint.lint_draft("---\nlead_id: x\n---\nno sections\n", ads_by_id=ADS)
        self.assertIn("no-email", codes(findings, "error"))

    def test_three_lines_is_an_error(self):
        text = draft("Saw your \"AI-Trained Developers From $999/Month\" ad.\n\nNice.\n\nWant 50 leads?")
        self.assertIn("line-count", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_more_than_35_words_is_an_error(self):
        long_line = " ".join(["word"] * 30) + "?"
        text = draft("Saw your \"AI-Trained Developers From $999/Month\" LinkedIn ad.\n\n" + long_line)
        self.assertIn("word-count", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_placeholder_brackets_are_an_error(self):
        text = draft("Saw your \"AI-Trained Developers From $999/Month\" ad, [company].\n\nWant 50 leads?")
        self.assertIn("placeholder", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_banned_opener_is_an_error(self):
        text = draft("Hope you're well. Saw \"AI-Trained Developers From $999/Month\".\n\nWant 50 leads?")
        self.assertIn("banned-phrase", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_second_line_without_a_question_is_a_warning(self):
        text = draft("Saw your \"AI-Trained Developers From $999/Month\" ad.\n\nI can send 50 leads.")
        findings = lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertIn("no-question", codes(findings, "warning"))
        self.assertEqual(codes(findings, "error"), [])


class QuoteTest(unittest.TestCase):
    def test_email_that_does_not_quote_the_ad_is_an_error(self):
        text = draft("Saw your LinkedIn ad about developers.\n\nWant 50 free leads?")
        self.assertIn("quote-missing", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_quote_that_is_not_in_the_ad_is_an_error(self):
        text = draft("Saw your \"Developers From $499/Month\" ad.\n\nWant 50 free leads?",
                     ad_quote="Developers From $499/Month")
        self.assertIn("quote-not-in-ad", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_unknown_ad_id_is_an_error(self):
        text = draft(ad_id="999")
        self.assertIn("ad-not-found", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_without_ad_records_the_quote_cannot_be_checked_and_says_so(self):
        findings = lint.lint_draft(draft(), ads_by_id=None, offer_text=OFFER_TEXT)
        self.assertIn("quote-unchecked", codes(findings, "warning"))


class NumbersTest(unittest.TestCase):
    def test_number_not_in_ad_quote_or_offer_is_a_warning(self):
        text = draft("Saw your \"AI-Trained Developers From $999/Month\" ad.\n\nWant 200 free leads?")
        findings = lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertIn("unbacked-number", codes(findings, "warning"))

    def test_number_backed_by_the_offer_file_is_fine(self):
        findings = lint.lint_draft(draft(), ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertNotIn("unbacked-number", codes(findings))


class SubjectTest(unittest.TestCase):
    def test_missing_subject_is_an_error(self):
        self.assertIn("subject-missing", codes(lint.lint_draft(draft(subject=None), ads_by_id=ADS), "error"))

    def test_fake_reply_prefix_is_an_error(self):
        findings = lint.lint_draft(draft(subject="Re: your ad"), ads_by_id=ADS)
        self.assertIn("subject-fake-thread", codes(findings, "error"))

    def test_long_subject_is_a_warning(self):
        findings = lint.lint_draft(draft(subject="a quick idea about the LinkedIn ad you run"), ads_by_id=ADS)
        self.assertIn("subject-long", codes(findings, "warning"))


class VariantTest(unittest.TestCase):
    A1 = "Saw your \"AI-Trained Developers From $999/Month\" LinkedIn ad."
    A2 = "Want 50 free verified emails of CTOs who are hiring developers?"

    def _with_b(self, b1, b2):
        return draft(extra="## Email B\n%s\n\n%s\n" % (b1, b2))

    def test_b_changing_one_line_is_fine(self):
        text = self._with_b("Your \"AI-Trained Developers From $999/Month\" ad caught my eye.", self.A2)
        findings = lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertNotIn("variant-diff", codes(findings))

    def test_b_changing_both_lines_is_an_error(self):
        text = self._with_b("Your \"AI-Trained Developers From $999/Month\" ad caught my eye.",
                            "Open to 50 free verified emails?")
        self.assertIn("variant-diff", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))

    def test_b_identical_to_a_is_an_error(self):
        text = self._with_b(self.A1, self.A2)
        self.assertIn("variant-diff", codes(lint.lint_draft(text, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))


class ExtrasTest(unittest.TestCase):
    def test_three_follow_ups_is_an_error(self):
        extra = "## Follow-up 1\nDid this land?\n## Follow-up 2\nWorth a look?\n## Follow-up 3\nLast try.\n"
        findings = lint.lint_draft(draft(extra=extra), ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertIn("followup-count", codes(findings, "error"))

    def test_long_follow_up_is_a_warning(self):
        extra = "## Follow-up 1\n" + " ".join(["word"] * 25) + "\n"
        findings = lint.lint_draft(draft(extra=extra), ads_by_id=ADS, offer_text=OFFER_TEXT)
        self.assertIn("followup-long", codes(findings, "warning"))

    def test_linkedin_note_over_300_chars_is_an_error_and_over_200_a_warning(self):
        over_300 = draft(extra="## LinkedIn note\n" + "x" * 320 + "\n")
        over_200 = draft(extra="## LinkedIn note\n" + "x" * 240 + "\n")
        self.assertIn("li-note-long", codes(lint.lint_draft(over_300, ads_by_id=ADS, offer_text=OFFER_TEXT), "error"))
        self.assertIn("li-note-long", codes(lint.lint_draft(over_200, ads_by_id=ADS, offer_text=OFFER_TEXT), "warning"))


class ReportTest(unittest.TestCase):
    def test_passed_is_false_only_when_there_are_errors(self):
        self.assertTrue(lint.passed(lint.lint_draft(GOOD, ads_by_id=ADS, offer_text=OFFER_TEXT)))
        self.assertFalse(lint.passed(lint.lint_draft(draft(subject=None), ads_by_id=ADS)))


if __name__ == "__main__":
    unittest.main()
