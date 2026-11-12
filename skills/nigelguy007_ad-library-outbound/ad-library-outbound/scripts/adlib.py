#!/usr/bin/env python3
"""Pull ads from the public ad libraries through the Scrape Creators API.

    python3 adlib.py search --keyword "CRM" --countries US --days 30 --pages 2 \
        --out outbound/runs/<run>/ads.jsonl
    python3 adlib.py search --library meta --keyword "meal prep" --countries US \
        --out outbound/runs/<run>/ads.jsonl
    python3 adlib.py company --url https://www.linkedin.com/company/<name>/ --expect-id 12345
    python3 adlib.py presence --name "Acme" --domain acme.com

Each page of results costs one API credit (24 LinkedIn ads or 30 Meta ads).
The key is read from SCRAPECREATORS_API_KEY. In a Claude cloud session with
the service connected, the network proxy adds the key and none is needed here.

What the libraries do and do not give you (checked against live data):
  - LinkedIn returns the full ad text, the advertiser, who paid, and for a
    boosted post its author and job title. For ads aimed at the US it returns
    no dates, no impressions and no landing-page link.
  - LinkedIn company pages can only be looked up by their named URL. The ad
    gives a numeric one. Two companies can share a name, so pass --expect-id
    with the number from the ad and check "id_match" before trusting a page.
  - Meta returns start dates, landing-page links and how many copies of an ad run.
  - Google has no keyword search: it is only used to check a known domain.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from ob_common import normalize_name, out, read_jsonl, write_jsonl

BASE_URL = "https://api.scrapecreators.com"
ENV_KEY = "SCRAPECREATORS_API_KEY"
PROXY_PLACEHOLDER_KEY = "set-by-network-proxy"
MAX_PAGES = 20
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 90
MAX_WINDOW_DAYS = 365
MAX_RESPONSE_BYTES = 20 * 1024 * 1024

Ad = Dict[str, Any]
Fetch = Callable[[str, Dict[str, str]], Dict[str, Any]]
Transport = Callable[[str, Dict[str, str], float], Tuple[int, str]]

_COUNTRIES = re.compile(r"[A-Z]{2}(,[A-Z]{2})*")
_COUNTRY = re.compile(r"[A-Z]{2}")
_COMPANY_URL = re.compile(r"https://(?:[a-z]{2,3}\.)?linkedin\.com/company/([^/?#\s]+)/?")
_COMPANY_ID = re.compile(r"/company/(\d+)(?:[/?#]|$)")


class ApiError(Exception):
    """The API refused or failed a request. Never carries the API key."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__("HTTP %d: %s" % (status, message))
        self.status = status
        self.message = message


# ---------------------------------------------------------------- HTTP

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects. Following one would send the API key to whatever host the redirect names."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _http_transport(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, str]:
    request = urllib.request.Request(url, headers=headers)  # url is always BASE_URL (https) + a fixed path
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ApiError(response.status, "response is larger than %d MB" % (MAX_RESPONSE_BYTES // 2 ** 20))
            return response.status, body.decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read(MAX_RESPONSE_BYTES).decode("utf-8", "replace")
    except OSError as err:  # URLError, socket timeouts, connection resets
        raise ApiError(0, "network error: %s" % getattr(err, "reason", err)) from err


def _error_message(status: int, text: str) -> str:
    try:
        body = json.loads(text)
        message = str(body.get("message") or body.get("error") or text[:200])
    except (ValueError, AttributeError):
        message = text[:200]
    if status in (401, 403):
        message += " (set %s, or connect the service in your Claude environment)" % ENV_KEY
    return message


def api_get(path: str, params: Dict[str, str], key: Optional[str] = None,
            transport: Optional[Transport] = None, sleep: Callable[[float], None] = time.sleep,
            timeout: float = TIMEOUT_SECONDS) -> Dict[str, Any]:
    """GET one API path. Retries rate limits and server errors, then raises ApiError."""
    transport = transport or _http_transport
    url = "%s%s?%s" % (BASE_URL, path, urlencode(params))
    headers = {"x-api-key": key or os.environ.get(ENV_KEY) or PROXY_PLACEHOLDER_KEY,
               "Accept": "application/json", "User-Agent": "ad-library-outbound/1.0"}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        status, text = transport(url, headers, timeout)
        if status == 200:
            try:
                return json.loads(text)
            except ValueError as err:
                raise ApiError(status, "response was not JSON") from err
        if (status == 429 or status >= 500) and attempt < MAX_ATTEMPTS:
            sleep(2 ** attempt)
            continue
        raise ApiError(status, _error_message(status, text))
    raise ApiError(0, "no attempt was made")  # unreachable; keeps the return type total


# ---------------------------------------------------------------- validation

def date_window(days: int, today: Optional[date] = None) -> Tuple[str, str]:
    """(start, end) for the last `days` days. The API will not take today as the end date."""
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise ValueError("--days must be between 1 and %d" % MAX_WINDOW_DAYS)
    end = (today or date.today()) - timedelta(days=1)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _check_dates(start: Optional[str], end: Optional[str]) -> None:
    if bool(start) != bool(end):
        raise ValueError("give both a start and an end date, or neither")
    if start and end and date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("start date is after end date")


def _check_pages(pages: int) -> None:
    if not 1 <= pages <= MAX_PAGES:
        raise ValueError("--pages must be between 1 and %d (each page costs a credit)" % MAX_PAGES)


def linkedin_params(keyword: Optional[str], company: Optional[str], countries: str, start: Optional[str],
                    end: Optional[str], token: Optional[str]) -> Dict[str, str]:
    if not (keyword or company):
        raise ValueError("give a --keyword or a --company")
    if not _COUNTRIES.fullmatch(countries or ""):
        raise ValueError("countries must be 2-letter codes separated by commas, e.g. US,CA")
    _check_dates(start, end)
    params = {"keyword": keyword, "company": company, "countries": countries,
              "startDate": start, "endDate": end, "paginationToken": token}
    return {name: value for name, value in params.items() if value}


def meta_params(keyword: Optional[str], country: str, start: Optional[str], end: Optional[str],
                cursor: Optional[str]) -> Dict[str, str]:
    if not keyword:
        raise ValueError("give a --keyword")
    if not _COUNTRY.fullmatch(country or ""):
        raise ValueError("the Meta library takes one 2-letter country at a time, e.g. US")
    _check_dates(start, end)
    params = {"query": keyword, "country": country, "status": "ACTIVE", "trim": "true",
              "start_date": start, "end_date": end, "cursor": cursor}
    return {name: value for name, value in params.items() if value}


def validate_company_url(url: str) -> str:
    match = _COMPANY_URL.fullmatch(url or "")
    if not match:
        raise ValueError("not a LinkedIn company URL: expected https://www.linkedin.com/company/<name>/")
    if match.group(1).isdigit():
        raise ValueError("numeric company URLs are not supported: find the company's named URL "
                         "(https://www.linkedin.com/company/<name>/) and pass the number as --expect-id")
    return url


# ---------------------------------------------------------------- records

def normalise_linkedin(raw: Dict[str, Any]) -> Ad:
    """Keep the fields the pipeline uses; drop images, video and logos."""
    page = raw.get("advertiserLinkedinPage") or ""
    company_id = _COMPANY_ID.search(page)
    title = (raw.get("posterTitle") or "").strip()
    label = (raw.get("promotedBy") or "").strip()
    if title.lower().startswith("promoted"):  # the "Promoted" label sometimes arrives in the title field
        title, label = "", label or title
    return {
        "library": "linkedin",
        "id": str(raw.get("id")),
        "url": raw.get("url"),
        "advertiser": raw.get("advertiser"),
        "advertiser_id": company_id.group(1) if company_id else None,
        "advertiser_url": page or None,
        "poster": raw.get("poster"),
        "poster_title": title or None,
        "promoted_by": label or None,
        "paid_for_by": raw.get("paidForBy") or None,
        "headline": raw.get("headline") or None,
        "description": raw.get("description") or None,
        "cta": raw.get("cta") or None,
        "destination_url": raw.get("destinationUrl") or None,
        "start_date": raw.get("startDate") or None,
        "end_date": raw.get("endDate") or None,
        "ad_type": raw.get("adType") or None,
        "duplicates": None,
    }


def normalise_meta(raw: Dict[str, Any]) -> Ad:
    snapshot = raw.get("snapshot") or {}
    body = (snapshot.get("body") or {}).get("text") or ""
    description = "\n".join(part for part in (body, snapshot.get("link_description") or "") if part)
    return {
        "library": "meta",
        "id": str(raw.get("ad_archive_id")),
        "url": raw.get("url"),
        "advertiser": raw.get("page_name") or snapshot.get("page_name"),
        "advertiser_id": str(raw.get("page_id")) if raw.get("page_id") else None,
        "advertiser_url": snapshot.get("page_profile_uri") or None,
        "poster": None,
        "poster_title": None,
        "promoted_by": None,
        "paid_for_by": snapshot.get("byline") or None,
        "headline": snapshot.get("title") or None,
        "description": description or None,
        "cta": snapshot.get("cta_text") or None,
        "destination_url": snapshot.get("link_url") or None,
        "start_date": (raw.get("start_date_string") or "")[:10] or None,
        "end_date": (raw.get("end_date_string") or "")[:10] or None,
        "ad_type": snapshot.get("display_format") or None,
        "duplicates": raw.get("collation_count"),
    }


def merge_ads(existing: List[Ad], new: List[Ad]) -> Tuple[List[Ad], int]:
    """Return (existing + unseen new ads, how many were added). Does not change its inputs."""
    seen = {(ad.get("library"), str(ad.get("id"))) for ad in existing}
    fresh: List[Ad] = []
    for ad in new:
        key = (ad.get("library"), str(ad.get("id")))
        if key not in seen:
            seen.add(key)
            fresh.append(ad)
    return existing + fresh, len(fresh)


# ---------------------------------------------------------------- searches

def _new_meta() -> Dict[str, Any]:
    return {"pages_fetched": 0, "credits_charged": 0, "credits_remaining": None, "total_available": None}


def _with_ids(page: Any, id_key: str) -> List[Dict[str, Any]]:
    """The ad records on a page that are objects with an id. Anything else cannot be tracked, so it is dropped."""
    return [raw for raw in (page or []) if isinstance(raw, dict) and raw.get(id_key) not in (None, "")]


def _fetch_page(fetch: Fetch, path: str, params: Dict[str, str], meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One page, or None when a later page fails: the pages already paid for are kept and the error noted."""
    try:
        return fetch(path, params)
    except ApiError as err:
        if not meta["pages_fetched"]:
            raise
        meta["error"] = "stopped after %d page(s): %s" % (meta["pages_fetched"], err)
        return None


def _count_page(meta: Dict[str, Any], data: Dict[str, Any], total_key: str) -> Dict[str, Any]:
    return {
        "pages_fetched": meta["pages_fetched"] + 1,
        "credits_charged": meta["credits_charged"] + int(data.get("credits_charged") or 0),
        "credits_remaining": data.get("credits_remaining", meta["credits_remaining"]),
        "total_available": data.get(total_key, meta["total_available"]),
    }


def search_linkedin(fetch: Fetch, keyword: Optional[str], company: Optional[str], countries: str,
                    start: Optional[str], end: Optional[str], pages: int) -> Tuple[List[Ad], Dict[str, Any]]:
    _check_pages(pages)
    ads: List[Ad] = []
    meta = _new_meta()
    token: Optional[str] = None
    for _ in range(pages):
        params = linkedin_params(keyword, company, countries, start, end, token)
        data = _fetch_page(fetch, "/v1/linkedin/ads/search", params, meta)
        if data is None:
            break
        meta = _count_page(meta, data, "totalAds")
        page = _with_ids(data.get("ads"), "id")
        ads.extend(normalise_linkedin(raw) for raw in page)
        token = data.get("paginationToken")
        if data.get("isLastPage") or not token or not page:
            break
    return ads, meta


def search_meta(fetch: Fetch, keyword: Optional[str], country: str, start: Optional[str], end: Optional[str],
                pages: int) -> Tuple[List[Ad], Dict[str, Any]]:
    _check_pages(pages)
    ads: List[Ad] = []
    meta = _new_meta()
    cursor: Optional[str] = None
    for _ in range(pages):
        params = meta_params(keyword, country, start, end, cursor)
        data = _fetch_page(fetch, "/v1/facebook/adLibrary/search/ads", params, meta)
        if data is None:
            break
        meta = _count_page(meta, data, "searchResultsCount")
        page = _with_ids(data.get("searchResults"), "ad_archive_id")
        ads.extend(normalise_meta(raw) for raw in page)
        cursor = data.get("cursor")
        if not cursor or not page:
            break
    return ads, meta


# ---------------------------------------------------------------- company and presence

def company_summary(raw: Dict[str, Any], expect_id: Optional[str]) -> Dict[str, Any]:
    """The few company facts the qualifier needs, plus whether this is the company that ran the ad."""
    found_id = str(raw.get("id")) if raw.get("id") is not None else None
    return {
        "name": raw.get("name"),
        "id": found_id,
        "handle": raw.get("handle"),
        "url": raw.get("url"),
        "employee_count": raw.get("employeeCount"),
        "industry": raw.get("industry"),
        "headquarters": raw.get("headquarters"),
        "website": raw.get("website"),
        "id_match": None if expect_id is None else found_id == str(expect_id),
    }


def exact_meta_pages(name: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Meta pages whose name is the same company name. Look-alike names are not matches."""
    wanted = normalize_name(name)
    return [page for page in results if wanted and normalize_name(page.get("name")) == wanted]


def google_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    ads = raw.get("ads") or []
    if not ads:
        return {"status": "none", "ads_estimate": 0}
    return {
        "status": "running",
        "ads_estimate": raw.get("number_of_ads_estimate") or len(ads),
        "last_shown": max((ad.get("lastShown") or "")[:10] for ad in ads) or None,
        "advertisers": sorted({ad.get("advertiserName") for ad in ads if ad.get("advertiserName")})[:5],
    }


def presence(fetch: Fetch, name: str, domain: Optional[str]) -> Dict[str, Any]:
    """Does this company also advertise on Meta (by exact page name) and Google (by domain)?"""
    result: Dict[str, Any] = {"name": name, "domain": domain}
    try:
        found = fetch("/v1/facebook/adLibrary/search/companies", {"query": name}).get("searchResults") or []
        pages = exact_meta_pages(name, found)
        result["meta"] = {
            "status": "page_found" if pages else "no_exact_match",
            "pages": [{"page_id": p.get("page_id"), "name": p.get("name"), "category": p.get("category")}
                      for p in pages[:3]],
            "similar_names_ignored": len(found) - len(pages),
            "note": "A page with this exact name exists in the Meta Ad Library. Open it to confirm it is the "
                    "same company before counting it." if pages else "",
        }
    except ApiError as err:
        result["meta"] = {"status": "error", "message": str(err)}
    if domain:
        try:
            result["google"] = google_summary(fetch("/v1/google/company/ads", {"domain": domain}))
        except ApiError as err:
            result["google"] = {"status": "error", "message": str(err)}
    return result


# ---------------------------------------------------------------- command line

def _cmd_search(args: argparse.Namespace, fetch: Fetch) -> int:
    start, end = (args.start, args.end) if args.start or args.end else date_window(args.days)
    if args.library == "meta":
        ads, meta = search_meta(fetch, args.keyword, args.countries, start, end, args.pages)
    else:
        ads, meta = search_linkedin(fetch, args.keyword, args.company, args.countries, start, end, args.pages)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    context = {"keyword": args.keyword or args.company, "countries": args.countries,
               "window": "%s..%s" % (start, end), "fetched_at": stamp}
    merged, added = merge_ads(read_jsonl(args.out), [dict(ad, **context) for ad in ads])
    write_jsonl(args.out, merged)
    out(json.dumps(dict(meta, library=args.library, window=context["window"], ads_fetched=len(ads),
                        new_ads_saved=added, ads_in_file=len(merged), out=args.out)))
    if meta.get("error"):
        sys.stderr.write("error: %s. The ads from the earlier pages were saved.\n" % meta["error"])
        return 1
    return 0


def _cmd_company(args: argparse.Namespace, fetch: Fetch) -> int:
    raw = fetch("/v1/linkedin/company", {"url": validate_company_url(args.url)})
    out(json.dumps(company_summary(raw, args.expect_id), indent=2))
    return 0


def _cmd_presence(args: argparse.Namespace, fetch: Fetch) -> int:
    out(json.dumps(presence(fetch, args.name, args.domain), indent=2))
    return 0


def main(argv: Optional[List[str]] = None, fetch: Optional[Fetch] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="pull ads by keyword and save them")
    search.add_argument("--library", choices=("linkedin", "meta"), default="linkedin")
    search.add_argument("--keyword", help="what you sell, or the industry you sell to")
    search.add_argument("--company", help="LinkedIn only: every ad from one company")
    search.add_argument("--countries", default="US", help="2-letter codes, comma separated (Meta: one only)")
    search.add_argument("--days", type=int, default=30, help="look back this many days (default 30)")
    search.add_argument("--start", help="YYYY-MM-DD, instead of --days")
    search.add_argument("--end", help="YYYY-MM-DD, instead of --days")
    search.add_argument("--pages", type=int, default=2, help="pages to pull, one credit each (default 2)")
    search.add_argument("--out", required=True, help="ads.jsonl to add the results to")
    search.set_defaults(run_command=_cmd_search)

    company = commands.add_parser("company", help="look up a LinkedIn company page by its named URL")
    company.add_argument("--url", required=True)
    company.add_argument("--expect-id", help="numeric company id from the ad, to confirm it is the same company")
    company.set_defaults(run_command=_cmd_company)

    check = commands.add_parser("presence", help="check Meta and Google for the same advertiser")
    check.add_argument("--name", required=True)
    check.add_argument("--domain", help="the company's website domain, for the Google check")
    check.set_defaults(run_command=_cmd_presence)

    args = parser.parse_args(argv)
    try:
        return args.run_command(args, fetch or api_get)
    except (ApiError, OSError, ValueError) as err:
        sys.stderr.write("error: %s\n" % err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
