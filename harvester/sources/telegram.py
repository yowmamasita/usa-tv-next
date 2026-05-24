from __future__ import annotations

import re

import aiohttp

from harvester.models import ParsedStream
from harvester.parser import extract_m3u_urls, extract_xtream_urls, parse_m3u
from harvester.sources.base import BaseSource

STREAM_URL_RE = re.compile(
    r'https?://[^\s<>"\']+(?:\.m3u8?|\.ts|/live/|/play/|:\d{4,5}/)[^\s<>"\']*',
    re.IGNORECASE,
)

# External IPTV sites that Telegram channels commonly link to
IPTV_SITE_RE = re.compile(
    r'https?://(?:www\.)?'
    r'(?:tvappapk\.com|world-iptv\.club|stbemuiptv\.com|myprostb\.blogspot\.com|sallam22\.blogspot\.com|titv\.site)'
    r'/[^\s<>"\']+',
    re.IGNORECASE,
)


class TelegramSource(BaseSource):
    async def fetch(self, session: aiohttp.ClientSession) -> list[ParsedStream]:
        channel = self.config.channel
        source_id = self.config.source_id()
        url = f"https://t.me/s/{channel}"
        html = await self.fetch_url(session, url)
        if not html:
            return []

        streams: list[ParsedStream] = []

        # 1. Direct M3U URLs in messages
        m3u_urls = extract_m3u_urls(html)
        for m3u_url in m3u_urls:
            content = await self.fetch_url(session, m3u_url)
            if content:
                streams.extend(parse_m3u(content, source_url=m3u_url, source_id=source_id))

        # 2. Direct stream URLs in messages
        for m in STREAM_URL_RE.finditer(html):
            url_found = m.group(0).rstrip(")")
            if not any(s.url == url_found for s in streams):
                streams.append(ParsedStream(url=url_found, source_id=source_id))

        # 3. Xtream Codes URLs directly in messages (limit to 3 servers)
        xtream_urls = extract_xtream_urls(html)
        for xtream_m3u in xtream_urls[:3]:
            content = await self.fetch_url(session, xtream_m3u)
            if content and "#EXTINF" in content:
                parsed = parse_m3u(content, source_url=xtream_m3u, source_id=source_id)
                streams.extend(parsed[:5000])

        # 4. Follow links to known IPTV sites (limit to 3 sites, 2 Xtream servers each)
        external_urls: set[str] = set()
        for m in IPTV_SITE_RE.finditer(html):
            external_urls.add(m.group(0))
        for ext_url in list(external_urls)[:3]:
            ext_html = await self.fetch_url(session, ext_url)
            if not ext_html:
                continue
            ext_xtream_urls = extract_xtream_urls(ext_html)
            for xtream_m3u in ext_xtream_urls[:2]:
                content = await self.fetch_url(session, xtream_m3u)
                if content and "#EXTINF" in content:
                    parsed = parse_m3u(content, source_url=xtream_m3u, source_id=source_id)
                    streams.extend(parsed[:5000])
            ext_m3u_urls = extract_m3u_urls(ext_html)
            for m3u_url in ext_m3u_urls[:5]:
                content = await self.fetch_url(session, m3u_url)
                if content:
                    streams.extend(parse_m3u(content, source_url=m3u_url, source_id=source_id))

        return streams
