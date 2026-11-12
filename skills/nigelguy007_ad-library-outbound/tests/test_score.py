import unittest
from datetime import date

import _path  # noqa: F401
import score


def li_ad(**over):
    """A normalised LinkedIn ad record; names are invented."""
    ad = {
        "library": "linkedin",
        "id": "100",
        "url": "https://www.linkedin.com/ad-library/detail/100",
        "advertiser": "Northbeam Data",
        "advertiser_id": "555",
        "advertiser_url": "https://www.linkedin.com/company/555",
        "poster": "Northbeam Data",
        "poster_title": None,
        "promoted_by": None,
        "paid_for_by": "Northbeam Data, Inc.",
        "headline": "AI-Trained Developers From $999/Month",
        "description": "Hire vetted engineers. No contract.",
        "cta": "Learn more",
        "destination_url": None,
        "start_date": None,
        "end_date": None,
        "duplicates": None,
    }
    ad.update(over)
    return ad


COMPANY_AD = li_ad()
BOOSTED_INSIDER = li_ad(
    id="101",
    poster="Vera Lindqvist",
    poster_title="Data for brokers | Co-Founder @ Northbeam Data (YC W24)",
    promoted_by="Promoted by Northbeam Data",
    headline=None,
    description="I know a broker with $31M+ listed in 12 months. He called 40+ owners.",
)
BOOSTED_CUSTOMER = li_ad(
    id="102",
    poster="Jon Aldana",
    poster_title="Brokerage Associate at Harbor Capital",
    promoted_by="Promoted by Northbeam Data",
    headline="I just generated 144 qualified leads as a broker",
    description="Here is how.",
)
SELF_OWNER = li_ad(
    id="200",
    advertiser="Greta Voss",
    advertiser_id=None,
    advertiser_url=None,
    poster="Greta Voss",
    poster_title="CEO, Voss Strategies",
    promoted_by="Promoted",
    paid_for_by="Voss Strategies",
    headline=None,
    description="Most boards get growth wrong.",
)
SELF_EMPLOYEE = li_ad(
    id="300",
    advertiser="Ravi Patel",
    advertiser_id=None,
    advertiser_url=None,
    poster="Ravi Patel",
    poster_title="Architect / AI Product Engineer",
    promoted_by="Promoted",
    paid_for_by="Ravi Patel",
    headline=None,
    description="Thoughts on agents.",
)


class ClassifyTest(unittest.TestCase):
    def test_company_ad(self):
        self.assertEqual(score.classify_ad(COMPANY_AD), "company")

    def test_person_post_boosted_by_a_company(self):
        self.assertEqual(score.classify_ad(BOOSTED_INSIDER), "boosted_by_company")

    def test_person_boosting_their_own_post(self):
        self.assertEqual(score.classify_ad(SELF_OWNER), "self_promoted")


    def test_person_without_a_title_is_spotted_by_their_profile_link(self):
        ad = li_ad(advertiser="Erik Vale", advertiser_id=None, poster="Erik Vale", poster_title=None,
                   advertiser_url="https://www.linkedin.com/in/erikvale", promoted_by=None,
                   paid_for_by="Vale XM, Inc.")
        self.assertEqual(score.classify_ad(ad), "self_promoted")


class OwnerRoleTest(unittest.TestCase):
    def test_owner_titles(self):
        for title in ("Co-Founder @ X", "Cofounder", "CEO, Y", "Owner", "Founder | Chief Executive Officer",
                      "Managing Partner", "President"):
            self.assertTrue(score.owner_role(title), title)

    def test_non_owner_titles(self):
        for title in ("Brokerage Associate at Z", "Founding Engineer", "Chief Growth Officer",
                      "Vice President of Sales", None, ""):
            self.assertFalse(score.owner_role(title), title)


class ContactHintTest(unittest.TestCase):
    def test_self_promoted_owner_is_a_contact(self):
        hint = score.contact_hint(SELF_OWNER)
        self.assertEqual(hint["name"], "Greta Voss")
        self.assertIn("own post", hint["basis"])

    def test_boosted_insider_owner_is_a_contact(self):
        hint = score.contact_hint(BOOSTED_INSIDER)
        self.assertEqual(hint["name"], "Vera Lindqvist")
        self.assertIn("names the advertiser", hint["basis"])

    def test_boosted_customer_is_not_a_contact(self):
        self.assertIsNone(score.contact_hint(BOOSTED_CUSTOMER))

    def test_self_promoted_owner_carries_their_profile_link(self):
        ad = dict(SELF_OWNER, advertiser_url="https://www.linkedin.com/in/gretavoss")
        self.assertEqual(score.contact_hint(ad)["profile_url"], "https://www.linkedin.com/in/gretavoss")

    def test_company_ad_has_no_contact(self):
        self.assertIsNone(score.contact_hint(COMPANY_AD))


class ClaimsTest(unittest.TestCase):
    def test_finds_sentences_with_money_percent_and_counts(self):
        text = "I know a broker with $31M+ listed in 12 months. He called 40+ owners. 25% said yes. Clever pitch."
        claims = score.find_claims(text)
        self.assertEqual(
            claims,
            ["I know a broker with $31M+ listed in 12 months.", "He called 40+ owners.", "25% said yes."],
        )

    def test_ignores_plain_years_and_number_free_text(self):
        self.assertEqual(score.find_claims("Join us in 2026. Where data meets agentic AI."), [])

    def test_durations_and_tenure_are_not_claims(self):
        self.assertEqual(score.find_claims("Length: 45 minutes. I've worked in cold email for 6+ years."), [])

    def test_time_saved_is_a_claim(self):
        self.assertEqual(score.find_claims("Save 10 hours a week."), ["Save 10 hours a week."])

    def test_has_claim_for_price_in_headline(self):
        self.assertTrue(score.has_claim("AI-Trained Developers From $999/Month"))
        self.assertFalse(score.has_claim("See agentic defense in action."))


class HookCandidatesTest(unittest.TestCase):
    def test_headline_with_number_comes_first_and_all_are_verbatim(self):
        ad = li_ad(description="Teams cut hiring time by 60%. Book a call.")
        hooks = score.hook_candidates(ad)
        self.assertEqual(hooks[0], {"ad_id": "100", "source": "headline", "has_number": True,
                                    "text": "AI-Trained Developers From $999/Month"})
        full = (ad["headline"] or "") + "\n" + (ad["description"] or "")
        for hook in hooks:
            self.assertIn(hook["text"], full)
        self.assertIn("Teams cut hiring time by 60%.", [h["text"] for h in hooks])

    def test_number_free_headline_is_kept_as_last_resort(self):
        ad = li_ad(headline="See agentic defense in action.", description="Learn more today.")
        hooks = score.hook_candidates(ad)
        self.assertEqual(len(hooks), 1)
        self.assertFalse(hooks[0]["has_number"])


class RankTest(unittest.TestCase):
    def setUp(self):
        self.ranked = score.rank(
            [COMPANY_AD, BOOSTED_INSIDER, BOOSTED_CUSTOMER, SELF_OWNER, SELF_EMPLOYEE],
            today=date(2026, 11, 12),
        )
        self.by_name = {row["advertiser"]: row for row in self.ranked}

    def test_groups_ads_by_company_id(self):
        northbeam = self.by_name["Northbeam Data"]
        self.assertEqual(northbeam["ad_count"], 3)
        self.assertEqual(northbeam["advertiser_id"], "555")

    def test_company_with_several_ads_claim_and_named_owner_scores_top(self):
        northbeam = self.by_name["Northbeam Data"]
        self.assertEqual(
            sorted(northbeam["signals"]), ["company_paid", "multi_ad", "named_owner", "number_or_claim"]
        )
        self.assertEqual(northbeam["score"], 4)
        self.assertEqual(northbeam["tier"], "strong")
        self.assertEqual(self.ranked[0]["advertiser"], "Northbeam Data")

    def test_self_promoted_owner_keeps_business_name_and_contact(self):
        voss = self.by_name["Greta Voss"]
        self.assertEqual(voss["business_names"], ["Voss Strategies"])
        self.assertEqual(voss["contact_hints"][0]["name"], "Greta Voss")
        self.assertIsNone(voss["skip_reason"])

    def test_personal_post_by_non_owner_is_flagged_and_sorted_last(self):
        patel = self.by_name["Ravi Patel"]
        self.assertIn("personal post", patel["skip_reason"])
        self.assertEqual(self.ranked[-1]["advertiser"], "Ravi Patel")

    def test_identical_creatives_do_not_count_as_several_ads(self):
        twin = li_ad(id="901", advertiser="Solo Co", advertiser_id="9", headline="Same line", description="Same body")
        twin2 = dict(twin, id="902")
        row = score.rank([twin, twin2], today=date(2026, 11, 12))[0]
        self.assertEqual(row["ad_count"], 2)
        self.assertEqual(row["distinct_creatives"], 1)
        self.assertNotIn("multi_ad", row["signals"])


class GroupingTest(unittest.TestCase):
    def test_ad_that_lost_its_company_id_joins_the_company_by_name(self):
        orphan = li_ad(id="103", advertiser_id=None, advertiser_url=None, headline="Another line")
        rows = score.rank([COMPANY_AD, BOOSTED_INSIDER, orphan], today=date(2026, 11, 12))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ad_count"], 3)
        self.assertEqual(rows[0]["advertiser_id"], "555")

    def test_same_name_with_two_different_ids_stays_separate(self):
        other = li_ad(id="104", advertiser_id="777")
        orphan = li_ad(id="105", advertiser_id=None, advertiser_url=None)
        rows = score.rank([COMPANY_AD, other, orphan], today=date(2026, 11, 12))
        self.assertEqual(len(rows), 3)


class TagsTest(unittest.TestCase):
    def test_hiring_ad_is_tagged(self):
        ad = li_ad(headline="We're hiring pipefitters", description="Apply now. $150 per diem.", cta="Apply")
        self.assertIn("hiring", score.rank([ad], today=date(2026, 11, 12))[0]["tags"])

    def test_product_ad_is_not_tagged_hiring(self):
        self.assertNotIn("hiring", score.rank([COMPANY_AD], today=date(2026, 11, 12))[0]["tags"])


class MetaSignalsTest(unittest.TestCase):
    def test_meta_ad_live_thirty_days_gets_long_running(self):
        ad = li_ad(library="meta", id="m1", advertiser="Jar Salads Co", advertiser_id="77",
                   start_date="2026-07-07", headline="4.9 of 5", description="60 recipes inside",
                   duplicates=3)
        row = score.rank([ad], today=date(2026, 11, 12))[0]
        self.assertIn("long_running", row["signals"])
        self.assertIn("multi_ad", row["signals"])

    def test_recent_meta_ad_is_not_long_running(self):
        ad = li_ad(library="meta", id="m2", advertiser="New Co", advertiser_id="78", start_date="2026-11-01")
        row = score.rank([ad], today=date(2026, 11, 12))[0]
        self.assertNotIn("long_running", row["signals"])


class MarkdownTest(unittest.TestCase):
    def test_table_lists_ranked_advertisers(self):
        ranked = score.rank([COMPANY_AD, SELF_EMPLOYEE], today=date(2026, 11, 12))
        table = score.to_markdown(ranked)
        self.assertIn("| # | Advertiser |", table)
        self.assertIn("Northbeam Data", table)
        self.assertIn("personal post", table)


if __name__ == "__main__":
    unittest.main()
