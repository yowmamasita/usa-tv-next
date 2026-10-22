"""stream/tv/<id>.json is what Stremio plays (manifest.json's `stream` resource). inject never
wrote it, so 131 of 439 files kept tvpass.org links after that host went DNS-dead and never
gained the catalog's replacements (GitHub #3 #4 #5 #6).

    python3 -m unittest discover -s tests
"""
import json
import tempfile
import unittest
from pathlib import Path

import harvester.inject as inject

ROOT = Path(__file__).resolve().parent.parent


class StreamFiles(unittest.TestCase):
    def test_no_stream_file_serves_a_dead_host_and_each_has_the_catalogs_streams(self):
        catalog = {ch["id"]: ch.get("streams", []) for ch in json.loads((ROOT / "catalog/tv/all.json").read_text())["metas"]}
        dead, missing = [], []
        for path in sorted((ROOT / "stream/tv").glob("*.json")):
            urls = [s.get("url", "") for s in json.loads(path.read_text())["streams"]]
            if any("tvpass.org" in url for url in urls):
                dead.append(path.name)
            if any(s["url"] not in urls for s in catalog.get(path.stem, [])):
                missing.append(path.name)
        self.assertEqual(dead, [], "%d stream files serve tvpass.org" % len(dead))
        self.assertEqual(missing, [], "%d stream files lack the catalog's streams" % len(missing))

    def test_inject_adds_the_catalogs_streams_keeps_live_ones_and_drops_tvpass(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ch = {"id": "ustv-test", "name": "Test Channel", "streams": [{"url": "http://catalog/", "title": "c"}]}
            (tmp / "all.json").write_text(json.dumps({"metas": [ch]}))
            (tmp / "meta").mkdir()
            (tmp / "meta/ustv-test.json").write_text(json.dumps({"meta": ch}))
            (tmp / "stream").mkdir()
            (tmp / "stream/ustv-test.json").write_text(json.dumps({"streams": [
                {"url": "http://tvpass.org/live/x/hd"}, {"url": "http://live/"}]}))
            (tmp / "results.json").write_text("[]")
            saved = inject.CATALOG_PATH, inject.META_DIR, inject.GENRE_DIR, inject.STREAM_DIR
            inject.CATALOG_PATH, inject.META_DIR, inject.GENRE_DIR, inject.STREAM_DIR = (
                tmp / "all.json", tmp / "meta", tmp / "genre", tmp / "stream")
            try:
                inject.inject(str(tmp / "results.json"))
            finally:
                inject.CATALOG_PATH, inject.META_DIR, inject.GENRE_DIR, inject.STREAM_DIR = saved
            urls = [s["url"] for s in json.loads((tmp / "stream/ustv-test.json").read_text())["streams"]]
            self.assertEqual(urls, ["http://live/", "http://catalog/"])


if __name__ == "__main__":
    unittest.main()
