"""A stream behind a certificate that fails verification still plays in players that don't check
it, and the catalog has always kept such streams (bozztv's Cartoon Network feed is one). FFmpeg 9
verifies by default and 8 does not, so on Windows' ffprobe 9 the first daily run pruned them as
dead. `-tls_verify 0` cannot fix that: FFmpeg 9's HLS demuxer does not pass it to the variant
playlists and segments it opens. So the job's ffprobe must be FFmpeg 8 or older, and this
fails on a host whose ffprobe verifies.

The fixture is a 1-second HLS stream served over HTTPS with a self-signed, test-only certificate
(tests/fixtures/selfsigned, generated with ffmpeg and openssl). Needs ffprobe on PATH.

    python3 -m unittest discover -s tests
"""
import asyncio
import functools
import http.server
import shutil
import ssl
import threading
import unittest
from pathlib import Path

from harvester.models import StreamStatus
from harvester.tester import test_stream

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "selfsigned"


@unittest.skipUnless(shutil.which("ffprobe"), "needs ffprobe")
class SelfSignedStream(unittest.TestCase):
    def test_plays(self):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURE))
        handler.log_message = lambda *_: None
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(FIXTURE / "cert.pem", FIXTURE / "key.pem")
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = asyncio.run(test_stream(f"https://localhost:{server.server_address[1]}/index.m3u8"))
        finally:
            server.shutdown()
        self.assertEqual(result.status, StreamStatus.WORKING)


if __name__ == "__main__":
    unittest.main()
