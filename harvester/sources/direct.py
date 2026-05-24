from __future__ import annotations

import aiohttp

from harvester.models import ParsedStream, SourceConfig
from harvester.parser import parse_m3u
from harvester.sources.base import BaseSource


class DirectSource(BaseSource):
    async def fetch(self, session: aiohttp.ClientSession) -> list[ParsedStream]:
        content = await self.fetch_url(session, self.config.url)
        if not content:
            return []
        return parse_m3u(content, source_url=self.config.url, source_id=self.config.source_id())
