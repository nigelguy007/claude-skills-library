import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import ob_common as c


class NormalizeNameTest(unittest.TestCase):
    def test_strips_case_punctuation_and_company_suffixes(self):
        self.assertEqual(c.normalize_name("Opal Labs Inc."), "opal labs")
        self.assertEqual(c.normalize_name("  NORTHBEAM,  LLC "), "northbeam")

    def test_empty_and_none_become_empty_string(self):
        self.assertEqual(c.normalize_name(None), "")
        self.assertEqual(c.normalize_name(""), "")


class FrontMatterTest(unittest.TestCase):
    def test_reads_flat_keys_quotes_and_colons_in_values(self):
        text = (
            "---\n"
            "lead_id: L-261112-01\n"
            '# a comment\n'
            'ad_quote: "Developers From $999/Month: no contract"\n'
            "website: https://example.com/a\n"
            "---\n"
            "## Email A\nhello\n"
        )
        meta, body = c.parse_front_matter(text)
        self.assertEqual(meta["lead_id"], "L-261112-01")
        self.assertEqual(meta["ad_quote"], "Developers From $999/Month: no contract")
        self.assertEqual(meta["website"], "https://example.com/a")
        self.assertTrue(body.startswith("## Email A"))

    def test_text_without_front_matter_returns_empty_meta(self):
        meta, body = c.parse_front_matter("just text\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just text\n")


class SectionsTest(unittest.TestCase):
    def test_splits_on_level_two_headings_in_order(self):
        body = "intro\n## Email A\nline one\n\nline two\n## Follow-up 1\nDid this land?\n"
        sections = c.split_sections(body)
        self.assertEqual(list(sections), ["Email A", "Follow-up 1"])
        self.assertEqual(sections["Email A"], "line one\n\nline two")
        self.assertEqual(sections["Follow-up 1"], "Did this land?")


class TextHelpersTest(unittest.TestCase):
    def test_word_count_splits_on_whitespace(self):
        self.assertEqual(c.word_count("Saw your ad.\n\nWant 50 free leads?"), 7)

    def test_numeric_tokens_drop_commas_and_keep_decimals(self):
        self.assertEqual(
            c.numeric_tokens("From $999/month, 12,000 users, 3.5x"),
            {"999", "12000", "3.5"},
        )

    def test_domain_of_email_and_url(self):
        self.assertEqual(c.domain_of("Ana@Example.COM"), "example.com")
        self.assertEqual(c.domain_of("https://www.example.io/path?x=1"), "example.io")
        self.assertEqual(c.domain_of(""), "")

    def test_fold_normalises_quotes_whitespace_and_case(self):
        self.assertEqual(c.fold("“AI-Trained”   Devs\n"), '"ai-trained" devs')


class JsonlTest(unittest.TestCase):
    def test_round_trip_and_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ads.jsonl"
            self.assertEqual(c.read_jsonl(path), [])
            c.write_jsonl(path, [{"id": "1"}, {"id": "2"}])
            self.assertEqual(c.read_jsonl(path), [{"id": "1"}, {"id": "2"}])


if __name__ == "__main__":
    unittest.main()
