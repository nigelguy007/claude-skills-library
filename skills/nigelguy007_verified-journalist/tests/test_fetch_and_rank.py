import pytest

from verified_journalist.credibility import canonical_url, rank_sources, tier_for
from verified_journalist.fetch import UnsafeURLError, assert_public_url
from verified_journalist.models import SearchResult


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://localhost:8080/",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http://user:pw@8.8.8.8/",
        "http://0.0.0.0/",
    ],
)
def test_ssrf_guard_blocks_internal_targets(url):
    with pytest.raises(UnsafeURLError):
        assert_public_url(url)


def test_ssrf_guard_allows_public_ip():
    assert_public_url("https://8.8.8.8/")


def test_canonical_url_strips_tracking_and_www():
    a = canonical_url("http://www.Example.com/story/?utm_source=x&id=3&fbclid=abc#top")
    b = canonical_url("https://example.com/story?id=3")
    assert a == b


def test_tiers():
    assert tier_for("www.reuters.com".removeprefix("www.")) == "wire"
    assert tier_for("data.census.gov") == "primary"
    assert tier_for("someone.medium.com") == "low"
    assert tier_for("randomblog.net") == "general"


def test_rank_dedupes_caps_domains_and_drops_low_tier():
    results = [SearchResult(url=f"https://reuters.com/a{i}") for i in range(5)]
    results += [SearchResult(url="https://reuters.com/a0?utm_medium=x")]
    results += [SearchResult(url="https://reddit.com/r/x"), SearchResult(url="https://blog.net/p")]
    picked = rank_sources(results, 10, max_per_domain=2, min_tier_score=0.3)
    urls = [r.url for r, _, _ in picked]
    assert urls[0] == "https://reuters.com/a0"  # seen twice -> ranked first
    assert sum("reuters.com" in u for u in urls) == 2
    assert not any("reddit" in u for u in urls)
    assert "https://blog.net/p" in urls
