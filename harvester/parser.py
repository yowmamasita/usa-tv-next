from __future__ import annotations

import re
from urllib.parse import urljoin

from harvester.models import ParsedStream

EXTINF_ATTRS = re.compile(r'([a-zA-Z_-]+)="([^"]*)"')
STREAM_URL_RE = re.compile(r"^https?://|^rtsp://|^rtmp://", re.IGNORECASE)
XTREAM_URL_RE = re.compile(
    r"https?://[^/]+(?::\d+)?/[^/]+/[^/]+/\d+|"
    r"https?://[^/]+(?::\d+)?/(?:get|player_api)\.php\?username=",
    re.IGNORECASE,
)


def parse_m3u(content: str, source_url: str = "", source_id: str = "") -> list[ParsedStream]:
    lines = content.strip().splitlines()
    streams: list[ParsedStream] = []
    current_attrs: dict[str, str] = {}
    current_name = ""

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF"):
            current_attrs = {}
            for m in EXTINF_ATTRS.finditer(line):
                current_attrs[m.group(1).lower()] = m.group(2)
            comma_idx = line.rfind(",")
            current_name = line[comma_idx + 1 :].strip() if comma_idx != -1 else ""
            continue

        if line.startswith("#"):
            continue

        if STREAM_URL_RE.match(line):
            url = line
        elif source_url and not line.startswith("#"):
            url = urljoin(source_url, line)
        else:
            continue

        if XTREAM_URL_RE.match(url):
            current_attrs = {}
            current_name = ""
            continue

        streams.append(
            ParsedStream(
                url=url,
                channel_name=current_name,
                group=current_attrs.get("group-title", ""),
                tvg_id=current_attrs.get("tvg-id", ""),
                tvg_logo=current_attrs.get("tvg-logo", ""),
                source_id=source_id,
            )
        )
        current_attrs = {}
        current_name = ""

    return streams


def extract_m3u_urls(text: str) -> list[str]:
    return re.findall(r'https?://[^\s<>"\']+\.m3u8?(?:\?[^\s<>"\']*)?', text)


