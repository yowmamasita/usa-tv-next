from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod

import aiohttp

from harvester.config import USER_AGENTS
from harvester.models import ParsedStream, SourceConfig


class BaseSource(ABC):
    def __init__(self, config: SourceConfig):
        self.config = config

    @abstractmethod
    async def fetch(self, session: aiohttp.ClientSession) -> list[ParsedStream]:
        ...

    async def fetch_url(self, session: aiohttp.ClientSession, url: str, retries: int = 3) -> str:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        for attempt in range(retries):
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="replace")
                    if resp.status == 404:
                        return ""
                    if resp.status == 429 or resp.status >= 500:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return ""
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return ""
