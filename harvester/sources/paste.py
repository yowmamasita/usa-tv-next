from __future__ import annotations

import aiohttp

from harvester.models import ParsedStream
from harvester.parser import extract_m3u_urls, parse_m3u
from harvester.sources.base import BaseSource


class PasteSource(BaseSource):
    async def fetch(self, session: aiohttp.ClientSession) -> list[ParsedStream]:
        html = await self.fetch_url(session, self.config.url)
        if not html:
            return []

        source_id = self.config.source_id()
        streams: list[ParsedStream] = []

        # Check for inline M3U content
        if "#EXTINF" in html or "#EXTM3U" in html:
            streams.extend(parse_m3u(html, source_url=self.config.url, source_id=source_id))

        # Extract and follow M3U URLs
        m3u_urls = extract_m3u_urls(html)
        for m3u_url in m3u_urls:
            content = await self.fetch_url(session, m3u_url)
            if content and ("#EXTINF" in content or "#EXTM3U" in content):
                streams.extend(parse_m3u(content, source_url=m3u_url, source_id=source_id))

        return streams
