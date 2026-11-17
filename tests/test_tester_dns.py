"""The DNS pre-filter must time each lookup, not its wait for a thread. On 2026-11-17 the daily run on
zen (2 cores, so a 6-thread default executor) started the 3 s clock while 200 lookups queued for those
6 threads: 12,497 of 14,007 hosts came out dead, 1,671 IP literals and jmp2.uk (10,675 streams) among
them, each with no error to say why. The fixture samples those hosts with each name's lookup time
measured on zen. The names that resolve need 27 s of lookups, more than 6 threads finish in 3 s, so a
clock that runs in the queue fails here whatever order the hosts go in.

    python3 -m unittest discover -s tests
"""
import asyncio
import ipaddress
import json
import socket
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

import harvester.tester as tester
from harvester.models import ParsedStream, StreamStatus, StreamTestResult

FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "dns" / "hosts.json").read_text())
NAMES = {urlparse(n["origin"]).hostname: n for n in FIXTURE["names"]}


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


class DnsPrefilter(unittest.TestCase):
    def test_times_the_lookup_not_the_queue(self):
        looked_up = []

        def getaddrinfo(host, *_):
            looked_up.append(host)
            host.encode("idna")  # as the real call does: a label over 63 characters raises UnicodeError
            name = NAMES.get(host)  # None for an IP literal, which needs no DNS
            if name:
                time.sleep(name["secs"])
                if name["error"]:
                    raise socket.gaierror(name["error"])
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 0))]

        async def probe(url, **_):
            return StreamTestResult(url=url, status=StreamStatus.WORKING)

        async def run():
            asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(6))  # zen's: 2 cores + 4
            origins = FIXTURE["ip_literals"] + [n["origin"] for n in FIXTURE["names"]]
            return await tester.test_streams([ParsedStream(url=o + "index.m3u8") for o in origins])

        with mock.patch.object(tester.socket, "getaddrinfo", getaddrinfo), mock.patch.object(tester, "test_stream", probe):
            results = {r.url[:-len("index.m3u8")]: r for r in asyncio.run(run())}

        resolvable = FIXTURE["ip_literals"] + [n["origin"] for n in FIXTURE["names"] if not n["error"] and n["secs"] < 3]
        lost = [o for o in resolvable if results[o].status != StreamStatus.WORKING]
        self.assertEqual(lost, [], f"{len(lost)} of {len(resolvable)} resolvable hosts counted dead")
        self.assertEqual([h for h in looked_up if _is_ip(h)], [], "IP literals sent to DNS")
        for n in FIXTURE["names"]:
            if n["error"] or n["secs"] >= 3:
                r = results[n["origin"]]
                self.assertEqual(r.status, StreamStatus.DEAD, n["origin"])
                reason = n["error"] or "timed out after 3s"
                if "idna" in reason:
                    reason = "DNS lookup failed"  # the codec words it differently from one Python to the next
                self.assertIn(reason, r.error, n["origin"])


if __name__ == "__main__":
    unittest.main()
