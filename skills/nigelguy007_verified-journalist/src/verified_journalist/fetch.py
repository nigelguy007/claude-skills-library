"""Safe article fetching and text extraction.

URLs come from search results and, indirectly, from model output, so they are untrusted.
Every hop (including redirects) is resolved and refused if it points at a private, loopback,
link-local or otherwise non-public address, which blocks SSRF into internal services and
cloud metadata endpoints.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

from .cache import DiskCache

log = logging.getLogger(__name__)

MAX_BYTES = 4_000_000
MAX_REDIRECTS = 5
MIN_TEXT_CHARS = 600
FETCH_TTL = 7 * 24 * 3600
USER_AGENT = os.environ.get(
    "VJ_USER_AGENT", "VerifiedJournalist/0.1 (+https://github.com/nigelguy007/verified-journalist)"
)
PAYWALL_MARKERS = (
    "subscribe to continue",
    "subscribe to read",
    "to continue reading",
    "already a subscriber",
    "sign in to read",
    "create a free account to continue",
)


class UnsafeURLError(ValueError):
    pass


@dataclass
class FetchedPage:
    url: str
    text: str
    title: str | None = None
    published: str | None = None
    author: str | None = None


def assert_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError(f"scheme {parts.scheme!r} not allowed")
    if parts.username or parts.password:
        raise UnsafeURLError("credentials in URL not allowed")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("URL has no host")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve {host}") from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0].split("%")[0])
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        if not addr.is_global or addr.is_multicast:
            raise UnsafeURLError(f"{host} resolves to non-public address {addr}")


def _looks_paywalled(text: str) -> bool:
    lowered = text[-2000:].lower()
    return len(text) < 3000 and any(marker in lowered for marker in PAYWALL_MARKERS)


class Fetcher:
    def __init__(self, cache: DiskCache | None = None, timeout: float = 20.0) -> None:
        self.cache = cache
        self.timeout = httpx.Timeout(timeout, connect=10.0)

    def _download(self, url: str) -> tuple[str, str]:
        current = url
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                assert_public_url(current)
                with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise httpx.HTTPError("redirect without location")
                        current = urljoin(current, location)
                        continue
                    resp.raise_for_status()
                    ctype = resp.headers.get("content-type", "").lower()
                    if "html" not in ctype and "text/plain" not in ctype:
                        raise httpx.HTTPError(f"unsupported content-type {ctype or 'unknown'}")
                    chunks, size = [], 0
                    for chunk in resp.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise httpx.HTTPError("response too large")
                        chunks.append(chunk)
                    encoding = resp.encoding or "utf-8"
                    return current, b"".join(chunks).decode(encoding, errors="replace")
        raise httpx.HTTPError("too many redirects")

    def fetch(self, url: str) -> FetchedPage | None:
        """Return extracted article text, or None if the page is unusable. Never raises for
        network or content problems; they're logged and the source is skipped."""
        if self.cache:
            hit = self.cache.get("fetch", url, FETCH_TTL)
            if hit is not None:
                return FetchedPage(**hit) if hit else None
        page = self._fetch_uncached(url)
        if self.cache:
            self.cache.set("fetch", url, page.__dict__ if page else {})
        return page

    def _fetch_uncached(self, url: str) -> FetchedPage | None:
        try:
            final_url, html = self._download(url)
        except (httpx.HTTPError, UnsafeURLError, UnicodeError, LookupError) as exc:
            log.info("skip %s: %s", url, exc)
            return None
        text = trafilatura.extract(
            html, url=final_url, include_comments=False, include_tables=True, favor_precision=True
        )
        if not text or len(text) < MIN_TEXT_CHARS or _looks_paywalled(text):
            log.info("skip %s: no usable article text", url)
            return None
        meta = trafilatura.extract_metadata(html, default_url=final_url)
        return FetchedPage(
            url=final_url,
            text=text,
            title=getattr(meta, "title", None),
            published=getattr(meta, "date", None),
            author=getattr(meta, "author", None),
        )
