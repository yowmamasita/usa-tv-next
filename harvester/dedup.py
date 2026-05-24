from __future__ import annotations

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from harvester.models import ParsedStream

STRIP_PARAMS = {"token", "t", "sid", "session", "ts", "_"}


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            port = None
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in sorted(params.items()) if k.lower() not in STRIP_PARAMS}
        query = urlencode(filtered, doseq=True)
        host_part = hostname + (f":{port}" if port else "")
        return urlunparse((parsed.scheme, host_part, path, "", query, ""))
    except Exception:
        return url


def deduplicate(streams: list[ParsedStream]) -> list[ParsedStream]:
    seen: dict[str, ParsedStream] = {}
    sources_map: dict[str, list[str]] = {}

    for s in streams:
        key = normalize_url(s.url)
        if key in seen:
            if s.source_id and s.source_id not in sources_map.get(key, []):
                sources_map.setdefault(key, []).append(s.source_id)
            existing = seen[key]
            if len(s.channel_name) > len(existing.channel_name):
                seen[key] = s
        else:
            seen[key] = s
            sources_map[key] = [s.source_id] if s.source_id else []

    results = []
    for key, stream in seen.items():
        stream.source_id = ",".join(sources_map.get(key, []))
        results.append(stream)
    return results
