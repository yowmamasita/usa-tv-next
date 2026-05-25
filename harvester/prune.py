"""Test all streams in the addon catalog and remove dead ones.

A stream is only considered dead after failing 3 consecutive tests
with a short pause between retries (all within ~1 minute).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console

from harvester.config import DEFAULT_TEST_CONCURRENCY, DEFAULT_TIMEOUT
from harvester.models import ParsedStream, StreamStatus
from harvester.tester import test_streams

CATALOG_PATH = Path(__file__).resolve().parent.parent / "catalog" / "tv" / "all.json"
META_DIR = Path(__file__).resolve().parent.parent / "meta" / "tv"
GENRE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "tv" / "all"
STREAM_DIR = Path(__file__).resolve().parent.parent / "stream" / "tv"

MAX_RETRIES = 3
RETRY_DELAY = 20

console = Console()


def _collect_catalog_streams(catalog: dict) -> list[ParsedStream]:
    seen: set[str] = set()
    streams: list[ParsedStream] = []
    for ch in catalog.get("metas", []):
        ch_name = ch.get("name", "")
        for s in ch.get("streams", []):
            url = s.get("url", "")
            if url and url not in seen:
                seen.add(url)
                streams.append(ParsedStream(url=url, channel_name=ch_name))
    return streams


def _remove_dead_from_list(streams: list[dict], dead_urls: set[str]) -> list[dict]:
    return [s for s in streams if s.get("url", "") not in dead_urls]


async def _prune(timeout: float, concurrency: int, dry_run: bool) -> dict:
    catalog = json.loads(CATALOG_PATH.read_text())
    all_streams = _collect_catalog_streams(catalog)

    if not all_streams:
        console.print("[red]No streams found in catalog[/]")
        return {"tested": 0, "dead": 0, "removed": 0}

    console.print(f"[bold]Found {len(all_streams)} unique stream URLs in catalog[/]")

    stream_by_url = {s.url: s for s in all_streams}
    results = await test_streams(all_streams, timeout=timeout, concurrency=concurrency)

    working_urls = {r.url for r in results if r.status == StreamStatus.WORKING}
    failed_urls = {r.url for r in results if r.status != StreamStatus.WORKING}

    console.print(f"\n[bold]Pass 1:[/] [green]{len(working_urls)} working[/], [red]{len(failed_urls)} failed[/]")

    for attempt in range(2, MAX_RETRIES + 1):
        if not failed_urls:
            break
        retry_streams = [stream_by_url[url] for url in failed_urls]
        console.print(f"\n[bold]Waiting {RETRY_DELAY}s before retry {attempt}/{MAX_RETRIES}...[/]")
        await asyncio.sleep(RETRY_DELAY)

        console.print(f"[bold]Pass {attempt}:[/] retesting {len(retry_streams)} failed streams")
        retry_results = await test_streams(retry_streams, timeout=timeout, concurrency=concurrency)

        recovered = {r.url for r in retry_results if r.status == StreamStatus.WORKING}
        working_urls |= recovered
        failed_urls -= recovered
        console.print(f"[bold]Pass {attempt}:[/] [green]{len(recovered)} recovered[/], [red]{len(failed_urls)} still failing[/]")

    dead_urls = failed_urls
    console.print(f"\n[bold]Final:[/] [green]{len(working_urls)} working[/], [red]{len(dead_urls)} dead (failed {MAX_RETRIES}x)[/]")

    if dry_run:
        console.print("[yellow]Dry run — no files modified[/]")
        return {"tested": len(results), "dead": len(dead_urls), "removed": 0}

    removed = 0
    for ch in catalog["metas"]:
        before = len(ch.get("streams", []))
        ch["streams"] = _remove_dead_from_list(ch.get("streams", []), dead_urls)
        removed += before - len(ch["streams"])

    CATALOG_PATH.write_text(json.dumps(catalog, separators=(",", ":")))

    genre_channels: dict[str, list] = {}
    for ch in catalog["metas"]:
        genre = ch.get("genre", "")
        if genre:
            genre_channels.setdefault(genre, []).append(ch)

    GENRE_DIR.mkdir(parents=True, exist_ok=True)
    for genre, chs in genre_channels.items():
        genre_file = GENRE_DIR / f"genre={genre}.json"
        genre_file.write_text(json.dumps({"metas": chs}, separators=(",", ":")))

    for ch in catalog["metas"]:
        meta_file = META_DIR / f"{ch['id']}.json"
        if meta_file.exists():
            meta_file.write_text(json.dumps({"meta": ch}, separators=(",", ":")))

        stream_file = STREAM_DIR / f"{ch['id']}.json"
        if stream_file.exists():
            stream_file.write_text(json.dumps({"streams": ch["streams"]}, separators=(",", ":")))

    console.print(f"[bold green]Removed {removed} dead streams from catalog[/]")
    return {"tested": len(results), "dead": len(dead_urls), "removed": removed}


def prune(timeout: float = DEFAULT_TIMEOUT, concurrency: int = DEFAULT_TEST_CONCURRENCY, dry_run: bool = False) -> dict:
    return asyncio.run(_prune(timeout, concurrency, dry_run))
