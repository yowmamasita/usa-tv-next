from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone

from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from harvester.models import CodecInfo, ParsedStream, StreamStatus, StreamTestResult


async def test_stream(url: str, timeout: float = 8.0) -> StreamTestResult:
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            "-analyzeduration", "3000000",
            "-probesize", "1000000",
            "-timeout", str(int(timeout * 1_000_000)),
            "-i", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if proc.returncode != 0:
            return StreamTestResult(
                url=url,
                status=StreamStatus.DEAD,
                response_time_ms=elapsed_ms,
                tested_at=datetime.now(timezone.utc).isoformat(),
            )

        codecs = CodecInfo()
        try:
            data = json.loads(stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and not codecs.video:
                    codecs.video = stream.get("codec_name", "")
                    w = stream.get("width", 0)
                    h = stream.get("height", 0)
                    if w and h:
                        codecs.resolution = f"{w}x{h}"
                elif stream.get("codec_type") == "audio" and not codecs.audio:
                    codecs.audio = stream.get("codec_name", "")
            fmt = data.get("format", {})
            if fmt.get("bit_rate"):
                codecs.bitrate = fmt["bit_rate"]
        except (json.JSONDecodeError, KeyError):
            pass

        return StreamTestResult(
            url=url,
            status=StreamStatus.WORKING,
            response_time_ms=elapsed_ms,
            codecs=codecs,
            tested_at=datetime.now(timezone.utc).isoformat(),
        )

    except asyncio.TimeoutError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return StreamTestResult(
            url=url,
            status=StreamStatus.TIMEOUT,
            response_time_ms=elapsed_ms,
            tested_at=datetime.now(timezone.utc).isoformat(),
        )
    except OSError as e:
        return StreamTestResult(
            url=url,
            status=StreamStatus.DEAD,
            response_time_ms=0,
            tested_at=datetime.now(timezone.utc).isoformat(),
            error=str(e),
        )


async def test_streams(
    streams: list[ParsedStream],
    timeout: float = 8.0,
    concurrency: int = 50,
    tested_urls: dict[str, str] | None = None,
    on_result: callable = None,
) -> list[StreamTestResult]:
    sem = asyncio.Semaphore(concurrency)
    tested = tested_urls or {}
    results: list[StreamTestResult] = []

    urls_to_test = []
    for s in streams:
        if s.url not in tested:
            urls_to_test.append(s)

    stream_meta = {s.url: s for s in streams}

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[green]{task.fields[working]}W[/] [red]{task.fields[dead]}D[/] [yellow]{task.fields[timeout]}T[/]"),
    ) as progress:
        task = progress.add_task("Testing streams", total=len(urls_to_test), working=0, dead=0, timeout=0)
        counts = {"working": 0, "dead": 0, "timeout": 0}

        async def test_one(stream: ParsedStream) -> StreamTestResult:
            async with sem:
                result = await test_stream(stream.url, timeout=timeout)
                result.channel_name = stream.channel_name
                result.group = stream.group
                result.sources = stream.source_id.split(",") if stream.source_id else []
                counts[result.status.value] += 1
                progress.update(task, advance=1, **counts)
                if on_result:
                    on_result(result)
                return result

        tasks = [test_one(s) for s in urls_to_test]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]
