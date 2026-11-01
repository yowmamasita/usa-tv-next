"""A probe that times out must kill its ffprobe: streams that never end kept theirs running, and
the first Windows run of the daily job held 600 of them (22 GB) after 38 minutes.

    python3 -m unittest discover -s tests
"""
import asyncio
import sys
import unittest

import harvester.tester as tester
from harvester.models import StreamStatus


class TimedOutProbe(unittest.TestCase):
    def test_is_killed(self):
        spawned = []
        real_exec = asyncio.create_subprocess_exec

        async def endless_ffprobe(*_args, **kwargs):
            proc = await real_exec(sys.executable, "-c", "import time; time.sleep(120)", **kwargs)
            spawned.append(proc)
            return proc

        async def probe():
            tester.asyncio.create_subprocess_exec = endless_ffprobe
            try:
                result = await tester.test_stream("http://never-ends/", timeout=-4.5)
            finally:
                tester.asyncio.create_subprocess_exec = real_exec
            await asyncio.sleep(0.5)
            return result, spawned[0].returncode

        status, returncode = asyncio.run(probe())
        self.assertEqual(status.status, StreamStatus.TIMEOUT)
        self.assertIsNotNone(returncode, "ffprobe still running after its probe timed out")


if __name__ == "__main__":
    unittest.main()
