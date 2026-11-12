import unittest
from datetime import date

import _path  # noqa: F401
import adlib

RAW_LI = {
    "id": "100",
    "description": "Hire vetted engineers.",
    "headline": "AI-Trained Developers From $999/Month",
    "poster": "Northbeam Data",
    "posterTitle": None,
    "promotedBy": "",
    "paidForBy": "Northbeam Data, Inc.",
    "url": "https://www.linkedin.com/ad-library/detail/100",
    "adType": "Single Image Ad",
    "advertiser": "Northbeam Data",
    "advertiserLinkedinPage": "https://www.linkedin.com/company/555",
    "advertiserLogo": "https://media.example/logo.png",
    "cta": "Learn more",
    "destinationUrl": None,
    "startDate": None,
    "endDate": None,
    "imageSources": ["https://media.example/a.png"],
}

RAW_META = {
    "ad_archive_id": "4449",
    "page_id": "77",
    "page_name": "Jar Salads Co",
    "collation_count": 3,
    "url": "https://www.facebook.com/ads/library?id=4449",
    "start_date_string": "2026-07-07T07:00:00.000Z",
    "end_date_string": "2026-11-11T08:00:00.000Z",
    "snapshot": {
        "body": {"text": "My daughter asks for salad now."},
        "title": "4.9 of 5",
        "link_description": "60 recipes inside",
        "link_url": "https://jarsalads.example/products/jar",
        "cta_text": "Learn more",
        "page_profile_uri": "https://www.facebook.com/jarsalads/",
    },
}


class DateWindowTest(unittest.TestCase):
    def test_last_30_days_ends_yesterday(self):
        self.assertEqual(adlib.date_window(30, today=date(2026, 11, 12)), ("2026-10-13", "2026-11-11"))

    def test_rejects_windows_outside_one_to_365_days(self):
        with self.assertRaises(ValueError):
            adlib.date_window(0, today=date(2026, 11, 12))
        with self.assertRaises(ValueError):
            adlib.date_window(400, today=date(2026, 11, 12))


class SearchParamsTest(unittest.TestCase):
    def test_linkedin_params(self):
        params = adlib.linkedin_params(keyword="CRM", company=None, countries="US,CA",
                                       start="2026-10-13", end="2026-11-11", token=None)
        self.assertEqual(params, {"keyword": "CRM", "countries": "US,CA",
                                  "startDate": "2026-10-13", "endDate": "2026-11-11"})

    def test_needs_keyword_or_company(self):
        with self.assertRaises(ValueError):
            adlib.linkedin_params(keyword=None, company=None, countries="US", start=None, end=None, token=None)

    def test_rejects_bad_country_codes(self):
        with self.assertRaises(ValueError):
            adlib.linkedin_params(keyword="CRM", company=None, countries="usa", start=None, end=None, token=None)

    def test_rejects_start_without_end(self):
        with self.assertRaises(ValueError):
            adlib.linkedin_params(keyword="CRM", company=None, countries="US", start="2026-10-13", end=None,
                                  token=None)

    def test_meta_takes_a_single_country(self):
        params = adlib.meta_params(keyword="meal prep", country="US", start=None, end=None, cursor=None)
        self.assertEqual(params["query"], "meal prep")
        self.assertEqual(params["country"], "US")
        self.assertEqual(params["status"], "ACTIVE")
        with self.assertRaises(ValueError):
            adlib.meta_params(keyword="meal prep", country="US,CA", start=None, end=None, cursor=None)


class NormaliseTest(unittest.TestCase):
    def test_linkedin_record_keeps_text_and_drops_media(self):
        ad = adlib.normalise_linkedin(RAW_LI)
        self.assertEqual(ad["library"], "linkedin")
        self.assertEqual(ad["id"], "100")
        self.assertEqual(ad["advertiser"], "Northbeam Data")
        self.assertEqual(ad["advertiser_id"], "555")
        self.assertEqual(ad["headline"], "AI-Trained Developers From $999/Month")
        self.assertEqual(ad["paid_for_by"], "Northbeam Data, Inc.")
        self.assertIsNone(ad["promoted_by"])
        self.assertNotIn("imageSources", ad)
        self.assertNotIn("advertiserLogo", ad)

    def test_meta_record_maps_snapshot_fields(self):
        ad = adlib.normalise_meta(RAW_META)
        self.assertEqual(ad["library"], "meta")
        self.assertEqual(ad["id"], "4449")
        self.assertEqual(ad["advertiser"], "Jar Salads Co")
        self.assertEqual(ad["advertiser_id"], "77")
        self.assertEqual(ad["headline"], "4.9 of 5")
        self.assertEqual(ad["description"], "My daughter asks for salad now.\n60 recipes inside")
        self.assertEqual(ad["destination_url"], "https://jarsalads.example/products/jar")
        self.assertEqual(ad["start_date"], "2026-07-07")
        self.assertEqual(ad["duplicates"], 3)


class SearchTest(unittest.TestCase):
    def test_follows_pagination_until_page_limit_and_counts_credits(self):
        calls = []

        def fetch(path, params):
            calls.append((path, dict(params)))
            page = len(calls)
            return {"ads": [dict(RAW_LI, id=str(page * 10 + i)) for i in range(2)],
                    "paginationToken": "tok%d" % page, "isLastPage": False,
                    "totalAds": 500, "credits_charged": 1, "credits_remaining": 900 - page}

        ads, meta = adlib.search_linkedin(fetch, keyword="CRM", company=None, countries="US",
                                          start="2026-10-13", end="2026-11-11", pages=3)
        self.assertEqual(len(ads), 6)
        self.assertEqual(len(calls), 3)
        self.assertNotIn("paginationToken", calls[0][1])
        self.assertEqual(calls[1][1]["paginationToken"], "tok1")
        self.assertEqual(meta["pages_fetched"], 3)
        self.assertEqual(meta["credits_charged"], 3)
        self.assertEqual(meta["credits_remaining"], 897)
        self.assertEqual(meta["total_available"], 500)

    def test_stops_on_last_page(self):
        def fetch(path, params):
            return {"ads": [RAW_LI], "paginationToken": None, "isLastPage": True, "totalAds": 1,
                    "credits_charged": 1, "credits_remaining": 10}

        ads, meta = adlib.search_linkedin(fetch, keyword="CRM", company=None, countries="US",
                                          start=None, end=None, pages=5)
        self.assertEqual(len(ads), 1)
        self.assertEqual(meta["pages_fetched"], 1)

    def test_rejects_page_counts_outside_the_cap(self):
        with self.assertRaises(ValueError):
            adlib.search_linkedin(lambda p, q: {}, keyword="CRM", company=None, countries="US",
                                  start=None, end=None, pages=adlib.MAX_PAGES + 1)

    def test_meta_search_uses_cursor(self):
        calls = []

        def fetch(path, params):
            calls.append(dict(params))
            return {"searchResults": [dict(RAW_META, ad_archive_id=str(len(calls)))],
                    "cursor": "c%d" % len(calls) if len(calls) < 2 else None,
                    "searchResultsCount": 40, "credits_charged": 1, "credits_remaining": 5}

        ads, meta = adlib.search_meta(fetch, keyword="meal prep", country="US", start=None, end=None, pages=4)
        self.assertEqual([a["id"] for a in ads], ["1", "2"])
        self.assertEqual(calls[1]["cursor"], "c1")
        self.assertEqual(meta["pages_fetched"], 2)


class MergeTest(unittest.TestCase):
    def test_dedupes_by_library_and_id(self):
        old = [{"library": "linkedin", "id": "1"}]
        new = [{"library": "linkedin", "id": "1"}, {"library": "meta", "id": "1"}, {"library": "linkedin", "id": "2"}]
        merged, added = adlib.merge_ads(old, new)
        self.assertEqual(added, 2)
        self.assertEqual(len(merged), 3)
        self.assertEqual(old, [{"library": "linkedin", "id": "1"}])


class CompanyTest(unittest.TestCase):
    def test_numeric_company_urls_are_rejected_with_a_hint(self):
        with self.assertRaises(ValueError) as ctx:
            adlib.validate_company_url("https://www.linkedin.com/company/99155491")
        self.assertIn("named", str(ctx.exception))

    def test_non_linkedin_urls_are_rejected(self):
        with self.assertRaises(ValueError):
            adlib.validate_company_url("https://example.com/company/acme")

    def test_named_url_is_accepted(self):
        self.assertEqual(adlib.validate_company_url("https://www.linkedin.com/company/northbeam-data/"),
                         "https://www.linkedin.com/company/northbeam-data/")

    def test_summary_flags_a_different_company_with_the_same_name(self):
        raw = {"id": 24354757, "name": "NORTHBEAM", "handle": "northbeam", "employeeCount": 3,
               "industry": "Retail", "headquarters": "Tournai", "website": None}
        summary = adlib.company_summary(raw, expect_id="555")
        self.assertFalse(summary["id_match"])
        self.assertEqual(summary["employee_count"], 3)
        self.assertTrue(adlib.company_summary(raw, expect_id="24354757")["id_match"])
        self.assertIsNone(adlib.company_summary(raw, expect_id=None)["id_match"])


class PresenceTest(unittest.TestCase):
    def test_meta_matches_only_exact_normalised_names(self):
        results = [{"page_id": "1", "name": "Opal Wilkins"}, {"page_id": "2", "name": "Opaline Bijoux"},
                   {"page_id": "3", "name": "OPAL, Inc."}]
        self.assertEqual([m["page_id"] for m in adlib.exact_meta_pages("Opal", results)], ["3"])

    def test_google_summary_counts_ads_for_the_domain(self):
        raw = {"ads": [{"advertiserName": "Acme", "lastShown": "2026-11-12T07:17:17.000Z"}],
               "number_of_ads_estimate": 40}
        summary = adlib.google_summary(raw)
        self.assertEqual(summary["status"], "running")
        self.assertEqual(summary["ads_estimate"], 40)
        self.assertEqual(adlib.google_summary({"ads": []})["status"], "none")


class ApiGetTest(unittest.TestCase):
    def test_retries_on_rate_limit_then_returns_json(self):
        attempts = []

        def transport(url, headers, timeout):
            attempts.append(url)
            if len(attempts) == 1:
                return 429, '{"message": "slow down"}'
            return 200, '{"success": true, "ads": []}'

        data = adlib.api_get("/v1/linkedin/ads/search", {"keyword": "CRM"}, key="k",
                             transport=transport, sleep=lambda s: None)
        self.assertEqual(data["ads"], [])
        self.assertEqual(len(attempts), 2)
        self.assertIn("keyword=CRM", attempts[0])

    def test_client_error_raises_with_status_and_message_but_never_the_key(self):
        def transport(url, headers, timeout):
            return 401, '{"message": "Invalid API key"}'

        with self.assertRaises(adlib.ApiError) as ctx:
            adlib.api_get("/v1/linkedin/ads/search", {"keyword": "CRM"}, key="SECRET-KEY-123",
                          transport=transport, sleep=lambda s: None)
        self.assertEqual(ctx.exception.status, 401)
        self.assertIn("Invalid API key", str(ctx.exception))
        self.assertNotIn("SECRET-KEY-123", str(ctx.exception))

    def test_gives_up_after_three_server_errors(self):
        attempts = []

        def transport(url, headers, timeout):
            attempts.append(1)
            return 500, '{"message": "Internal Server Error"}'

        with self.assertRaises(adlib.ApiError):
            adlib.api_get("/v1/google/company/ads", {"domain": "x.com"}, key="k",
                          transport=transport, sleep=lambda s: None)
        self.assertEqual(len(attempts), 3)

    def test_sends_key_in_header_not_in_url(self):
        seen = {}

        def transport(url, headers, timeout):
            seen["url"], seen["headers"] = url, headers
            return 200, "{}"

        adlib.api_get("/v1/linkedin/ads/search", {"keyword": "CRM"}, key="SECRET-KEY-123",
                      transport=transport, sleep=lambda s: None)
        self.assertEqual(seen["headers"]["x-api-key"], "SECRET-KEY-123")
        self.assertNotIn("SECRET-KEY-123", seen["url"])


if __name__ == "__main__":
    unittest.main()
