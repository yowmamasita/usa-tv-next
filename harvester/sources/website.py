from __future__ import annotations

import re
from urllib.parse import urljoin

import aiohttp

from harvester.models import ParsedStream, SourceConfig
from harvester.parser import extract_m3u_urls, parse_m3u
from harvester.sources.base import BaseSource

HREF_RE = re.compile(r'href=["\']([^"\']*\.m3u8?(?:\?[^"\']*)?)["\']', re.IGNORECASE)
STREAM_RE = re.compile(r'https?://[^\s<>"\']+(?:\.ts|/live/|/stream|:\d{4,5}/)', re.IGNORECASE)
ARTICLE_LINK_RE = re.compile(
    r'href=["\']'
    r'(https?://[^"\']+)'
    r'["\']',
    re.IGNORECASE,
)


class WebsiteSource(BaseSource):
    async def fetch(self, session: aiohttp.ClientSession) -> list[ParsedStream]:
        html = await self.fetch_url(session, self.config.url)
        if not html:
            return []

        source_id = self.config.source_id()
        strategy = self.config.strategy
        streams: list[ParsedStream] = []

        if strategy == "direct_m3u":
            return parse_m3u(html, source_url=self.config.url, source_id=source_id)

        streams.extend(self._scrape_page(html, source_id))

        m3u_urls = self._collect_m3u_urls(html)

        for m3u_url in m3u_urls:
            if m3u_url.startswith("http"):
                content = await self.fetch_url(session, m3u_url)
                if content:
                    streams.extend(parse_m3u(content, source_url=m3u_url, source_id=source_id))

        # Deep scrape: follow article links on blog index pages and scrape subpages
        if strategy == "deep_scrape":
            subpage_urls = self._extract_subpage_urls(html, self.config.url)
            for sub_url in subpage_urls[:10]:
                sub_html = await self.fetch_url(session, sub_url)
                if not sub_html:
                    continue
                streams.extend(self._scrape_page(sub_html, source_id))
                sub_m3u_urls = self._collect_m3u_urls(sub_html)
                for m3u_url in sub_m3u_urls:
                    if m3u_url.startswith("http"):
                        content = await self.fetch_url(session, m3u_url)
                        if content:
                            streams.extend(parse_m3u(content, source_url=m3u_url, source_id=source_id))

        return streams

    @staticmethod
    def _collect_m3u_urls(html: str) -> set[str]:
        m3u_urls: set[str] = set()
        for m in HREF_RE.finditer(html):
            m3u_urls.add(m.group(1))
        m3u_urls.update(extract_m3u_urls(html))
        return m3u_urls

    @staticmethod
    def _scrape_page(html: str, source_id: str) -> list[ParsedStream]:
        streams: list[ParsedStream] = []
        for m in STREAM_RE.finditer(html):
            url = m.group(0).rstrip(")")
            if not url.endswith((".m3u", ".m3u8")):
                streams.append(ParsedStream(url=url, source_id=source_id))
        return streams

    @staticmethod
    def _extract_subpage_urls(html: str, base_url: str) -> list[str]:
        """Extract article/post links from a blog index page for deep scraping."""
        from urllib.parse import urlparse
        base_host = urlparse(base_url).netloc
        urls: list[str] = []
        seen: set[str] = set()
        for m in ARTICLE_LINK_RE.finditer(html):
            href = m.group(1)
            parsed = urlparse(href)
            # Only follow links on the same host
            if parsed.netloc != base_host:
                continue
            # Skip pagination, categories, tags, feeds, static assets
            path_lower = href.lower()
            if any(skip in path_lower for skip in [
                "/page/", "/category/", "/tag/", "/feed/", "/author/",
                ".css", ".js", ".png", ".jpg", ".gif", ".svg", ".ico",
                "/wp-", "/xmlrpc", "/comment", "#",
            ]):
                continue
            if href not in seen and href != base_url and href != base_url.rstrip("/"):
                seen.add(href)
                urls.append(href)
        return urls
