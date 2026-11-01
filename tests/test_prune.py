"""prune must never shrink stream/tv/<id>.json to the catalog's streams: 108 live URLs exist only
in stream files (SYFY's USA_SYFY HD feed among them), and replacing the file would drop them.
It also must not empty the addon when the network is down and every probe fails.

    python3 -m unittest discover -s tests
"""
import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import harvester.prune as prune
from harvester.models import StreamStatus, StreamTestResult

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "syfy"
SYFY = "ustv-061d6c0b-9786-4ff7-a483-f025d6765a2b"
CATALOG_URL = "http://99.27.51.147:8080/SYFY/index.m3u8"
STREAM_ONLY_URL = "http://23.237.104.106:8080/USA_SYFY/index.m3u8"


def _run(working: set[str]) -> tuple[dict, list[str], list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(FIXTURE, tmp, dirs_exist_ok=True)

        async def fake_test_streams(streams, **_):
            return [StreamTestResult(url=s.url, status=StreamStatus.WORKING if s.url in working else StreamStatus.DEAD)
                    for s in streams]

        async def fake_test_stream(url, **_):
            return StreamTestResult(url=url, status=StreamStatus.WORKING if url in working else StreamStatus.DEAD)

        saved = (prune.CATALOG_PATH, prune.META_DIR, prune.GENRE_DIR, prune.STREAM_DIR,
                 prune.test_streams, prune.test_stream, prune.RETRY_INTERVAL, prune.RETRY_DURATION)
        prune.CATALOG_PATH, prune.META_DIR, prune.GENRE_DIR, prune.STREAM_DIR = (
            tmp / "all.json", tmp / "meta", tmp / "genre", tmp / "stream")
        prune.test_streams, prune.test_stream, prune.RETRY_INTERVAL, prune.RETRY_DURATION = (
            fake_test_streams, fake_test_stream, 1, 1)
        try:
            stats = asyncio.run(prune._prune(timeout=1, concurrency=1, dry_run=False))
        finally:
            (prune.CATALOG_PATH, prune.META_DIR, prune.GENRE_DIR, prune.STREAM_DIR,
             prune.test_streams, prune.test_stream, prune.RETRY_INTERVAL, prune.RETRY_DURATION) = saved
        served = [s["url"] for s in json.loads((tmp / "stream" / f"{SYFY}.json").read_text())["streams"]]
        catalog = [s["url"] for s in json.loads((tmp / "all.json").read_text())["metas"][0]["streams"]]
        return stats, served, catalog


class Prune(unittest.TestCase):
    def test_keeps_a_live_stream_only_url_when_the_catalogs_one_dies(self):
        stats, served, catalog = _run(working={STREAM_ONLY_URL})
        self.assertEqual(served, [STREAM_ONLY_URL])
        self.assertEqual(catalog, [])
        self.assertEqual(stats["tested"], 2)

    def test_removes_a_dead_stream_only_url(self):
        _, served, catalog = _run(working={CATALOG_URL})
        self.assertEqual(served, [CATALOG_URL])
        self.assertEqual(catalog, [CATALOG_URL])

    def test_writes_nothing_when_every_probe_fails(self):
        stats, served, catalog = _run(working=set())
        self.assertEqual(stats["removed"], 0)
        self.assertEqual(served, [STREAM_ONLY_URL, CATALOG_URL])
        self.assertEqual(catalog, [CATALOG_URL])


if __name__ == "__main__":
    unittest.main()
