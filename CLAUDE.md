# USA TV Next

Static Stremio addon for US IPTV channels. GitHub raw URLs serve the JSON;
there is no application server. Follow the parent workspace's Git and testing rules.

## Harvester

Python 3.10+ managed with `uv`; stream verification requires `ffprobe`.
Run tests on zen, with concurrency sized for the host.

```bash
uv run python -m harvester harvest
uv run python -m harvester test --limit 100
uv run python -m harvester report
uv run python -m harvester run
uv run python -m harvester.inject
```

`run` performs harvest, test and report; injection is separate and modifies the
published catalog. `sources.yaml` defines upstreams. `harvester/` owns parsing,
URL deduplication, DNS filtering, ffprobe checks and channel matching.
`data/` contains resumable state/results and remains gitignored.

## Data invariants

- Keep `catalog/tv/all.json`, genre slices, `meta/tv/` and `stream/tv/` consistent
  when adding channels or injecting streams. Inspect the actual files for counts.
- Match normalized channel names exactly or at a word boundary; preserve the
  non-US exclusions and the preference for a more-specific catalog channel.
- Stream quality comes from probe results. Excess ffprobe concurrency can create
  false failures; do not increase it without measuring on the test host.
- `manifest.json` identifies the addon; `public/` holds its images.

## Daily job

`deploy/daily.sh` runs on `ben@zen` from `~/usatv`, from ben's crontab at 05:00 UTC under
`flock`, logging to `~/logs/usatv-daily.log`: prune, `run --no-resume` (a resumed run skips
sources already harvested), the tests, then a push of `main` with the repository's write deploy
key `usatv daily job (zen)` (`~/.ssh/usatv_deploy`, set in the clone's `core.sshCommand`, with
commit signing off). `NO_PUSH=1` stops after the local commit. The router sends all port-53 DNS
to NextDNS, which blocks some stream hosts (`world-iptv.club`, ad-insertion hosts), and prune
counts an unresolvable host as dead. So the script re-runs itself in a private mount namespace
(`unshare --user --mount`, no root) whose `/etc/resolv.conf` is `deploy/resolv.conf`: unbound on
`127.0.0.2:53` (apt package, `/etc/unbound/unbound.conf.d/usatv-doh.conf`), forwarding over DNS over
TLS to 1.1.1.1 and 9.9.9.9. The rest of zen keeps NextDNS through systemd-resolved. Keep its ffprobe on FFmpeg 8 or
older: FFmpeg 9 verifies TLS certificates, even in HLS segments with `-tls_verify 0`, and prunes
streams that play (`tests/test_tester_tls.py` fails there). The previous job (May to 2026-08-24)
lived on a machine nobody recorded and never updated `stream/tv/`.

## Deployment

Pushing catalog/meta/stream changes to `yowmamasita/usa-tv-next` publishes the
files Stremio clients fetch. Validate changed JSON and exercise affected streams
before pushing. Documentation-only changes do not alter addon data.
