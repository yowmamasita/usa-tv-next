"""Test all streams in the addon catalog and remove dead ones.

A stream is only considered dead after failing every 30s for 10 minutes.
All failed URLs are retried in parallel — each gets its own retry loop.

A removed stream is kept in data/pruned.json and tested again on every later run, and put back in
its channels' stream files once it works: inject only adds streams the harvest sources carry, so a
stream no source lists (Toonami Aftermath's own) was lost for good after one outage.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from harvester.inject import merged_streams
from harvester.config import DATA_DIR, DEFAULT_TEST_CONCURRENCY, DEFAULT_TIMEOUT
from harvester.models import ParsedStream, StreamStatus
from harvester.tester import test_stream, test_streams

CATALOG_PATH = Path(__file__).resolve().parent.parent / "catalog" / "tv" / "all.json"
META_DIR = Path(__file__).resolve().parent.parent / "meta" / "tv"
GENRE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "tv" / "all"
STREAM_DIR = Path(__file__).resolve().parent.parent / "stream" / "tv"
PRUNED_PATH = DATA_DIR / "pruned.json"
PRUNED_KEEP = timedelta(days=30)

RETRY_INTERVAL = 30
RETRY_DURATION = 600

console = Console()


def _served(ch_id: str) -> list[dict]:
    path = STREAM_DIR / f"{ch_id}.json"
    return json.loads(path.read_text())["streams"] if path.exists() else []


def _collect_catalog_streams(catalog: dict) -> list[ParsedStream]:
    """The catalog's streams and each channel's stream file's, which can hold live ones the catalog lacks."""
    seen: set[str] = set()
    streams: list[ParsedStream] = []
    for ch in catalog.get("metas", []):
        ch_name = ch.get("name", "")
        for s in ch.get("streams", []) + _served(ch["id"]):
            url = s.get("url", "")
            if url and url not in seen:
                seen.add(url)
                streams.append(ParsedStream(url=url, channel_name=ch_name))
    return streams


def _remove_dead_from_list(streams: list[dict], dead_urls: set[str]) -> list[dict]:
    return [s for s in streams if s.get("url", "") not in dead_urls]


async def _retry_one(url: str, timeout: float, sem: asyncio.Semaphore) -> tuple[str, bool]:
    """Retry a single URL every RETRY_INTERVAL seconds for RETRY_DURATION. Returns (url, recovered)."""
    max_attempts = RETRY_DURATION // RETRY_INTERVAL
    for _ in range(max_attempts):
        await asyncio.sleep(RETRY_INTERVAL)
        async with sem:
            result = await test_stream(url, timeout=timeout)
        if result.status == StreamStatus.WORKING:
            return url, True
    return url, False


async def _prune(timeout: float, concurrency: int, dry_run: bool) -> dict:
    catalog = json.loads(CATALOG_PATH.read_text())
    all_streams = _collect_catalog_streams(catalog)
    # {url: {"stream": entry, "channels": [ids], "since": iso}}
    pruned: dict[str, dict] = json.loads(PRUNED_PATH.read_text()) if PRUNED_PATH.exists() else {}
    listed = {s.url for s in all_streams}
    all_streams += [ParsedStream(url=url) for url in pruned if url not in listed]

    if not all_streams:
        console.print("[red]No streams found in catalog[/]")
        return {"tested": 0, "dead": 0, "removed": 0}

    console.print(f"[bold]Found {len(all_streams)} unique stream URLs in catalog[/]")

    results = await test_streams(all_streams, timeout=timeout, concurrency=concurrency)

    working_urls = {r.url for r in results if r.status == StreamStatus.WORKING}
    failed_urls = {r.url for r in results if r.status != StreamStatus.WORKING}

    console.print(f"\n[bold]Pass 1:[/] [green]{len(working_urls)} working[/], [red]{len(failed_urls)} failed[/]")

    if failed_urls:
        max_attempts = RETRY_DURATION // RETRY_INTERVAL
        console.print(f"[bold]Retrying {len(failed_urls)} failed streams every {RETRY_INTERVAL}s for {RETRY_DURATION}s ({max_attempts} attempts each, all in parallel)...[/]\n")

        sem = asyncio.Semaphore(concurrency)
        tasks = [_retry_one(url, timeout, sem) for url in failed_urls]

        recovered_urls: set[str] = set()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[green]{task.fields[recovered]}R[/] [red]{task.fields[dead]}D[/]"),
        ) as progress:
            ptask = progress.add_task("Retrying", total=len(tasks), recovered=0, dead=0)
            for coro in asyncio.as_completed(tasks):
                url, recovered = await coro
                if recovered:
                    recovered_urls.add(url)
                progress.update(
                    ptask, advance=1,
                    recovered=len(recovered_urls),
                    dead=len(failed_urls) - len(recovered_urls) - (len(tasks) - progress.tasks[ptask].completed - 1),
                )

        working_urls |= recovered_urls
        failed_urls -= recovered_urls
        console.print(f"\n[bold]Retries done:[/] [green]{len(recovered_urls)} recovered[/], [red]{len(failed_urls)} confirmed dead[/]")

    dead_urls = failed_urls
    console.print(f"\n[bold]Final:[/] [green]{len(working_urls)} working[/], [red]{len(dead_urls)} dead[/]")

    # Every probe failing means the network is down, not that the addon died.
    if not working_urls:
        console.print("[red]No stream is working; refusing to prune[/]")
        return {"tested": len(results), "dead": len(dead_urls), "removed": 0}

    if dry_run:
        console.print("[yellow]Dry run — no files modified[/]")
        return {"tested": len(results), "dead": len(dead_urls), "removed": 0}

    restored = {url: p for url, p in pruned.items() if url in working_urls}
    now = datetime.now(timezone.utc)
    removed = 0
    for ch in catalog["metas"]:
        for s in ch.get("streams", []) + _served(ch["id"]):
            url = s.get("url", "")
            if url in dead_urls:
                entry = pruned.setdefault(url, {"stream": s, "channels": [], "since": now.isoformat()})
                if ch["id"] not in entry["channels"]:
                    entry["channels"].append(ch["id"])
                console.print(f"Removing {url} from {ch.get('name', ch['id'])}")
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
            served = _remove_dead_from_list(_served(ch["id"]), dead_urls)
            served_urls = {s.get("url") for s in served}
            for url, p in restored.items():
                if ch["id"] in p["channels"] and url not in served_urls:
                    served.append(p["stream"])
                    console.print(f"Restoring {url} to {ch.get('name', ch['id'])}")
            stream_file.write_text(json.dumps({"streams": merged_streams(served, ch["streams"])}, separators=(",", ":")))

    for url in restored:
        del pruned[url]
    for url in [u for u, p in pruned.items() if now - datetime.fromisoformat(p["since"]) > PRUNED_KEEP]:
        del pruned[url]
    PRUNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRUNED_PATH.write_text(json.dumps(pruned, indent=1))

    console.print(f"[bold green]Removed {removed} dead streams from catalog, restored {len(restored)}[/]")
    return {"tested": len(results), "dead": len(dead_urls), "removed": removed}


def prune(timeout: float = DEFAULT_TIMEOUT, concurrency: int = DEFAULT_TEST_CONCURRENCY, dry_run: bool = False) -> dict:
    return asyncio.run(_prune(timeout, concurrency, dry_run))
